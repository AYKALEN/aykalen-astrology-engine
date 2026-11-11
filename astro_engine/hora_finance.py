"""Opt-in research data for Rao's NATAL financial method, never an AI report.

Rules use named source variants. Interval qualification is separate from
central-instant computation; no implicit approval of an interpretation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import swisseph as swe

from .arudha import bhava_arudhas
from .narayana import period_structure, dated_periods
from .rasi_rules import (PLANETS, LORDS, UnresolvedRule, chart_signs,
                         house_from, rasi_aspects)
from .solar_calendar import SolarArcCalendar
from .special_lagnas import hora_ghati_lagnas
from .pachakadi import pachakadi_relations, VARIANT as PACHAKADI_VARIANT

TECHNIQUE_ID = "rao_hora_finance_2003_v1"
SOURCE_ISSUES = (
    {"id": "ghati_example_9", "status": "arithmetic_discrepancy",
     "detail": "Textbook example 9 prints Virgo 21deg17; 294deg47 + 766*1.25 degrees gives Virgo 22deg17. Implemented formula, not printed arithmetic."},
    {"id": "pachakadi_venus_variant", "status": "explicit_source_variant",
     "detail": "Narayana Dasa 2004 tables 55/57 give Venus karaka Saturn and vedhaka Sun; Crux table 2.1 reverses them. This profile consistently implements the former, not a universal resolution."},
)


def _jd(iso: str) -> float:
    value = datetime.fromisoformat(iso)
    if value.tzinfo is None:
        raise ValueError("Window dates must include a timezone.")
    return 2451545 + (value.astimezone(timezone.utc) - datetime(2000,1,1,12,tzinfo=timezone.utc)).total_seconds()/86400


def _sidereal_sun(jd: float) -> float:
    # Swiss SIDEREAL applies NONUT consistently with the selected ayanamsa.
    # Subtracting a mean ayanamsa from apparent tropical longitude mixes frames.
    return swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0] % 360


def _sign_facts(chart, arudhas):
    result = []
    for sign in range(12):
        # Resolve co-lord-dependent facts through already computed arudha decisions.
        pada = next(row for row in arudhas["padas"].values() if row["origin_sign"] == sign)
        selected = pada["lord"]
        paka, bhoga = chart[selected], pada["sign"]
        result.append({"sign": sign, "house_from_lagna": house_from(chart["AS"], sign),
                       "house_from_AL": house_from(arudhas["AL"], sign),
                       "occupants": [p for p in PLANETS if chart[p] == sign],
                       "rasi_aspecting_planets": [p for p in PLANETS if sign in rasi_aspects(chart[p])],
                       "arudha_labels": [label for label, row in arudhas["padas"].items() if row["sign"] == sign],
                       "lord_for_paka": selected, "paka_sign": paka,
                       "paka_house_from_lagna": house_from(chart["AS"], paka),
                       "bhoga_sign": bhoga, "bhoga_house_from_AL": house_from(arudhas["AL"], bhoga)})
    return result


def build_hora_finance(chart_object, natal: dict, *, window_start_utc: str,
                       window_end_utc: str) -> dict:
    """Called under the API's Swiss Ephemeris lock with Lahiri configured.

    Charts and all dates are natal. TP start/end may delimit the requested
    observation window; this does not reset or compress the natal dasa.
    """
    if not {"D1", "D2_kashinatha"} <= natal["charts"].keys():
        raise ValueError("Rao finance requires explicitly selected D1 and D2_kashinatha.")
    d1 = chart_signs(natal["charts"]["D1"]["positions"])
    hora = chart_signs(natal["charts"]["D2_kashinatha"]["positions"])
    degrees = {p: natal["charts"]["D1"]["positions"][p]["position_degrees_exact"] % 30 for p in PLANETS}
    second = (d1["AS"] + 1) % 12
    issues = deepcopy(list(SOURCE_ISSUES))
    # Karyesha follows the classical D1 ruler used in the article's NTR example.
    karyesha = LORDS[second][0]
    result = {
        "technique_id": TECHNIQUE_ID, "technique_version": "0.2.0",
        "status": "computed_pending_interval_review", "ready_for_interpretation": False,
        "calculation_complete": True,
        "scope": "natal_finance", "sources": [
            "https://www.vedicastrologer.org/articles/hora.pdf",
            "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
            "https://storage.yandexcloud.net/j108/library/6fhh7uus/Sanjay_Rath_-_Narayana_Dasa.pdf"],
        "rules_profile": {"strength_and_dasa": "rao_textbook_2000_sections_15_18",
                          "maximum_md_years": "12; Rath 2004 p.40 exception 3(b), including Mercury in Virgo",
                          "solar_calendar": "Lahiri Sun, Swiss FLG_SIDEREAL (NONUT); equal solar arcs",
                          "longitude_tie_break": "explicit natal D1 degrees, reversed for nodes; no fabricated varga degrees",
                          "nodes_exaltation": "Rao table 6: Rahu Gemini, Ketu Sagittarius; isolated from legacy dignity output",
                          "special_lagna_sunrise": "upper limb, refraction, pressure 1013.25 hPa, temperature 15 C",
                          "karyesha": "classical D1 second lord as in Hora article",
                          "narayana_seed_lord": "classical D1 second lord; Hora article NTR example uses Mars, not Ketu",
                          "annual_compression": False},
        "source_issues": issues,
        "qualification": {"calculated_at": "central_birth_instant_only",
                          "interval_stability_verified": False,
                          "note": "Existing rectification declarations do not certify new special lagnas or this technique."},
        "window": {"start_utc": window_start_utc, "end_utc": window_end_utc},
        "charts": deepcopy({k: natal["charts"][k] for k in ("D1", "D2_kashinatha")}),
        "karyesha": {"planet": karyesha, "d1_second_sign": second,
                     "hora_sign": hora[karyesha], "hora_house": house_from(hora["AS"], hora[karyesha])},
        "hora_day_night_condition": {
            p: {"sign": hora[p], "day_strong_sign": hora[p] in (4,5,6,7,10,11),
                "preferred_class": "day" if p in ("SU","MA","JU") else "night",
                "in_preferred_class": (hora[p] in (4,5,6,7,10,11)) == (p in ("SU","MA","JU"))}
            for p in PLANETS if p not in ("RA", "KE")},
        "rasi_aspects": {p: list(rasi_aspects(hora[p])) for p in PLANETS},
        "pachakadi": pachakadi_relations(hora, variant=PACHAKADI_VARIANT),
    }
    try:
        arudhas = bhava_arudhas(hora, degrees=degrees)
        result["arudhas"] = arudhas
        result["sign_contexts"] = _sign_facts(hora, arudhas)
        result["karyesha"]["house_from_AL"] = house_from(arudhas["AL"], hora[karyesha])
        seed_choice = {"winner": karyesha, "rule": "hora_article_classical_second_lord", "comparisons": []}
        result["seed_lord_decision"] = seed_choice
        structure = period_structure(hora, reference_sign=hora[seed_choice["winner"]], degrees=degrees)
        result["narayana_structure"] = structure
        calendar = SolarArcCalendar(natal["jd_ut"], _sidereal_sun)
        result["narayana"] = dated_periods(structure, hora, calendar,
            window=(_jd(window_start_utc), _jd(window_end_utc)), degrees=degrees)
    except UnresolvedRule as exc:
        issues.append({"id": "case_rule_unresolved", "status": "unresolved", "detail": str(exc)})
        result["status"] = "blocked_unresolved_rule"
        result["calculation_complete"] = False
    sr, _, nxt = chart_object._sr_ss_by_se(natal["jd_ut"], mode="standard")
    special = hora_ghati_lagnas(moment_jd=natal["jd_ut"], sunrise_jd=sr,
        next_sunrise_jd=nxt, sun_longitude_at_sunrise=_sidereal_sun(sr))
    special["hora_positions"] = {}
    for code in ("HL", "GL"):
        longitude = special[code]
        special["hora_positions"][code] = chart_object.calculate_hora_kashinatha_position(
            longitude, int(longitude // 30), hora["AS"])
    result["special_lagnas"] = special
    return result
