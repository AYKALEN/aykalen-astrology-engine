# -*- coding: utf-8 -*-
"""
Viṃśopaka Bala — isolated legacy numerical profile.

This is the inherited simplified natural-friendship approximation, not a
complete fivefold-friendship implementation. It is optional raw arithmetic,
not enabled as an annual interpretive signal. Incomplete inputs and invalid
weight profiles return score=None; only diagnostic_partial_sum is available.

Wagi powinny sumować się do 20. Odziedziczona Daśavarga sumuje się do 21:
pozostaje zachowana do jawnej korekty metody, ale jej wynik jest zablokowany.
D2 w wagach = **Horā Parāśara** (Rak/Lew), nie Parivṛtti.

Punktacja jakości vargi (`VARGA_VISHVA`) wg KS-101.6 / BPHS 7.24–25:
  SVAKSHETRA / UCCHA / mūlatrikoṇa → 20
  MITRA (przyjacielski)            → 15   (ADHI_MITRA=18 wymaga pañcadhā — TODO)
  SAMA (neutralna)                 → 10
  SHATRU (wrogi)                   → 7    (ADHI_SHATRU=5 wymaga pañcadhā — TODO)
  neecha (upadek)                  → 5    (najniższy dostępny tier bez pañcadhā)
  węzły                            → n/d

Wkład vargi: w(v) * varga_viśva / 20  (KS-101.6).
"""

from __future__ import annotations

from typing import Any

from .facts import (
    chart_dict_from_detailed,
    sign_dignity,
)

CLASSICAL = ("SU", "MO", "ME", "VE", "MA", "JU", "SA")

# Wagi BPHS (suma = 20). Klucz D2 → mapa Parāśara w packu.
WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "shadvarga": [
        ("D1", 6),
        ("D2", 2),
        ("D3", 4),
        ("D9", 5),
        ("D12", 2),
        ("D30", 1),
    ],
    "saptavarga": [
        ("D1", 5),
        ("D2", 2),
        ("D3", 3),
        ("D7", 2.5),
        ("D9", 4.5),
        ("D12", 2),
        ("D30", 1),
    ],
    "dashavarga": [
        ("D1", 3),
        ("D2", 3),
        ("D3", 1),
        ("D7", 1.5),
        ("D9", 1.5),
        ("D10", 1.5),
        ("D12", 1.5),
        ("D16", 1.5),
        ("D30", 1.5),
        ("D60", 5),
    ],
    "shodashavarga": [
        ("D1", 3.5),
        ("D2", 1),
        ("D3", 1),
        ("D4", 0.5),
        ("D7", 0.5),
        ("D9", 3),
        ("D10", 0.5),
        ("D12", 0.5),
        ("D16", 2),
        ("D20", 0.5),
        ("D24", 0.5),
        ("D27", 0.5),
        ("D30", 1),
        ("D40", 0.5),
        ("D45", 0.5),
        ("D60", 4),
    ],
}

SYSTEM_LABELS = {
    "shadvarga": "Ṣaḍvarga",
    "saptavarga": "Saptavarga",
    "dashavarga": "Daśavarga",
    "shodashavarga": "Ṣoḍaśavarga",
}


def dignity_factor(planet: str, sign: str, deg_in_sign: float | None = None) -> float | None:
    """Zwraca varga_viśva / 20 (KS-101.6). None = nie liczymy (węzły).

    Bez pełnej pañcadhā maitrī (tātkālika) mapujemy naisargika na MITRA/SHATRU,
    nie na ADHI_MITRA/ADHI_SHATRU. To zaniża przyjaciela względem pełnego kanonu
    tylko gdy faktycznie byłby adhi-mitra — nie względem poprzedniej skali 0.5.
    """
    if planet in ("RA", "KE"):
        return None
    dig = sign_dignity(planet, sign, deg_in_sign)
    if "upadek" in dig:
        visva = 5  # najniższy tier BPHS bez osobnej kategorii neecha
    elif any(x in dig for x in ("egzaltacja", "mūlatrikoṇa", "własny znak")):
        visva = 20
    elif "przyjacielski" in dig:
        visva = 15  # MITRA; ADHI_MITRA=18 wymaga pañcadhā
    elif "wrogi" in dig:
        visva = 7  # SHATRU; ADHI_SHATRU=5 wymaga pañcadhā
    else:
        visva = 10  # SAMA
    return visva / 20.0


