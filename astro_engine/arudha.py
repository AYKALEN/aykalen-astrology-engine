"""Bhava arudhas in any supplied whole-sign chart; Rao section 9.2."""
from __future__ import annotations

from collections.abc import Mapping
from .rasi_rules import house_from, sign_index, stronger_lord, validate_chart


def arudha_sign(origin: int, lord_position: int) -> int:
    origin, lord_position = sign_index(origin), sign_index(lord_position)
    reflected = (2 * lord_position - origin) % 12
    return (reflected + 9) % 12 if house_from(origin, reflected) in (1, 7) else reflected


def bhava_arudhas(chart: Mapping, *, degrees: Mapping | None = None) -> dict:
    validate_chart(chart)
    result = {}
    for house in range(1, 13):
        origin = (chart["AS"] + house - 1) % 12
        decision = stronger_lord(origin, chart, purpose="arudha", degrees=degrees)
        lord = decision["winner"]
        reflected = (2 * chart[lord] - origin) % 12
        result[f"A{house}"] = {
            "house": house, "origin_sign": origin, "lord": lord,
            "lord_sign": chart[lord], "sign": arudha_sign(origin, chart[lord]),
            "exception_applied": house_from(origin, reflected) in (1, 7),
            "lord_decision": decision,
        }
    return {"padas": result, "AL": result["A1"]["sign"], "UL": result["A12"]["sign"]}
