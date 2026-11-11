# Silnik — samodzielny silnik danych astrologicznych

Ten folder można skopiować do nowego projektu. Nie potrzebuje `10_ENGINE`,
badań, standardów analizy, katalogów semantycznych ani poprzednich raportów.
Przyjmuje jawne dane wejściowe i zwraca JSON. Nie interpretuje życia klienta,
nie wywołuje AI i nie potrzebuje klucza API.

To wydzielenie istniejących obliczeń, nie nowa metodologia ani potwierdzenie
poprawności wszystkich odziedziczonych konwencji. Oryginały pozostają w starym projekcie.

## Szybki start

Python 3.11. Zależności: `pyswisseph`, `pytz`, `python-dateutil`.
W obecnym środowisku są już zainstalowane. Na nowym komputerze, po przygotowaniu
środowiska, zależności instaluje się z `requirements.txt`.

Z katalogu `engine`:

```powershell
python -X utf8 -B engine.py --input example.synthetic.json
```

To przykład syntetyczny, nie dane klienta. Wynik trafia na standardowe wyjście.
Opcjonalne `--output <nowy_plik.json>` zapisuje nowy plik; nigdy nie nadpisuje istniejącego.
`--input -` czyta JSON ze standardowego wejścia. Błędne dane kończą wykonanie kodem 2,
bez zapisywania częściowego wyniku.

Z Pythona, gdy `engine` jest katalogiem roboczym lub znajduje się w ścieżce importu:

```python
import json
from astro_engine import calculate

with open("example.synthetic.json", encoding="utf-8") as source:
    data = calculate(json.load(source))
```

## Dane wejściowe

- `birth`: data `YYYY-MM-DD`, czas `HH:MM:SS`, strefa IANA lub `UTC`, szerokość
  i długość geograficzna. Współrzędne są obowiązkowe; nie ma geokodowania ani bazy miast.
- `target_year`: opcjonalny rok dla TP. Bez niego eksport zawiera natal i Viṃśottarī.
- `allowed_vargas`: jawna lista dopuszczonych wykresów, zawierająca `D1`.
  Domyślnie tylko `D1`. To deklaracja użytkownika, nie automatyczna rektyfikacja.
- `sunrise_mode`: `center` (domyślnie) lub `standard`.
- `ephemeris_path`: opcjonalny katalog lokalnych plików Swiss Ephemeris.
- `techniques`: opcjonalne `[]` (domyślnie) lub `["rao_hora_finance_2003_v1"]`.
  Ten profil badawczy wymaga `target_year`, `D1` i `D2_kashinatha`.

Eksporter obsługuje lata urodzenia 1800–2398 i rok docelowy od roku urodzenia
do 2398, o ile mieści się w zaimplementowanym cyklu Viṃśottarī. Odrzuca
niejednoznaczne/nieistniejące godziny podczas zmiany czasu oraz szerokości
poza ±66°. Nie zgaduje strefy ani wariantu DST.

**Ważne: odziedziczony `target_year` oznacza rok ingresu Słońca do natalnego
znaku syderycznego, nie zawsze rok kalendarzowy samego powrotu TP.**
Dla niektórych urodzeń styczniowych `2026` daje powrót w styczniu 2027.
Rzeczywisty zakres jest w `annual.start_utc` / `annual.end_utc`.
Przed automatycznym zamawianiem raportów „na rok 2026” trzeba osobno ustalić
docelową politykę wyboru powrotu; tej metodologii nie zmieniano podczas wydzielenia.

## Co jest dostępne

Wersja `0.5.2` przyjmuje 24 równe hory od wschodu do następnego wschodu
zamiast poprzedniego podziału dnia i nocy osobno na 12 części. Konwencja jest
jawna w wyniku; szczegóły w sekcji poniżej. Pozycje planet, moment TP oraz
algorytmy daś pozostają bez zmian.

Wersja `0.5.0` dodaje opcjonalne obliczenia finansowej metody Rao; szczegóły
i ograniczenia poniżej. Nie zmienia wcześniejszych algorytmów wykresów.

- D1: dokładne długości planet i ascendentu, znaki, domy whole-sign, nakṣatry,
  pady, ruch; węzeł prawdziwy i kontrolne położenie średniego.
