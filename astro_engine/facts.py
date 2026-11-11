# -*- coding: utf-8 -*-
"""Pure derived chart facts, extracted from the existing calculation helpers.

No client registry, file reads, report formatting, AI, confidence or domain
workflow is imported. Input charts use Polish zodiac names and AS/SU/MO etc.

The functions preserve the original arithmetic and conventions. Optional
combustion, kazimi, graha-yuddha and nica-bhanga helpers are LEGACY profiles,
not newly validated classical rules. In particular:
- conjunctions require the same sign; labels are inherited orb bands;
- sign dignity uses natural friendship only (not fivefold friendship);
- combustion uses fixed legacy orbs, without retrograde-specific limits;
- yuddha requires the same sign and <= 1 degree, with lower degree as winner;
- nica-bhanga strength labels are inherited heuristics, not measured strength.
Do not treat divisional coordinates as physical angular distances.
"""
from __future__ import annotations

OPTIONAL_LEGACY_PROFILES = {
    "combustion": "LEGACY_FIXED_ORBS_NO_RETROGRADE_ADJUSTMENT",
    "kazimi": "LEGACY_17_ARCMIN",
    "graha_yuddha": "LEGACY_SAME_SIGN_1_DEG_LOWER_DEGREE_WINS",
    "nica_bhanga": "LEGACY_PATTERN_HELPER_WITH_HEURISTIC_LABELS",
}

ZODIAC_SIGNS = [
    "Baran",
    "Byk",
    "Bliźnięta",
    "Rak",
    "Lew",
    "Panna",
    "Waga",
    "Skorpion",
    "Strzelec",
    "Koziorożec",
    "Wodnik",
    "Ryby",
]

SIGN_LORD = {
    "Baran": "MA",
    "Byk": "VE",
    "Bliźnięta": "ME",
    "Rak": "MO",
    "Lew": "SU",
    "Panna": "ME",
    "Waga": "VE",
    "Skorpion": "MA",
    "Strzelec": "JU",
    "Koziorożec": "SA",
    "Wodnik": "SA",
    "Ryby": "JU",
}

PLANET_NAMES_PL = {
    "AS": "AS",
    "RA": "Rahu",
    "KE": "Ketu",
    "SU": "Słońce",
    "MO": "Księżyc",
    "ME": "Merkury",
    "VE": "Wenus",
    "MA": "Mars",
    "JU": "Jowisz",
    "SA": "Saturn",
}

OWN_SIGNS = {
    "SU": ["Lew"],
    "MO": ["Rak"],
    "ME": ["Bliźnięta", "Panna"],
    "VE": ["Byk", "Waga"],
    "MA": ["Baran", "Skorpion"],
    "JU": ["Strzelec", "Ryby"],
    "SA": ["Koziorożec", "Wodnik"],
}

EXALTATION = {
    "SU": "Baran",
    "MO": "Byk",
    "MA": "Koziorożec",
    "ME": "Panna",
    "JU": "Rak",
    "VE": "Ryby",
    "SA": "Waga",
}

# Znak → planeta, która w nim egzaltuje (odwrotność EXALTATION)
EXALTED_IN_SIGN = {sign: planet for planet, sign in EXALTATION.items()}

# Siła kancelacji (do etykiet LLM)
NICA_STRENGTH = {
    "parivartana_nica": "mocna (≈parivartana)",
    "d9_exalt": "mocna (D9)",
    "vargottama_nica": "mocna (Vargottama)",
    "exalt_planet": "średnia",
    "sign_lord": "średnia",
    "kendra_lord": "średnia",
    "exalt_lord": "słabsza niż parivartana",
}

DEBILITATION = {
    "SU": "Waga",
    "MO": "Skorpion",
    "MA": "Rak",
    "ME": "Ryby",
    "JU": "Koziorożec",
    "VE": "Panna",
    "SA": "Baran",
}

# Mūlatrikoṇa: (znak, od_stopnia, do_stopnia) — tylko gdy mamy stopnie (D1)
MOOLATRIKONA = {
    "SU": ("Lew", 0, 20),
    "MO": ("Byk", 4, 20),
    "MA": ("Baran", 0, 12),
    "ME": ("Panna", 16, 20),
    "JU": ("Strzelec", 0, 10),
    "VE": ("Waga", 0, 15),
    "SA": ("Wodnik", 0, 20),
}

