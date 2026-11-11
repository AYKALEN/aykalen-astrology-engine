"""Reusable natal Narayana periods; Rao textbook sections 18.2, 18.3, 18.6.

Caller supplies an explicit reference sign (not implicitly the chart Lagna).
No annual compression, report routing, interpretation, or OpenAI calls.
"""
from __future__ import annotations

from collections.abc import Mapping

from .rasi_rules import (ODD_FOOTED, UnresolvedRule, sign_index, stronger_lord,
                         stronger_sign, validate_chart, years_for_lord)
from .solar_calendar import SolarArcCalendar, jd_to_utc


def progression(seed: int, chart: Mapping) -> dict:
    seed = sign_index(seed)
    direction = 1 if (seed + 8) % 12 in ODD_FOOTED else -1
    exception = None
    if chart["SA"] == seed and chart["KE"] == seed:
        raise UnresolvedRule("Saturn and Ketu both occupy MD seed; precedence needs a source.")
    if chart["SA"] == seed:
        offsets = tuple(range(12))
        direction, exception = 1, "saturn"
    else:
        if chart["KE"] == seed:
            direction, exception = -direction, "ketu"
        offsets = (tuple(range(12)) if seed % 3 == 0 else
                   tuple(i * 5 for i in range(12)) if seed % 3 == 1 else
                   (0, 4, 8, 9, 1, 5, 6, 10, 2, 3, 7, 11))
    return {"signs": [(seed + direction * n) % 12 for n in offsets],
            "direction": direction, "exception": exception}


def subperiod_order(parent_sign: int, chart: Mapping, *, degrees: Mapping | None = None) -> dict:
    decision = stronger_sign(parent_sign, (parent_sign + 6) % 12, chart, degrees=degrees)
    seed = decision["winner"]
    lord_decision = stronger_lord(seed, chart, purpose="duration", degrees=degrees)
    first = chart[lord_decision["winner"]]
    direction = 1 if first % 2 == 0 else -1  # odd/even, not odd/even-footed
    exception = None
    if chart["SA"] == seed and chart["KE"] == seed:
        raise UnresolvedRule("Saturn and Ketu both occupy AD seed; precedence needs a source.")
    if chart["SA"] == seed:
        direction, exception = 1, "saturn"
    elif chart["KE"] == seed:
        direction, exception = -direction, "ketu"
    return {"seed_sign": seed, "seed_decision": decision, "lord_decision": lord_decision,
            "signs": [(first + direction * i) % 12 for i in range(12)],
            "direction": direction, "exception": exception}


def third_topics(sign: int) -> tuple[str, ...]:
    """Order of factors, not three predictions (Hora paper table 2)."""
    sign_index(sign)
    if sign == 11:
        return ("occupants_and_aspectors", "house", "lord")
    if sign in (2, 4, 5, 6, 7, 10):
        return ("house", "lord", "occupants_and_aspectors")
    return ("occupants_and_aspectors", "lord", "house")


def period_structure(chart: Mapping, *, reference_sign: int,
                     degrees: Mapping | None = None) -> dict:
    validate_chart(chart)
    reference_sign = sign_index(reference_sign)
    decision = stronger_sign(reference_sign, (reference_sign + 6) % 12, chart, degrees=degrees)
    seed = decision["winner"]
    order = progression(seed, chart)
    durations, decisions = {}, {}
    for sign in order["signs"]:
        choice = stronger_lord(sign, chart, purpose="duration", degrees=degrees)
        decisions[sign] = choice
        durations[sign] = years_for_lord(sign, choice["winner"], chart)
    rows, offset = [], 0
    for cycle in (1, 2):
        for sign in order["signs"]:
            years = durations[sign] if cycle == 1 else 12 - durations[sign]
            rows.append({"sign": sign, "cycle": cycle, "years": years,
                         "start_year": offset, "end_year": offset + years,
                         "lord_decision": decisions[sign]})
            offset += years
    assert offset == 144
    return {"reference_sign": reference_sign, "seed_sign": seed,
            "starts_from_opposite": seed != reference_sign, "seed_decision": decision,
            "progression": order, "periods": rows}


def dated_periods(structure: Mapping, chart: Mapping, calendar: SolarArcCalendar, *,
                  window: tuple[float, float], degrees: Mapping | None = None) -> dict:
    """Full MD/AD/PD boundaries for a requested window, preserving source dates.

    144 years is the mathematical two-cycle span. This profile exposes only
    the first 120 solar years, following Rao's chapter 18 examples.
    """
    start, end = window
    if not calendar.epoch_jd <= start < end <= calendar.at_years(120):
        raise ValueError("Window must be within the first 120 solar years from birth.")
    result = []
    for raw in structure["periods"]:
        if raw["years"] == 0 or raw["start_year"] >= 120:
            continue
        lo, hi = calendar.at_years(raw["start_year"]), calendar.at_years(raw["end_year"])
        if max(lo, start) >= min(hi, end):
            continue
        row = dict(raw)
        row.update(_boundaries(lo, hi, start, end))
        row["thirds"] = [dict(factor=factor, **_boundaries(
            calendar.at_years(raw["start_year"] + raw["years"] * i / 3),
            calendar.at_years(raw["start_year"] + raw["years"] * (i + 1) / 3)))
            for i, factor in enumerate(third_topics(raw["sign"]))]
        ad_order = subperiod_order(raw["sign"], chart, degrees=degrees)
        row["antardasa_order"] = ad_order
        row["antardasas"] = []
        for i, ad in enumerate(ad_order["signs"]):
            ad_offset = raw["start_year"] + raw["years"] * i / 12
            ad_end = raw["start_year"] + raw["years"] * (i + 1) / 12
            a, b = calendar.at_years(ad_offset), calendar.at_years(ad_end)
            if max(a, start) >= min(b, end):
                continue
            ad_row = {"sign": ad, **_boundaries(a, b, start, end)}
            pd_order = subperiod_order(ad, chart, degrees=degrees)
            ad_row["pratyantardasa_order"] = pd_order
            ad_row["pratyantardasas"] = []
            for j, pd in enumerate(pd_order["signs"]):
                # Share exact parent endpoints despite floating-point subdivision.
                p = a if j == 0 else calendar.at_years(ad_offset + (ad_end - ad_offset) * j / 12)
                q = b if j == 11 else calendar.at_years(ad_offset + (ad_end - ad_offset) * (j + 1) / 12)
                if max(p, start) < min(q, end):
                    ad_row["pratyantardasas"].append({"sign": pd, **_boundaries(p, q, start, end)})
            row["antardasas"].append(ad_row)
        result.append(row)
    if not result:
        raise ValueError("No periods cover the requested window.")
    return {"window_start_utc": jd_to_utc(start), "window_end_utc": jd_to_utc(end),
            "intervals": "[start,end)", "calendar": "sidereal_solar_arc",
            "periods": result}


def _boundaries(start, end, clip_start=None, clip_end=None):
    result = {"start_utc": jd_to_utc(start), "end_utc": jd_to_utc(end)}
    if clip_start is not None:
        result.update(window_start_utc=jd_to_utc(max(start, clip_start)),
                      window_end_utc=jd_to_utc(min(end, clip_end)))
    return result