- Natal i TP: D2 Parāśara, D2 Parivṛtti, D2 Kāśinātha, D3, D4, D5, D6, D7, D8, D9, D10, D11 Iyera, D12, D16,
  D20, D24, D27, D30, D40, D45, D60. Nazwy kluczy odpowiadają `VARGAS` w `api.py`.
- Władcy domów, dyspozytorzy, godności znakowe i aspekty Parāśari całoznakowe.
- Tithi z granicami i saldem, dagdha rāśi; siedem karak Jaimini i Indu Lagna.
- TP: moment powrotu, Hora Lord, Vaara Lord, harmonogram 24 hor,
  geometryczna odległość natalnej Lagny od Lagny TP w wybranych wykresach.
  Sama odległość nie otrzymuje interpretacji ani wagi.
- Natalna Viṃśottarī MD/AD/PD: jeden cykl, pełne granice UTC oraz okna roku TP.
- Roczna Tithi Aṣṭottarī MD/AD z kompresją w jednostkach tithi i pełnymi
  granicami okresów źródłowych oraz widokiem przyciętym do roku TP.
- Składowe Śaḍbali, z jawnym statusem niekompletności i nierozstrzygniętymi wartościami.

`calculation_profile`, `scope`, `limitations` oraz flagi `ephemeris` opisują
konwencje wyniku. Eksporter nie przycina danych do wybranej dziedziny życia.
Wyższe vargi można obliczyć technicznie; ich dopuszczenie do analizy wymaga
odpowiednio ustalonej godziny urodzenia.

## Hora Lord i Vāra Lord — od wersji 0.5.2

