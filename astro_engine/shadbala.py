# -*- coding: utf-8 -*-
"""Profiled Śaḍbala component arithmetic (standalone extraction).

This module deliberately does **not** claim that full Śaḍbala is production
ready.  It implements the component formulae already frozen in KS-101.6 and
the observed JHora 8 compatibility profile.  A total is emitted only when all
six required components are supplied for the same planet and profile.

The current pilot remains Lahiri-only.  Rāhu and Ketu are outside the
classical seven-planet calculation.  Graha-yuddha is disabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CLASSICAL_PLANETS = ("SU", "MO", "MA", "ME", "JU", "VE", "SA")
REQUIRED_COMPONENTS = ("sthana", "dig", "kala", "cheshta", "naisargika", "drik")

PROFILE_ID = "JHORA_8_LAHIRI_PILOT_V1"
DIG_PROFILE = "JHORA_8_EQUAL_FROM_LAGNA"
CHESHTA_PROFILE = "JHORA_8_CHESHTA_DUTT_NAIVE"
DRIK_PROFILE = "JHORA_8_PARASARA_DRIK_PARTIAL"

# BPHS 27.32–33 as frozen in KS-101.6.  These are not the denominators shown
# by every modern program, therefore the profile must remain explicit.
CLASSICAL_MINIMUM_VIRUPA = {
    "SU": 390.0,
    "MO": 360.0,
    "MA": 300.0,
    "ME": 420.0,
    "JU": 390.0,
    "VE": 330.0,
    "SA": 300.0,
}

# Opposite point of the direction of maximum Dig Bala, expressed as an
# offset from the exact Lagna.  This table belongs to the named compatibility
# profile and must not be silently reused for a true-MC/Sripati profile.
_DIG_ZERO_OFFSET = {
    "SU": 90.0,
    "MA": 90.0,
    "MO": 270.0,
    "VE": 270.0,
    "ME": 180.0,
    "JU": 180.0,
    "SA": 0.0,
}

_NAISARGIKA_MULTIPLIER = {
    "SA": 1,
    "MA": 2,
    "ME": 3,
    "JU": 4,
    "VE": 5,
    "MO": 6,
    "SU": 7,
}

_FIXED_VALENCE = {
    "SU": -1,
    "MA": -1,
    "SA": -1,
    "JU": 1,
    "VE": 1,
}


@dataclass(frozen=True)
class PilotProfile:
    profile_id: str = PROFILE_ID
    ayanamsa: str = "lahiri"
    dig_profile: str = DIG_PROFILE
    cheshta_profile: str = CHESHTA_PROFILE
    drik_profile: str = DRIK_PROFILE
    graha_yuddha: str = "OFF"
    full_total_emission: str = "GATED"


PILOT_PROFILE = PilotProfile()


def _result(
    value: float | None,
    status: str,
    *,
    profile: str,
    source_refs: tuple[str, ...] = (),
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "value": value,
        "unit": "virupa",
        "status": status,
        "profile": profile,
        "source_refs": list(source_refs),
    }
    out.update(extra)
    return out


def normalize_degrees(value: float) -> float:
    return float(value) % 360.0


def shortest_arc_degrees(a: float, b: float) -> float:
    raw = abs(normalize_degrees(a) - normalize_degrees(b))
    return min(raw, 360.0 - raw)


def _require_classical(planet: str) -> str:
    code = str(planet).upper()
    if code not in CLASSICAL_PLANETS:
        raise ValueError(f"planet outside classical Śaḍbala: {planet!r}")
    return code


def dig_bala(
    planet: str,
    longitude_deg: float,
    lagna_longitude_deg: float,
    *,
    profile: str = DIG_PROFILE,
) -> dict[str, Any]:
    """Degree-sensitive Dig Bala for the validated equal-from-Lagna profile."""
    code = _require_classical(planet)
    if profile != DIG_PROFILE:
        return _result(
            None,
            "UNRESOLVED",
            profile=profile,
            source_refs=("KS101.6-R017", "KS101.6-R018", "KS101.6-R019"),
            reason="unsupported_dig_reference_profile",
        )
    zero = normalize_degrees(lagna_longitude_deg + _DIG_ZERO_OFFSET[code])
    distance = shortest_arc_degrees(longitude_deg, zero)
    return _result(
        distance / 3.0,
        "READY",
        profile=profile,
        source_refs=("KS101.6-R017", "KS101.6-R018", "KS101.6-R019"),
        zero_point_deg=zero,
        distance_deg=distance,
    )


def dig_bala_vector(
    longitudes: Mapping[str, float],
    lagna_longitude_deg: float,
) -> dict[str, dict[str, Any]]:
    return {
        planet: dig_bala(planet, longitudes[planet], lagna_longitude_deg)
        for planet in CLASSICAL_PLANETS
        if planet in longitudes
    }


def naisargika_bala(planet: str) -> dict[str, Any]:
    code = _require_classical(planet)
    return _result(
        _NAISARGIKA_MULTIPLIER[code] * 60.0 / 7.0,
        "READY",
        profile="BPHS_27_14",
        source_refs=("KS101.6-R043", "KS101.6-R044", "KS101.6-R045", "KS101.6-R046", "KS101.6-R047", "KS101.6-R048", "KS101.6-R049"),
    )


def paksha_base(sun_longitude_deg: float, moon_longitude_deg: float) -> float:
    return shortest_arc_degrees(sun_longitude_deg, moon_longitude_deg) / 3.0


def paksha_bala(
    sun_longitude_deg: float,
    moon_longitude_deg: float,
    *,
    valence: int,
    multiplier: float = 1.0,
) -> dict[str, Any]:
    """Pakṣa contribution after an explicit śubha/pāpa classification.

    ``valence`` must be +1 or -1.  The caller owns Mercury classification and
    the selected bookkeeping profile; the function never guesses either.
    """
    if valence not in (-1, 1):
        return _result(
            None,
            "UNRESOLVED",
            profile="BPHS_PAKSHA_EXPLICIT_VALENCE",
            source_refs=("KS101.6-R024", "KS101.6-R025", "KS101.6-R026"),
            reason="valence_must_be_explicit",
        )
    base = paksha_base(sun_longitude_deg, moon_longitude_deg)
    value = (base if valence > 0 else 60.0 - base) * float(multiplier)
    return _result(
        value,
        "READY",
        profile="BPHS_PAKSHA_EXPLICIT_VALENCE",
        source_refs=("KS101.6-R024", "KS101.6-R025", "KS101.6-R026"),
        base_virupa=base,
        valence=valence,
        multiplier=float(multiplier),
    )


def moon_valence_elongation_90(
    sun_longitude_deg: float, moon_longitude_deg: float
) -> int:
    """Observed JHora rule: Moon is śubha from 90° elongation."""
    return 1 if shortest_arc_degrees(sun_longitude_deg, moon_longitude_deg) >= 90.0 else -1


def jhora_natonnata_bala(
    planet: str, sun_longitude_deg: float, lagna_longitude_deg: float
) -> dict[str, Any]:
    """Observed JHora 8 Natonnata compatibility formula.

    This is a program-compatibility profile (class D), not a replacement for
    the classical local-apparent-time profile.
    """
    code = _require_classical(planet)
    diva = shortest_arc_degrees(sun_longitude_deg, lagna_longitude_deg + 90.0) / 3.0
    ratri = 60.0 - diva
    if code == "ME":
        value = 60.0
    elif code in {"SU", "JU", "VE"}:
        value = diva
    else:
        value = ratri
    return _result(
        value,
        "READY",
        profile="JHORA_8_NATONNATA_SUN_DIG",
        source_refs=("KS101.6-R020", "KS101.6-R021", "KS101.6-R022", "KS101.6-R023"),
        diva_virupa=diva,
        ratri_virupa=ratri,
    )


def tribhaga_bala(planet: str, *, half: str, tercile: int) -> dict[str, Any]:
    code = _require_classical(planet)
    half_norm = str(half).lower()
    if half_norm not in {"day", "night"} or tercile not in {1, 2, 3}:
        return _result(
            None,
            "UNRESOLVED",
            profile="BPHS_TRIBHAGA",
            source_refs=("KS101.6-R027", "KS101.6-R028", "KS101.6-R029"),
            reason="invalid_day_night_or_tercile",
        )
    rulers = {
        "day": {1: "ME", 2: "SU", 3: "SA"},
        "night": {1: "MO", 2: "VE", 3: "MA"},
    }
    active = rulers[half_norm][tercile]
    value = 60.0 if code == "JU" or code == active else 0.0
    return _result(
        value,
        "READY",
        profile="BPHS_TRIBHAGA",
        source_refs=("KS101.6-R027", "KS101.6-R028", "KS101.6-R029"),
        half=half_norm,
        tercile=tercile,
        active_lord=active,
    )


def period_lord_bala(
    planet: str,
    *,
    year_lord: str,
    month_lord: str,
    day_lord: str,
    hora_lord: str,
) -> dict[str, Any]:
    """Apply the frozen 15/30/45/60 weights to already resolved lords."""
    code = _require_classical(planet)
    lords = {
        "year": _require_classical(year_lord),
        "month": _require_classical(month_lord),
        "day": _require_classical(day_lord),
        "hora": _require_classical(hora_lord),
    }
    weights = {"year": 15.0, "month": 30.0, "day": 45.0, "hora": 60.0}
    hits = {name: weights[name] for name, lord in lords.items() if lord == code}
    return _result(
        sum(hits.values()),
        "READY",
        profile="JHORA_8_VEDIC_SUNRISE_RAMAN_LITERAL",
        source_refs=("KS101.6-R030",),
        hits=hits,
        lords=lords,
    )


def circular_mean_short_arc(a: float, b: float) -> float:
    start = normalize_degrees(a)
    delta = (normalize_degrees(b) - start + 180.0) % 360.0 - 180.0
    return normalize_degrees(start + delta / 2.0)


def cheshta_kendra_bala(
    sighrocca_deg: float | None,
    mean_longitude_deg: float | None,
    true_longitude_deg: float | None,
    *,
    averaging: str = "naive",
) -> dict[str, Any]:
    if sighrocca_deg is None or mean_longitude_deg is None or true_longitude_deg is None:
        return _result(
            None,
            "UNRESOLVED",
            profile=CHESHTA_PROFILE,
            source_refs=("KS101.6-R039", "KS101.6-R040"),
            reason="missing_sighrocca_mean_or_true_longitude",
        )
    if averaging == "naive":
        midpoint = normalize_degrees((float(mean_longitude_deg) + float(true_longitude_deg)) / 2.0)
        profile = CHESHTA_PROFILE
    elif averaging == "circular":
        midpoint = circular_mean_short_arc(float(mean_longitude_deg), float(true_longitude_deg))
        profile = "PARASHARA_CLOSEST_CIRCULAR"
    else:
        raise ValueError(f"unknown cheshta averaging profile: {averaging!r}")
    kendra = shortest_arc_degrees(float(sighrocca_deg), midpoint)
    return _result(
        kendra / 3.0,
        "READY",
        profile=profile,
        source_refs=("KS101.6-R039", "KS101.6-R040"),
        midpoint_deg=midpoint,
        kendra_deg=kendra,
        averaging=averaging,
    )


def sphuta_general(distance_deg: float) -> float:
    d = normalize_degrees(distance_deg)
    if d <= 30.0:
        return 0.0
    if d <= 60.0:
        return (d - 30.0) / 2.0
    if d <= 90.0:
        return d - 45.0
    if d <= 120.0:
        return 30.0 + (120.0 - d) / 2.0
    if d <= 150.0:
        return 150.0 - d
    if d <= 180.0:
        return 2.0 * (d - 150.0)
    if d < 300.0:
        return (300.0 - d) / 2.0
    return 0.0


def sphuta_drishti(aspector: str, distance_deg: float) -> float:
    """JHora 8 Parāśara special-replacement profile."""
    code = _require_classical(aspector)
    d = normalize_degrees(distance_deg)
    r = d % 30.0
    if code == "SA":
        if 30.0 <= d < 60.0:
            return 2.0 * r
        if 60.0 <= d < 90.0:
            return 60.0 - r / 2.0
        if 240.0 <= d < 270.0:
            return r + 30.0
        if 270.0 <= d < 300.0:
            return 2.0 * (30.0 - r)
    elif code == "MA":
        if 60.0 <= d < 90.0:
            return 1.5 * r + 15.0
        if 90.0 <= d < 120.0 or 210.0 <= d < 240.0:
            return 60.0 - r
        if 180.0 <= d < 210.0:
            return 60.0
    elif code == "JU":
        if 90.0 <= d < 120.0 or 210.0 <= d < 240.0:
            return r / 2.0 + 45.0
        if 120.0 <= d < 150.0:
            return 60.0 - 2.0 * r
        if 240.0 <= d < 270.0:
            # Observed JHora 8 branch; intentionally separate from the
            # source-literal doubled and Santhanam-single variants.
            return 60.0 - 1.5 * r
    return sphuta_general(d)


def _valence_map(
    longitudes: Mapping[str, float],
    explicit: Mapping[str, int] | None,
) -> dict[str, int | None]:
    out: dict[str, int | None] = {planet: _FIXED_VALENCE.get(planet) for planet in CLASSICAL_PLANETS}
    if "SU" in longitudes and "MO" in longitudes:
        out["MO"] = moon_valence_elongation_90(longitudes["SU"], longitudes["MO"])
    if explicit:
        for planet, valence in explicit.items():
            code = _require_classical(planet)
            if valence not in (-1, 1):
                raise ValueError(f"valence for {code} must be -1 or +1")
            out[code] = int(valence)
    return out


def drik_bala_vector(
    longitudes: Mapping[str, float],
    *,
    explicit_valence: Mapping[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute signed Dṛk Bala; unresolved valence is never guessed."""
    missing_positions = [p for p in CLASSICAL_PLANETS if p not in longitudes]
    if missing_positions:
        raise ValueError(f"missing classical longitudes: {missing_positions}")
    valence = _valence_map(longitudes, explicit_valence)
    out: dict[str, dict[str, Any]] = {}
    for target in CLASSICAL_PLANETS:
        contributions: list[dict[str, Any]] = []
        unresolved: list[str] = []
        signed_sum = 0.0
        for aspector in CLASSICAL_PLANETS:
            if aspector == target:
                continue
            distance = normalize_degrees(longitudes[target] - longitudes[aspector])
            strength = sphuta_drishti(aspector, distance)
            sign = valence.get(aspector)
            if sign is None:
                unresolved.append(aspector)
                signed = None
            else:
                signed = strength * sign
                signed_sum += signed
            contributions.append(
                {
                    "aspector": aspector,
                    "distance_deg": distance,
                    "strength_virupa": strength,
                    "valence": sign,
                    "signed_virupa": signed,
                }
            )
        if unresolved:
            out[target] = _result(
                None,
                "UNRESOLVED",
                profile=DRIK_PROFILE,
                source_refs=("KS101.6-R051", "KS101.6-R053", "KS101.6-R054", "KS101.6-R055", "KS101.6-R056", "KS101.6-R057", "KS101.6-R058"),
                reason="aspector_valence_unresolved",
                unresolved_aspectors=unresolved,
                known_quarter_sum=signed_sum / 4.0,
                contributions=contributions,
            )
        else:
            out[target] = _result(
                signed_sum / 4.0,
                "READY",
                profile=DRIK_PROFILE,
                source_refs=("KS101.6-R051", "KS101.6-R053", "KS101.6-R054", "KS101.6-R055", "KS101.6-R056", "KS101.6-R057", "KS101.6-R058"),
                contributions=contributions,
            )
    return out


