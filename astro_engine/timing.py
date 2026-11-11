# -*- coding: utf-8 -*-
"""Unfiltered natal Vimshottari periods, with optional precise UTC endpoints.

Extracted without changing the legacy balance/subdivision algorithm:
365.25-day years; first MD balance rounded to five decimals; its AD/PD
durations proportionally divide that remaining MD from birth. This is not
a reconstructed pre-birth full-MD timeline. The legacy cycle contains nine
MDs and has no date-today filter. UTC intervals use [start, end).
"""
from __future__ import annotations

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from .facts import _sidereal_lon

VIMSHOTTARI_PROFILE = {
    "year_days": 365.25,
    "first_md_balance_decimals": 5,
    "first_md_subdivision": "remaining_balance_proportional_from_birth",
    "interval_convention": "[start_utc,end_utc)",
    "cycle": "nine_mahadashas_from_birth_balance",
}

def unfiltered_vimshottari(chart, *, include_timestamps: bool = False) -> list[dict]:
    """Pełny cykl bez filtra 'od dziś', opcjonalnie z granicami UTC.

    Legacy ``start``/``end`` retain their date-only format.  The opt-in UTC
    fields preserve intraday boundaries for the canonical annual timeline;
    the balance, 365.25-day year and first-MD calculation remain unchanged.
    """
    def timestamps(start: datetime, end: datetime) -> dict[str, str]:
        if not include_timestamps:
            return {}
        return {
            "start_utc": start.replace(tzinfo=timezone.utc).isoformat(),
            "end_utc": end.replace(tzinfo=timezone.utc).isoformat(),
        }

    # skopiuj logikę z natal, ale bez filtrowania
    nakshatra_length = 13 + 1 / 3
    NAKSHATRA_LORDS_L = [
        "KE",
        "VE",
        "SU",
        "MO",
        "MA",
        "RA",
        "JU",
        "SA",
        "ME",
        "KE",
        "VE",
        "SU",
        "MO",
        "MA",
        "RA",
        "JU",
        "SA",
        "ME",
        "KE",
        "VE",
        "SU",
        "MO",
        "MA",
        "RA",
        "JU",
        "SA",
        "ME",
    ]
    DASHA_SEQUENCE = ["KE", "VE", "SU", "MO", "MA", "RA", "JU", "SA", "ME"]
    DASHA_YEARS = {
        "KE": 7,
        "VE": 20,
        "SU": 6,
        "MO": 10,
        "MA": 7,
        "RA": 18,
        "JU": 16,
        "SA": 19,
        "ME": 17,
    }
    start_date = datetime.strptime(f"{chart.utc_date} {chart.calc_time}", "%Y-%m-%d %H:%M:%S")
    moon = chart.detailed_chart_data["MO"]
    moon_deg = _sidereal_lon(moon)
    if moon_deg is None:
        moon_deg = float(moon["position_degrees"])
    nakshatra_index = int(moon_deg // nakshatra_length)
    lord = NAKSHATRA_LORDS_L[nakshatra_index]
    dasha_index = DASHA_SEQUENCE.index(lord)
    degrees_in_nakshatra = moon_deg % nakshatra_length
    fraction_left = 1 - (degrees_in_nakshatra / nakshatra_length)
    first_dasha_years = round(fraction_left * DASHA_YEARS[lord], 5)

    dashas = []
    current_date = start_date
    for i in range(9):
        idx = (dasha_index + i) % len(DASHA_SEQUENCE)
        planet = DASHA_SEQUENCE[idx]
        full_duration_years = DASHA_YEARS[planet]
        duration = first_dasha_years if i == 0 else full_duration_years
        end_date = current_date + relativedelta(days=duration * 365.25)
        dasha_entry = {
            "mahadasha_lord": planet,
            "start": current_date.strftime("%d-%m-%Y"),
            "end": end_date.strftime("%d-%m-%Y"),
            **timestamps(current_date, end_date),
            "duration_years": round(duration, 2),
            "antardashas": [],
        }
        antardasha_date = current_date
        start_idx = DASHA_SEQUENCE.index(planet)
        antardasha_sequence = DASHA_SEQUENCE[start_idx:] + DASHA_SEQUENCE[:start_idx]
        for sub_index, sub_planet in enumerate(antardasha_sequence):
            sub_duration = (DASHA_YEARS[sub_planet] / 120.0) * duration
            sub_end_date = antardasha_date + relativedelta(days=sub_duration * 365.25)
            # The final child shares its parent's endpoint.  This removes only
            # accumulated timedelta microsecond rounding from the projection.
            precise_ad_end = end_date if sub_index == 8 else sub_end_date
            pd_list = []
            pd_date = antardasha_date
            pd_seq = DASHA_SEQUENCE[DASHA_SEQUENCE.index(sub_planet) :] + DASHA_SEQUENCE[
                : DASHA_SEQUENCE.index(sub_planet)
            ]
            for pd_index, pd_planet in enumerate(pd_seq):
                pd_duration = (DASHA_YEARS[pd_planet] / 120.0) * sub_duration
                pd_end = pd_date + relativedelta(days=pd_duration * 365.25)
                pd_list.append(
                    {
                        "pratyantardasha_lord": pd_planet,
                        "start": pd_date.strftime("%d-%m-%Y"),
                        "end": pd_end.strftime("%d-%m-%Y"),
                        **timestamps(
                            pd_date, precise_ad_end if pd_index == 8 else pd_end
                        ),
                        "duration_years": round(pd_duration, 4),
                    }
                )
                pd_date = pd_end
            dasha_entry["antardashas"].append(
                {
                    "antardasha_lord": sub_planet,
                    "start": antardasha_date.strftime("%d-%m-%Y"),
                    "end": sub_end_date.strftime("%d-%m-%Y"),
                    **timestamps(antardasha_date, precise_ad_end),
                    "duration_years": round(sub_duration, 3),
                    "pratyantardashas": pd_list,
                }
            )
            antardasha_date = sub_end_date
        dashas.append(dasha_entry)
        current_date = end_date
    return dashas
