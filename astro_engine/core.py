"""Independent astronomical calculations extracted from the original ChartData core.

No client registry, file lookup, report templates, printing or network I/O.
All positions use the inherited Lahiri / true-node calculation profile.
"""

import math
from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

import pytz
import swisseph as swe


HORA_METHOD = "sunrise_to_sunrise_24_equal_v1"


def _signed_angle_diff_deg(a: float, b: float) -> float:
    """
    Różnica kątowa z podpisem w przedziale (-180, +180].
    Przydatne, gdy porównujemy kąty 0..360 (np. test na przekroczenie celu).
    """
    return (a - b + 180.0) % 360.0 - 180.0


def _bisect_root_scalar(
    f,
    a: float,
    b: float,
    time_tol_sec: float = 0.1,
    max_iter: int = 100
) -> float:
    """
    Klasyczna bisekcja z dokładnością czasową w sekundach.
    Zakładamy, że na przedziale [a, b] jest zero (po wcześniejszym bracketingu).
    a, b to czasy w dniach juliańskich (JD), więc tolerancję sekundy
    przeliczamy na część doby.

    Zwraca punkt ~korzenia (float JD).
    """
    for _ in range(max_iter):
        m = 0.5 * (a + b)
        fm = f(m)

        # kryterium dokładności: długość przedziału w sekundach
        if (b - a) * 86400.0 < time_tol_sec or abs(fm) < 1e-12:
            return m

        fa = f(a)
        if fa * fm <= 0.0:
            b = m
        else:
            a = m

    # Jeżeli nie zbiegnie w max_iter, oddaj środek
    return 0.5 * (a + b)


def _bracket_root_scalar(
    f: Callable[[float], float],
    a: float,
    b: float,
    step: float,
    guard180: bool = False
) -> Optional[Tuple[float, float]]:
    """
    Skanuje na [a, b] co `step` i zwraca przedział [x0, x1],
    w którym jest zero (zmiana znaku lub dokładne 0).
    Jeśli `guard180=True`, ignoruje “fałszywe” przejścia przez ±180°
    (gdy |f| jest bardzo duże po obu stronach).
    """
    fa = f(a)
    x = a + step
    while x <= b + 1e-12:
        fx = f(x)

        # klasyczny test “zero w przedziale”:
        crossed = (fa == 0.0) or (fa * fx <= 0.0)

        if crossed:
            if guard180 and (abs(fa) > 170.0 and abs(fx) > 170.0):
                # skok przez ±180° – nie traktuj jako prawdziwego zera
                pass
            else:
                return (x - step, x)

        fa = fx
        x += step

    return None


def _ensure_iana_tz(name: str, lat: float, lon: float) -> str:
    """Validate an explicit timezone, without geographic guessing or fallback."""
    if not isinstance(name, str) or not name:
        raise ValueError("An explicit IANA timezone or UTC is required.")
    pytz.timezone(name)
    return name


_TITHI_EPHE_FLAGS = swe.FLG_SWIEPH | swe.FLG_TRUEPOS


def _sun_sidereal_long_deg(jd):
    sun_long = swe.calc_ut(jd, swe.SUN, _TITHI_EPHE_FLAGS)[0][0]
    ay = swe.get_ayanamsa_ut(jd)
    return (sun_long - ay) % 360.0


def _tithi_angle_deg(jd):
    # JHora's displayed tithi balance matches Swiss Ephemeris TRUEPOS. Keep
    # this profile isolated from the ordinary planetary-position pipeline.
    moon_long = swe.calc_ut(jd, swe.MOON, _TITHI_EPHE_FLAGS)[0][0]
    sun_long  = swe.calc_ut(jd, swe.SUN, _TITHI_EPHE_FLAGS)[0][0]
    ay        = swe.get_ayanamsa_ut(jd)
    moon_sid  = (moon_long - ay) % 360.0
    sun_sid   = (sun_long  - ay) % 360.0
    return (moon_sid - sun_sid) % 360.0


def _find_ingress_egress(year, natal_sign_index):
    jd_start = swe.julday(year,     1, 1, 0.0)
    jd_end   = swe.julday(year + 1, 1, 1, 0.0)
    k = natal_sign_index

    target_ing = (k * 30.0) % 360.0
    jd_ingress = root_for_target(target_ing, jd_start, jd_end)

    target_egr = ((k + 1) * 30.0) % 360.0
    # One solar sign may extend past 1 January; 40 days bounds that sign.
    jd_egress = root_for_target(target_egr, jd_ingress + 0.05, jd_ingress + 40.0)

    return jd_ingress, jd_egress


def _crossed_target(prev, cur, target):
    """
    Czy od prev->cur przecięliśmy 'target' na okręgu 0..360?
    Obsługuje zawijanie przez 360->0.
    """
    prev %= 360.0
    cur  %= 360.0
    target %= 360.0
    if prev <= cur:
        return prev <= target <= cur
    # zawinięcie (np. 359° -> 2°)
    return (target >= prev) or (target <= cur)


def root_for_target(target_deg, search_start_jd, jd_end):
    """
    Szuka JD, w którym sun_sidereal_long przechodzi przez target_deg.
    Skan 1h + bisekcja z kryterium 'crossed_target'.
    """
    step = 1.0/24.0  # 1 godzina; możesz zacząć od 6h i potem doprecyzować
    t0 = search_start_jd
    prev = _sun_sidereal_long_deg(t0)     # <- poprawna nazwa
    t = t0 + step
    while t <= jd_end + 1e-12:
        cur = _sun_sidereal_long_deg(t)
        if _crossed_target(prev, cur, target_deg):
            # bisekcja na [t-step, t], kryterium = crossed_target
            a, b = t - step, t
            for _ in range(80):
                m = 0.5*(a+b)
                am = _sun_sidereal_long_deg(a)
                mm = _sun_sidereal_long_deg(m)
                if _crossed_target(am, mm, target_deg):
                    b = m
                else:
                    a = m
                if (b-a)*86400.0 < 0.1:
                    break
            return 0.5*(a+b)
        t0, prev = t, cur
        t += step
    raise RuntimeError("Nie znaleziono przecięcia Sun_sid == target")