def aggregate_shadbala(
    planet: str,
    components: Mapping[str, float | Mapping[str, Any] | None],
    *,
    profile: str = PROFILE_ID,
    diagnostic: bool = False,
) -> dict[str, Any]:
    """Aggregate only a complete six-component vector.

    Missing, unresolved and cross-profile components do not become zero.
    ``partial_sum`` is diagnostic only and must not be interpreted as a total.
    Even a complete vector remains gated in the pilot profile.  Its arithmetic
    can be inspected only through the explicit ``diagnostic=True`` path and is
    never marked publishable.
    """
    code = _require_classical(planet)
    values: dict[str, float] = {}
    missing: list[str] = []
    unresolved: list[str] = []
    profile_mismatch: list[str] = []
    for component in REQUIRED_COMPONENTS:
        raw = components.get(component)
        if raw is None:
            missing.append(component)
            continue
        if isinstance(raw, Mapping):
            value = raw.get("value")
            status = str(raw.get("status", "UNRESOLVED"))
            component_profile = raw.get("profile")
            if status != "READY" or value is None:
                unresolved.append(component)
                continue
            if component_profile not in (None, profile, DIG_PROFILE, CHESHTA_PROFILE, DRIK_PROFILE, "BPHS_27_14", "BPHS_PAKSHA_EXPLICIT_VALENCE", "BPHS_TRIBHAGA", "JHORA_8_NATONNATA_SUN_DIG", "JHORA_8_VEDIC_SUNRISE_RAMAN_LITERAL"):
                profile_mismatch.append(component)
                continue
            values[component] = float(value)
        else:
            values[component] = float(raw)

    incomplete = bool(missing or unresolved or profile_mismatch)
    partial_sum = sum(values.values())
    if incomplete:
        return {
            "planet": code,
            "profile": profile,
            "status": "INCOMPLETE",
            "value": None,
            "unit": "virupa",
            "partial_sum": partial_sum,
            "missing_components": missing,
            "unresolved_components": unresolved,
            "profile_mismatch_components": profile_mismatch,
            "components": values,
            "publishable": False,
            "source_refs": ["KS101.6-R005", "KS101.6-R059", "KS101.6-R060"],
        }

    if not diagnostic:
        return {
            "planet": code,
            "profile": profile,
            "status": "GATED",
            "value": None,
            "unit": "virupa",
            "missing_components": [],
            "unresolved_components": [],
            "profile_mismatch_components": [],
            "components": values,
            "publishable": False,
            "reason": "full_shadbala_release_gate_closed",
            "source_refs": ["KS101.6-R005", "KS101.6-R059", "KS101.6-R060"],
        }

    total = partial_sum
    minimum = CLASSICAL_MINIMUM_VIRUPA[code]
    return {
        "planet": code,
        "profile": profile,
        "status": "CALCULATED_GATED",
        "value": total,
        "unit": "virupa",
        "rupa": total / 60.0,
        "minimum_virupa": minimum,
        "ratio": total / minimum,
        "threshold_candidate": total >= minimum,
        "is_strong": None,
        "components": values,
        "publishable": False,
        "source_refs": ["KS101.6-R005", "KS101.6-R059", "KS101.6-R060", "KS101.6-R061", "KS101.6-R062", "KS101.6-R063", "KS101.6-R064", "KS101.6-R065"],
        "warning": "diagnostic_only; full total and strength predicates remain gated",
    }


def component_snapshot(
    longitudes: Mapping[str, float],
    lagna_longitude_deg: float,
    *,
    explicit_valence: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Safe pilot snapshot: verified components only; never a full total."""
    return {
        "profile": PILOT_PROFILE.__dict__.copy(),
        "dig": dig_bala_vector(longitudes, lagna_longitude_deg),
        "naisargika": {p: naisargika_bala(p) for p in CLASSICAL_PLANETS},
        "drik": drik_bala_vector(longitudes, explicit_valence=explicit_valence),
        "full_shadbala_status": "INCOMPLETE",
        "full_shadbala_publishable": False,
        "missing_runtime_components": ["sthana", "kala", "cheshta"],
    }
