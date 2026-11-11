"""Pachakadi facts for an explicitly named source variant, in any supplied chart.

Sanjay Rath, Narayana Dasa, version 3 (2004), Appendix 1, tables 55-57,
printed pp.191-193. Natural and positional relationships are separate.
This implements the printed tables, not a claim that editions agree.
"""
from __future__ import annotations

from collections.abc import Mapping
from .rasi_rules import PLANETS, validate_chart

VARIANT = "rath_narayana_2004_tables_55_57"
SOURCE = "https://storage.yandexcloud.net/j108/library/6fhh7uus/Sanjay_Rath_-_Narayana_Dasa.pdf"
ROLES = ("pachaka", "bodhaka", "karaka", "vedhaka")
_NATURAL = {
    "SU": ("SA", "MA", "JU", "VE"),
    "MO": ("VE", "MA", "SA", "SU"),
    "MA": ("SU", "MO", "SA", "ME"),
    "ME": ("MO", "JU", "VE", "MA"),
    "JU": ("SA", "MA", "MO", "SU"),
    "VE": ("MO", "ME", "SA", "SU"),
    "SA": ("VE", "MO", "JU", "MA"),
}
_HOUSES = {
    "SU": (6, 7, 9, 11), "MO": (7, 9, 11, 3),
    "MA": (2, 6, 11, 12), "ME": (2, 4, 5, 3),
    "JU": (6, 5, 7, 12), "VE": (2, 6, 12, 4),
    "SA": (3, 11, 6, 7),
}
# Table 57 is a distinct list, not "every vedhaka is an enemy".
_INIMICAL = {
    "SU": ("pachaka", "SA", 6), "MO": ("vyaya", None, 12),
    "MA": ("vedhaka", "ME", 12), "ME": ("vedhaka", "MA", 3),
    "JU": ("pachaka", "SA", 6), "VE": ("vedhaka", "SU", 4),
    "SA": ("karaka", "JU", 6),
}


def pachakadi_relations(chart: Mapping, *, variant: str) -> dict:
    """Return directed relations from each of seven classical planets.

Nodes may act by placement; the source has no natural-role row for a node.
No aspects are required for a natural relationship. No score or outcome is
inferred from the relation, even if natural and positional roles coincide.
"""
    if variant != VARIANT:
        raise ValueError("Select the documented Pachakadi source variant explicitly.")
    validate_chart(chart)

    def position(house, origin):
        sign = (chart[origin] + house - 1) % 12
        return {"house_from_subject": house, "sign": sign,
                "planets": [p for p in PLANETS if chart[p] == sign]}

    subjects = {}
    for subject in PLANETS[:7]:
        roles = {}
        for role, natural, house in zip(ROLES, _NATURAL[subject], _HOUSES[subject]):
            positional = position(house, subject)
            roles[role] = {"natural_planet": natural, "positional": positional,
                           "natural_also_positional": natural in positional["planets"]}
        role, natural, house = _INIMICAL[subject]
        subjects[subject] = {
            "sign": chart[subject], "roles": roles,
            "inimical_table_57": {"role": role, "natural_planet": natural,
                                   "positional": position(house, subject)},
        }
    return {"variant": variant, "source": SOURCE, "subjects": subjects,
            "conventions": {"counting": "inclusive forward from subject planet",
                            "natural_and_positional": "separate directed relations",
                            "nodes": "positional actors only; no invented natural rows"},
            "source_variant_note": {
                "subject": "VE", "selected_karaka": "SA", "selected_vedhaka": "SU",
                "alternative": "Rath Crux table 2.1 reverses these two natural roles (SU/SA).",
                "decision": "Use Narayana Dasa printed tables consistently, as the work referenced by the Hora article; not a universal resolution of the textual discrepancy."}}