class ChartData:
    def __init__(self, full_name: str, date: str, real_time: str, latitude=None, longitude=None, city=None, timezone: str = "UTC", silent_mode=True):
        self.full_name = full_name
        self.date = date
        self.real_time = real_time
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.timezone = timezone
        self.detailed_chart_data = {}
        self.silent_mode = silent_mode
        self.birth_year = int(self.date.split('-')[0])

        if latitude is None or longitude is None:
            raise ValueError("Explicit latitude and longitude are required; no city lookup is performed.")
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        if not math.isfinite(self.latitude) or not -90.0 <= self.latitude <= 90.0:
            raise ValueError("Latitude must be finite and within [-90, 90].")
        if not math.isfinite(self.longitude) or not -180.0 <= self.longitude <= 180.0:
            raise ValueError("Longitude must be finite and within [-180, 180].")
        self.city_found = None
        _ensure_iana_tz(timezone, self.latitude, self.longitude)

        # Constants for planets
        self.PLANETS = {
            'SU': swe.SUN,
            'MO': swe.MOON,
            'ME': swe.MERCURY,
            'VE': swe.VENUS,
            'MA': swe.MARS,
            'JU': swe.JUPITER,
            'SA': swe.SATURN,
        }

       
        self.PLANET_NAMES = {
            'RA': 'Rahu',
            'KE': 'Ketu',          
            'SU': 'Słońce',
            'MO': 'Księżyc',
            'ME': 'Merkury',
            'VE': 'Wenus',
            'MA': 'Mars',
            'JU': 'Jowisz',
            'SA': 'Saturn'
        }

        self.ZODIAC_SIGNS = [
            "Baran", "Byk", "Bliźnięta", "Rak",
            "Lew", "Panna", "Waga", "Skorpion",
            "Strzelec", "Koziorożec", "Wodnik", "Ryby"
        ]


        self.WEEKDAY_LORDS = {0:'SU', 1:'MO', 2:'MA', 3:'ME', 4:'JU', 5:'VE', 6:'SA'}

        self.HORA_LORD_SEQUENCE = ['SU', 'VE', 'ME', 'MO', 'SA', 'JU', 'MA']


        self.NAKSHATRAS = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha",
            "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
            "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
            "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
            "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
        ]

        self.AS_LORD = {
            "Baran": 'MA', 
            "Byk": 'VE', 
            "Bliźnięta": 'ME',
            "Rak": 'MO',
            "Lew": 'SU', 
            "Panna": 'ME', 
            "Waga": 'VE', 
            "Skorpion": 'MA',
            "Strzelec": 'JU', 
            "Koziorożec": 'SA', 
            "Wodnik": 'SA', 
            "Ryby": 'JU'
        }

        self.planets_as_sign_lords = {
            'Słońce': ['Lew',''],
            'Księżyc': ['Rak',''],
            'Merkury': ['Bliźnięta', 'Panna'],
            'Wenus': ['Byk', 'Waga'],
            'Mars': ['Baran', 'Skorpion'],
            'Jowisz': ['Strzelec', 'Ryby'],
            'Saturn': ['Koziorożec', 'Wodnik'],
            # Rāhu/Ketu: NIE w canonical_sign_lords (KS-101.2 R047).
        }


        self.TITHI_BASE = [
            "Pratipada","Dwitiya","Tritiya","Chaturthi","Panchami",
            "Shashthi","Saptami","Ashtami","Navami","Dashami",
            "Ekadashi","Dwadashi","Trayodashi","Chaturdashi","Purnima"  # 15
]

        self.DAGDHA_BY_TITHI_1_15 = {
            1:[6,9], 2:[8,11], 3:[4,9], 4:[1,10], 5:[2,5],
            6:[0,4], 7:[3,8], 8:[2,5], 9:[4,7], 10:[4,7],
            11:[8,11], 12:[6,9], 13:[1,4], 14:[2,5,8,11], 15:[]
        }

        self.ASHTOTTARI_SEQ_BPHS = ['SU', 'MO', 'MA', 'ME', 'SA', 'JU', 'RA', 'VE']
        self.ASHTOTTARI_YEARS_BPHS = {
            'SU': 6, 'MO': 15, 'MA': 8, 'ME': 17, 
            'SA': 10, 'JU': 19, 'RA': 12, 'VE': 21
        }
        self.ASHTOTTARI_TOTAL_YEARS = 108
        self.TITHI_RULERS = {
            1: 'SU', 2: 'MO', 3: 'MA', 4: 'ME', 5: 'JU', 6: 'VE', 7: 'SA', 8: 'RA',
            9: 'SU', 10: 'MO', 11: 'MA', 12: 'ME', 13: 'JU', 14: 'VE', 15: 'SA',
            16: 'SU', 17: 'MO', 18: 'MA', 19: 'ME', 20: 'JU', 21: 'VE', 22: 'SA', 23: 'RA',
            24: 'SU', 25: 'MO', 26: 'MA', 27: 'ME', 28: 'JU', 29: 'VE', 30: 'RA'
        }


        self.birth_time_for_calc()
        self.get_chart_data()
        # Separate D2 variants; the historical Hora alias remains Parāśara.
        self.hora_chart_data = self.calculate_hora_chart()  # alias = Parāśara
        self.hora_parashara_chart_data = self.hora_chart_data
        self.hora_parivritti_chart_data = self.calculate_hora_parivritti_chart()
        self.hora_kashinatha_chart_data = self.calculate_hora_kashinatha_chart()
        self.drekana_chart_data = self.calculate_drekana_chart()
        self.chaturthamsa_chart_data = self.calculate_chaturthamsa_chart()
        # D5/D6 poza rdzeniem (DEC-002) — wołaj calculate_panchamsa_chart() /
        # calculate_shashtamsa_chart() jawnie, jeśli potrzebne do pracy eksperymentalnej.
        self.saptamsa_chart_data = self.calculate_saptamsa_chart()
        self.ashtamsa_chart_data = self.calculate_ashtamsa_chart()
        self.navamsa_chart_data = self.calculate_navamsa_chart()
        self.dasamsa_chart_data = self.calculate_dasamsa_chart()
        self.ekadasamsa_iyer_chart_data = self.calculate_ekadasamsa_iyer_chart()
        self.dwadasamsa_chart_data = self.calculate_dwadasamsa_chart()
        self.shodasamsa_chart_data = self.calculate_shodasamsa_chart()
        self.vimsamsa_chart_data = self.calculate_vimsamsa_chart()
        self.chaturvimsamsa_chart_data = self.calculate_chaturvimsamsa_chart()
        self.saptavimsamsa_chart_data = self.calculate_saptavimsamsa_chart()
        self.trimsamsa_chart_data = self.calculate_trimsamsa_chart()
        self.khavedamsa_chart_data = self.calculate_khavedamsa_chart()
        self.akshavedamsa_chart_data = self.calculate_akshavedamsa_chart()
        self.shashtiamsa_chart_data = self.calculate_shashtiamsa_chart()

    def _tithi_ruler_from_index(self, tithi_idx_1_30: int) -> str:
        """Władca tithi 1..30 — kanoniczna mapa `TITHI_RULERS` (profil BPHS 8 planet).

        Jedyna definicja w klasie (audyt K4). Nie używać niezdefiniowanych
        `TITHI_RULER_1_14` / `ASHTOTTARI_SEQ` / `TITHI_TO_ASHTOTTARI_START`.
        """
        idx = int(tithi_idx_1_30)
        if idx not in self.TITHI_RULERS:
            raise ValueError(f"tithi index poza 1..30: {tithi_idx_1_30}")
        return self.TITHI_RULERS[idx]


    def localize_datetime(self, date_str, time_str, timezone_str):
        naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        local_tz = pytz.timezone(timezone_str)
        return local_tz.localize(naive_dt, is_dst=None)


    def format_decimal_to_dms(self, decimal, is_lat=True):
        degrees = int(abs(decimal))
        minutes = int(round((abs(decimal) - degrees) * 60))
        direction = ''
        if is_lat:
            direction = 'N' if decimal >= 0 else 'S'
        else:
            direction = 'E' if decimal >= 0 else 'W'
        return f"{degrees}°{minutes:02d}′ {direction}"


    def get_tithi_number(jd):
        """
        Oblicza numer tithi (1–30) na podstawie różnicy długości ekliptycznych Księżyca i Słońca.
        """
        moon_long = swe.calc_ut(jd, swe.MOON)[0][0]
        sun_long = swe.calc_ut(jd, swe.SUN)[0][0]
        ayanamsa = swe.get_ayanamsa_ut(jd)

        # Syderyczne pozycje
        moon_sidereal = (moon_long - ayanamsa) % 360
        sun_sidereal = (sun_long - ayanamsa) % 360

        angle = (moon_sidereal - sun_sidereal) % 360
        tithi_number = int(angle // 12) + 1  # Każde 12° to jedno tithi
        return tithi_number


    def birth_time_for_calc(self, return_datetime=False):
        local = pytz.timezone(self.timezone)
        local_time = datetime.strptime(f"{self.date} {self.real_time}", "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(local_time, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)

        self.utc_date = utc_dt.strftime("%Y-%m-%d")
        self.calc_time = utc_dt.strftime("%H:%M:%S")

        if return_datetime:
            return local_dt
        

    def get_zodiac_sign(self, degree):
        self.index = int(degree // 30)  # Each zodiac sign corresponds to 30 degrees
        return self.ZODIAC_SIGNS[self.index]


    def get_nakshatra(self, degree):
        self.index = int(degree // (360 / len(self.NAKSHATRAS)))  # Each nakshatra corresponds to 360/27 degrees
        return self.NAKSHATRAS[self.index]


    def get_node_details(self, name, position):
        zodiac_index = int(position // 30)
        position_within_sign = round(position % 30, 2)  # Zaokrąglenie pozycji w obrębie znaku
        zodiac_sign = self.ZODIAC_SIGNS[zodiac_index]
        nakshatra = self.get_nakshatra(position)
        house_number = (zodiac_index - self.ascendant_zodiac_index) % 12 + 1

        return {
            name: {
                'house': house_number,
                'position_degrees': round(position, 2),
                'position_within_sign_degrees': position_within_sign,  # Zaokrąglona wartość
                'zodiac_sign': zodiac_sign,
                'nakshatra': nakshatra
            }
        }
    

    def get_complete_astro_details(self):
            def format_degrees_to_dm(degrees):
                d = int(degrees)
                m = int(round((degrees - d) * 60, 0))
                if m == 60:
                    d += 1
                    m = 0
                return f"{d}°{m:02d}'"

            swe.set_sid_mode(swe.SIDM_LAHIRI)

            year, month, day = map(int, self.utc_date.split('-'))
            hour, minute, second = map(int, self.calc_time.split(':'))
            decimal_hour = hour + (minute + second / 60.0) / 60.0
            julian_day_corrected = swe.julday(year, month, day, decimal_hour)
            # CDC-006 / Chart_Data_Contract: kanoniczny moment wykresu (JD UT).
            # Przy TP `_compute_detailed_chart_at_jd` robi snapshot i przywraca
            # natalne `jd_ut` po liczeniu — patrz restore w finally.
            self.jd_ut = julian_day_corrected

            ayanamsa = swe.get_ayanamsa_ut(julian_day_corrected)
            
            # ... (Twoja sekcja 'print' pozostaje bez zmian) ...

            houses = swe.houses(julian_day_corrected, self.latitude, self.longitude, b'P')
            self.ascendant_position = houses[0][0]
            self.ascendant_adjusted_position = (self.ascendant_position - ayanamsa) % 360
            self.ascendant_degree = self.ascendant_adjusted_position % 30
            self.ascendant_zodiac_index = int(self.ascendant_adjusted_position // 30)
            self.ascendant_zodiac_sign = self.ZODIAC_SIGNS[self.ascendant_zodiac_index]
            self.ascendant_nakshatra = self.get_nakshatra(self.ascendant_adjusted_position)

            ascendant_degree_rounded = self.ascendant_adjusted_position % 30
            self.detailed_chart_data['AS'] = {
                'house': 1,
                'position_degrees': round(self.ascendant_adjusted_position, 2),
                # Vargi liczą z tego pola — zaokrąglenie do 0.01° przesuwa granice w D45/D60.
                'position_degrees_exact': self.ascendant_adjusted_position,
                'position_within_sign_degrees': format_degrees_to_dm(ascendant_degree_rounded),
                'zodiac_sign': self.ascendant_zodiac_sign,
                'nakshatra': self.ascendant_nakshatra
            }

            # --- POCZĄTEK ZMIANY: Poprawiona sekcja Rahu i Ketu ---
            # Obliczanie Rahu i Ketu
            rahu_exact = (swe.calc_ut(julian_day_corrected, swe.TRUE_NODE, swe.FLG_SWIEPH)[0][0] - ayanamsa) % 360
            ketu_exact = (rahu_exact + 180) % 360
            self.rahu_position = round(rahu_exact, 2)
            self.ketu_position = round(ketu_exact, 2)

            # Węzeł średni — wyłącznie jako wariant kontrolny (DEC-008). Kanoniczne
            # wejście to węzeł prawdziwy; średni służy do wykrycia varg, w których
            # wybór definicji węzła zmienia znak. Rozpiętość dochodzi do 1.7°, więc
            # w D24/D40/D45/D60 przekracza szerokość części.
            rahu_mean_exact = (swe.calc_ut(julian_day_corrected, swe.MEAN_NODE, swe.FLG_SWIEPH)[0][0] - ayanamsa) % 360
            ketu_mean_exact = (rahu_mean_exact + 180) % 360

            # Rahu i Ketu są z definicji zawsze w retrogradacji
            rahu_ketu_motion = 'R'

            # Dane dla Rahu
            zodiac_index_rahu = int(rahu_exact // 30)
            zodiac_position_rahu = rahu_exact % 30
            zodiac_sign_rahu = self.ZODIAC_SIGNS[zodiac_index_rahu]
            nakshatra_rahu = self.get_nakshatra(rahu_exact)
            house_number_rahu = (zodiac_index_rahu - self.ascendant_zodiac_index) % 12 + 1
            self.detailed_chart_data['RA'] = {
                'house': house_number_rahu,
                'position_degrees': self.rahu_position,
                'position_degrees_exact': rahu_exact,
                'position_degrees_mean_node': rahu_mean_exact,
                'position_within_sign_degrees': format_degrees_to_dm(zodiac_position_rahu),
                'zodiac_sign': zodiac_sign_rahu,
                'nakshatra': nakshatra_rahu,
                'motion': rahu_ketu_motion # Dodano status ruchu
            }

            # Dane dla Ketu
            zodiac_index_ketu = int(ketu_exact // 30)
            zodiac_position_ketu = ketu_exact % 30
            zodiac_sign_ketu = self.ZODIAC_SIGNS[zodiac_index_ketu]
            nakshatra_ketu = self.get_nakshatra(ketu_exact)
            house_number_ketu = (zodiac_index_ketu - self.ascendant_zodiac_index) % 12 + 1
            self.detailed_chart_data['KE'] = {
                'house': house_number_ketu,
                'position_degrees': self.ketu_position,
                'position_degrees_exact': ketu_exact,
                'position_degrees_mean_node': ketu_mean_exact,
                'position_within_sign_degrees': format_degrees_to_dm(zodiac_position_ketu),
                'zodiac_sign': zodiac_sign_ketu,
                'nakshatra': nakshatra_ketu,
                'motion': rahu_ketu_motion # Dodano status ruchu
            }
            # --- KONIEC ZMIANY ---

            for planet_name, planet_code in self.PLANETS.items():
                # Pomijamy Rahu i Ketu w pętli, bo zostały już obliczone osobno
                if planet_name in ['RA', 'KE']:
                    continue

                planet_position = swe.calc_ut(julian_day_corrected, planet_code, swe.FLG_SWIEPH)[0][0]
                planet_adjusted_position = (planet_position - ayanamsa) % 360
                zodiac_index = int(planet_adjusted_position // 30)
                zodiac_position = planet_adjusted_position % 30
                zodiac_sign = self.ZODIAC_SIGNS[zodiac_index]
                nakshatra = self.get_nakshatra(planet_adjusted_position)
                house_number = (zodiac_index - self.ascendant_zodiac_index) % 12 + 1
                motion_status = self.get_planet_motion(julian_day_corrected, planet_code)

                self.detailed_chart_data[planet_name] = {
                    'house': house_number,
                    'position_degrees': round(planet_adjusted_position, 2),
                    'position_degrees_exact': planet_adjusted_position,
                    'position_within_sign_degrees': format_degrees_to_dm(zodiac_position),
                    'zodiac_sign': zodiac_sign,
                    'nakshatra': nakshatra,
                    'motion': motion_status
                }

            self.birth_date = datetime.strptime(self.date, "%Y-%m-%d")


    def calculate_hora_position(self, degree, rasi_sign_index, ascendant_hora_index):
        """
        Oblicza pozycję w Hora (D2) dla danego stopnia w Rasi, uwzględniając męskie i żeńskie znaki.
        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_hora_index: Indeks znaku Ascendentu w Hora (0–11).
        :return: Słownik z pozycją w Hora (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Numer połowy znaku. `int(x/w)` zamiast `<= 15`: punkt dokładnie graniczny
        # należy do części wyższej, spójnie z pozostałymi 15 vargami (KS100-R050).
        part = min(int(degree_in_sign // 15.0), 1)
        # Znak nieparzysty (indeks parzysty): Sūrya Horā → Lew, potem Candra Horā → Rak.
        # Znak parzysty: kolejność odwrócona.
        if rasi_sign_index % 2 == 0:
            hora_sign = "Lew" if part == 0 else "Rak"
        else:
            hora_sign = "Rak" if part == 0 else "Lew"
        # Obliczenie numeru domu w Hora
        hora_sign_index = self.ZODIAC_SIGNS.index(hora_sign)
        house_number = (hora_sign_index - ascendant_hora_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': hora_sign,
            'house': house_number
        }


    def calculate_hora_chart(self):
        """D2 Hora — metoda Parāśara (tylko Rak/Lew)."""
        return self._build_divisional_chart(self.calculate_hora_position)

    def calculate_hora_parivritti_position(self, degree, rasi_sign_index, ascendant_hora_index):
        """
        D2 Parivṛtti Dwaya (bicyclical): 24 hory → dwa obiegi zodiaku od Barana.
        Połowy Barana → Baran, Byk; połowy Byka → Bliźnięta, Rak; itd.
        """
        degree_in_sign = degree % 30
        half = 0 if degree_in_sign < 15 else 1
        sign_idx = (rasi_sign_index * 2 + half) % 12
        house_number = (sign_idx - ascendant_hora_index) % 12 + 1
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': house_number,
        }

    def calculate_hora_parivritti_chart(self):
        """D2 Hora — metoda Parivṛtti Dwaya."""
        return self._build_divisional_chart(self.calculate_hora_parivritti_position)

    def calculate_hora_kashinatha_position(self, degree, rasi_sign_index, ascendant_hora_index):
        """Kāśinātha Hora, Rao: Personal Finances from Hora Chart, pp. 1–3.

        Odd signs: Sun/Moon halves; even signs: Moon/Sun halves. Select the
        day/night-strong sign owned by the D1 sign lord, pairing Leo/Cancer
        for both luminaries. Boundaries are [0,15), [15,30), without rounding.
        """
        sign = rasi_sign_index % 12
        half = self._equal_varga_part(degree, 2)
        sun_hora = half == sign % 2
        day = (7, 6, 5, 4, 4, 5, 6, 7, 11, 10, 10, 11)
        night = (0, 1, 2, 3, 3, 2, 1, 0, 8, 9, 9, 8)
        sign_idx = (day if sun_hora else night)[sign]
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_hora_index) % 12 + 1,
        }

    def calculate_hora_kashinatha_chart(self):
        return self._build_divisional_chart(self.calculate_hora_kashinatha_position)

    @staticmethod
    def _exact_degrees(pdata):
        """Stopnie w pełnej precyzji.

        `position_degrees` jest zaokrąglone do 0.01°, co przy szerokościach części
        D45 (0.67°) i D60 (0.5°) potrafi przesunąć pozycję o jedną część. Fallback
        obsługuje mapy bez pola exact (np. starsze zrzuty TP).
        """
        val = pdata.get('position_degrees_exact')
        if val is None:
            val = pdata['position_degrees']
        return float(val)

    def _build_divisional_chart(self, position_fn, detailed=None):
        """Buduje Vargę z detailed_chart_data (natal lub TP). Ascendent Vargi = dom 1."""
        if detailed is None:
            detailed = self.detailed_chart_data
        chart = {}
        asc = detailed['AS']
        asc_deg = self._exact_degrees(asc)
        asc_sign_idx = int(asc_deg // 30)
        # znak Asc z index=0 (dom chwilowo nieistotny), potem wymuszamy house=1
        asc_pos = position_fn(asc_deg, asc_sign_idx, 0)
        asc_div_idx = self.ZODIAC_SIGNS.index(asc_pos['zodiac_sign'])
        chart['AS'] = {
            'zodiac_sign': asc_pos['zodiac_sign'],
            'house': 1,
        }
        for code in ['RA', 'KE', 'SU', 'MO', 'ME', 'VE', 'MA', 'JU', 'SA']:
            pdata = detailed.get(code)
            if not pdata:
                continue
            deg = self._exact_degrees(pdata)
            sign_idx = int(deg // 30)
            chart[code] = position_fn(deg, sign_idx, asc_div_idx)
            if code in ('RA', 'KE'):
                self._flag_node_ambiguity(chart[code], pdata, position_fn, asc_div_idx)
        return chart

    def _flag_node_ambiguity(self, entry, pdata, position_fn, asc_div_idx):
        """Oznacza vargi, w których wybór węzeł średni/prawdziwy zmienia znak (DEC-008).

        Niepewność jest definicyjna, nie rektyfikacyjna: nie usuwa jej doprecyzowanie
        godziny urodzenia, bo nie wynika z niedokładności czasu, tylko z tego, że
        „Rāhu" ma dwie konkurencyjne definicje. Flaga jest wejściem dla warstwy
        pewności — pozycja oznaczona nie może dostać wysokiego confidence ceiling.

        Brak pola `position_degrees_mean_node` (starsze zrzuty TP) = brak flagi.
        """
        alt = pdata.get('position_degrees_mean_node')
        if alt is None:
            return
        alt_deg = float(alt)
        alt_pos = position_fn(alt_deg, int(alt_deg // 30), asc_div_idx)
        if alt_pos['zodiac_sign'] == entry['zodiac_sign']:
            return
        entry['node_ambiguous'] = True
        entry['node_alt_sign'] = alt_pos['zodiac_sign']
        entry['node_alt_house'] = alt_pos['house']

    def calculate_panchamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D5, equal 6° parts; Rao, Vedic Astrology, section 6.2.5.

        Replaces the previously unused experimental modality-based variant.
        Odd signs: Aries, Aquarius, Sagittarius, Gemini, Libra.
        Even signs: Taurus, Virgo, Pisces, Capricorn, Scorpio.
        """
        part = self._equal_varga_part(degree, 5)
        signs = (0, 10, 8, 2, 6) if rasi_sign_index % 2 == 0 else (1, 5, 11, 9, 7)
        sign_idx = signs[part]
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_panchamsa_chart(self):
        return self._build_divisional_chart(self.calculate_panchamsa_position)

    def calculate_shashtamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D6 Shashtamsa — 5°; nieparzyste od Barana, parzyste od Wagi."""
        part = self._equal_varga_part(degree, 6)
        start = 0 if (rasi_sign_index % 2 == 0) else 6
        sign_idx = (start + part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_shashtamsa_chart(self):
        return self._build_divisional_chart(self.calculate_shashtamsa_position)

    @staticmethod
    def _equal_varga_part(degree, divisions):
        """Zero-based part, [start,end), without rounding fractional boundaries.

        Compare absolute longitudes to boundaries in the same sign. This avoids
        subtraction/division rounding moving an exact boundary to its left part.
        """
        longitude = degree % 360
        sign_start = 30 * int(longitude // 30)
        boundaries = [sign_start + 30 * part / divisions for part in range(1, divisions)]
        return bisect_right(boundaries, longitude)

    def calculate_ashtamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D8 Ashtamsa: 3°45'; movable/fixed/dual start at Aries/Sagittarius/Leo."""
        part = self._equal_varga_part(degree, 8)
        start = (0, 8, 4)[rasi_sign_index % 3]
        sign_idx = (start + part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_ashtamsa_chart(self):
        return self._build_divisional_chart(self.calculate_ashtamsa_position)

    def calculate_ekadasamsa_iyer_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D11 Iyer: 30°/11; all D1 signs start at Aries and count backwards.

        H.R. Seshadri Iyer, New Techniques of Prediction II, chapter III.
        The D1 sign deliberately does not affect the destination sign.
        """
        part = self._equal_varga_part(degree, 11)
        sign_idx = (-part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_ekadasamsa_iyer_chart(self):
        return self._build_divisional_chart(self.calculate_ekadasamsa_iyer_position)

    def calculate_vimsamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D20 Vimsamsa — 1.5°; ruchome od Barana, stałe od Strzelca, dualne od Lwa."""
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign // 1.5), 19)
        if rasi_sign_index in (0, 3, 6, 9):
            start = 0
        elif rasi_sign_index in (1, 4, 7, 10):
            start = 8
        else:
            start = 4
        sign_idx = (start + part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_vimsamsa_chart(self):
        return self._build_divisional_chart(self.calculate_vimsamsa_position)

    def calculate_chaturvimsamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D24 Chaturvimsamsa — 1.25°; nieparzyste od Lwa, parzyste od Raka."""
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign / 1.25), 23)
        start = 4 if (rasi_sign_index % 2 == 0) else 3
        sign_idx = (start + part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_chaturvimsamsa_chart(self):
        return self._build_divisional_chart(self.calculate_chaturvimsamsa_position)

    def calculate_saptavimsamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D27 Saptaviṃśāṃśa — 30°/27; ogień→Baran, ziemia→Rak, powietrze→Waga, woda→Koziorożec."""
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign / (30.0 / 27.0)), 26)
        if rasi_sign_index in (0, 4, 8):
            start = 0
        elif rasi_sign_index in (1, 5, 9):
            start = 3
        elif rasi_sign_index in (2, 6, 10):
            start = 6
        else:
            start = 9
        sign_idx = (start + part) % 12
        return {
            "zodiac_sign": self.ZODIAC_SIGNS[sign_idx],
            "house": (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_saptavimsamsa_chart(self):
        return self._build_divisional_chart(self.calculate_saptavimsamsa_position)

    def calculate_trimsamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D30 Triṃśāṃśa — nierówne części; znak = znak władcy części (BPHS)."""
        d = degree % 30
        odd = rasi_sign_index % 2 == 0  # 0=Baran = nieparzysty w numeracji 1–12
        if odd:
            if d < 5:
                sign_idx = 0  # Mars → Baran
            elif d < 10:
                sign_idx = 10  # Saturn → Wodnik
            elif d < 18:
                sign_idx = 8  # Jowisz → Strzelec
            elif d < 25:
                sign_idx = 2  # Merkury → Bliźnięta
            else:
                sign_idx = 6  # Wenus → Waga
        else:
            if d < 5:
                sign_idx = 1  # Wenus → Byk
            elif d < 12:
                sign_idx = 5  # Merkury → Panna
            elif d < 20:
                sign_idx = 11  # Jowisz → Ryby
            elif d < 25:
                sign_idx = 9  # Saturn → Koziorożec
            else:
                sign_idx = 7  # Mars → Skorpion
        return {
            "zodiac_sign": self.ZODIAC_SIGNS[sign_idx],
            "house": (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_trimsamsa_chart(self):
        return self._build_divisional_chart(self.calculate_trimsamsa_position)

    def calculate_khavedamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D40 Khavedāṃśa — 0.75°; nieparzyste od Barana, parzyste od Wagi."""
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign / 0.75), 39)
        start = 0 if (rasi_sign_index % 2 == 0) else 6
        sign_idx = (start + part) % 12
        return {
            "zodiac_sign": self.ZODIAC_SIGNS[sign_idx],
            "house": (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_khavedamsa_chart(self):
        return self._build_divisional_chart(self.calculate_khavedamsa_position)

    def calculate_akshavedamsa_position(self, degree, rasi_sign_index, ascendant_div_index):
        """D45 Akṣavedāṃśa — 30°/45; ruchome→Baran, stałe→Lew, dualne→Strzelec."""
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign / (30.0 / 45.0)), 44)
        if rasi_sign_index in (0, 3, 6, 9):
            start = 0
        elif rasi_sign_index in (1, 4, 7, 10):
            start = 4
        else:
            start = 8
        sign_idx = (start + part) % 12
        return {
            "zodiac_sign": self.ZODIAC_SIGNS[sign_idx],
            "house": (sign_idx - ascendant_div_index) % 12 + 1,
        }

    def calculate_akshavedamsa_chart(self):
        return self._build_divisional_chart(self.calculate_akshavedamsa_position)

    def calculate_all_divisionals_from_detailed(self, detailed: dict) -> dict:
        """Full AYKALEN catalogue, including D5/D6, for natal and TP."""
        return {
            "D2_parashara": self._build_divisional_chart(self.calculate_hora_position, detailed),
            "D2_parivritti": self._build_divisional_chart(self.calculate_hora_parivritti_position, detailed),
            "D2_kashinatha": self._build_divisional_chart(self.calculate_hora_kashinatha_position, detailed),
            "D3": self._build_divisional_chart(self.calculate_drekana_position, detailed),
            "D4": self._build_divisional_chart(self.calculate_chaturthamsa_position, detailed),
            "D5": self._build_divisional_chart(self.calculate_panchamsa_position, detailed),
            "D6": self._build_divisional_chart(self.calculate_shashtamsa_position, detailed),
            "D7": self._build_divisional_chart(self.calculate_saptamsa_position, detailed),
            "D8": self._build_divisional_chart(self.calculate_ashtamsa_position, detailed),
            "D9": self._build_divisional_chart(self.calculate_navamsa_position, detailed),
            "D10": self._build_divisional_chart(self.calculate_dasamsa_position, detailed),
            "D11_iyer": self._build_divisional_chart(self.calculate_ekadasamsa_iyer_position, detailed),
            "D12": self._build_divisional_chart(self.calculate_dwadasamsa_position, detailed),
            "D16": self._build_divisional_chart(self.calculate_shodasamsa_position, detailed),
            "D20": self._build_divisional_chart(self.calculate_vimsamsa_position, detailed),
            "D24": self._build_divisional_chart(self.calculate_chaturvimsamsa_position, detailed),
            "D27": self._build_divisional_chart(self.calculate_saptavimsamsa_position, detailed),
            "D30": self._build_divisional_chart(self.calculate_trimsamsa_position, detailed),
            "D40": self._build_divisional_chart(self.calculate_khavedamsa_position, detailed),
            "D45": self._build_divisional_chart(self.calculate_akshavedamsa_position, detailed),
            "D60": self._build_divisional_chart(self.calculate_shashtiamsa_position, detailed),
        }


    def calculate_drekana_position(self, degree, rasi_sign_index, ascendant_drekana_index):
        """
        Oblicza pozycję w Drekana (D3) dla danego stopnia w Rasi, uwzględniając domy i warunek przesunięcia znaków.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_drekana_index: Indeks znaku Ascendentu w Drekana (0–11).
        :return: Słownik z pozycją w Drekana (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Numer drekkāṇy. `int(x/w)` zamiast `<= 10`: punkt dokładnie graniczny należy
        # do części wyższej, spójnie z pozostałymi 15 vargami (KS100-R050).
        part = min(int(degree_in_sign // 10.0), 2)
        # Części 1/2/3 → 1., 5. i 9. znak od wejściowego (BPHS 6.7–8).
        shift = part * 4

        # Obliczenie znaku Drekany
        drekana_sign_index = (rasi_sign_index + shift) % 12
        drekana_sign = self.ZODIAC_SIGNS[drekana_sign_index]
        # Obliczenie numeru domu w Drekana
        house_number = (drekana_sign_index - ascendant_drekana_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': drekana_sign,
            'house': house_number
        }


    def calculate_drekana_chart(self):
        """
        Oblicza pełny Drekana Chart (D3) dla Ascendentu i planet.
        """
        drekana_chart_data = {}
        # Oblicz Ascendent w Drekana
        ascendant_drekana = self.calculate_drekana_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Drekany jako odniesienie
        )
        drekana_chart_data['AS'] = ascendant_drekana
        ascendant_drekana_index = self.ZODIAC_SIGNS.index(ascendant_drekana['zodiac_sign'])

        # Oblicz planety w Drekana
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            drekana_chart_data[planet_name] = self.calculate_drekana_position(
                planet_degree,
                planet_sign_index,
                ascendant_drekana_index
            )
        return drekana_chart_data


    def calculate_chaturthamsa_position(self, degree, rasi_sign_index, ascendant_chaturthamsa_index):
        """
        Oblicza pozycję w Chaturthamsa (D4) dla danego stopnia w Rasi.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_chaturthamsa_index: Indeks znaku Ascendentu w Chaturthamsa (0–11).
        :return: Słownik z pozycją w Chaturthamsa (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30

        # Każda Chaturthamsa ma szerokość 7°30' (7.5°)
        chaturthamsa_width = 7.5

        # Numer Chaturthamsa w znaku (1–4)
        chaturthamsa_number = int(degree_in_sign / chaturthamsa_width) + 1

        # Obliczenie znaku Chaturthamsa na podstawie reguł:
        if chaturthamsa_number == 1:
            chaturthamsa_sign_index = rasi_sign_index  # Pierwsza część: ten sam znak
        elif chaturthamsa_number == 2:
            chaturthamsa_sign_index = (rasi_sign_index + 3) % 12  # Druga część: 4. znak od aktualnego
        elif chaturthamsa_number == 3:
            chaturthamsa_sign_index = (rasi_sign_index + 6) % 12  # Trzecia część: 7. znak od aktualnego
        else:  # chaturthamsa_number == 4
            chaturthamsa_sign_index = (rasi_sign_index + 9) % 12  # Czwarta część: 10. znak od aktualnego

        chaturthamsa_sign = self.ZODIAC_SIGNS[chaturthamsa_sign_index]

        # Obliczenie numeru domu w Chaturthamsa
        house_number = (chaturthamsa_sign_index - ascendant_chaturthamsa_index) % 12 + 1

        # Zwrócenie wyniku
        return {
            'zodiac_sign': chaturthamsa_sign,
            'house': house_number
        }


    def calculate_chaturthamsa_chart(self):
        """
        Oblicza pełny Chaturthamsa Chart (D4) dla Ascendentu, planet oraz Rahu i Ketu.
        """
        chaturthamsa_chart_data = {}

        # Oblicz Ascendent w Chaturthamsa
        ascendant_chaturthamsa = self.calculate_chaturthamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Chaturthamsy jako odniesienie
        )
        chaturthamsa_chart_data['AS'] = ascendant_chaturthamsa
        ascendant_chaturthamsa_index = self.ZODIAC_SIGNS.index(ascendant_chaturthamsa['zodiac_sign'])

        # Oblicz planety w Chaturthamsa
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            chaturthamsa_chart_data[planet_name] = self.calculate_chaturthamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_chaturthamsa_index
            )

        return chaturthamsa_chart_data


    def calculate_shodasamsa_position(self, degree, rasi_sign_index, ascendant_shodasamsa_index):
        """D16 Ṣoḍaśāṃśa — 30/16; ruchome→Baran, stałe→Lew, dwoiste→Strzelec.

        :param degree: Stopień ekliptyczny planety (0–360).
        :param rasi_sign_index: Indeks znaku (0–11) dla Rasi.
        :param ascendant_shodasamsa_index: Indeks ascendentu D16 (0–11) do wyliczenia domu.
        :return: Dict z 'zodiac_sign' i 'house'.
        """
        degree_in_sign = degree % 30
        part = min(int(degree_in_sign // (30.0 / 16.0)), 15)
        if rasi_sign_index in (0, 3, 6, 9):
            start = 0
        elif rasi_sign_index in (1, 4, 7, 10):
            start = 4
        else:
            start = 8
        sign_idx = (start + part) % 12
        return {
            'zodiac_sign': self.ZODIAC_SIGNS[sign_idx],
            'house': (sign_idx - ascendant_shodasamsa_index) % 12 + 1,
        }


    def calculate_shodasamsa_chart(self):
        d16_chart = {}

        # ASC jako referencja
        asc = self.calculate_shodasamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Referencyjnie 0, aby uzyskać znak
        )
        d16_chart['AS'] = asc
        asc_index = self.ZODIAC_SIGNS.index(asc['zodiac_sign'])

        for planet_name, planet_data in self.detailed_chart_data.items():
            degree = self._exact_degrees(planet_data)
            rasi_sign_index = int(degree // 30)

            d16_chart[planet_name] = self.calculate_shodasamsa_position(
                degree,
                rasi_sign_index,
                asc_index
            )

        return d16_chart


    def calculate_saptamsa_position(self, degree, rasi_sign_index, ascendant_saptamsa_index):
        """
        Oblicza pozycję w Saptamsie (D7) dla danego stopnia w Rasi, uwzględniając domy.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_saptamsa_index: Indeks znaku Ascendentu w Saptamsie (0–11).
        :return: Słownik z pozycją w Saptamsie (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Początek Saptamsy dla danego znaku Rasi
        saptamsa_start_signs = {
            0: 0, 
            1: 7,
            2: 2,
            3: 9,
            4: 4,
            5: 11,
            6: 6,
            7: 1,
            8: 8,
            9: 3,
            10: 10,
            11: 5
        }
        # Szerokość jednej Saptamsy — dokładne 30/7 (4°17'08.57''), nie zaokrąglone DMS
        saptamsa_width = 30.0 / 7.0
        # Numer Saptamsy w znaku (1–7)
        saptamsa_number = min(int(degree_in_sign // saptamsa_width), 6) + 1
        # Obliczenie znaku Saptamsy
        saptamsa_start_sign = saptamsa_start_signs[rasi_sign_index]
        saptamsa_sign_index = (saptamsa_start_sign + saptamsa_number - 1) % 12
        saptamsa_sign = self.ZODIAC_SIGNS[saptamsa_sign_index]
        # Obliczenie numeru domu w Saptamsie
        house_number = (saptamsa_sign_index - ascendant_saptamsa_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': saptamsa_sign,
            'house': house_number
        }


    def calculate_saptamsa_chart(self):
        """
        Oblicza pełny Saptamsa Chart (D7) dla Ascendentu i planet.
        """
        saptamsa_chart_data = {}

        # Oblicz Ascendent w Saptamsie
        ascendant_saptamsa = self.calculate_saptamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Saptamsy jako odniesienie
        )
        saptamsa_chart_data['AS'] = ascendant_saptamsa
        ascendant_saptamsa_index = self.ZODIAC_SIGNS.index(ascendant_saptamsa['zodiac_sign'])
        # Oblicz planety w Saptamsie
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            saptamsa_chart_data[planet_name] = self.calculate_saptamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_saptamsa_index
            )
        return saptamsa_chart_data


    def calculate_navamsa_position(self, degree, rasi_sign_index, ascendant_navamsa_index):
        """
        Oblicza pozycję w Navamsie dla danego stopnia w Rasi, uwzględniając domy.
        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_navamsa_index: Indeks znaku Ascendentu w Navamsie (0–11).
        :return: Słownik z pozycją w Navamsie (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Początek Navamsy dla danego znaku Rasi
        navamsa_start_signs = {
            0: 0,  # Baran zaczyna od Barana
            1: 9,  # Byk zaczyna od Koziorożca
            2: 6,  # Bliźnięta zaczyna od Wagi
            3: 3,  # Rak zaczyna od Raka
            4: 0,  # Lew zaczyna od Barana
            5: 9,  # Panna zaczyna od Koziorożca
            6: 6,  # Waga zaczyna od Wagi
            7: 3,  # Skorpion zaczyna od Raka
            8: 0,  # Strzelec zaczyna od Barana
            9: 9,  # Koziorożec zaczyna od Koziorożca
            10: 6, # Wodnik zaczyna od Wagi
            11: 3  # Ryby zaczyna od Raka
        }
        # Szerokość jednej Navamsy — dokładne 30/9, nie zaokrąglone DMS (KS100-R055)
        navamsa_width = 30.0 / 9.0
        # Numer Navamsy w znaku (1–9)
        navamsa_number = min(int(degree_in_sign // navamsa_width), 8) + 1
        # Obliczenie znaku Navamsy
        navamsa_start_sign = navamsa_start_signs[rasi_sign_index]
        navamsa_sign_index = (navamsa_start_sign + navamsa_number - 1) % 12
        navamsa_sign = self.ZODIAC_SIGNS[navamsa_sign_index]
        # Obliczenie numeru domu w Navamsie
        house_number = (navamsa_sign_index - ascendant_navamsa_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': navamsa_sign,
            'house': house_number
        }


    def calculate_navamsa_chart(self):
        """
        Oblicza pełny Navamsa Chart dla Ascendentu i planet (znak zodiaku i dom).
        """
        navamsa_chart_data = {}
        # Oblicz Ascendent w Navamsie
        ascendant_navamsa = self.calculate_navamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Navamsy jako odniesienie
        )
        navamsa_chart_data['AS'] = ascendant_navamsa
        ascendant_navamsa_index = self.ZODIAC_SIGNS.index(ascendant_navamsa['zodiac_sign'])
        # Oblicz planety w Navamsie
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            navamsa_chart_data[planet_name] = self.calculate_navamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_navamsa_index
            )
        return navamsa_chart_data


    def calculate_dasamsa_position(self, degree, rasi_sign_index, ascendant_dasamsa_index):
        """
        Oblicza pozycję w Dasamsie (D10) dla danego stopnia w Rasi, uwzględniając domy.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_dasamsa_index: Indeks znaku Ascendentu w Dasamsie (0–11).
        :return: Słownik z pozycją w Dasamsie (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Początek Dasamsy dla danego znaku Rasi
        dasamsa_start_signs = {
            0: 0,
            1: 9,  
            2: 2,  
            3: 11, 
            4: 4,  
            5: 1,  
            6: 6,  
            7: 3,  
            8: 8,  
            9: 5,  
            10: 10, 
            11: 7  
        }
        # Szerokość jednej Dasamsy (3°)
        dasamsa_width = 3  # Każda Dasamsa to 3°
        # Numer Dasamsy w znaku (1–10)
        dasamsa_number = int(degree_in_sign // dasamsa_width) + 1
        # Obliczenie znaku Dasamsy
        dasamsa_start_sign = dasamsa_start_signs[rasi_sign_index]
        dasamsa_sign_index = (dasamsa_start_sign + dasamsa_number - 1) % 12
        dasamsa_sign = self.ZODIAC_SIGNS[dasamsa_sign_index]
        # Obliczenie numeru domu w Dasamsie
        house_number = (dasamsa_sign_index - ascendant_dasamsa_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': dasamsa_sign,
            'house': house_number
        }


    def calculate_dasamsa_chart(self):
        """
        Oblicza pełny Dasamsa Chart (D10) dla Ascendentu i planet.
        """
        dasamsa_chart_data = {}
        # Oblicz Ascendent w Dasamsie
        ascendant_dasamsa = self.calculate_dasamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Dasamsy jako odniesienie
        )
        dasamsa_chart_data['AS'] = ascendant_dasamsa
        ascendant_dasamsa_index = self.ZODIAC_SIGNS.index(ascendant_dasamsa['zodiac_sign'])
        # Oblicz planety w Dasamsie
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            dasamsa_chart_data[planet_name] = self.calculate_dasamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_dasamsa_index
            )
        return dasamsa_chart_data


    def calculate_dwadasamsa_position(self, degree, rasi_sign_index, ascendant_dwadasamsa_index):
        """
        Oblicza pozycję w Dwadasamsie (D12) dla danego stopnia w Rasi, uwzględniając domy.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_dwadasamsa_index: Indeks znaku Ascendentu w Dwadasamsie (0–11).
        :return: Słownik z pozycją w Dwadasamsie (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30
        # Początek Dwadasamsy dla danego znaku Rasi
        dwadasamsa_start_signs = {
            0: 0,  # Baran zaczyna od Barana
            1: 1,  # Byk zaczyna od Byka
            2: 2,  # Bliźnięta zaczyna od Bliźniąt
            3: 3,  # Rak zaczyna od Raka
            4: 4,  # Lew zaczyna od Lwa
            5: 5,  # Panna zaczyna od Panny
            6: 6,  # Waga zaczyna od Wagi
            7: 7,  # Skorpion zaczyna od Skorpiona
            8: 8,  # Strzelec zaczyna od Strzelca
            9: 9,  # Koziorożec zaczyna od Koziorożca
            10: 10, # Wodnik zaczyna od Wodnika
            11: 11  # Ryby zaczyna od Ryb
        }
        # Szerokość jednej Dwadasamsy (2°30')
        dwadasamsa_width = 2 + 30 / 60  # 2.5°
        # Numer Dwadasamsy w znaku (1–12)
        dwadasamsa_number = int(degree_in_sign // dwadasamsa_width) + 1
        # Obliczenie znaku Dwadasamsy
        dwadasamsa_start_sign = dwadasamsa_start_signs[rasi_sign_index]
        dwadasamsa_sign_index = (dwadasamsa_start_sign + dwadasamsa_number - 1) % 12
        dwadasamsa_sign = self.ZODIAC_SIGNS[dwadasamsa_sign_index]
        # Obliczenie numeru domu w Dwadasamsie
        house_number = (dwadasamsa_sign_index - ascendant_dwadasamsa_index) % 12 + 1
        # Zwrócenie wyniku
        return {
            'zodiac_sign': dwadasamsa_sign,
            'house': house_number
        }


    def calculate_dwadasamsa_chart(self):
        """
        Oblicza pełny Dwadasamsa Chart (D12) dla Ascendentu i planet.
        """
        dwadasamsa_chart_data = {}
        # Oblicz Ascendent w Dwadasamsie
        ascendant_dwadasamsa = self.calculate_dwadasamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Dwadasamsy jako odniesienie
        )
        dwadasamsa_chart_data['AS'] = ascendant_dwadasamsa
        ascendant_dwadasamsa_index = self.ZODIAC_SIGNS.index(ascendant_dwadasamsa['zodiac_sign'])
        # Oblicz planety w Dwadasamsie
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            dwadasamsa_chart_data[planet_name] = self.calculate_dwadasamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_dwadasamsa_index
            )
        return dwadasamsa_chart_data


    def calculate_shashtiamsa_position(self, degree, rasi_sign_index, ascendant_shashtiamsa_index):
        """
        Oblicza pozycję w Shashtiamsa (D60) dla danego stopnia w Rasi.

        :param degree: Stopień w Rasi (0°–360°).
        :param rasi_sign_index: Indeks znaku Rasi (0–11).
        :param ascendant_shashtiamsa_index: Indeks znaku Ascendentu w Shashtiamsa (0–11).
        :return: Słownik z pozycją w Shashtiamsa (znak zodiaku i dom).
        """
        # Stopnie w znaku Rasi (0°–30°)
        degree_in_sign = degree % 30

        # Każda Shashtiamsa ma szerokość 0°30' (0.5°)
        shashtiamsa_width = 0.5

        # Numer Shashtiamsa w znaku (1–60)
        shashtiamsa_number = int(degree_in_sign / shashtiamsa_width) + 1

        # Obliczenie znaku Shashtiamsa (progresja przez 60 części)
        shashtiamsa_sign_index = (rasi_sign_index + (shashtiamsa_number - 1) % 12) % 12
        shashtiamsa_sign = self.ZODIAC_SIGNS[shashtiamsa_sign_index]

        # Obliczenie numeru domu w Shashtiamsa
        house_number = (shashtiamsa_sign_index - ascendant_shashtiamsa_index) % 12 + 1

        # Zwrócenie wyniku
        return {
            'zodiac_sign': shashtiamsa_sign,
            'house': house_number
        }


    def calculate_shashtiamsa_chart(self):
        """
        Oblicza pełny Shashtiamsa Chart (D60) dla Ascendentu, planet oraz Rahu i Ketu.
        """
        shashtiamsa_chart_data = {}

        # Oblicz Ascendent w Shashtiamsa
        ascendant_shashtiamsa = self.calculate_shashtiamsa_position(
            self.ascendant_adjusted_position,
            self.ascendant_zodiac_index,
            0  # Ascendent Shashtiamsy jako odniesienie
        )
        shashtiamsa_chart_data['AS'] = ascendant_shashtiamsa
        ascendant_shashtiamsa_index = self.ZODIAC_SIGNS.index(ascendant_shashtiamsa['zodiac_sign'])

        # Oblicz planety w Shashtiamsa
        for planet_name, planet_data in self.detailed_chart_data.items():
            planet_degree = self._exact_degrees(planet_data)
            planet_sign_index = int(planet_degree // 30)
            shashtiamsa_chart_data[planet_name] = self.calculate_shashtiamsa_position(
                planet_degree,
                planet_sign_index,
                ascendant_shashtiamsa_index
            )

        return shashtiamsa_chart_data


    def get_chart_data(self):
        self.get_complete_astro_details()
        self.chart_data = {}
        for key, value in self.detailed_chart_data.items():
            self.chart_data[key] = [value['house'], value['zodiac_sign']]
        self.ascendent_sign = self.chart_data['AS'][1]
        self.get_ascendent_and_its_lord_signs()
        return self.detailed_chart_data, self.chart_data


    def get_as_lord_house(self):
        """
        Finds the house number where the planet corresponding to the Ascendant sign is located.
        """
        as_lord_planet = self.AS_LORD.get(self.ascendent_sign)
        if not as_lord_planet:
            return None
        
        for key, value in self.chart_data.items():
            if key == as_lord_planet:
                return value[0]
        return None


    def get_ascendent_and_its_lord_signs(self):
        """
        Tworzy słownik, który mapuje znak zodiaku ascendentu na znak zodiaku, w którym znajduje się jego władca.
        """
        # Pobierz znak zodiaku ascendentu
        ascendent_sign = self.chart_data['AS'][1]
        # Znajdź planetę przypisaną do znaku zodiaku ascendentu
        as_lord_planet = self.AS_LORD.get(ascendent_sign)
        if not as_lord_planet:
            raise ValueError(f"Nie znaleziono władcy dla znaku zodiaku {ascendent_sign}.")
        # Znajdź znak zodiaku, w którym znajduje się ta planeta
        lord_planet_sign = None
        for planet, data in self.chart_data.items():
            if planet == as_lord_planet:
                lord_planet_sign = data[1]  # Drugi element to znak zodiaku
                break
        if not lord_planet_sign:
            raise ValueError(f"Nie znaleziono pozycji planety {as_lord_planet} w horoskopie.")
        # Stwórz słownik ascendentu i znaku jego władcy
        self.ascendent_and_its_lord_signs = {ascendent_sign: lord_planet_sign}
        return self.ascendent_and_its_lord_signs


    def find_house_for_sign(self, ascendant_sign, target_sign):
        """
        Znajduje numer domu dla znaku docelowego, licząc od znaku Ascendentu.
        """
        asc_index = self.ZODIAC_SIGNS.index(ascendant_sign)
        target_index = self.ZODIAC_SIGNS.index(target_sign)
        house_number = (target_index - asc_index) % 12 + 1
        return house_number


    def _sun_altitude_deg(self, jd, alt0=-0.833):
        """Wysokość Słońca [deg] minus alt0 (threshold)."""
        import math
        lon = float(self.longitude)
        lat = float(self.latitude)
        flg = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL  # RA, DEC
        ra_deg, dec_deg = swe.calc_ut(jd, swe.SUN, flg)[0][:2]
        lst_hours = swe.sidtime(jd) + lon / 15.0
        lst_deg = (lst_hours * 15.0) % 360.0
        H = ((lst_deg - ra_deg + 180.0) % 360.0) - 180.0
        phi = math.radians(lat)
        dec = math.radians(dec_deg)
        Hrad = math.radians(H)
        sin_alt = math.sin(phi)*math.sin(dec) + math.cos(phi)*math.cos(dec)*math.cos(Hrad)
        sin_alt = max(-1.0, min(1.0, sin_alt))
        return math.degrees(math.asin(sin_alt)) - alt0



    def _jd_to_local(self, jd_ut: float):
        y,m,d,fr = swe.revjul(jd_ut)
        hh = int(fr); mm = int((fr-hh)*60); ss = int((((fr-hh)*60)-mm)*60)
        dt_utc = datetime(y,m,d,hh,mm,ss, tzinfo=pytz.utc)
        return dt_utc.astimezone(self.tp_datetime_local.tzinfo if hasattr(self,"tp_datetime_local") else pytz.timezone(self.timezone))


    def _sr_ss_by_se(self, jd_ut: float, mode: str = "center"):
        import swisseph as swe
        lon = float(self.longitude)
        lat = float(self.latitude)

        # Tryb refrakcji/średnicy tarczy
        if mode == "center":
            rsmi_base = swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION
            atpress, attemp = 0.0, 0.0
        else:
            rsmi_base = 0
            atpress, attemp = 1013.25, 15.0

        geopos = (lon, lat, 0.0)

        # Kompatybilna nakładka na swe.rise_trans (różne sygnatury w różnych wersjach)
        def _rise_trans_compat(jd, ipl, rsmi):
            try:
                # nowy podpis
                retflag, t = swe.rise_trans(jd, ipl, None, swe.FLG_SWIEPH, rsmi, geopos, atpress, attemp)
            except TypeError:
                # stary podpis
                retflag, t = swe.rise_trans(jd, ipl, rsmi, geopos, atpress, attemp)

            # --- NORMALIZACJA: bierzemy JD jako float ---
            if isinstance(t, (tuple, list)):
                t = t[0]
            return retflag, float(t)


        # Znajdź poprzedni i następny wschód wokół jd_ut
        def _sunrise_around(jd):
            # Re-solving the same Swiss event may differ by a fraction of a
            # millisecond. Only sunrise-event comparison uses this tolerance;
            # hora intervals below retain exact [start,end) boundaries.
            event_tolerance = 0.01 / 86400.0
            _, t1 = _rise_trans_compat(jd, swe.SUN, rsmi_base | swe.CALC_RISE)
            if t1 > jd + event_tolerance:
                _, t1 = _rise_trans_compat(jd - 1.0, swe.SUN, rsmi_base | swe.CALC_RISE)
            if t1 > jd + event_tolerance:
                # When sunrise is getting later, the preceding sunrise can
                # be more than 24h ago; jd-1 would skip it.
                _, t1 = _rise_trans_compat(jd - 2.0, swe.SUN, rsmi_base | swe.CALC_RISE)
            _, t2 = _rise_trans_compat(t1 + 0.1, swe.SUN, rsmi_base | swe.CALC_RISE)
            if t2 <= jd + event_tolerance:
                t1 = t2
                _, t2 = _rise_trans_compat(t1 + 0.1, swe.SUN, rsmi_base | swe.CALC_RISE)
            if abs(t1 - jd) <= event_tolerance:
                t1 = jd
            if not t1 <= jd < t2:
                raise ValueError("Could not bracket TP between consecutive sunrises")
            return t1, t2

        sr_prev, sr_next = _sunrise_around(jd_ut)
        # Zachód między tymi wschodami
        _, ss_between = _rise_trans_compat(sr_prev + 0.1, swe.SUN, rsmi_base | swe.CALC_SET)

        return sr_prev, ss_between, sr_next

    def _tithi_index_1_30(self, jd_ut: float) -> int:
        """Indeks tithi 1..30 w chwili jd_ut (sidereal)."""
        ang = _tithi_angle_deg(jd_ut) % 360.0
        return int(ang // 12.0) + 1


    def _tithi_fraction(self, jd_ut: float) -> float:
        """Ułamek BIEŻĄCEGO tithi, który już upłynął (0.0..1.0)."""
        ang = _tithi_angle_deg(jd_ut) % 360.0
        return (ang % 12.0) / 12.0


    def _fmt_local(self, jd_ut: float) -> str:
        import pytz, swisseph as swe
        from datetime import datetime
        y,m,d,fr = swe.revjul(jd_ut)
        hh = int(fr); mm = int((fr-hh)*60); ss = int((((fr-hh)*60)-mm)*60)
        dt_utc = datetime(y,m,d,hh,mm,ss, tzinfo=pytz.utc)
        tzinfo = self.tp_datetime_local.tzinfo if hasattr(self, "tp_datetime_local") else pytz.utc
        return dt_utc.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S")



    def _signed_angle_diff_deg(self, a: float, b: float) -> float:
        """Oblicza różnicę kątową ze znakiem w zakresie (-180, 180]."""
        return (a - b + 180.0) % 360.0 - 180.0

    def _find_root_bisection(self, func, a: float, b: float, max_iter=100, tol_sec=0.1) -> float:
        """Precyzyjnie znajduje miejsce zerowe funkcji metodą bisekcji."""
        fa = func(a)
        for _ in range(max_iter):
            m = 0.5 * (a + b)
            if (b - a) * 86400.0 < tol_sec:
                return m
            fm = func(m)
            if fa * fm <= 0:
                b = m
            else:
                a, fa = m, fm
        return 0.5 * (a + b)

    def _get_tithi_boundaries(self, jd_ut: float) -> tuple[float, float]:
        """Znajduje czas rozpoczęcia i zakończenia tithi aktywnego w danym momencie jd_ut."""
        elongation_now = self._get_sidereal_elongation(jd_ut)
        tithi_index_float = elongation_now / 12.0
        current_tithi_num = int(tithi_index_float)

        prev_target_elongation = current_tithi_num * 12.0
        next_target_elongation = ((current_tithi_num + 1) * 12.0) % 360.0

        def f_prev(jd): return self._signed_angle_diff_deg(self._get_sidereal_elongation(jd), prev_target_elongation)
        def f_next(jd): return self._signed_angle_diff_deg(self._get_sidereal_elongation(jd), next_target_elongation)

        # Szukanie granicy początkowej (wstecz)
        a, b = jd_ut - 1.5, jd_ut
        start_jd = self._find_root_bisection(f_prev, a, b)

        # Szukanie granicy końcowej (w przód)
        a, b = jd_ut, jd_ut + 1.5
        end_jd = self._find_root_bisection(f_next, a, b)

        return start_jd, end_jd

    def _jd_to_local_datetime(self, jd_ut: float) -> datetime:
            """Konwertuje JD (UT) na zlokalizowany obiekt datetime."""
            # Upewnij się, że importy są dostępne w pliku
            import swisseph as swe
            import pytz
            from datetime import datetime
            
            year, mon, day, h_frac = swe.revjul(jd_ut)
            hour = int(h_frac)
            minute = int((h_frac - hour) * 60)
            second = int((((h_frac - hour) * 60) - minute) * 60)
            dt_utc = datetime(year, mon, day, hour, minute, second, tzinfo=pytz.utc)
            
            # Używa strefy czasowej zapisanej w obiekcie ('self.timezone')
            local_tz = pytz.timezone(self.timezone)
            return dt_utc.astimezone(local_tz)

    def _get_sidereal_elongation(self, jd_ut: float) -> float:
            """Oblicza syderyczną elongację (Księżyc - Słońce)."""
            return _tithi_angle_deg(jd_ut)

    def _tithi_phase_offset_degrees(self, reference_jd: float, jd_ut: float) -> float:
        """Continuous Moon-Sun elongation advance relative to ``reference_jd``.

        The raw elongation wraps at 360 degrees. The mean synodic rate gives
        an unambiguous turn count for the TP-year range used here, while the
        returned position itself comes from Swiss Ephemeris.
        """
        mean_rate = 360.0 / 29.530588853
        reference_angle = self._get_sidereal_elongation(reference_jd)
        angle = self._get_sidereal_elongation(jd_ut)
        raw_delta = angle - reference_angle
        expected_delta = (float(jd_ut) - float(reference_jd)) * mean_rate
        turns = round((expected_delta - raw_delta) / 360.0)
        return raw_delta + 360.0 * turns

    def _jd_at_tithi_phase_offset(
        self, reference_jd: float, offset_tithis: float
    ) -> float:
        """Solve the JD at a continuous tithi-phase offset from a reference."""
        target_degrees = float(offset_tithis) * 12.0
        if abs(target_degrees) <= 1e-12:
            return float(reference_jd)

        mean_rate = 360.0 / 29.530588853
        estimate = float(reference_jd) + target_degrees / mean_rate

        def f(jd: float) -> float:
            return (
                self._tithi_phase_offset_degrees(float(reference_jd), jd)
                - target_degrees
            )

        half_width = 1.0
        a = estimate - half_width
        b = estimate + half_width
        fa = f(a)
        fb = f(b)
        for _ in range(16):
            if fa == 0.0:
                return a
            if fb == 0.0:
                return b
            if fa * fb < 0.0:
                return _bisect_root_scalar(f, a, b, time_tol_sec=0.05)
            half_width *= 2.0
            a = estimate - half_width
            b = estimate + half_width
            fa = f(a)
            fb = f(b)
        raise RuntimeError(
            "Cannot solve tithi-compression boundary for "
            f"offset {offset_tithis:.9f}."
        )


    def generate_tithi_pravesha_chart(self, year: int, ayanamsa_mode=swe.SIDM_LAHIRI, sunrise_mode: str = "center"):
        swe.set_sid_mode(ayanamsa_mode)

        # zapisz tryb w obiekcie (jeden switch na wszystko)
        self.sunrise_mode = "center" if sunrise_mode not in ("center", "standard") else sunrise_mode

        iana_tz = _ensure_iana_tz(getattr(self, "timezone", ""), float(self.latitude), float(self.longitude))
        naive_birth = datetime.strptime(f"{self.date} {self.real_time}", "%Y-%m-%d %H:%M:%S")

        tz_obj = pytz.timezone(iana_tz)
        birth_dt_local = tz_obj.localize(naive_birth, is_dst=None)

        # możesz dalej używać tz_obj jako lokalnej strefy
        local_tz = tz_obj

        birth_dt_utc = birth_dt_local.astimezone(pytz.utc)

        jd_birth = swe.julday(
            birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day,
            birth_dt_utc.hour + birth_dt_utc.minute/60 + birth_dt_utc.second/3600
        )

        natal_tithi_angle = _tithi_angle_deg(jd_birth)
        natal_sun_sid     = _sun_sidereal_long_deg(jd_birth)
        natal_sign_index  = int(natal_sun_sid // 30)

        # --- OKNO: Słońce w natalnym znaku (sidereal) ---
        jd_ing, jd_egr = _find_ingress_egress(year, natal_sign_index)

        # --- DOPASOWANIE TITHI: globalne minimum w całym oknie ---
        def _circ_diff_deg(a: float, b: float) -> float:
            d = (a - b) % 360.0
            return 360.0 - d if d > 180.0 else d  # 0..180

        def g(jd: float) -> float:
            return _circ_diff_deg(_tithi_angle_deg(jd), natal_tithi_angle)

        # globalny skan 10-minutowy
        step = 10.0 / (24.0 * 60.0)
        best_t, best_v = jd_ing, g(jd_ing)
        t = jd_ing + step
        while t <= jd_egr + 1e-12:
            v = g(t)
            if v < best_v:
                best_v, best_t = v, t
            t += step

        # doskan 5-min w okolicy znalezionego minimum (dla „wąskich” minimów)
        if best_v > 0.02:  # ~72"
            fine = 5.0 / (24.0 * 60.0)
            t = max(jd_ing, best_t - 2*step)
            t_end = min(jd_egr, best_t + 2*step)
            while t <= t_end + 1e-12:
                v = g(t)
                if v < best_v:
                    best_v, best_t = v, t
                t += fine

        # złoty podział ±30 min wokół best_t
        a = max(jd_ing, best_t - 0.5/24.0)
        b = min(jd_egr, best_t + 0.5/24.0)
        phi = (1 + 5**0.5) / 2
        invphi = 1 / phi
        c = b - (b - a) * invphi
        d = a + (b - a) * invphi
        fc = g(c); fd = g(d)
        for _ in range(120):
            if fc < fd:
                b, d, fd = d, c, fc
                c = b - (b - a) * invphi
                fc = g(c)
            else:
                a, c, fc = c, d, fd
                d = a + (b - a) * invphi
                fd = g(d)
            if (b - a) * 86400.0 < 0.1:
                break
        tp_jd_ut = 0.5*(a+b)

        # --- SANITY: Słońce w natalnym znaku, różnica tithi bliska 0° ---
        sun_sid = _sun_sidereal_long_deg(tp_jd_ut)
        if not (natal_sign_index*30 - 1e-5 <= sun_sid < (natal_sign_index+1)*30 + 1e-5):
            # awaryjne doprecyzowanie: ±1h wokół best_t
            a2 = max(jd_ing, best_t - 1.0/24.0)
            b2 = min(jd_egr, best_t + 1.0/24.0)
            c = b2 - (b2 - a2) * invphi
            d = a2 + (b2 - a2) * invphi
            fc = g(c); fd = g(d)
            for _ in range(160):
                if fc < fd:
                    b2, d, fd = d, c, fc
                    c = b2 - (b2 - a2) * invphi
                    fc = g(c)
                else:
                    a2, c, fc = c, d, fd
                    d = a2 + (b2 - a2) * invphi
                    fd = g(d)
                if (b2 - a2) * 86400.0 < 0.1:
                    break
            tp_jd_ut = 0.5*(a2+b2)

        # --- KONWERSJE CZASU ---
        y, m, d, fr = swe.revjul(tp_jd_ut)
        hh = int(fr)
        mm = int((fr - hh) * 60)
        ss = int((((fr - hh) * 60) - mm) * 60)
        dt_utc = datetime(y, m, d, hh, mm, ss, tzinfo=pytz.utc)
        dt_loc = dt_utc.astimezone(local_tz) 

        self.tp_jd_ut      = tp_jd_ut
        self.tp_datetime_utc   = dt_utc
        self.tp_datetime_local = dt_loc
        self.tp_year           = year
        self.tp_chart_data     = self._compute_detailed_chart_at_jd(tp_jd_ut, ayanamsa_mode)

        # Vaara licz w tym samym trybie (SR/SS)
        self.tp_sr_prev_ut, self.tp_ss_ut, self.tp_sr_next_ut = self._sr_ss_by_se(tp_jd_ut, mode=self.sunrise_mode)
        self.tp_vaara = self.get_vaara_lord_for_tp()  

        return self


    # --- DAGDHA: numer tithi i spalone rasi ---

    def tithi_index_1_30(self, jd_ut: float) -> int:
        ang = _tithi_angle_deg(jd_ut)
        return int((ang // 12.0) % 30) + 1  # 1..30

    def dagdha_rasi_for_tithi(self, tithi_idx_1_30: int):
        reduced = tithi_idx_1_30 if tithi_idx_1_30 <= 15 else (tithi_idx_1_30 - 15)
        idxs = self.DAGDHA_BY_TITHI_1_15.get(reduced, [])
        return [(i, self.ZODIAC_SIGNS[i]) for i in idxs]


    def tithi_name(self, tithi_idx_1_30: int) -> str:
        """e.g. 'Shukla Dwadashi', 'Krishna Trayodashi', 'Purnima', 'Amavasya'."""
        if tithi_idx_1_30 == 30:
            return "Amavasya"
        if tithi_idx_1_30 == 15:
            return "Purnima"
        if 1 <= tithi_idx_1_30 <= 14:
            return f"Shukla {self.TITHI_BASE[tithi_idx_1_30 - 1]}"
        # 16..29 -> Krishna 1..14
        return f"Krishna {self.TITHI_BASE[tithi_idx_1_30 - 16]}"


    def tithi_index_at_jd(self, jd_ut: float) -> int:
        """Zwraca numer porządkowy tithi (1-30) dla danego momentu."""
        elongation = self._get_sidereal_elongation(jd_ut)
        return int(elongation / 12.0) + 1

    def get_tithi_ashtottari_md_schedule(self, tp_year: int):
        """
        Oblicza i zwraca roczny harmonogram Mahadasha (MD) dla Tithi Ashtottari.
        Logika oparta o Tithi w momencie Tithi Pravesha (zgodnie z JHora).
        """
        if not hasattr(self, 'tp_jd_ut'):
            # Upewnij się, że horoskop TP został wcześniej wygenerowany
            self.generate_tithi_pravesha_chart(tp_year)

        tp_start_jd = self.tp_jd_ut
        
        # Oblicz moment TP na następny rok, aby uzyskać długość roku TPC
        # Tworzymy tymczasową instancję, aby uniknąć nadpisywania danych
        import copy
        next_year_chart = copy.deepcopy(self)
        next_year_chart.generate_tithi_pravesha_chart(tp_year + 1)
        tp_end_jd = next_year_chart.tp_jd_ut
        
        tpyl_days = tp_end_jd - tp_start_jd

        # JHora option "tithi based dasa compression": consecutive TP returns
        # close after a whole number of lunations. Compress 108 nominal years
        # into that many tithis (normally 360 or 390), then solve each boundary
        # from the real Moon-Sun phase. Equal fractions of clock days are not
        # equivalent because lunar speed is variable.
        annual_tithis_raw = (
            self._tithi_phase_offset_degrees(tp_start_jd, tp_end_jd) / 12.0
        )
        annual_tithis = float(round(annual_tithis_raw / 30.0) * 30)
        if abs(annual_tithis_raw - annual_tithis) > 1e-5:
            raise RuntimeError(
                "Rok TP nie domyka się do pełnej liczby lunacji: "
                f"{annual_tithis_raw:.9f} tithi."
            )

        boundary_cache = {
            round(0.0, 12): float(tp_start_jd),
            round(annual_tithis, 12): float(tp_end_jd),
        }

        def jd_for_offset(offset_tithis: float) -> float:
            key = round(float(offset_tithis), 12)
            if key not in boundary_cache:
                boundary_cache[key] = self._jd_at_tithi_phase_offset(
                    tp_start_jd, float(offset_tithis)
                )
            return boundary_cache[key]

        # --- Kluczowa zmiana: Logika oparta o Tithi w momencie TP, a nie natalne ---
        
        # 1. Władca i saldo na podstawie Tithi w momencie Tithi Pravesha
        (
            tp_tithi_index,
            inaugural_lord,
            _tithi_start,
            _tithi_end,
            tithi_balance,
        ) = self.tithi_balance_at(tp_start_jd)
        
        # 2. Kompresja cyklu w jednostkach tithi
        compressed_dashas = {
            planet: (
                self.ASHTOTTARI_YEARS_BPHS[planet]
                / self.ASHTOTTARI_TOTAL_YEARS
                * annual_tithis
            )
            for planet in self.ASHTOTTARI_SEQ_BPHS
        }
        
        # 3. Odtworzenie pełnej fazy inauguralnej Mahadashy.
        #
        # JHora nie restartuje MD ani AD w chwili TP.  ``fraction left``
        # wyznacza pozostały ogon pełnej skompresowanej MD, dlatego jej
        # źródłowy początek leży przed TP.  Widok roczny zostanie przycięty
        # dopiero do [tp_start, tp_end).
        full_first_dasha_tithis = compressed_dashas[inaugural_lord]
        first_full_end_offset = full_first_dasha_tithis * tithi_balance
        first_full_start_offset = first_full_end_offset - full_first_dasha_tithis

        # 4. Ustalenie pełnej sekwencji Mahadasha i jej widoku rocznego
        md_timeline_raw = []

        # Pierwszy okres: zachowaj pełną fazę, ale eksportuj tylko część od TP.
        first_visible_end_offset = min(first_full_end_offset, annual_tithis)
        md_timeline_raw.append(
            {
                "lord": inaugural_lord,
                "start_tithi": 0.0,
                "end_tithi": first_visible_end_offset,
                "full_start_tithi": first_full_start_offset,
                "full_end_tithi": first_full_end_offset,
            }
        )
        current_end_offset = first_full_end_offset
        
        # Kolejne okresy
        start_index = (self.ASHTOTTARI_SEQ_BPHS.index(inaugural_lord) + 1) % len(self.ASHTOTTARI_SEQ_BPHS)
        for i in range(len(self.ASHTOTTARI_SEQ_BPHS) * 2): # Pętla na ponad rok, dla pewności
            lord_index = (start_index + i) % len(self.ASHTOTTARI_SEQ_BPHS)
            current_lord = self.ASHTOTTARI_SEQ_BPHS[lord_index]
            current_start_offset = current_end_offset
            
            if current_start_offset >= annual_tithis - 1e-12:
                break
                
            duration_tithis = compressed_dashas[current_lord]
            full_end_offset = current_start_offset + duration_tithis

            md_timeline_raw.append({
                "lord": current_lord,
                "start_tithi": current_start_offset,
                "end_tithi": min(full_end_offset, annual_tithis),
                "full_start_tithi": current_start_offset,
                "full_end_tithi": full_end_offset,
            })
            current_end_offset = full_end_offset

        # 5. Formatowanie wyniku + Antardaśe.
        # AD są fazowane na pełnej MD, zaczynają się od następnego lorda i
        # kończą lordem MD.  Dopiero gotowe przedziały są przycinane do
        # widocznej części roku TP.
        final_timeline = []
        for md in md_timeline_raw:
            start_jd = jd_for_offset(md["start_tithi"])
            end_jd = jd_for_offset(md["end_tithi"])
            full_start_jd = jd_for_offset(md["full_start_tithi"])
            full_end_jd = jd_for_offset(md["full_end_tithi"])
            start_dt = self._jd_to_local_datetime(start_jd)
            end_dt = self._jd_to_local_datetime(end_jd)
            full_start_dt = self._jd_to_local_datetime(full_start_jd)
            full_end_dt = self._jd_to_local_datetime(full_end_jd)
            full_md_tithis = float(
                md["full_end_tithi"] - md["full_start_tithi"]
            )
            antardashas = []
            full_antardashas = []
            if full_md_tithis > 0:
                md_lord = md["lord"]
                start_i = (
                    self.ASHTOTTARI_SEQ_BPHS.index(md_lord) + 1
                ) % len(self.ASHTOTTARI_SEQ_BPHS)
                ad_seq = (
                    self.ASHTOTTARI_SEQ_BPHS[start_i:] + self.ASHTOTTARI_SEQ_BPHS[:start_i]
                )
                ad_full_start_tithi = float(md["full_start_tithi"])
                for ad_index, sub in enumerate(ad_seq):
                    ad_tithis = (
                        self.ASHTOTTARI_YEARS_BPHS[sub] / self.ASHTOTTARI_TOTAL_YEARS
                    ) * full_md_tithis
                    ad_full_end_tithi = (
                        float(md["full_end_tithi"])
                        if ad_index == len(ad_seq) - 1
                        else ad_full_start_tithi + ad_tithis
                    )
                    visible_start_tithi = max(
                        ad_full_start_tithi, float(md["start_tithi"])
                    )
                    visible_end_tithi = min(
                        ad_full_end_tithi, float(md["end_tithi"])
                    )
                    ad_full_start = jd_for_offset(ad_full_start_tithi)
                    ad_full_end = jd_for_offset(ad_full_end_tithi)
                    ad_full_start_dt = self._jd_to_local_datetime(ad_full_start)
                    ad_full_end_dt = self._jd_to_local_datetime(ad_full_end)
                    full_antardashas.append(
                        {
                            "lord": sub,
                            "start_jd": float(ad_full_start),
                            "end_jd": float(ad_full_end),
                            "start_date": ad_full_start_dt.strftime(
                                "%Y-%m-%d (%H:%M:%S)"
                            ),
                            "end_date": ad_full_end_dt.strftime(
                                "%Y-%m-%d (%H:%M:%S)"
                            ),
                        }
                    )
                    if visible_end_tithi > visible_start_tithi + 1e-12:
                        visible_start = jd_for_offset(visible_start_tithi)
                        visible_end = jd_for_offset(visible_end_tithi)
                        ad_start_dt = self._jd_to_local_datetime(visible_start)
                        ad_end_dt = self._jd_to_local_datetime(visible_end)
                        antardashas.append(
                            {
                                "lord": sub,
                                "start_jd": float(visible_start),
                                "end_jd": float(visible_end),
                                "full_start_jd": float(ad_full_start),
                                "full_end_jd": float(ad_full_end),
                                "start_date": ad_start_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                                "end_date": ad_end_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                                "full_start_date": ad_full_start_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                                "full_end_date": ad_full_end_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                            }
                        )
                    ad_full_start_tithi = ad_full_end_tithi
            final_timeline.append(
                {
                    "lord": md["lord"],
                    "start_jd": float(start_jd),
                    "end_jd": float(end_jd),
                    "full_start_jd": float(full_start_jd),
                    "full_end_jd": float(full_end_jd),
                    "start_date": start_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                    "end_date": end_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                    "full_start_date": full_start_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                    "full_end_date": full_end_dt.strftime("%Y-%m-%d (%H:%M:%S)"),
                    "clipped_at_tp_start": (
                        md["full_start_tithi"] < md["start_tithi"] - 1e-12
                    ),
                    "clipped_at_tp_end": (
                        md["full_end_tithi"] > md["end_tithi"] + 1e-12
                    ),
                    "full_antardashas": full_antardashas,
                    "antardashas": antardashas,
                }
            )

        return {
            "profile_version": "tithi-ashtottari-annual-v4-jhora-tithi-compression",
            "tp_year": int(tp_year),
            "tp_start_jd": float(tp_start_jd),
            "tp_end_jd": float(tp_end_jd),
            "tp_year_days": float(tpyl_days),
            "tp_year_tithis": float(annual_tithis),
            "compression_basis": "continuous_moon_sun_phase",
            "tp_start_date": self._jd_to_local_datetime(tp_start_jd).isoformat(),
            "tp_end_date": self._jd_to_local_datetime(tp_end_jd).isoformat(),
            "periods": final_timeline,
        }

    def get_active_tithi_ashtottari_at(self, tp_year: int, when_jd: float):
        """Return the annual Aṣṭottarī MD/AD active at a Julian day.

        The interval convention is half-open ``[start_jd, end_jd)``.  The
        exact TP-year endpoint is accepted only for the final MD/AD so a
        caller inspecting a closed report range does not get an empty value.
        """
        schedule = self.get_tithi_ashtottari_md_schedule(tp_year)
        target = float(when_jd)
        periods = schedule.get("periods") or []
        year_end = float(schedule["tp_end_jd"])

        def contains(start: float, end: float) -> bool:
            return start <= target < end or (
                abs(target - year_end) <= 1e-9 and abs(end - year_end) <= 1e-9
            )

        for md in periods:
            if not contains(float(md["start_jd"]), float(md["end_jd"])):
                continue
            active_ad = None
            for ad in md.get("antardashas") or []:
                if contains(float(ad["start_jd"]), float(ad["end_jd"])):
                    active_ad = dict(ad)
                    break
            return {
                "profile_version": schedule["profile_version"],
                "tp_year": int(tp_year),
                "when_jd": target,
                "mahadasha": dict(md),
                "antardasha": active_ad,
            }
        return None


    def _tp_sunrise_window(self, sunrise_mode: str | None = None):
        """Return the sunrise day containing TP, without reusing another mode's cache."""
        if not hasattr(self, "tp_jd_ut"):
            raise RuntimeError("TP nie policzone: brak self.tp_jd_ut")
        mode = sunrise_mode or getattr(self, "sunrise_mode", "center")
        if mode not in {"center", "standard"}:
            raise ValueError("sunrise_mode must be center or standard")
        sr_prev_ut = getattr(self, "tp_sr_prev_ut", None)
        ss_ut      = getattr(self, "tp_ss_ut", None)
        sr_next_ut = getattr(self, "tp_sr_next_ut", None)
        if (mode != getattr(self, "sunrise_mode", "center")
                or any(value is None for value in (sr_prev_ut, ss_ut, sr_next_ut))
                or not sr_prev_ut <= self.tp_jd_ut < sr_next_ut):
            sr_prev_ut, ss_ut, sr_next_ut = self._sr_ss_by_se(self.tp_jd_ut, mode=mode)
        if not sr_prev_ut <= self.tp_jd_ut < sr_next_ut:
            raise ValueError("Sunrise window does not contain TP")
        return sr_prev_ut, ss_ut, sr_next_ut, mode


    def get_hora_schedule_for_tp(self, sunrise_mode: str | None = None, offset_all: int | None = None):
        """24 equal intervals [start,end) between consecutive sunrises; indices 1..24."""
        sr_prev_ut, _, sr_next_ut, mode = self._tp_sunrise_window(sunrise_mode)
        vaara = self.get_vaara_lord_for_tp(sunrise_mode=mode)
        base = self.HORA_LORD_SEQUENCE.index(vaara['lord_code'])
        base = (base + ((offset_all or 0) % 7)) % 7
        bounds = [sr_prev_ut + (sr_next_ut - sr_prev_ut) * i / 24 for i in range(24)]
        bounds.append(sr_next_ut)
        return [
            ("sunrise_day", i + 1, self.HORA_LORD_SEQUENCE[(base + i) % 7], bounds[i], bounds[i + 1])
            for i in range(24)
        ]


    def _compute_detailed_chart_at_jd(self, jd_ut: float, ayanamsa_mode=swe.SIDM_LAHIRI):
        """
        Zwraca dict w tym samym formacie co self.detailed_chart_data,
        policzony dla podanego JD(UT), bez trwałego nadpisywania danych natalnych.
        Wykorzystuje istniejący pipeline (get_complete_astro_details).
        """
        import copy
        swe.set_sid_mode(ayanamsa_mode)

        # JD → UTC yyyy-mm-dd HH:MM:SS
        y, m, d, fr = swe.revjul(jd_ut)
        hh = int(fr)
        mm = int((fr - hh) * 60)
        ss = int((((fr - hh) * 60) - mm) * 60)
        utc_date = f"{y:04d}-{m:02d}-{d:02d}"
        calc_time = f"{hh:02d}:{mm:02d}:{ss:02d}"

        # Restore all natal fields, including derived ascendant/node attributes.
        snap = copy.deepcopy(self.__dict__)

        try:
            # ustaw wejścia dla Twojego pipeline'u (liczymy w UTC!)
            self.utc_date = utc_date
            self.calc_time = calc_time
            # uruchom standardowe liczenie (to powinno wypełnić self.detailed_chart_data)
            self.get_complete_astro_details()
            # skopiuj wynik i zwróć
            return copy.deepcopy(self.detailed_chart_data)
        finally:
            self.__dict__.clear()
            self.__dict__.update(snap)


    def get_muntha_details(self, target_year: int, natal_chart: 'ChartData') -> dict:
        """
        Oblicza pozycję Munthy, jej władcę (Munthesha) oraz jego pełną pozycję w TP.
        """
        # Kroki 1-4 pozostają bez zmian
        completed_years = target_year - natal_chart.birth_year
        natal_asc_sign = natal_chart.detailed_chart_data['AS']['zodiac_sign']
        try:
            natal_asc_sign_index = self.ZODIAC_SIGNS.index(natal_asc_sign)
        except (ValueError, KeyError):
            return {'error': 'Nie można odnaleźć ascendentu natalnego.'}

        muntha_sign_index = (natal_asc_sign_index + completed_years) % 12
        muntha_sign_name = self.ZODIAC_SIGNS[muntha_sign_index]

        tp_asc_sign = self.tp_chart_data['AS']['zodiac_sign']
        try:
            tp_asc_sign_index = self.ZODIAC_SIGNS.index(tp_asc_sign)
        except (ValueError, KeyError):
            return {'error': 'Nie można odnaleźć ascendentu TP.'}
            
        muntha_house_in_tp = (muntha_sign_index - tp_asc_sign_index + 12) % 12 + 1

        # 5. Określ władcę Munthy (Munthesha)
        munthesha_code = self.AS_LORD.get(muntha_sign_name, "N/A")
        munthesha_name = self.PLANET_NAMES.get(munthesha_code, "N/A")

        # 6. Znajdź dom ORAZ ZNAK, w którym znajduje się Munthesha w horoskopie TP
        munthesha_tp_house = "N/A"
        munthesha_tp_sign = "N/A" # Nowa zmienna
        if munthesha_code != "N/A" and self.tp_chart_data.get(munthesha_code):
            munthesha_data = self.tp_chart_data[munthesha_code]
            munthesha_tp_house = munthesha_data.get('house', "N/A")
            munthesha_tp_sign = munthesha_data.get('zodiac_sign', "N/A") # Pobieranie znaku

        # 7. Zwróć wszystkie potrzebne wyniki
        return {
            'muntha_sign': muntha_sign_name,
            'muntha_house': muntha_house_in_tp,
            'munthesha_name': munthesha_name,
            'munthesha_tp_house': munthesha_tp_house,
            'munthesha_tp_sign': munthesha_tp_sign # Dodano znak Muntheshy
        }


    def get_vaara_lord_for_tp(self, sunrise_mode: str | None = None):
        sr_start_ut, _, sr_next_ut, _ = self._tp_sunrise_window(sunrise_mode)

        # lokalny TZ jak w TP
        tzinfo = self.tp_datetime_local.tzinfo

        def _to_local(jd_ut: float):
            y,m,d,fr = swe.revjul(jd_ut)
            hh = int(fr); mm = int((fr-hh)*60); ss = int((((fr-hh)*60)-mm)*60)
            return datetime(y,m,d,hh,mm,ss, tzinfo=pytz.utc).astimezone(tzinfo)

        sr_start_local = _to_local(sr_start_ut)
        sr_next_local  = _to_local(sr_next_ut)

        # weekday(): Mon=0..Sun=6  -> Vaara: Sun=0..Sat=6
        vaara_idx = (sr_start_local.weekday() + 1) % 7
        lord_code = self.WEEKDAY_LORDS[vaara_idx]
        weekday_name_pl = ["Niedziela","Poniedziałek","Wtorek","Środa","Czwartek","Piątek","Sobota"][vaara_idx]

        return {
            "vaara_index": vaara_idx,
            "weekday_name_pl": weekday_name_pl,
            "lord_code": lord_code,
            "lord_name_pl": self.PLANET_NAMES[lord_code],
            "sunrise_start_local": sr_start_local,
            "sunrise_next_local":  sr_next_local,
        }


    def get_hora_lord_for_tp(self, sunrise_mode: str | None = None):
        mode = sunrise_mode or getattr(self, "sunrise_mode", "center")
        schedule = self.get_hora_schedule_for_tp(sunrise_mode=mode)
        which, idx, lord_code, start_ut, end_ut = next(
            row for row in schedule if row[3] <= self.tp_jd_ut < row[4]
        )
        return {
            "method": HORA_METHOD,
            "lord_code": lord_code,
            "which": which,
            "index": idx,
            "start_ut": start_ut,
            "end_ut": end_ut,
            "vaara_lord_code": schedule[0][2],
            "sunrise_mode": mode,
        }

    def tithi_balance_at(self, jd_ut: float):
        """
        Zwraca:
        idx_1_30  – indeks tithi (1..30),
        ruler     – kod planety władcy tithi,
        prev_bd   – JD poprzedniej granicy,
        next_bd   – JD następnej granicy,
        frac_left – ułamek tithi POZOSTAŁY w chwili jd_ut (0..1)

        Granice i władca: ta sama ścieżka co `get_tithi_ashtottari_md_schedule`
        (`_get_tithi_boundaries` + `TITHI_RULERS`).

        The returned balance is the angular part of the current 12-degree
        tithi arc still left.  Boundary times are provenance only; their
        clock-time ratio is not the dasha balance.
        """
        idx = self.tithi_index_1_30(jd_ut)
        ruler = self._tithi_ruler_from_index(idx)
        prev_bd, next_bd = self._get_tithi_boundaries(jd_ut)
        if prev_bd is None or next_bd is None or not (prev_bd <= jd_ut < next_bd):
            raise RuntimeError("Nie udało się wyznaczyć granic tithi dla tej chwili.")
        # JHora/PVR balance: angular fraction of the 12-degree tithi arc left.
        # Do not use the fraction of clock time between tithi boundaries; the
        # Moon's changing speed makes that a different quantity.
        elongation = self._get_sidereal_elongation(jd_ut)
        frac_left = 1.0 - ((elongation % 12.0) / 12.0)
        # At the exact boundary a new tithi has just begun.
        if frac_left <= 1e-12:
            frac_left = 1.0
        return idx, ruler, prev_bd, next_bd, frac_left


    def get_planet_motion(self, jd_ut: float, planet_id: int) -> str:
            """
            Sprawdza, czy planeta jest w retrogradacji (R), w ruchu prostym (D) czy stacjonarna (S).
            
            Args:
                jd_ut (float): Data juliańska w UTC.
                planet_id (int): Identyfikator planety z biblioteki swisseph (np. swe.MARS).

            Returns:
                str: 'R' dla retrogradacji, 'D' dla ruchu prostego, 'S' dla stacji.
            """
            # Oblicz pozycję i prędkość planety
            # SEFLG_SPEED sprawia, że obliczenia są zoptymalizowane pod kątem prędkości
            planet_data = swe.calc_ut(jd_ut, planet_id, swe.FLG_SPEED)
            
            # Prędkość wzdłuż ekliptyki to czwarty element (indeks 3)
            longitude_speed = planet_data[0][3]
            
            # Sprawdź znak prędkości
            if abs(longitude_speed) < 0.0001:  # Mały próg na stacjonarność
                return "S"
            elif longitude_speed < 0:
                return "R"
            else:
                return "D"


    def get_jaimini_karakas(self):
        karaka_labels = ['AK', 'AmK', 'BK', 'MK', 'PiK', 'GK', 'DK']  # skróty z obrazka
        jaimini_planets = ['SU', 'MO', 'MA', 'ME', 'JU', 'VE', 'SA']

        # Pobieramy tylko stopnie W ZNAKU (0°–30°), zgodnie z Jaimini klasycznym
        planet_degrees = {
            p: self.detailed_chart_data[p]['position_degrees'] % 30  # <--- KLUCZOWA ZMIANA
            for p in jaimini_planets
        }

        # Sortujemy po stopniach malejąco
        sorted_planets = sorted(planet_degrees.items(), key=lambda x: x[1], reverse=True)

        karakas = {}
        for i, (planet_code, deg) in enumerate(sorted_planets):
            karaka_label = karaka_labels[i]
            karakas[karaka_label] = {
                'planet': self.PLANET_NAMES.get(planet_code, planet_code),
                'code': planet_code,
                'degrees_in_sign': round(deg, 2),
                'zodiac_sign': self.detailed_chart_data[planet_code]['zodiac_sign'],
                'nakshatra': self.detailed_chart_data[planet_code]['nakshatra']
            }

        return karakas


    def calculate_indu_lagna(self):
        # Punktowe wartości planet zgodnie z klasyczną metodą
        planet_points = {
            'SU': 30,  # Słońce
            'MO': 16,  # Księżyc
            'MA': 6,   # Mars
            'ME': 8,   # Merkury
            'JU': 10,  # Jowisz
            'VE': 12,  # Wenus
            'SA': 1    # Saturn
        }

        # Sprawdź, czy dane dla Ascendentu i Księżyca są dostępne
        if 'AS' not in self.detailed_chart_data or 'MO' not in self.detailed_chart_data:
            raise ValueError("Brak danych o Ascendencie lub Księżycu – najpierw uruchom get_complete_astro_details().")

        # Pobierz znaki Ascendentu i Księżyca
        lagna_sign = self.detailed_chart_data['AS']['zodiac_sign']
        moon_sign = self.detailed_chart_data['MO']['zodiac_sign']

        # Znajdź 9. znak od Lagny i Księżyca
        lagna_index = self.ZODIAC_SIGNS.index(lagna_sign)
        moon_index = self.ZODIAC_SIGNS.index(moon_sign)

        ninth_from_lagna = self.ZODIAC_SIGNS[(lagna_index + 8) % 12]
        ninth_from_moon = self.ZODIAC_SIGNS[(moon_index + 8) % 12]

        # Władcy 9. domów
        lord_from_lagna = self.AS_LORD[ninth_from_lagna]
        lord_from_moon = self.AS_LORD[ninth_from_moon]

        # Punkty z tabeli
        points_lagna = planet_points.get(lord_from_lagna, 0)
        points_moon = planet_points.get(lord_from_moon, 0)

        total_points = points_lagna + points_moon
        remainder = total_points % 12

        # Oblicz Indu Lagnę
        if remainder == 0:
            indu_lagna_index = (moon_index - 1) % 12
        else:
            indu_lagna_index = (moon_index + remainder - 1) % 12

        indu_lagna_sign = self.ZODIAC_SIGNS[indu_lagna_index]

        # Zapisz wynik w strukturze danych
        self.detailed_chart_data['INDU_LAGNA'] = {
            'zodiac_sign': indu_lagna_sign,
            'from_moon': remainder if remainder != 0 else 12,
            'total_points': total_points,
            'lord_from_lagna': self.PLANET_NAMES[lord_from_lagna],
            'lord_from_moon': self.PLANET_NAMES[lord_from_moon]
        }

        return self.detailed_chart_data['INDU_LAGNA']
    


