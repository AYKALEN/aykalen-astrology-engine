"""Date boundaries measured by solar arcs, independent of a particular dasa.

Rao section 18.6. The injected longitude function fixes sidereal/tropical and
ephemeris conventions explicitly. No global ephemeris settings are changed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math


def jd_to_utc(jd: float) -> str:
    return (datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
            + timedelta(days=jd - 2451545.0)).isoformat(timespec="microseconds")


class SolarArcCalendar:
    """A bounded root solver with a per-instance cache; not an average-day calendar."""

    def __init__(self, epoch_jd: float, longitude, *, mean_year_days: float = 365.25636):
        if not math.isfinite(epoch_jd) or not 360 < mean_year_days < 370:
            raise ValueError("Invalid epoch or search estimate.")
        self.epoch_jd = epoch_jd
        self.longitude = longitude
        self.mean_year_days = mean_year_days  # brackets only; never the final dates
        self.origin = float(longitude(epoch_jd)) % 360
        if not math.isfinite(self.origin):
            raise ValueError("Non-finite solar longitude at epoch.")
        self._cache = {0.0: epoch_jd}

    def at_years(self, years: float) -> float:
        if isinstance(years, bool) or not isinstance(years, (int, float)) or not math.isfinite(years) or not 0 <= years <= 144:
            raise ValueError("Solar-arc offset must be in 0..144 years.")
        key = float(years)
        if key in self._cache:
            return self._cache[key]
        target = (self.origin + 360 * years) % 360
        estimate = self.epoch_jd + years * self.mean_year_days

        def residual(jd):
            value = float(self.longitude(jd))
            if not math.isfinite(value):
                raise ValueError("Non-finite solar longitude.")
            return (value - target + 180) % 360 - 180

        lo, hi = estimate - 8, estimate + 8
        if not residual(lo) < 0 < residual(hi):
            raise ValueError("Cannot bracket solar boundary with the selected convention.")
        for _ in range(60):
            mid = (lo + hi) / 2
            if residual(mid) >= 0:
                hi = mid
            else:
                lo = mid
            if (hi - lo) * 86400 < 0.01:
                break
        result = (lo + hi) / 2
        self._cache[key] = result
        return result
