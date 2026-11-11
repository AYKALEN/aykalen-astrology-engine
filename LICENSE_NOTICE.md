# AYKALEN Astrology Engine

Deterministyczny silnik obliczeń astrologicznych AYKALEN. Przyjmuje jawne dane JSON i zwraca dane JSON; nie zawiera danych klientów, promptów, modeli AI ani interpretacji raportowych.

## Licencja

Kod tego repozytorium jest udostępniony na licencji GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`).

Silnik wykorzystuje `pyswisseph`, binding Swiss Ephemeris. Swiss Ephemeris jest oprogramowaniem dual-licensed: AGPL lub Swiss Ephemeris Professional License Astrodienst. Uruchomienie tego silnika jako dostępnej przez sieć usługi wymaga spełnienia obowiązków AGPL albo uzyskania licencji profesjonalnej Swiss Ephemeris.

Nie dołączamy plików danych ephemerid Swiss Ephemeris. Instalacja może wskazać własny lokalny katalog przez `ephemeris_path`.

Szczegóły interfejsu i lokalnego uruchomienia: [`README.md`](README.md).