Hora ma długość `(następny_wschód − poprzedni_wschód) / 24`. Pierwszą horą
rządzi władca dnia tygodnia wyznaczonego przez poprzedni wschód. Kolejność:
Saturn → Jowisz → Mars → Słońce → Wenus → Merkury → Księżyc, cyklicznie.
Zachód Słońca nie rozdziela harmonogramu; hora nie musi mieć dokładnie 60 minut.
Źródło: P.V.R. Narasimha Rao, *Vedic Astrology: An Integrated Approach*,
§1.3.11, s. 17 ([PDF, strona 29](https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf#page=29)).

- Identyfikator `sunrise_to_sunrise_24_equal_v1` trafia do
  `calculation_profile.hora_method` i `annual.hora.method`, a przez adapter do
  pakietów raportu.
- `annual.hora.index` i indeksy w `annual.hora_schedule` mają zakres **1–24**,
  `which` / pierwszy element wiersza harmonogramu to `sunrise_day` (doba od
  wschodu; nie oznaczenie światła dziennego). Wiersz zachowuje pięć elementów:
  `[which, index, lord_code, start_ut, end_ut]`. Granice są JD UT.
- Przedziały są `[start,end)`: dokładna granica należy do nowej hory, następny
  wschód rozpoczyna nową dobę i horę nr 1 z nowym władcą dnia.
  Ponowne wyznaczenie tego samego wschodu Swiss Ephemeris może różnić się
  o ułamek milisekundy; porównanie samego zdarzenia wschodu ma tolerancję
  numeryczną 0,01 s. Nie jest to tolerancja czasu urodzenia ani przesunięcie
  wszystkich granic hór. Wyszukiwanie uwzględnia także doby od wschodu
  dłuższe niż 24 h.
- `sunrise_mode=center` lub `standard` wybiera konwencję samego wschodu,
  a nie podział hor. Jawne nadpisanie trybu nie korzysta z cache innego trybu.
- Vāra nadal wynika z dnia poprzedniego wschodu. Zmiana hory nie zmienia
  długości planet, ascendentów ani obliczeń Tithi Aṣṭottarī.

Wyniki silnika do `0.5.1` włącznie zachowują wcześniejszą konwencję: osobno
12 części dnia i 12 części nocy, `which=day/night`, indeksy 1–12. Nie nadpisujemy
historycznych wyników. Nowa wersja silnika wymaga nowego przebiegu i właściwej
weryfikacji danych; nie przepisujemy automatycznie starych dowodów stabilności
ani nie mieszamy wyników przy wznowieniu.

## D2 Kāśinātha Hora — od wersji 0.4.0

Jawny klucz `D2_kashinatha`, np. `allowed_vargas=["D1", "D2_kashinatha"]`.
Obliczenia natalne i TP korzystają z dokładnych długości D1, wspólnego eksportu
domów, władztw, dyspozytorów, godności, aspektów i relacji Lagn. Węzeł prawdziwy
pozostaje podstawą, średni — kontrolą. Bez wymyślonych stopni w wardze.
Alias `hora_chart_data` i dotychczasowe `D2_parashara` / `D2_parivritti` nie zmieniają znaczenia.

Reguła: w znakach nieparzystych pierwsza połowa należy do Słońca, druga do
Księżyca; w parzystych odwrotnie. Hora słoneczna wybiera dzienny znak władcy
znaku D1, księżycowa — nocny. Dla obu świateł parą jest Lew/Rak.
Przedziały `[0°,15°)` i `[15°,30°)`; 15° należy do drugiej połowy.

| Znak D1 | Pierwsza połowa → | Druga połowa → |
|---|---|---|
| Baran | Skorpion | Baran |
| Byk | Byk | Waga |
| Bliźnięta | Panna | Bliźnięta |
| Rak | Rak | Lew |
| Lew | Lew | Rak |
| Panna | Bliźnięta | Panna |
| Waga | Waga | Byk |
| Skorpion | Baran | Skorpion |
| Strzelec | Ryby | Strzelec |
| Koziorożec | Koziorożec | Wodnik |
| Wodnik | Wodnik | Koziorożec |
| Ryby | Strzelec | Ryby |

Źródło: P.V.R. Narasimha Rao,
[Personal Finances from Hora Chart](https://www.vedicastrologer.org/articles/hora.pdf),
2003, strony 1–3 PDF. Dokument wyjaśnia konkretny wariant, nie zgodność wszystkich
szkół Hory. Zastosowanie do TP i relacji natal–TP jest konwencją AYKALEN.
Ta zmiana nie dodaje Hora Narayana Daśā ani nowej metody timingu.

## D5 i D6 — od wersji 0.3.0

D5 i D6 należą do pełnego kanonu AYKALEN. Są dostępne przez `allowed_vargas`
dla natalu i TP, z Lagną, domami, aspektami, władztwami i odległością natal → TP.
Jak pozostałe wykresy wymagają osobnej kwalifikacji dokładności w warstwie raportu.

- D5: pięć równych części po 6°. W znakach nieparzystych kolejno Baran, Wodnik,
  Strzelec, Bliźnięta, Waga; w parzystych Byk, Panna, Ryby, Koziorożec, Skorpion.
  Zastępuje wcześniej nieużywany wariant eksperymentalny oparty na modalności.
- D6: sześć równych części po 5°, od Barana w znakach nieparzystych i od Wagi
  w parzystych, zgodnie z kolejnością zodiaku. Reguła była już obecna w kodzie.
- Przedziały `[start,end)`, dokładne długości wejściowe, zachowane oba warianty
  węzłów. Testy sprawdzają wszystkie części, granice i sąsiednie liczby zmiennoprzecinkowe.

Źródło reguł D5/D6: P.V.R. Narasimha Rao,
[Vedic Astrology: An Integrated Approach](https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf),
§6.2.5–6.2.6, drukowana strona 54. Pozostałych zatwierdzonych wzorów nie zmieniono.

## D8 i D11 Iyera — od wersji 0.2.0

Oba wykresy można jawnie zamówić przez `allowed_vargas`, np.
`["D1", "D8", "D11_iyer"]`. Powstają dla natalu i TP, wraz z ascendentami,
domami whole-sign i inkluzywną odległością natal → TP. Warianty są opisane
w `calculation_profile.varga_methods`, jeśli zostały wybrane. Samo `D11`
jest odrzucane, aby nie mieszać metod obliczeń.

- **D8:** osiem równych części po 3°45′. Dla znaków ruchomych pierwsza część
  przypada na Barana, dla stałych na Strzelca, dla podwójnych na Lwa;
  dalsze części biegną w kolejności zodiakalnej.
- **D11_iyer:** jedenaście równych części po dokładnie 30°/11. W każdym znaku
  D1 pierwsza część przypada na Barana; dalsze biegną wstecz: Ryby, Wodnik,
  Koziorożec, Strzelec, Skorpion, Waga, Panna, Lew, Rak, Bliźnięta. Byk
  nie otrzymuje żadnej części. Nie jest to wariant Rudrāṃśa z początkiem
  zależnym od znaku D1.

Źródła reguł: H.R. Seshadri Iyer, *New Techniques of Prediction*, tom II,
rozdział III ([tekst źródłowy](https://www.scribd.com/document/348090352/H-R-Seshadri-Iyer-New-Techniques-of-Prediction-vol-2-pdf));
D8 również P.V.R. Narasimha Rao, *Vedic Astrology: An Integrated Approach*,
§6.2.8 ([podręcznik autora](https://vedicastrologer.org/articles/vedic_astro_textbook.pdf#page=66)).

Obliczenia wykorzystują pełne długości źródłowe i przedziały `[początek,koniec)`;
nie zaokrąglają szerokości D11 do minut ani sekund. Węzeł prawdziwy pozostaje
wariantem głównym, a różnica znaków względem średniego jest oznaczana istniejącą
flagą. Rāhu i Ketu mogą zajmować ten sam znak D8 i D11 Iyera — nie wymuszamy
opozycji przeniesionej z D1.

Dodanie obliczeń nie zmienia zestawu źródeł rozdziałów w `reporting/`, promptów,
timingu ani poprzednich analiz. Wersja silnika wzrosła do 0.2.0, żeby nowe
wyniki miały jawne pochodzenie. Weryfikacja zewnętrznym programem musi
uwzględniać wybrany wariant, ayanāṃśę i rodzaj węzłów.

## Profil badawczy Rao — od wersji 0.5.0

Do jawnego wejścia można dodać:

```json
{
  "allowed_vargas": ["D1", "D2_kashinatha"],
  "target_year": 2024,
  "techniques": ["rao_hora_finance_2003_v1"]
}
```

To fragment konfiguracji: nadal wymagane są pełne dane `birth`. Wynik
`techniques.rao_hora_finance_2003_v1` zawiera dane natalne Hory, kāryeśę,
aspekty znakowe, arudhy, HL/GL i Nārāyaṇa MD/AD/PD. Rok TP wyznacza okno;
nie uruchamia rocznej kompresji tej natalnej daśy.

Funkcje w `rasi_rules.py`, `arudha.py`, `special_lagnas.py`, `narayana.py`
i `solar_calendar.py` są wspólne i przyjmują jawne parametry. Wyboru dla
metody finansowej dokonuje `hora_finance.py`. Żaden moduł nie wywołuje AI.
Nie jest to uniwersalna zgoda na stosowanie tych samych reguł w każdej wardze.

**Profil jest eksperymentalny; surowy wynik zwraca `ready_for_interpretation=false`.**
Od wersji `0.5.1` moduł `pachakadi.py` dodaje pełne tabele 55–57 Ratha
(wariant `rath_narayana_2004_tables_55_57`), oddzielając relacje naturalne
od pozycyjnych. Wersja techniki: `0.2.0`. Różnica dwóch ról Wenus względem
„Crux” jest jawna, podobnie jak rozbieżność rachunkowa przykładu GL.
Nowe punkty nie otrzymują automatycznej kwalifikacji stabilności; gotowość
konkretnego pakietu testowego wymaga osobnego, zapisanego sprawdzenia.
[Karta techniki](../knowledge/techniques/finance/rao_hora_2003.md)
opisuje źródła, warianty i ograniczenia.

Nowy kalendarz używa łuków Słońca i `FLG_SIDEREAL` (Lahiri, bez nutacji).
Szacunkowa długość roku służy tylko znalezieniu przedziału dla rozwiązania
numerycznego. Dotychczasowe dane natalu i TP zachowują stare konwencje.
`reporting/` nie przekazuje jeszcze tego profilu do interpretacji.

Brak `techniques` zachowuje wcześniejszy zakres eksportu. Zmiana wersji jest
jawna; nie przepisuj hashy klientów ani nie wznawiaj starych przebiegów z
nowymi obliczeniami. Testy: `python -X utf8 -B -m unittest discover -s engine/tests`.

## Ważne ograniczenia odziedziczonych obliczeń

- Profil główny: Lahiri, węzeł prawdziwy, whole-sign, TP dla współrzędnych urodzenia.
  Nie zaimplementowano osobnego miejsca pobytu w chwili TP w tym eksporterze.
- Plików efemeryd nie dołączono. Obecne testy używają wbudowanego Moshiera;
  JSON ujawnia rzeczywisty backend. Nie należy opisywać go jako obliczeń na
  zewnętrznych plikach Swiss, jeśli flagi tego nie potwierdzają.
- Pełna Śaḍbala nie jest gotowa: brakuje kompletnego Sthāna, Kāla i Ceṣṭā.
  Dṛk może pozostać nierozstrzygnięta bez kwalifikacji Merkurego. Nie ma pozornej sumy.
- Viṃśottarī zachowuje starszą konwencję podziału pozostałego salda pierwszej MD
  na AD/PD oraz rok 365,25 dnia. Nie była tu ponownie kalibrowana źródłowo.
- Pozycje TP są liczone dla czasu obciętego do pełnej sekundy; JD powrotu jest
  dokładniejszy. Karaki sortują odziedziczone pozycje zaokrąglone do 0,01°.
- Godności wykorzystują przyjaźnie naturalne, nie pełną przyjaźń pięciostopniową.
  Ruch `R` węzłów jest konwencją, nie pomiarem prędkości prawdziwego węzła.
- Nie ma pełnego pañcāṅga, Aṣṭakavargi, Guliki ani Māndiego — te obliczenia
  nie były dostępne w wydzielanym silniku.

Zachowano również opcjonalne pomocnicze obliczenia w kodzie: eksperymentalne
Starsze profile spalania, kazimi, graha-yuddha i nīca-bhaṅga w `facts.py`
oraz uproszczoną Viṃśopakę w `vimsopaka.py`. **Nie są domyślnym sygnałem JSON.**
Nie przywracają technik wyłączonych z analizy rocznej. W odziedziczonym profilu
Daśavargi wagi sumują się do 21 zamiast 20; wynik punktowy jest zablokowany
(`UNRESOLVED`), bez arbitralnego poprawiania wag.

## Pliki i granica odpowiedzialności

- `engine.py`: wejście/wyjście JSON, bez rejestru klientów.
- `astro_engine/api.py`: walidacja, pakiet natal/TP, zakres eksportu i metadane.
- `astro_engine/core.py`: pozycje, vargi, TP, tithi, Hora/Vaara, Tithi Aṣṭottarī.
- `astro_engine/facts.py`, `timing.py`, `shadbala.py`, `vimsopaka.py`: wydzielone obliczenia pomocnicze.
- `tests/`: wyłącznie dane syntetyczne, testy obliczeń i izolacji folderu.

Źródło wydzielenia: lokalne wersje `natal.py`, `mapa_enrichment.py`, `shadbala.py`
i `vimsopaka.py` z `10_ENGINE/silnik`, 2026-10-26. Drzewo źródłowe zawierało
niezatwierdzone zmiany; nie jest to kopia wyłącznie wersji z HEAD.
Usunięto zależności od klientów, CSV, wydruków, dokumentów i starej narracji.
Poprawki techniczne dotyczą walidacji stref/DST, odtworzenia stanu natalnego,
okna ingres–egress przez styczeń, domyślnego offsetu Hora i blokad niepełnych wyników.

Nie ma tu badań, promptów, standardów dziedzin, wag predykcyjnych, katalogów
znaczeń, heurystycznego rankingu jog, agentów, redaktora ani raportów.
Nową warstwę analizy należy budować jako konsumenta JSON, nie dopisywać jej do `core.py`.
Bez osobnych procesów nie uruchamiaj równolegle niskopoziomowych funkcji z różnymi
ustawieniami Swiss Ephemeris; publiczne `calculate()` serializuje własne wywołania.

Prawdziwe dane w tym repozytorium zapisuj wyłącznie w ignorowanym
`clients.local/` (aktualne przypadki), `cases.local/` (wcześniejsze przypadki)
w głównym katalogu projektu lub przekazuj przez zmienne środowiskowe/stdin.
Nie wkładaj danych, wyników klientów ani kluczy do przenoszonego folderu `engine`.
Biblioteki pozostają osobnymi zależnościami; przed dystrybucją produktu sprawdź ich licencje.

## Testy

Z katalogu `engine`:

```powershell
python -X utf8 -B -m unittest discover -s tests -v
```

Testy obejmują wejście, wybrane granice obliczeń, spójność osi czasu,
wszystkie eksportowane vargi, brak nadpisywania plików oraz rzeczywiste
uruchomienie kopii folderu poza repozytorium. Nie dowodzą trafności prognoz
ani kompletnej zgodności każdej konwencji z dowolnym programem astrologicznym.
