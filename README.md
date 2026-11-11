# AYKALEN Astrology Engine

A deterministic astrology calculation engine for AYKALEN. It accepts an explicit JSON request and returns JSON data for a natal chart and, when requested, a Tithi Pravesha (TP) year.

It does **not** contain client records, report prompts, AI calls, life interpretation, editorial logic, PDF rendering, or API keys.

## Scope

The public interface is `astro_engine.calculate(request)`. It serializes access to the process-global Swiss Ephemeris configuration and returns calculation metadata with the result.

The engine provides, where requested:

- planetary and ascendant positions, whole-sign houses, nakshatras, dispositors, dignities, and Parashari sign aspects;
- natal and TP charts including D1, D2 variants, D3–D12 where implemented, D16, D20, D24, D27, D30, D40, D45, and D60;
- house lords, Jaimini karakas, Indu Lagna, tithi and dagdha rasi;
- Vimshottari MD/AD/PD, Tithi Ashtottari periods, TP boundaries, Hora Lord, and Vara Lord;
- selected optional research profiles, returned with their explicit limitations.

The calculation result identifies its own conventions through `calculation_profile`, `scope`, `limitations`, and `ephemeris` fields. Producing a chart does not establish that every available varga or research profile is suitable for interpretation.

## Installation

Python 3.11 is the reference runtime.

```powershell
python -m pip install -r requirements.txt
```

Dependencies:

- `pyswisseph`
- `pytz`
- `python-dateutil`

Swiss Ephemeris data files are deliberately not bundled. Pass a local directory through `ephemeris_path` when required. The response states the ephemeris backend actually used; do not assume that external Swiss data files were used unless the returned flags confirm it.

## CLI

The included CLI reads a UTF-8 JSON file or standard input and writes JSON to standard output.

```powershell
python -X utf8 -B engine.py --input example.synthetic.json
```

Optional output writes only to a new path and never overwrites an existing file:

```powershell
python -X utf8 -B engine.py --input example.synthetic.json --output result.json
```

Use `--input -` to read JSON from standard input. Invalid input returns exit code `2` without writing a partial result.

## Python API

```python
import json
from astro_engine import calculate

with open("example.synthetic.json", encoding="utf-8") as source:
    result = calculate(json.load(source))
```

## Request contract

Required `birth` fields are:

```json
{
  "date": "1990-01-01",
  "time": "12:00:00",
  "timezone": "Europe/Warsaw",
  "latitude": 52.2297,
  "longitude": 21.0122
}
```

Additional request fields:

- `target_year`: optional TP target year. Without it, the result contains natal calculations and Vimshottari data.
- `allowed_vargas`: an explicit list of accepted charts that includes `D1`. The default is `D1` only.
- `sunrise_mode`: `center` (default) or `standard`.
- `ephemeris_path`: optional local directory of Swiss Ephemeris data files.
- `techniques`: optional list of enabled research profiles. `rao_hora_finance_2003_v1` requires `target_year`, `D1`, and `D2_kashinatha`.

The engine requires exact coordinates and an IANA timezone or `UTC`; it does not geocode locations or guess timezones. It rejects ambiguous and nonexistent DST local times, latitudes outside ±66°, birth years outside 1800–2398, and unsupported target years.

`target_year` currently means the year of the Sun's ingress into the natal sidereal sign. It is not necessarily the calendar year in which the returned TP starts. Always use `annual.start_utc` and `annual.end_utc` as the actual interval.

## Conventions and limitations

- Main profile: Lahiri ayanamsha, true node, whole-sign houses, and TP calculated for the birth coordinates.
- Hora: 24 equal intervals from one sunrise to the next. The schedule uses `[start, end)` intervals and preserves the Vara determined by the preceding sunrise.
- `D2_kashinatha`, `D5`, `D6`, `D8`, and `D11_iyer` are explicit variants. Use the exact API identifiers rather than generic chart names where an ambiguity exists.
- The full Shadbala result is intentionally marked incomplete. The engine does not manufacture a combined score.
- Historical Vimshottari conventions were retained; they were not recalibrated during extraction.
- The Rao finance profile is experimental and returns `ready_for_interpretation=false`.

No result is a prediction or a recommendation. A separate interpretation layer must assess source qualification, uncertainty, and domain meaning.

## Repository boundary

This repository is the public calculation boundary. A reporting or product layer should consume the JSON contract and must not add prompts, client data, AI orchestration, or interpretation to `astro_engine`.

The current AYKALEN private reporting repository references this engine as a Git submodule. A network-facing deployment should expose this contract through a dedicated calculation service and identify the exact public source revision used by that service.

## Tests

```powershell
python -X utf8 -B -m unittest discover -s tests -v
```

Tests use synthetic data. They cover input validation, selected numerical boundaries, time consistency, requested vargas, output serialization, and portable-folder execution. They do not prove the predictive validity of any astrological method or universal agreement with other astrology software.

## License

This repository is licensed under **GNU Affero General Public License v3.0 or later**. See [LICENSE](LICENSE).

It uses `pyswisseph`, a binding for Swiss Ephemeris. Swiss Ephemeris is dual-licensed under AGPL or the Swiss Ephemeris Professional License from Astrodienst. Before distributing or operating a network service, ensure that the selected licensing path and all attribution/source obligations are satisfied.
