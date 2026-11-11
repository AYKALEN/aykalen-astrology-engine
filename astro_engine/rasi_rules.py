"""Reusable sign geometry and explicit Rao rules, without report interpretation.

Sign indices are zero based. Source: Rao, Vedic Astrology: An Integrated
Approach, sections 3.2.16, 8.2, 15.5. These rules are a named convention,
not a replacement for the existing Parashari facts or a generic strength score.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from .facts import ZODIAC_SIGNS

PLANETS = ("SU", "MO", "MA", "ME", "JU", "VE", "SA", "RA", "KE")
LORDS = (("MA",), ("VE",), ("ME",), ("MO",), ("SU",), ("ME",),
         ("VE",), ("MA", "KE"), ("JU",), ("SA",), ("SA", "RA"), ("JU",))
EXALTED = dict(zip(PLANETS, (0, 1, 9, 5, 3, 11, 6, 2, 8)))
ODD_FOOTED = frozenset((0, 1, 2, 6, 7, 8))


class UnresolvedRule(ValueError):
    """A source rule did not select a unique result; never silently break a tie."""


def sign_index(value: int) -> int:
    if type(value) is not int or not 0 <= value < 12:
        raise ValueError("Sign index must be an integer in 0..11.")
    return value


def chart_signs(positions: Mapping) -> dict[str, int]:
    """Adapt the existing engine chart, requiring actual (not inferred) Lagna."""
    result = {}
    for code in ("AS", *PLANETS):
        try:
            result[code] = ZODIAC_SIGNS.index(positions[code]["zodiac_sign"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Missing or invalid sign for {code}.") from exc
    return result


def validate_chart(chart: Mapping) -> None:
    for code in ("AS", *PLANETS):
        if code not in chart:
            raise ValueError(f"Missing sign for {code}.")
        sign_index(chart[code])


def house_from(origin: int, target: int) -> int:
    return (sign_index(target) - sign_index(origin)) % 12 + 1


def rasi_aspects(origin: int) -> tuple[int, ...]:
    """Rasi drishti, distinct from the existing graha drishti."""
    origin = sign_index(origin)
    if origin % 3 == 2:
        return tuple(i for i in range(2, 12, 3) if i != origin)
    target_type = 1 if origin % 3 == 0 else 0
    return tuple(i for i in range(target_type, 12, 3)
                 if (i - origin) % 12 not in (1, 11))


def occupants(chart: Mapping, sign: int) -> list[str]:
    return [p for p in PLANETS if chart[p] == sign]


def _support(chart: Mapping, sign: int) -> list[str]:
    # Roles count separately: Mercury can count as Mercury AND as dispositor.
    # Both co-lords can contribute (Rao, answer to Exercise 26, pair Le/Aq).
    roles = [("JU", "JU"), ("ME", "ME")]
    roles += [("lord:" + p, p) for p in LORDS[sign]]
    return [role for role, p in roles
            if chart[p] == sign or sign in rasi_aspects(chart[p])]


def advancement(code: str, degrees: Mapping | None) -> float:
    if degrees is None or code not in degrees:
        raise UnresolvedRule(f"Longitude tie-break requires explicit degrees for {code}.")
    value = degrees[code]
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value < 30:
        raise ValueError("Tie-break degrees must be finite and in [0,30).")
    return 30 - value if code in ("RA", "KE") else float(value)


def years_for_lord(sign: int, lord: str, chart: Mapping) -> int:
    """Narayana first-cycle duration; zero is permitted, never rounded to one."""
    direction = 1 if sign_index(sign) in ODD_FOOTED else -1
    distance = ((chart[lord] - sign) * direction) % 12
    years = distance or 12
    if chart[lord] == EXALTED[lord]:
        years += 1
    elif chart[lord] == (EXALTED[lord] + 6) % 12:
        years -= 1
    # Rath, Narayana Dasa (2004), printed p.40, exception 3(b):
    # Mercury in Virgo is both own and exalted; maximum is 12, not 13.
    years = min(years, 12)
    if not 0 <= years <= 12:
        raise UnresolvedRule("Duration outside 0..12; conflicting own/exaltation conventions.")
    return years


def stronger_lord(sign: int, chart: Mapping, *, purpose: str,
                  degrees: Mapping | None = None) -> dict:
    """Resolve co-lords lexicographically, keeping the determining rule."""
    sign_index(sign)
    if purpose not in ("arudha", "duration"):
        raise ValueError("purpose must be arudha or duration.")
    candidates = LORDS[sign]
    if len(candidates) == 1:
        return {"winner": candidates[0], "rule": "sole_lord", "comparisons": []}
    a, b = candidates
    if (chart[a] == sign) != (chart[b] == sign):
        return {"winner": b if chart[a] == sign else a,
                "rule": "co_lord_outside_own_sign", "comparisons": []}
    checks = (
        ("companions", lambda p: len(occupants(chart, chart[p])) - 1),
        ("jupiter_mercury_dispositor_support", lambda p: len(_support(chart, chart[p]))),
        ("exaltation", lambda p: int(chart[p] == EXALTED[p])),
        ("dual_fixed_movable", lambda p: chart[p] % 3),
        (("longer_dasa" if purpose == "duration" else "longitude_advancement"),
         (lambda p: years_for_lord(sign, p, chart)) if purpose == "duration"
         else (lambda p: advancement(p, degrees))),
    )
    trace = []
    for rule, measure in checks:
        av, bv = measure(a), measure(b)
        trace.append({"rule": rule, a: av, b: bv})
        if av != bv:
            return {"winner": a if av > bv else b, "rule": rule, "comparisons": trace}
    raise UnresolvedRule(f"Equal co-lords for sign {sign}, purpose {purpose}.")


def stronger_sign(a: int, b: int, chart: Mapping, *, degrees: Mapping | None = None) -> dict:
    sign_index(a); sign_index(b)
    if a == b:
        raise ValueError("Compare different signs.")
    trace = []
    lord_cache = {}

    def lord(s):
        if s not in lord_cache:
            lord_cache[s] = stronger_lord(s, chart, purpose="duration", degrees=degrees)
        return lord_cache[s]["winner"]

    checks = (
        ("occupants", lambda s: len(occupants(chart, s))),
        ("jupiter_mercury_lord_support", lambda s: len(_support(chart, s))),
        ("contains_exalted_planet", lambda s: int(any(chart[p] == EXALTED[p] for p in occupants(chart, s)))),
        ("lord_different_parity", lambda s: int(s % 2 != chart[lord(s)] % 2)),
        ("dual_fixed_movable", lambda s: s % 3),
        ("lord_advancement", lambda s: advancement(lord(s), degrees)),
    )
    for rule, measure in checks:
        av, bv = measure(a), measure(b)
        trace.append({"rule": rule, "left": av, "right": bv})
        if av != bv:
            return {"winner": a if av > bv else b, "rule": rule, "comparisons": trace,
                    "lord_decisions": lord_cache}
    raise UnresolvedRule(f"Equal signs {a} and {b}; no documented tie-break remains.")