def build_varga_pack_for_vimsopaka(chart_obj, detailed: dict) -> dict[str, dict]:
    """Pack D1 + Vargi; D2 = Parāśara."""
    divs = chart_obj.calculate_all_divisionals_from_detailed(detailed)
    pack: dict[str, dict] = {"D1": chart_dict_from_detailed(detailed)}
    mapping = {
        "D2": "D2_parashara",
        "D3": "D3",
        "D4": "D4",
        "D7": "D7",
        "D9": "D9",
        "D10": "D10",
        "D12": "D12",
        "D16": "D16",
        "D20": "D20",
        "D24": "D24",
        "D27": "D27",
        "D30": "D30",
        "D40": "D40",
        "D45": "D45",
        "D60": "D60",
    }
    for label, key in mapping.items():
        raw = divs.get(key)
        if raw:
            pack[label] = chart_dict_from_detailed(raw)
    return pack


def _deg_in_sign(data: dict) -> float | None:
    if data.get("position_within_sign_degrees") is not None:
        try:
            return float(data["position_within_sign_degrees"])
        except (TypeError, ValueError):
            pass
    pos = data.get("position_degrees")
    if pos is None:
        return None
    try:
        return float(pos) % 30
    except (TypeError, ValueError):
        return None


def score_planet_system(planet: str, pack: dict[str, dict], system: str) -> dict[str, Any]:
    weights = WEIGHTS[system]
    total = 0.0
    parts = []
    for varga, w in weights:
        ch = pack.get(varga)
        if not ch or planet not in ch:
            parts.append({"varga": varga, "weight": w, "factor": None, "points": 0.0})
            continue
        data = ch[planet]
        sign = data["zodiac_sign"]
        # stopnie w znaku D1 tylko dla D1 (MT); w Vargach zwykle brak dokładnego °
        deg = _deg_in_sign(data) if varga == "D1" else None
        fac = dignity_factor(planet, sign, deg)
        if fac is None:
            return {
                "planet": planet,
                "system": system,
                "score": None,
                "max": 20.0,
                "band": "n/d",
                "parts": [],
            }
        pts = w * fac
        total += pts
        parts.append(
            {
                "varga": varga,
                "weight": w,
                "sign": sign,
                "factor": fac,
                "points": round(pts, 3),
            }
        )
    missing = [part["varga"] for part in parts if part["factor"] is None]
    weight_sum = sum(weight for _, weight in weights)
    if weight_sum != 20.0 or missing:
        return {
            "planet": planet,
            "system": system,
            "score": None,
            "max": 20.0,
            "band": "n/d",
            "parts": parts,
            "complete": not missing,
            "missing_vargas": missing,
            "weight_sum": weight_sum,
            "status": "UNRESOLVED" if weight_sum != 20.0 else "INCOMPLETE",
            "reason": "invalid_weight_sum" if weight_sum != 20.0 else "missing_vargas",
            "diagnostic_partial_sum": round(total, 2),
        }
    return {
        "planet": planet,
        "system": system,
        "score": round(total, 2),
        "max": 20.0,
        "band": band_for_score(total),
        "parts": parts,
        "complete": True,
        "missing_vargas": [],
        "weight_sum": weight_sum,
        "status": "CALCULATED_SIMPLIFIED",
    }


def band_for_score(score: float) -> str:
    """Klasyfikacja BPHS 7.26–27: >15 pūrṇa, >10 madhyama, >5 svalpa, <5 brak śubha.

    Endpointy dokładnie 5/10/15 są `[U · research-required]` w KS-101.6 (RG-BALA-09).
    Konwencja systemowa: punkt graniczny należy do **niższego** pasa (strict `>`),
    spójnie z lekturą „above/below” w przekładzie. DEC do potwierdzenia.
    """
    if score > 15:
        return "silna"
    if score > 10:
        return "średnia"
    if score > 5:
        return "słaba"
    return "bardzo_słaba"


def compute_all(pack: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """system → planet → result."""
    out: dict[str, dict[str, dict]] = {}
    for sys in WEIGHTS:
        out[sys] = {}
        for p in CLASSICAL:
            out[sys][p] = score_planet_system(p, pack, sys)
    return out
