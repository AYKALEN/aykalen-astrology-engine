"""Small data-only boundary around the extracted computational modules.

The Swiss Ephemeris configuration is process-global: serialize calculations
inside this API. Run separate processes for independently configured workers.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import version
import math
from pathlib import Path
import threading

import pytz
import swisseph as swe

from . import __version__
from .core import ChartData, HORA_METHOD, _tithi_angle_deg
from .facts import (
    CLASSICAL, SIGN_LORD, ZODIAC_SIGNS, aspects_for_chart,
    conjunctions_d1, house_lords_rows, rules_houses, sign_dignity,
)
from .shadbala import component_snapshot
from .timing import unfiltered_vimshottari

VARGAS = (
    "D1", "D2_parashara", "D2_parivritti", "D2_kashinatha", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11_iyer",
    "D12", "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60",
)
ADDITIONAL_VARGA_METHODS = {
    "D2_kashinatha": "Kashinatha Hora: odd signs Sun/Moon, even signs Moon/Sun in 15-degree halves; day/night-strong sign of the D1 sign lord; Leo/Cancer pair for luminaries; [start,end). Rao, Personal Finances from Hora Chart, pp. 1-3; https://www.vedicastrologer.org/articles/hora.pdf",
    "D5": "Panchamsa: five equal 6-degree parts; odd signs Aries/Aquarius/Sagittarius/Gemini/Libra; even signs Taurus/Virgo/Pisces/Capricorn/Scorpio; [start,end). Rao section 6.2.5.",
    "D6": "Shashthamsa: six equal 5-degree parts; odd/even signs start at Aries/Libra, zodiacal order; [start,end). Rao section 6.2.6.",
    "D8": "Ashtamsa: eight equal 30/8-degree parts; movable/fixed/dual signs start at Aries/Sagittarius/Leo, then zodiacal order; [start,end).",
    "D11_iyer": "H.R. Seshadri Iyer Ekadasamsa: eleven equal 30/11-degree parts; every D1 sign starts at Aries, then reverse zodiacal order; Taurus is unused; [start,end).",
}
_LOCK = threading.RLock()
_FIELDS = {"birth", "target_year", "allowed_vargas", "sunrise_mode", "ephemeris_path", "techniques"}


def _validate(request):
    if not isinstance(request, dict) or set(request) - _FIELDS:
        raise ValueError("Input must be an object with documented fields only.")
    birth = request.get("birth")
    required = {"date", "time", "timezone", "latitude", "longitude"}
    if not isinstance(birth, dict) or set(birth) != required:
        raise ValueError("birth requires exactly date, time, timezone, latitude, longitude.")
    if not all(isinstance(birth[k], str) for k in ("date", "time", "timezone")):
        raise ValueError("Date, time and IANA timezone must be strings.")
    naive = datetime.strptime(birth["date"] + " " + birth["time"], "%Y-%m-%d %H:%M:%S")
    if not 1800 <= naive.year <= 2398:
        raise ValueError("This export supports birth years 1800..2398.")
    # is_dst=None rejects both nonexistent and ambiguous local civil times.
    try:
        localized = pytz.timezone(birth["timezone"]).localize(naive, is_dst=None)
    except (pytz.UnknownTimeZoneError, pytz.InvalidTimeError) as exc:
        raise ValueError("Unknown timezone, or ambiguous/nonexistent local birth time.") from exc
    for key, limit in (("latitude", 66), ("longitude", 180)):
        value = birth[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number.")
        if not -limit <= value <= limit:
            raise ValueError(f"{key} must be within [-{limit}, {limit}]; polar charts are not supported.")
    selected = request.get("allowed_vargas", ["D1"])
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(v, str) or v not in VARGAS for v in selected)
            or len(set(selected)) != len(selected) or "D1" not in selected):
        raise ValueError("allowed_vargas must be a unique supported list including D1.")
    year = request.get("target_year")
    if year is not None and (type(year) is not int or not naive.year <= year <= 2398):
        raise ValueError("target_year must be an integer from birth year through 2398.")
    mode = request.get("sunrise_mode", "center")
    if mode not in ("center", "standard"):
        raise ValueError("sunrise_mode must be center or standard.")
    techniques = request.get("techniques", [])
    if (not isinstance(techniques, list) or
            techniques not in ([], ["rao_hora_finance_2003_v1"])):
        raise ValueError("techniques supports only [] or ['rao_hora_finance_2003_v1'].")
    if techniques and (year is None or not {"D1", "D2_kashinatha"} <= set(selected)):
        raise ValueError("Rao research profile requires target_year and D1/D2_kashinatha.")
    path = request.get("ephemeris_path")
    if path is not None and (not isinstance(path, str) or not Path(path).is_dir()):
        raise ValueError("ephemeris_path must identify an existing local directory.")
    return birth, localized, selected, year, mode


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _backend(jd):
    flags = {}
    for label, body in (("SU", swe.SUN), ("MO", swe.MOON), ("ME", swe.MERCURY),
                        ("VE", swe.VENUS), ("MA", swe.MARS), ("JU", swe.JUPITER),
                        ("SA", swe.SATURN), ("RA", swe.TRUE_NODE)):
        _, actual = swe.calc_ut(jd, body, swe.FLG_SWIEPH)
        flags[label] = {
            "returned_flags": actual,
            "backend": "swiss" if actual & swe.FLG_SWIEPH else
                       "moshier" if actual & swe.FLG_MOSEPH else "jpl",
        }
    return flags


def _chart_data(chart, detailed, jd, selected):
    raw = deepcopy(detailed)
    charts = {"D1": raw, **chart.calculate_all_divisionals_from_detailed(raw)}
    result = {}
    for label in selected:
        positions = deepcopy(charts[label])
        for code, body in positions.items():
            if code not in ("AS", *chart.PLANET_NAMES):
                continue
            body["rules_houses"] = rules_houses(code, positions)
            body["dispositor"] = SIGN_LORD[body["zodiac_sign"]]
            if code != "AS":
                degree = body["position_degrees_exact"] % 30 if label == "D1" else None
                body["dignity"] = sign_dignity(code, body["zodiac_sign"], degree)
            if label == "D1":
                longitude = body["position_degrees_exact"]
                body["nakshatra_pada"] = int((longitude % (360 / 27)) / (360 / 108)) + 1
        result[label] = {
            "positions": positions,
            "house_lords": house_lords_rows(positions),
            "aspects": aspects_for_chart(positions),
        }
    longitudes = {p: raw[p]["position_degrees_exact"] for p in CLASSICAL}
    tithi = chart.tithi_balance_at(jd)
    # Extracted methods use the object's D1; avoid contaminating natal state for TP.
    view = deepcopy(chart)
    view.detailed_chart_data = deepcopy(raw)
    return {
        "jd_ut": jd,
        "ayanamsa_degrees": swe.get_ayanamsa_ut(jd),
        "ephemeris": _backend(jd),
        "charts": result,
        "tithi": {
            "index": tithi[0], "name": chart.tithi_name(tithi[0]), "lord": tithi[1],
            "start_jd": tithi[2], "end_jd": tithi[3], "fraction_left": tithi[4],
            "dagdha_rasi": chart.dagdha_rasi_for_tithi(tithi[0]),
        },
        "conjunctions_d1": [
            {k: v for k, v in pair.items() if k != "label"}
            for pair in conjunctions_d1(raw)
        ],
        "sun_separation_degrees": {
            p: min((v - longitudes["SU"]) % 360, (longitudes["SU"] - v) % 360)
            for p, v in longitudes.items() if p != "SU"
        },
        "jaimini_karakas_7": view.get_jaimini_karakas(),
        "indu_lagna": view.calculate_indu_lagna(),
        "shadbala_components": component_snapshot(longitudes, raw["AS"]["position_degrees_exact"]),
    }


def _vimshottari_windows(periods, start, end):
    """Clip existing MD/AD/PD; retain source boundaries and reject incomplete coverage."""
    rows = []
    for md in periods:
        for ad in md["antardashas"]:
            for pd in ad["pratyantardashas"]:
                a, b = (datetime.fromisoformat(pd[k]) for k in ("start_utc", "end_utc"))
                lo, hi = max(a, start), min(b, end)
                if lo < hi:
                    rows.append({
                        "md": md["mahadasha_lord"], "ad": ad["antardasha_lord"],
                        "pd": pd["pratyantardasha_lord"], "start_utc": lo.isoformat(),
                        "end_utc": hi.isoformat(), "source_start_utc": a.isoformat(),
                        "source_end_utc": b.isoformat(),
                    })
    if not rows or rows[0]["start_utc"] != start.isoformat() or rows[-1]["end_utc"] != end.isoformat():
        raise ValueError("Annual window is outside the implemented natal Vimshottari cycle.")
    for left, right in zip(rows, rows[1:]):
        if left["end_utc"] != right["start_utc"]:
            raise ValueError("Gap in natal Vimshottari timeline.")
    return rows


def calculate(request):
    """Generate raw data, never a report or life-domain interpretation.

    No files are read other than optional Swiss ephemerides; this function never
    saves client data or contacts a service. The caller provides permitted vargas.
    """
    birth, localized, selected, year, mode = _validate(request)
    with _LOCK:
        # A local, deliberately unbundled directory. Swiss falls back to its
        # built-in Moshier implementation; actual returned flags are disclosed.
        swe.set_ephe_path(request.get("ephemeris_path") or str(Path(__file__).parent / "ephemeris"))
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        chart = ChartData(
            full_name="", date=birth["date"], real_time=birth["time"],
            latitude=birth["latitude"], longitude=birth["longitude"],
            timezone=birth["timezone"], silent_mode=True,
        )
        natal = _chart_data(chart, chart.detailed_chart_data, chart.jd_ut, selected)
        vimshottari = unfiltered_vimshottari(chart, include_timestamps=True)
        out = {
            "schema_version": "astro-data-1", "engine_version": __version__,
            "software": {"swiss_ephemeris": swe.version, "pyswisseph": version("pyswisseph"),
                         "pytz": version("pytz"), "python_dateutil": version("python-dateutil")},
            "calculation_profile": {
                "ayanamsa": "Lahiri", "nodes": "true; mean-node varga comparison",
                "houses": "whole-sign; Placidus routine used only for ascendant",
                "planet_positions": "apparent geocentric ecliptic, tropical minus Lahiri",
                "tithi_phase": "Moon-Sun TRUEPOS", "sunrise_mode": mode,
                "hora_method": HORA_METHOD,
                "tp_location": "birth_coordinates", "aspects": "Parashari whole-sign; no node aspects",
                "target_year_definition": "calendar year of solar ingress into natal sidereal sign; TP may fall in next January",
                "conjunction": "same sign, with angular separation; no strength inference",
                "dignity": "natural relationships; vargas sign-only",
                "node_motion": "R is legacy convention, not measured true-node speed",
                "jaimini": "7 karakas; inherited ranking from rounded 0.01-degree positions",
                "vimshottari": "legacy balance-prorated first MD/AD/PD; 365.25-day year; one cycle",
                "intervals": "[start,end)",
            },
            "scope": {"exported_vargas": selected, "rectification": "caller-declared, not verified",
                      "analysis_permission": "calculation is not authorization to interpret higher vargas"},
            "input": {"birth_local": localized.isoformat(), "birth_utc": localized.astimezone(timezone.utc).isoformat(),
                      "timezone": birth["timezone"], "latitude": birth["latitude"], "longitude": birth["longitude"]},
            "natal": natal, "natal_vimshottari": vimshottari,
            "limitations": [
                "Full Shadbala is incomplete (Sthana/Kala/Cheshta); unresolved Drik values remain null.",
                "No yoga interpretation, confidence, predictions, transits or report generation.",
                "No external ephemeris files bundled; inspect returned backend flags.",
                "Vimshottari first-period subperiod convention is inherited, not newly validated against an external reference.",
                "TP chart positions retain legacy whole-second timestamp precision; return JD has subsecond precision.",
                "target_year is the solar-ingress year, not a guaranteed calendar year of the TP instant.",
            ],
        }
        methods = {label: ADDITIONAL_VARGA_METHODS[label] for label in selected
                   if label in ADDITIONAL_VARGA_METHODS}
        if methods:
            out["calculation_profile"]["varga_methods"] = methods
        if year is not None:
            chart.generate_tithi_pravesha_chart(year, sunrise_mode=mode)
            residual = abs((_tithi_angle_deg(chart.tp_jd_ut) - _tithi_angle_deg(chart.jd_ut) + 180) % 360 - 180)
            if residual > 1e-4:
                raise ValueError("No sufficiently exact TP return in the selected solar-sign window.")
            annual = _chart_data(chart, chart.tp_chart_data, chart.tp_jd_ut, selected)
            schedule = chart.get_tithi_ashtottari_md_schedule(year)
            start = datetime.fromisoformat(schedule["tp_start_date"]).astimezone(timezone.utc)
            end = datetime.fromisoformat(schedule["tp_end_date"]).astimezone(timezone.utc)
            lagna_distances = {}
            for label in selected:
                natal_sign = natal["charts"][label]["positions"]["AS"]["zodiac_sign"]
                tp_sign = annual["charts"][label]["positions"]["AS"]["zodiac_sign"]
                lagna_distances[label] = {
                    "from": natal_sign, "to": tp_sign,
                    "inclusive_sign_count": (ZODIAC_SIGNS.index(tp_sign) - ZODIAC_SIGNS.index(natal_sign)) % 12 + 1,
                }
            annual.update({
                "target_year": year, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
                "phase_residual_degrees": residual,
                "hora": chart.get_hora_lord_for_tp(), "vaara": chart.get_vaara_lord_for_tp(),
                "hora_schedule": chart.get_hora_schedule_for_tp(offset_all=0),
                "lagna_distances": {"direction": "natal_to_tp", "interpretation": None, "charts": lagna_distances},
                "tithi_ashtottari": schedule,
                "natal_vimshottari_windows": _vimshottari_windows(vimshottari, start, end),
            })
            out["annual"] = annual
        if request.get("techniques"):
            from .hora_finance import TECHNIQUE_ID, build_hora_finance
            out["techniques"] = {TECHNIQUE_ID: build_hora_finance(
                chart, natal, window_start_utc=out["annual"]["start_utc"],
                window_end_utc=out["annual"]["end_utc"])}
        return _json_value(out)