# Naturalne relacje Parāśari (uproszczenie; tymczasowe pomijamy)
NATURAL_FRIENDS = {
    "SU": {"MO", "MA", "JU"},
    "MO": {"SU", "ME"},
    "MA": {"SU", "MO", "JU"},
    "ME": {"SU", "VE"},
    "JU": {"SU", "MO", "MA"},
    "VE": {"ME", "SA"},
    "SA": {"ME", "VE"},
}
NATURAL_ENEMIES = {
    "SU": {"VE", "SA"},
    "MO": {},  # brak klasycznych wrogów; Ketu czasem, tu pomijamy
    "MA": {"ME"},
    "ME": {"MO"},
    "JU": {"ME", "VE"},
    "VE": {"SU", "MO"},
    "SA": {"SU", "MO", "MA"},
}

NAKSHATRA_LORDS = [
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

PLANET_ORDER = ["AS", "RA", "KE", "SU", "MO", "ME", "VE", "MA", "JU", "SA"]
PLANETS_ONLY = ["RA", "KE", "SU", "MO", "ME", "VE", "MA", "JU", "SA"]
CLASSICAL = ["SU", "MO", "ME", "VE", "MA", "JU", "SA"]

def _sign_index(sign: str) -> int:
    return ZODIAC_SIGNS.index(sign)


def _house_for_sign(asc_sign: str, target_sign: str) -> int:
    return (_sign_index(target_sign) - _sign_index(asc_sign)) % 12 + 1


def _deg_in_sign(position_degrees: float) -> float:
    return float(position_degrees) % 30


def _sidereal_lon(data: dict) -> float | None:
    """Kanoniczna długość do progów (S11 / Chart_Data_Contract §3).

    Preferuje `position_degrees_exact`; fallback na zaokrąglone `position_degrees`
    dla starszych zrzutów bez pola exact.
    """
    if data is None:
        return None
    exact = data.get("position_degrees_exact")
    if exact is not None:
        return float(exact)
    rounded = data.get("position_degrees")
    if rounded is not None:
        return float(rounded)
    return None


def _parse_dm(dm: str) -> float | None:
    """'6°01'' → 6.016..."""
    if not dm:
        return None
    try:
        clean = dm.replace("′", "'").replace("’", "'")
        if "°" not in clean:
            return float(clean)
        d_part, rest = clean.split("°", 1)
        m_part = rest.replace("'", "").strip()
        return int(d_part) + int(m_part) / 60.0
    except Exception:
        return None


def chart_dict_from_detailed(detailed: dict) -> dict:
    """AS/planety → {code: {zodiac_sign, house, ...}}."""
    out = {}
    for code, data in detailed.items():
        if not isinstance(data, dict) or "zodiac_sign" not in data:
            continue
        out[code] = {
            "zodiac_sign": data["zodiac_sign"],
            "house": data.get("house"),
            "position_degrees": data.get("position_degrees"),
            "position_degrees_exact": data.get("position_degrees_exact"),
            "position_within_sign_degrees": data.get("position_within_sign_degrees"),
            "nakshatra": data.get("nakshatra"),
            "motion": data.get("motion"),
            # DEC-008: niepewność definicyjna węzła; konsument = sufit C003 (DEC-013)
            "node_ambiguous": bool(data.get("node_ambiguous")),
            "node_alt_sign": data.get("node_alt_sign"),
            "node_alt_house": data.get("node_alt_house"),
        }
    return out


def house_lords_rows(chart: dict) -> list[dict]:
    asc = chart["AS"]["zodiac_sign"]
    rows = []
    for h in range(1, 13):
        sign = ZODIAC_SIGNS[(_sign_index(asc) + h - 1) % 12]
        lord = SIGN_LORD[sign]
        lord_pos = chart.get(lord, {})
        rows.append(
            {
                "house": h,
                "sign": sign,
                "lord": lord,
                "lord_name": PLANET_NAMES_PL[lord],
                "lord_house": lord_pos.get("house"),
                "lord_sign": lord_pos.get("zodiac_sign"),
            }
        )
    return rows



def rules_houses(planet: str, chart: dict) -> list[int]:
    if planet not in CLASSICAL:
        return []
    asc = chart["AS"]["zodiac_sign"]
    ruled = []
    for sign in OWN_SIGNS.get(planet, []):
        ruled.append(_house_for_sign(asc, sign))
    return sorted(set(ruled))


def sign_dignity(planet: str, sign: str, deg_in_sign: float | None = None) -> str:
    """Jedna etykieta godności znakowej (bez tymczasowych przyjaciół)."""
    if planet in ("RA", "KE"):
        return "węzeł (bez klasycznej godności znakowej)"

    tags = []
    if planet in MOOLATRIKONA and deg_in_sign is not None:
        mt_sign, lo, hi = MOOLATRIKONA[planet]
        if sign == mt_sign and lo <= deg_in_sign < hi:
            tags.append("mūlatrikoṇa")

    if EXALTATION.get(planet) == sign:
        tags.append("egzaltacja")
    elif DEBILITATION.get(planet) == sign:
        tags.append("upadek")
    elif sign in OWN_SIGNS.get(planet, []):
        tags.append("własny znak")
    else:
        # natural friend/enemy via dispositor of the sign
        lord = SIGN_LORD[sign]
        if lord == planet:
            tags.append("własny znak")
        elif lord in NATURAL_FRIENDS.get(planet, set()):
            tags.append("znak przyjacielski")
        elif lord in NATURAL_ENEMIES.get(planet, set()):
            tags.append("znak wrogi")
        else:
            tags.append("neutralna")

    return " + ".join(tags) if tags else "neutralna"


def _contact_conjunct_or_aspect(chart: dict, fallen: str, rescuer: str) -> str | None:
    """
    Ratunek: koniunkcja (ten sam znak) LUB aspekt Parāśari **od** kancelatora **na** upadłą.
    (MA: 4/7/8, JU: 5/7/9, SA: 3/7/10, pozostałe: 7.)
    """
    if fallen not in chart or rescuer not in chart or fallen == rescuer:
        return None
    if chart[fallen]["zodiac_sign"] == chart[rescuer]["zodiac_sign"]:
        return "koniunkcja"
    h_f = chart[fallen].get("house")
    h_r = chart[rescuer].get("house")
    if h_f is None or h_r is None:
        return None
    h_f, h_r = int(h_f), int(h_r)
    for offset in ASPECT_HOUSES.get(rescuer, (7,)):
        target = (h_r + offset - 2) % 12 + 1
        if target == h_f:
            return f"aspekt_{offset}"
    return None


def _contact_conjunct_or_7(chart: dict, a: str, b: str) -> str | None:
    """Alias wsteczny → pełny kontakt ratunkowy (a=upadła, b=kancelator)."""
    return _contact_conjunct_or_aspect(chart, a, b)

def _parivartana_pairs(chart: dict) -> list[tuple[str, str]]:
    pairs = []
    codes = [c for c in CLASSICAL if c in chart]
    for i, a in enumerate(codes):
        for b in codes[i + 1 :]:
            sa, sb = chart[a]["zodiac_sign"], chart[b]["zodiac_sign"]
            if SIGN_LORD.get(sa) == b and SIGN_LORD.get(sb) == a:
                pairs.append((a, b))
    return pairs


def detect_nica_bhanga_for_planet(
    planet: str,
    chart: dict,
    d9_chart: dict | None = None,
) -> list[dict]:
    """
    Lista kancelacji upadku dla planety.
    Zwraca [] jeśli nie ma upadku.
    """
    if planet not in CLASSICAL or planet not in chart:
        return []
    sign = chart[planet]["zodiac_sign"]
    if DEBILITATION.get(planet) != sign:
        return []

    hits: list[dict] = []
    deb_lord = SIGN_LORD[sign]
    exalt_sign = EXALTATION.get(planet)
    exalt_lord = SIGN_LORD.get(exalt_sign) if exalt_sign else None
    exalt_in_deb_sign = EXALTED_IN_SIGN.get(sign)  # kto egzaltuje W znaku upadku

    # 1) parivartana z udziałem upadłej
    for a, b in _parivartana_pairs(chart):
        if planet in (a, b):
            other = b if planet == a else a
            hits.append(
                {
                    "typ": "parivartana_nica",
                    "przez": other,
                    "kontakt": "wymiana_znaków",
                    "siła": NICA_STRENGTH["parivartana_nica"],
                }
            )

    # 2) exalt_lord — władca znaku egzaltacji upadłej (np. JU dla VE w Pannie)
    if exalt_lord and exalt_lord in chart:
        kontakt = _contact_conjunct_or_7(chart, planet, exalt_lord)
        if kontakt:
            hits.append(
                {
                    "typ": "exalt_lord",
                    "przez": exalt_lord,
                    "kontakt": kontakt,
                    "siła": NICA_STRENGTH["exalt_lord"],
                    "opis": (
                        f"władca znaku egzaltacji ({exalt_sign}) upadłej planety"
                    ),
                }
            )

    # 3) sign_lord — władca znaku upadku
    if deb_lord and deb_lord != planet and deb_lord in chart:
        kontakt = _contact_conjunct_or_7(chart, planet, deb_lord)
        if kontakt:
            hits.append(
                {
                    "typ": "sign_lord",
                    "przez": deb_lord,
                    "kontakt": kontakt,
                    "siła": NICA_STRENGTH["sign_lord"],
                }
            )

    # 4) exalt_planet — kto egzaltuje w znaku upadku (np. SA w Wadze przy SU)
    if exalt_in_deb_sign and exalt_in_deb_sign != planet and exalt_in_deb_sign in chart:
        kontakt = _contact_conjunct_or_7(chart, planet, exalt_in_deb_sign)
        if kontakt:
            hits.append(
                {
                    "typ": "exalt_planet",
                    "przez": exalt_in_deb_sign,
                    "kontakt": kontakt,
                    "siła": NICA_STRENGTH["exalt_planet"],
                }
            )

    # 5) kendra_lord — władca znaku upadku w kendrze od Lagna lub MO
    if deb_lord and deb_lord in chart:
        h = chart[deb_lord].get("house")
        mo_h = chart.get("MO", {}).get("house")
        if h is not None and int(h) in KENDRA:
            hits.append(
                {
                    "typ": "kendra_lord",
                    "przez": deb_lord,
                    "kontakt": f"władca_upadku_w_kendrze_od_Lagna ({h}.)",
                    "siła": NICA_STRENGTH["kendra_lord"],
                }
            )
        elif mo_h is not None and h is not None:
            # kendra from Moon: house relative
            rel = (int(h) - int(mo_h)) % 12 + 1
            if rel in KENDRA:
                hits.append(
                    {
                        "typ": "kendra_lord",
                        "przez": deb_lord,
                        "kontakt": f"władca_upadku_w_kendrze_od_MO (rel={rel})",
                        "siła": NICA_STRENGTH["kendra_lord"],
                    }
                )

    # 6–7) D9
    if d9_chart and planet in d9_chart:
        d9_sign = d9_chart[planet]["zodiac_sign"]
        if EXALTATION.get(planet) == d9_sign:
            hits.append(
                {
                    "typ": "d9_exalt",
                    "przez": "D9",
                    "kontakt": f"egzaltacja_w_D9 ({d9_sign})",
                    "siła": NICA_STRENGTH["d9_exalt"],
                }
            )
        if d9_sign == sign:
            hits.append(
                {
                    "typ": "vargottama_nica",
                    "przez": "D9",
                    "kontakt": "Vargottama_w_upadku",
                    "siła": NICA_STRENGTH["vargottama_nica"],
                }
            )

    # dedupe by typ+przez
    seen = set()
    uniq = []
    for h in hits:
        key = (h["typ"], h["przez"], h.get("kontakt"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)
    return uniq



def angular_sep(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def conjunctions_d1(detailed: dict) -> list[dict]:
    """Pary planet w tym samym znaku + orb kątowy."""
    bodies = []
    for code in CLASSICAL + ["RA", "KE"]:
        data = detailed.get(code)
        lon = _sidereal_lon(data) if data else None
        if lon is None:
            continue
        bodies.append(
            (
                code,
                lon,
                data["zodiac_sign"],
            )
        )
    pairs = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            c1, lon1, s1 = bodies[i]
            c2, lon2, s2 = bodies[j]
            if s1 != s2:
                continue
            orb = angular_sep(lon1, lon2)
            if orb < 1.0:
                label = "bardzo ścisła"
            elif orb < 5.0:
                label = "ścisła"
            elif orb < 10.0:
                label = "średnia"
            else:
                label = "wspólny znak (szeroka)"
            pairs.append(
                {
                    "a": c1,
                    "b": c2,
                    "sign": s1,
                    "orb": orb,
                    "label": label,
                }
            )
    pairs.sort(key=lambda x: x["orb"])
    return pairs



ASPECT_HOUSES = {
    "SU": (7,),
    "MO": (7,),
    "ME": (7,),
    "VE": (7,),
    "MA": (4, 7, 8),
    "JU": (5, 7, 9),
    "SA": (3, 7, 10),
}
# Rahu/Ketu: wyłączone w tej konwencji Mapa Roku

# Klasyczne orby spalenia — profil operacyjny DEC-011 (nie kotwica BPHS).
# KS-101.1 R048: threshold = unresolved. Wartości = powszechne softy; status [D · encodable].
COMBUSTION_ORB = {
    "MO": 12.0,
    "MA": 17.0,
    "ME": 14.0,
    "JU": 11.0,
    "VE": 10.0,
    "SA": 15.0,
}
KAZIMI_ORB_DEG = 17.0 / 60.0  # 0°17′ — DEC-011, warstwa T / KONSTYTUCJA §3
YUDDHA_ORB_DEG = 1.0  # próg detekcji [U]; KS-101.1 R050 — DEC-011
YUDDHA_PLANETS = ("MA", "ME", "JU", "VE", "SA")  # bez SU/MO/RA/KE
UPACHAYA = {3, 6, 10, 11}
KENDRA = {1, 4, 7, 10}
TRIKONA = {5, 9}  # KS-101.3; Lagna = kendra, nie trikona

def aspects_for_chart(chart: dict) -> list[dict]:
    """Lista aspektów: kto → jakie domy + kogo trafia."""
    out = []
    for code in ("SU", "MO", "ME", "VE", "MA", "JU", "SA"):
        data = chart.get(code)
        if not data or data.get("house") is None:
            continue
        from_house = int(data["house"])
        targets = []
        for offset in ASPECT_HOUSES[code]:
            # N-ty dom od planety w domu H: (H + N - 2) % 12 + 1
            th = (from_house + offset - 2) % 12 + 1
            occupants = [
                c
                for c in PLANETS_ONLY
                if c != code and chart.get(c) and int(chart[c].get("house") or 0) == th
            ]
            targets.append({"house": th, "offset": offset, "occupants": occupants})
        out.append(
            {
                "planet": code,
                "from_house": from_house,
                "from_sign": data["zodiac_sign"],
                "targets": targets,
            }
        )
    return out



def combustion_rows(detailed: dict) -> list[dict]:
    sun = detailed.get("SU")
    sun_lon = _sidereal_lon(sun) if sun else None
    if sun_lon is None:
        return []
    rows = []
    for code in ("MO", "MA", "ME", "JU", "VE", "SA"):
        data = detailed.get(code)
        lon = _sidereal_lon(data) if data else None
        if lon is None:
            continue
        orb = angular_sep(sun_lon, lon)
        limit = COMBUSTION_ORB[code]
        kazimi = orb <= KAZIMI_ORB_DEG
        rows.append(
            {
                "planet": code,
                "orb": orb,
                "limit": limit,
                "combust": orb <= limit,
                "kazimi": kazimi,
                "motion": data.get("motion"),
            }
        )
    rows.sort(key=lambda x: x["orb"])
    return rows



def graha_yuddha_rows(detailed: dict) -> list[dict]:
    bodies = []
    for code in YUDDHA_PLANETS:
        data = detailed.get(code)
        lon = _sidereal_lon(data) if data else None
        if lon is None:
            continue
        bodies.append((code, lon, lon % 30, int(lon // 30)))
    pairs = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            c1, lon1, d1, s1 = bodies[i]
            c2, lon2, d2, s2 = bodies[j]
            if s1 != s2:
                continue  # klasycznie: ta sama rāśi
            orb = angular_sep(lon1, lon2)
            if orb > YUDDHA_ORB_DEG:
                continue
            # Zwycięzca: konwencja robocza DEC-011 = niższy stopień w znaku.
            # KS-101.1 R049: kanon = bardziej północna + jaśniejsze promienie —
            # wymaga szerokości ekliptycznej i jasności; brak w ChartData → profil D.
            if d1 <= d2:
                lower, higher = c1, c2
            else:
                lower, higher = c2, c1
            pairs.append(
                {
                    "a": c1,
                    "b": c2,
                    "orb": orb,
                    "lower_degree": lower,
                    "higher_degree": higher,
                    "winner": lower,  # DEC-011 — nie KS-101.1 R049
                    "loser": higher,
                }
            )
    pairs.sort(key=lambda x: x["orb"])
    return pairs
