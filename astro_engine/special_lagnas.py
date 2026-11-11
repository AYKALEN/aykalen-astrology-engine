"""Pure Hora/Ghati Lagna calculation from an explicitly selected sunrise.

Rao textbook sections 5.3-5.4. Astronomy and sunrise convention are the
caller's responsibility, so these functions also work without Swiss Ephemeris.
"""
from __future__ import annotations

import math


def hora_ghati_lagnas(*, moment_jd: float, sunrise_jd: float,
                     next_sunrise_jd: float, sun_longitude_at_sunrise: float) -> dict:
    values = (moment_jd, sunrise_jd, next_sunrise_jd, sun_longitude_at_sunrise)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise ValueError("Finite numeric JD and longitude values are required.")
    if not sunrise_jd <= moment_jd < next_sunrise_jd or not 0 < next_sunrise_jd - sunrise_jd < 2:
        raise ValueError("Sunrise interval must contain the moment: [sunrise,next_sunrise).")
    if not 0 <= sun_longitude_at_sunrise < 360:
        raise ValueError("Sun longitude must be in [0,360).")
    minutes = (moment_jd - sunrise_jd) * 1440
    return {
        "HL": (sun_longitude_at_sunrise + minutes / 2) % 360,
        "GL": (sun_longitude_at_sunrise + minutes * 1.25) % 360,
        "elapsed_minutes": minutes, "sunrise_jd": sunrise_jd,
        "next_sunrise_jd": next_sunrise_jd,
        "sun_longitude_at_sunrise": sun_longitude_at_sunrise,
    }
