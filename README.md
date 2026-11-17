# Pocket Operator mobile v17.0

[English documentation](README.en.md)

Pocket Operator mobile to dostępny syntezator 8-bitowy, automat perkusyjny,
16-krokowy sekwencer i prosty looper melodii dla Windows. Program jest napisany
w Pythonie i używa wxPython, NumPy, SoundDevice oraz MIDI przez Mido/RTMidi.

Wersja 16.0 dodaje mapowanie kontrolerów MIDI, obsługę fizycznych przycisków
i enkoderów, polski i angielski interfejs oraz motywy. Zachowuje konsolidację
wszystkich historycznych wariantów projektu (v5.0,
v8.2, v9.0, v11.0, v13.0 i v14.1), naprawia ich rozłączone interfejsy i dodaje
pełny zapis projektów. Interfejs jest projektowany tak, aby dało się go obsłużyć
wyłącznie klawiaturą oraz czytnikiem ekranu.

Wersja 16.1 ujednolica informacje głosowe o zmianach z MIDI i klawiatury
komputerowej. Każde źródło można niezależnie włączyć lub wyłączyć.
Wersja 16.2 dodaje muzyczny Odstrajanie ±2 półtony, nagrywanie jego ruchów oraz
wyłączanie pojedynczych przypisań bez ich usuwania. Gotowe profile AKM322 i NI
są częścią źródeł na GitHubie i każdego portable.
Wersja 17.0 zachowuje kolejność i zaznaczenie edytowanych mapowań, dodaje opcję
„Stosuj zmiany na bieżąco” oraz nowy układ AKM322: gałki 1/2 sterują instrumentem
A/B, enkoder DATA wybiera brzmienie, gałka 3 reguluje jasność filtrem, a kółko
modulacji głębokość vibrato. Poprawiono polskie nazwy instrumentów, warstw,
efektów i perkusji w menu, komunikatach oraz edytorze mapowań.

## Najważniejsze możliwości

- pięć głównych instrumentów: Prostokąt, Piła, Trójkąt, Szum i Perkusja;
- czternaście jednocześnie działających warstw brzmienia;
- trzynaście efektów DSP z osobnymi parametrami A/B;
- prawdziwy tryb Efekt chwilowy: efekt działa podczas trzymania skrótu;
- osiem syntetycznych brzmień perkusyjnych;
- 16-krokowy sekwencer dla wszystkich ośmiu bębnów;
- nagrywanie i zapętlone odtwarzanie melodii;
- wejście MIDI z velocity i obsługą pedału sustain;
- macierz wyboru warstw i efektów sterowanych gałkami;
- zapis Zapamiętywanie ustawień do `po.ini`;
- przenośne projekty `.po15`;
- eksport miksu do WAV bez naruszania dźwięku granego na żywo;
- komunikaty przez `accessible-output2` i pełna obsługa klawiaturą;
- zgodność API ze skryptami przygotowanymi dla starszych wersji.

## Szybki start

### Wydanie portable — bez instalowania Pythona

1. Pobierz aktualny plik ZIP z [wydań GitHub](https://github.com/Pates2004/pocket-operator-mobile/releases).
2. Rozpakuj cały katalog do zapisywalnej lokalizacji.
3. Uruchom `PocketOperator-mobile.exe`.
4. W pierwszym oknie wybierz **zarówno język, jak i motyw**, następnie „Dalej”.

Obie listy początkowo nie mają zaznaczenia. Bez wyboru obu opcji nie można
przejść dalej. Anulowanie lub zamknięcie okna kończy uruchomienie i nie zapisuje
zakończenia konfiguracji; po kolejnym starcie pytanie pojawi się ponownie.
Dotyczy to również aktualizacji ze starszego `po.ini`, który nie zawiera tych opcji.

Ustawienia można później zmieniać w `Ustawienia → Język i motyw...`.
Dostępne motywy: systemowy, jasny i ciemny. Podpowiedzi przy głównej etykiecie
można wyłączyć pozycją `Ustawienia → Pokazuj podpowiedzi`.

### Uruchamianie ze źródeł

1. Zainstaluj 64-bitowy Python 3.10 lub nowszy.
2. W katalogu programu wykonaj:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Uruchom `Graj.bat` albo `python run.py` w przygotowanym środowisku.

`Graj.bat` najpierw używa lokalnego wydania w `Installfiles`, jeśli istnieje.
W przeciwnym razie `Start.ps1` przygotowuje lokalne `.venv`, instaluje brakujące
biblioteki i uruchamia program. Wymaga to Pythona 3.10+ oraz internetu podczas
instalacji bibliotek. Portable działa bez tych wymagań.

Wykryta przyczyna problemu na badanym komputerze: systemowy Python nie miał
bibliotek wxPython, NumPy, SoundDevice, Mido ani SciPy. Wcześniejszy launcher
próbował kolejnych interpreterów bez przygotowania zależności.

### Uruchamianie z terminala

```powershell
python run.py
```

Można również wykonać `python main.py`, ale `run.py` wcześniej sprawdza wersję
Pythona i obecność najważniejszych bibliotek, dlatego jest zalecany.

## Wymagania

- Windows 10 lub Windows 11;
- dla źródeł: Python 3.10 lub nowszy; dla portable nie jest wymagany;
- działające urządzenie wyjściowe audio;
- opcjonalnie: urządzenie wejściowe MIDI;
- opcjonalnie: czytnik ekranu obsługiwany przez `accessible-output2`.

Biblioteki Pythona znajdują się w `requirements.txt`:

- `wxPython` — interfejs Windows;
- `numpy` — generowanie i przetwarzanie próbek;
- `sounddevice` — wyjście PortAudio;
- `mido` i `python-rtmidi` — MIDI;
- `scipy` — zapis WAV;
- `accessible-output2` — komunikaty dla czytnika ekranu.

## Główne instrumenty

| Instrument | Skrót | Charakter i parametr A |
|---|---:|---|
| Prostokąt | `Ctrl+F1` | Fala prostokątna; A zmienia szerokość impulsu. |
| Piła | `Ctrl+F2` | Piła z regulowanym punktem załamania. |
| Trójkąt | `Ctrl+F3` | Trójkąt; A zwiększa nasycenie i zaokrąglenie. |
| Szum | `Ctrl+F4` | Szum; A zmienia wygładzenie/barwę. |
| Perkusja | `Ctrl+F5` | Klawiatura nutowa wyzwala osiem typów bębnów. |

Gałka instrumentu B steruje czasem zaniku i release. W trybie Podtrzymanie dźwięk
jest utrzymywany do zwolnienia klawisza. Po wyłączeniu Podtrzymanie ten sam parametr
określa automatyczny decay.

## Warstwy

Warstwy można łączyć dowolnie. Każda nowa nuta kopiuje aktualny zestaw warstw,
dzięki czemu zmiana zestawu nie ucina już trwających głosów.

| Warstwa | Skrót | Działanie parametru A |
|---|---:|---|
| Oktawa niżej | `Alt+Backtick` | Kopia głównej fali oktawę niżej. |
| Prostokąt subbasowy | `Alt+1` | Prostokątny subbas oktawę niżej. |
| Suboktawa | `Alt+2` | Główna fala odtworzona oktawę niżej. |
| Kwinta | `Alt+3` | Kwinta czysta. |
| Tercja wielka | `Alt+4` | Tercja wielka. |
| Tercja mała | `Alt+5` | Tercja mała. |
| Oktawa wyżej | `Alt+6` | Prostokąt oktawę wyżej. |
| Rozstrojenie | `Alt+7` | Drugi oscylator; A ustala rozstrojenie. |
| Szum | `Alt+8` | Warstwa szumu; A zmienia jej wygładzenie. |
| Cyfrowa | `Alt+9` | Kwantyzowany prostokąt. |
| Harmoniczne | `Alt+0` | Domieszka drugiej i trzeciej harmonicznej. |
| Organy | `Alt+-` | Stos prostokątnych harmonicznych. |
| Winyl | `Alt+=` | Losowe, bipolarne trzaski. |
| Sinusoida subbasowa | `Alt+\` | Sinusoidalny subbas z regulowanym nasyceniem. |

Parametr B każdej warstwy jest jej poziomem w miksie. To celowa poprawka v15:
w starszych wariantach gałka B była widoczna i zapisywana, ale nie miała wpływu
na audio.

### Sterowanie wieloma warstwami

- jeśli nie zaznaczono celu, zmiana gałki warstw obejmuje wszystkie aktywne
  warstwy oraz wartość domyślną;
- jeżeli zaznaczono konkretne cele w menu `Sterowanie`, zmiana obejmuje tylko
  te warstwy;
- wyłączenie warstwy automatycznie usuwa ją z listy celów;
- `Ctrl+NumDel` zaznacza lub odznacza wszystkie aktywne warstwy.

## Efekty

Efekty są przetwarzane w ustalonej kolejności: Szum, Mocny przester, Przester,
Redukcja bitów, Redukcja próbkowania, Modulacja pierścieniowa, Tremolo, Cięcie rytmiczne, Pompowanie, LPF, HPF, Pogłos,
Zakłócenia cyfrowe. Każdy efekt ma działające parametry A i B.

| Efekt | Efekt chwilowy | Parametr A | Parametr B |
|---|---:|---|---|
| Pogłos | `Ctrl+Shift+Backtick` | miks pogłosu | feedback/długość |
| Filtr dolnoprzepustowy | `Ctrl+Shift+1` | częstotliwość/siła filtra | miks wet/dry |
| Filtr górnoprzepustowy | `Ctrl+Shift+2` | siła odcięcia dołu | miks wet/dry |
| Redukcja bitów | `Ctrl+Shift+3` | rozdzielczość kwantyzacji | miks wet/dry |
| Przester | `Ctrl+Shift+4` | drive | miks wet/dry |
| Cięcie rytmiczne | `Ctrl+Shift+5` | szybkość bramkowania | głębokość |
| Pompowanie | `Ctrl+Shift+6` | szybkość pompowania | głębokość |
| Tremolo | `Ctrl+Shift+7` | szybkość | głębokość |
| Modulacja pierścieniowa | `Ctrl+Shift+8` | częstotliwość modulatora | miks wet/dry |
| Redukcja próbkowania | `Ctrl+Shift+9` | długość sample-and-hold | miks wet/dry |
| Mocny przester | `Ctrl+Shift+0` | gain | miks wet/dry |
| Zakłócenia cyfrowe | `Ctrl+Shift+-` | liczba fragmentów | miks wet/dry |
| Szum | `Ctrl+Shift+=` | poziom szumu | intensywność |

Skrót Efekt chwilowy jest momentary: naciśnięcie włącza efekt, a puszczenie klawisza
przywraca wcześniejszy stan. Jeśli efekt był już włączony na stałe z menu,
Efekt chwilowy go nie wyłączy. Pozycje menu służą do trwałego włączania efektów.

`Ctrl+Shift+NumDel` zaznacza lub odznacza wszystkie aktywne efekty jako cele
gałek FX.

## Macierz sterowania na klawiaturze numerycznej

NumLock może wpływać na kody wysyłane przez konkretną klawiaturę. Program
korzysta z natywnych kodów numpada wxPython.

| Numpad | Warstwa (`Ctrl`) | Efekt (`Ctrl+Shift`) |
|---:|---|---|
| `/` | Oktawa niżej | Pogłos |
| `1` | Prostokąt subbasowy | Filtr dolnoprzepustowy |
| `2` | Suboktawa | Filtr górnoprzepustowy |
| `3` | Kwinta | Redukcja bitów |
| `4` | Tercja wielka | Przester |
| `5` | Tercja mała | Cięcie rytmiczne |
| `6` | Oktawa wyżej | Pompowanie |
| `7` | Rozstrojenie | Tremolo |
| `8` | Szum | Modulacja pierścieniowa |
| `9` | Cyfrowa | Redukcja próbkowania |
| `0` | Harmoniczne | Mocny przester |
| `*` | Organy | Zakłócenia cyfrowe |
| `-` | Winyl | Szum |
| `.` | Sinusoida subbasowa | brak przypisania |

Nieaktywny element nie może zostać zaznaczony jako cel. Program komunikuje to
głosem i pozostawia jego pozycję wyłączoną.

## Gałki i ich skróty

### Zmiany płynne

| Cel | A + / A - | B + / B - |
|---|---|---|
| Instrument | `PgUp` / `PgDn` | `Home` / `End` |
| Warstwy | `Ctrl+Alt+PgUp` / `Ctrl+Alt+PgDn` | `Ctrl+Alt+Home` / `Ctrl+Alt+End` |
| Efekty | `Alt+PgUp` / `Alt+PgDn` | `Alt+Home` / `Alt+End` |

Krok zmiany wynosi 5 punktów procentowych.

### Wartości skrajne i reset

- `Ctrl+PgUp` / `Ctrl+PgDn`: instrument A maksimum/minimum;
- `Ctrl+Home` / `Ctrl+End`: instrument B maksimum/minimum;
- `Ctrl+Delete`: reset instrumentu A do 50%;
- `Ctrl+Backspace`: reset instrumentu B do 20%;
- bez modyfikatora `Delete` i `Backspace` resetują A/B do tych samych wartości;
- `Ctrl+Alt+Delete` / `Ctrl+Alt+Backspace`: reset gałek warstw;
- `Alt+Delete` / `Alt+Backspace`: reset gałek efektów.

Każdą z sześciu grup gałek można też ustawić dokładnie z menu `Edycja`.
Bezpieczny zakres A instrumentu i warstw wynosi 1–99%; pozostałe gałki mają
zakres 0–100%.

## Perkusja

Silnik zawiera osiem odrębnie syntezowanych głosów:

| Głos | Klawisz bez modyfikatora | Globalny skrót |
|---|---:|---:|
| Kick | `F5` | `Ctrl+Shift+Z` |
| Snare | `F6` | `Ctrl+Shift+X` |
| HiHat | `F7` | `Ctrl+Shift+C` |
| Tom | `F8` | `Ctrl+Shift+V` |
| Clap | `F9` | `Ctrl+Shift+B` |
| Cowbell | `F10` | `Ctrl+Shift+N` |
| Crash | `F11` | `Ctrl+Shift+M` |
| Laser | `F12` | `Ctrl+Shift+,` |

Globalne skróty można wyłączyć ustawieniem `Globalne bębny`. W instrumencie
Perkusja kolejne nuty wybierają głosy modulo 8.

Gałka instrumentu A zmienia wysokość/barwę bębna, a B czas jego wybrzmiewania.
Tom, Clap, Cowbell, Crash i Laser korzystają z pełnych algorytmów odzyskanych z
historycznych wersji v5/v8, zamiast wspólnego generatora szumu. Crash został
dodatkowo rozszerzony o regulowaną gałką A metaliczną składową talerza.

## Sekwencer i looper

### Odtwarzanie i nagrywanie

- `Spacja` uruchamia lub zatrzymuje pętlę;
- `Ctrl+R` włącza nagrywanie; jeżeli pętla nie gra, zostaje uruchomiona;
- pętla ma 16 kroków, czyli jeden takt 4/4;
- zmiana BPM skaluje zapisane czasy melodii, zachowując ich pozycję rytmiczną;
- nowe zdarzenie nagrane na żywo nie jest powtarzane drugi raz w tej samej
  pętli;
- zatrzymanie sekwencera bezpiecznie zwalnia wszystkie nuty.

### Edytor perkusji

Otwórz go przez `Ctrl+E` lub menu `Gra`.

- `Lewo` / `Prawo`: poprzedni/następny krok;
- `Góra` / `Dół`: poprzedni/następny z ośmiu instrumentów;
- `Spacja`: włącz lub wyłącz wybrany krok;
- `Escape`: zamknij edytor.

Czytnik ekranu otrzymuje nazwę instrumentu, numer kroku i jego stan.

Menu `Edycja` pozwala osobno wyczyścić melodię, patterny perkusyjne albo cały
sekwencer. Każde czyszczenie wymaga potwierdzenia.

## Klawiatura nutowa

Dolny rząd zaczyna się od C4:

```text
Z S X D C V G B H N J M , L . ; /
```

Górny rząd kontynuuje skalę:

```text
Q 2 W 3 E 4 R 5 T 6 Y 7 U
```

- `Ctrl+Góra` / `Ctrl+Dół`: oktawa wyżej/niżej;
- `Ctrl+Lewo`: oktawa 0;
- zakres oktaw wynosi od -3 do +3;
- `Ctrl+H`: tryb akordów;
- białe klawisze tworzą tercję wielką i kwintę;
- czarne klawisze tworzą tercję małą i kwintę;
- zwolnienie klawisza wyłącza wszystkie trzy głosy — nie ma wiszących akordów;
- `Ctrl+B`: blokada systemowych powtórzeń klawisza.

Kody interpunkcji są normalizowane zarówno z ASCII, jak i z windowsowych
VK_OEM, dzięki czemu `, . ; / - = ` i `\` działają na typowych klawiaturach.

## Głośność, Podtrzymanie i Portamento

- `Alt+Góra` / `Alt+Dół`: głośniej/ciszej o 5%;
- `Alt+Lewo`: reset głośności do 20%;
- `Ctrl+S`: Podtrzymanie;
- `Ctrl+G`: Portamento;
- `Ctrl+Shift+P`: globalne bębny;
- `Ctrl+B`: blokada powtarzania;
- `Ctrl+Shift+Escape`: PANIC, natychmiastowe wyciszenie wszystkich głosów.

Zachowane aliasy starszych wersji:

- `Ctrl+-`, `Ctrl+=`, `Ctrl+0`: oktawa w dół, w górę i reset;
- `Ctrl+Shift+PgUp/PgDn/Home/End`: płynna regulacja FX A/B;
- `Ctrl+Shift+Alt+PgUp/PgDn/Home/End`: skrajne wartości warstw A/B;
- `Ctrl+Shift+Alt+Delete/Backspace`: reset warstw A/B.

Opcja `Wyrównany release` zachowuje aktualny poziom obwiedni podczas przejścia
z automatycznego decay do release. Jej wyłączenie odtwarza zachowanie Legacy
Release ze starszych wersji.

## MIDI

Menu `MIDI` udostępnia wybór wejścia i ponowne skanowanie portów.

Obsługiwane komunikaty:

- Note On i Note Off;
- velocity Note On — wpływa na głośność oscylatora;
- Note On z velocity 0 jako Note Off;
- Control Change 64 — pedał sustain z odroczonym Note Off;
- Control Change 120 — All Sound Off;
- Control Change 123 — All Notes Off.

Nuty z MIDI używają aktualnie wybranego instrumentu i są zapisywane przez
looper, gdy aktywne jest nagrywanie. Zmiana lub zamknięcie portu zwalnia nuty,
które mogły pozostać aktywne.

Jeżeli nie ma biblioteki MIDI albo urządzenia, reszta programu działa normalnie.

### Informacje głosowe o zmianach

W menu `Ustawienia` znajdują się dwie niezależne pozycje:

- `Czytaj zmiany z MIDI` — skrót `Ctrl+Alt+Shift+F9`;
- `Czytaj zmiany z klawiatury komputerowej` — skrót `Ctrl+Alt+Shift+F10`.

Zaznacz obie, jedną albo żadną, aby wybrać odpowiednio oba źródła, tylko MIDI,
tylko klawiaturę lub wyłączyć informacje o zmianach. Domyślnie oba źródła są
włączone, również przy aktualizacji ze starszego INI. Wybór zapisuje się od razu
w sekcji `FEEDBACK` pliku `po.ini`. Komunikaty o błędach, gotowości aplikacji
i potwierdzenie zmiany samego trybu mowy pozostają dostępne.

W edytorze mapowań MIDI można przypisać przyciskowi działania
`Włącz/wyłącz mowę zmian z MIDI`, `Włącz/wyłącz mowę zmian z klawiatury komputerowej`
lub `Przełącz źródła informacji głosowych`. Użyj trybu przycisku. Ostatnie działanie
przełącza kolejno oba źródła, tylko MIDI, tylko klawiaturę i wyciszenie.

Zmiana gałki podaje nazwę i rzeczywistą wartość parametru. Nieprzypisane kontrolery,
identyczne wartości oraz próby przekroczenia już osiągniętej granicy milczą.
Szybkie ruchy MIDI są łączone: bez kolejki setek komunikatów, z odczytem wartości
końcowej po zatrzymaniu. Mowa z klawiatury komputerowej pozostaje natychmiastowa.

### Nauka i edycja mapowania

Otwórz `MIDI → Mapowania MIDI...`. Okno zawiera listę mapowań, ostatni komunikat,
wybór działania, trybu, numeru kontrolera i kanału oraz przyciski nauki i zapisu.

1. Wybierz właściwe wejście w menu MIDI.
2. Naciśnij „Naucz następny kontroler”.
3. Obróć gałkę lub naciśnij przycisk na urządzeniu.
4. Wybierz działanie i tryb, następnie „Zapisz mapowanie”.

Nauka tylko rozpoznaje źródło; zapis następuje po świadomym wyborze działania.
Ręcznie można też podać typ komunikatu, numer i kanał. Kanały w oknie mają numery
1–16, a w JSON 0–15; „Dowolny kanał” jest zapisywany jako `null`.
Mapowanie tego samego źródła zastępuje poprzednie. Przycisk „Usuń wybrane
mapowanie” usuwa tylko wskazaną pozycję. Zmiany zapisywane są od razu w INI.

Zapis i kolejne poprawki zachowują pozycję oraz zaznaczenie edytowanego wpisu.
Zmiana typu, kanału lub numeru wybranego wpisu zastępuje jego źródło; próba
użycia źródła zajętego przez inny wpis jest odrzucana bez utraty mapowań.
„Naucz następny kontroler” pozwala dodać nowe źródło.

Zaznacz **Stosuj zmiany na bieżąco**, aby poprawne zmiany działania, trybu,
kroku, kierunku i włączenia stosowały się bez przycisku „Zapisz mapowanie”.
Program stosuje je po krótkiej, około 0,18 s przerwie w edycji i zapisuje w INI.
Wybór ten jest zapamiętywany. Domyślnie obowiązuje ręczny zapis.
Samo zaznaczenie pozycji nie zmienia jej przypisania. Niedokończone albo
sprzeczne dane pozostawiają ostatnie poprawne przypisanie; informacja pojawia
się w monitorze. Błąd zapisu przywraca poprzednią listę mapowań.

Aby czasowo wyłączyć wpis, zaznacz go na liście, odznacz `Przypisanie włączone`
i wybierz `Zapisz mapowanie`. Wpis pozostanie na liście jako wyłączony; ponowne
zaznaczenie pola i zapis go przywrócą. Wyłączony wpis ignoruje odpowiadający mu
sygnał, również gdy pochodzi on z pada/nuty. Usunięcie wpisu pozwala z kolei
wrócić do zwykłej interpretacji MIDI dla danej nuty lub pedału.
Wyłączone i usunięte mapowania nie są samoczynnie przywracane przy restarcie.
Ręczne wczytanie profilu zastępuje listę jego domyślnymi, włączonymi wpisami.

### Kółko lub pasek Odstrajanie

Fabryczne profile przypisują komunikat `Odstrajanie` do muzycznego odstrajania
nut MIDI w zakresie ±2 półtonów. Środek dokładnie przywraca normalną wysokość.
Działa to na już grające i kolejne nuty danego kanału, także podczas Portamento;
nuty z klawiatury komputerowej i pozostałe kanały nie są odstrajane.
Zmiany są nagrywane w looperze, zapisywane w projekcie i renderowane do WAV.
Zatrzymanie pętli, PANIC, zamknięcie portu oraz zmiana/wyłączenie przypisania
przywracają normalny strój. Zapobiega to pozostawieniu odstrojenia po wyłączeniu
kółka w połowie ruchu.

Własne przypisanie Odstrajanie można wyłączyć, usunąć albo zastąpić innym działaniem.
Dla działania muzycznego Odstrajanie wybierz tryb bezwzględny. Profile NI zachowują
ten bezwzględny tryb kółka również wtedy, gdy ich gałki pracują względnie.

Obsługiwane źródła: CC, Note On/Off (np. pady), Program Change, Odstrajanie,
Channel Pressure, Start/Continue/Stop oraz MIDI Machine Control (MMC) przez
Universal Realtime SysEx. Przypisana nuta działa jako przycisk i nie gra dźwięku;
pozostałe nuty zachowują normalne działanie. CC64/120/123 mają standardowe znaczenie,
chyba że użytkownik jawnie przypisze im inną funkcję.

| Tryb | Przeznaczenie |
| --- | --- |
| Bezwzględny | Zwykła gałka lub suwak 0–127; Odstrajanie używa pełnych 14 bitów. |
| Względny 1/127 | Enkoder: 1 zwiększa, 127 zmniejsza; m.in. NI Relative. |
| Względny 65/63 | Enkoder względem 64; m.in. NI Relative Offset. |
| Względny 1/65 | Znak/wartość; 1 zwiększa, 65 zmniejsza. |
| Przycisk | Jedno działanie na naciśnięcie; zwolnienie nie uruchamia go drugi raz. |
| Chwilowy | Warstwa lub efekt działa podczas trzymania i wraca do wcześniejszego stanu. |

Tryby względne pozwalają ustawić wielkość kroku i odwrócić kierunek. Nie wykrywamy
trybu enkodera z pojedynczego komunikatu, ponieważ te same liczby mogą oznaczać
różne rzeczy w różnych urządzeniach.

Działania obejmują sześć grup gałek, osobne A/B każdej warstwy i efektu, głośność,
BPM, start/stop, nagrywanie, PANIC, oktawę, zmianę instrumentu, Podtrzymanie, Portamento,
akordy, przełączanie warstw/efektów i wyzwalanie każdego z ośmiu bębnów.

### MIDIPLUS AKM322 — profil sprawdzony na fizycznym urządzeniu

Przy pierwszym wykryciu AKM322 program ładuje profil oparty na rzeczywistym
przechwyceniu komunikatów. Można też wybrać go ręcznie przyciskiem profilu.

| Kontroler | Komunikat | Domyślne działanie |
| --- | --- | --- |
| Enkoder DATA | CC10 bezwzględny | Wybór brzmienia |
| Lewe sprężynujące kółko | Odstrajanie | Odstrojenie nut MIDI ±2 półtony |
| Gałka 1 | CC21 | Instrument A (Page Up/Down) |
| Gałka 2 | CC22 | Instrument B (Home/End) |
| Gałka 3 | CC23 | Jasność — filtr dolnoprzepustowy |
| Kółko modulacji | CC1 | Głębokość vibrato |
| Opcjonalny kontroler głośności | CC7 | Głośność (standard MIDI; nie wystąpił w przechwyceniu) |
| Play / Stop / Record | MMC 2 / 1 / 6 | Odtwarzanie / Stop / nagrywanie |

Gałka 1 reguluje parametr A instrumentu, a gałka 2 zanik/release (przy Podtrzymanie
słychać go po puszczeniu nuty). Enkoder wybiera pięć brzmień w kolejnych zakresach
wartości. Filtr gałki 3 działa niezależnie od włączonych efektów i warstw:
minimum daje ciemny dźwięk (100 Hz), maksimum pomija filtr. Vibrato ma częstotliwość
5 Hz i maksymalną głębokość ±0,5 półtonu; minimum kółka je wyłącza. Oba parametry
działają na bieżące i kolejne głosy, także z klawiatury PC. Filtr obejmuje miks,
w tym perkusję. Nie włączają samoczynnie pozostałych efektów ani warstw.

Te same parametry można ustawić klawiaturą przez `Instrument → Jasność (filtr)...`
oraz `Instrument → Głębokość vibrato...`. Zapisują się w INI i projekcie;
ich ruchy podczas nagrywania trafiają do loopera i eksportu WAV. Wyłączenie
przypisania zatrzymuje dalsze ruchy kontrolera; ostatnia wartość parametru zostaje,
tak jak przy zwykłych gałkach. Vibrato wyłączysz wartością 0 w menu instrumentu.

Klawiatura ma własne funkcje lokalne. Przycisk, który nie wysyła żadnego komunikatu
do komputera, nie może być przejęty przez program. Po przeprogramowaniu kontrolera
użyj nauki lub zmień odpowiedni wpis. [Instrukcja producenta AKM322](https://www.midiplus.com.tw/cn/MIDIPLUS-Download-detail/0/Manual_Of_AKM322_EN/)
opisuje programowanie gałek, enkodera i przycisków transportu.

Nieedytowany stary profil AKM322 jest przy aktualizacji dostosowywany do nowego
układu; v16.0/v16.1 otrzymują też brakujące kółko. Własne, usunięte i wyłączone
przypisania są zachowywane. Nowy układ można ręcznie wczytać przyciskiem profilu.

### Native Instruments

Kontroler musi działać w zwykłym trybie MIDI. Dla M32, A-Series i S-Series MK2
producent podaje `SHIFT + MIDI / PLUG-IN`; dla S-Series MK1 `SHIFT + INSTANCE`.
Dla MK3 należy użyć ustawień MIDI właściwych dla modelu/firmware.
[Oficjalna instrukcja trybu MIDI](https://support.native-instruments.com/support/solutions/articles/69000880031-native-instruments-switching-your-controller-to-midi-mode).

Profile `NI CC14–21 Relative` i `NI CC14–21 Relative Offset` są szablonami dla
ośmiu kontrolerów. Przypisz w edytorze NI CC14–21 albo użyj MIDI Learn do
aktualnego szablonu. Nie są one deklaracją fabrycznych CC każdego modelu NI.
Znaczenie względnych wartości pochodzi z
[dokumentacji Native Instruments](https://docs.native-instruments.com/online-guides/komplete-kontrol-manual/en/automation-and-midi-control.html).
Protokół NKS, wyświetlacze, diody i zastrzeżone tryby DAW/HID nie są implementowane.
Nie testowano fizycznej klawiatury NI; algorytmy i routing sprawdzają testy.

Nowe konfiguracje wykrywają po nazwie portu KOMPLETE/KONTROL/Native Instruments
i wybierają profil `NI CC14–21 Absolute`. Jeśli dostępny jest zwykły port muzyczny,
ma pierwszeństwo przed portem DAW. W profilu CC14–21 sterują kolejno instrumentem
A/B, warstwami A/B, efektami A/B, głośnością i BPM; CC1 steruje FX B, kółko Pitch
Bend odstrajaniem, a komunikaty realtime i MMC transportem.
Układ CC14–21 pokazuje [oficjalna instrukcja M32](https://docs.native-instruments.com/pdf-guides/komplete_kontrol/KOMPLETE_KONTROL_M32_Manual_English_200127.pdf).
To gotowy punkt startowy, nie rozpoznanie dowolnego zmienionego szablonu NI.
Zapisane własne lub celowo puste mapowania mają pierwszeństwo przed automatyką.

## Zapamiętywanie ustawień i pliki projektów

### Automatyczny stan `po.ini`

Konfiguracja znajduje się w `po.ini` obok EXE w portable lub obok `main.py`
w źródłach. Pierwszy zatwierdzony wybór tworzy sekcję `INTERFACE`; normalne
zamknięcie zapisuje też sesję muzyczną:

- instrument, BPM i oktawę;
- głośność;
- Podtrzymanie, Portamento, akordy, klawiaturę PC, blokadę powtórzeń, globalne bębny i
  tryb release;
- aktywne warstwy i efekty;
- zaznaczone cele macierzy;
- wszystkie wartości A/B — globalne, per warstwa i per efekt;
- wybrane urządzenie audio i nazwę portu MIDI;
- wszystkie patterny ośmiu bębnów;
- nagraną ścieżkę melodii.
- mapowania MIDI, język, motyw i ustawienie podpowiedzi.

Zapis INI jest atomowy przez plik tymczasowy w tym samym folderze. Zapis ustawień
muzycznych zachowuje sekcję interfejsu. Dane programu i `logs/startup.log` nie
trafiają do AppData; katalog aplikacji musi być zapisywalny.

`Ctrl+Shift+Delete` wykonuje reset fabryczny. Po potwierdzeniu `po.ini` jest
usuwany, a zamykanie nie zapisuje go ponownie.

### Projekty `.po15`

Menu `Plik` pozwala zapisywać i otwierać czytelne pliki JSON z rozszerzeniem
`.po15`. Projekt zawiera kompletny stan muzyczny, parametry, sekwencer i mapowania
MIDI. Rozszerzenie zachowano dla zgodności z v15; stare projekty wczytują się
bez wymagania nowych pól. Język i motyw są preferencjami aplikacji, nie projektu.

Przy ręcznym otwieraniu projektu ustawienia sprzętowe są zachowywane z bieżącej
sesji, aby plik z innego komputera nie przełączył programu na nieistniejące
urządzenie. Nazwa MIDI i indeks audio pozostają zapisane w projekcie jako
informacja Zapamiętywanie ustawień.

Format ma identyfikator `pocket-operator-mobile-project` oraz wersję schematu.
V17.0 zapisuje schemat 3 i czyta również schematy 1 i 2. Nowszy schemat chroni przed
otwarciem wyłączonych mapowań jako aktywnych w starszej wersji programu.
Niepoprawne lub przyszłe, nieobsługiwane schematy są odrzucane z komunikatem,
zamiast częściowo nadpisywać sesję.

## Eksport WAV

`Ctrl+Shift+E` otwiera okno eksportu. Program pyta o liczbę pętli od 1 do 99.

- format: mono, 44,1 kHz, 16-bit PCM;
- eksportuje melodię, wszystkie patterny, warstwy i pełny łańcuch efektów;
- zdarzenia są umieszczane na osi próbek, nie tylko na początku bloku audio;
- renderowanie odbywa się w osobnym silniku offline;
- bieżące nuty, pogłos, delay i stan wyjścia audio nie są zmieniane;
- wynik jest normalizowany tylko wtedy, gdy zawiera niezerowy sygnał.

## Dostępność

- wszystkie najważniejsze działania mają skróty klawiszowe;
- kontrolki i okna używają natywnych elementów wxPython;
- menu pozostaje dostępne przez `Alt`;
- komunikaty parametrów są wysyłane przez `accessible-output2`;
- bez sterownika mowy komunikaty trafiają do konsoli;
- edytor perkusji podaje głosem instrument, krok i stan;
- nieaktywne cele macierzy są blokowane, a próba ich wyboru jest komunikowana;
- `F1` otwiera skróconą pomoc wewnątrz programu.

## Struktura katalogu

| Plik/katalog | Rola |
|---|---|
| `main.py` | Okno, menu, skróty, dostępność, Zapamiętywanie ustawień i projekty. |
| `synth.py` | Oscylatory, warstwy, bębny, efekty, strumień i eksport WAV. |
| `sequencer.py` | 16 kroków, nagrywanie melodii, scheduler i serializacja. |
| `midi_handler.py` | Porty MIDI, velocity, sustain i All Notes Off. |
| `midi_mapping.py`, `midi_dialog.py` | Profile, dekodowanie kontrolerów, nauka i edytor. |
| `preferences.py`, `app_paths.py` | Przenośne ścieżki i atomowy zapis INI. |
| `localization.py`, `langs/*.lng` | Katalogi tłumaczeń UTF-8 w formacie JSON. |
| `ui_support.py` | Obowiązkowy first run, motywy i dostępne okna. |
| `run.py` | Kontrola wersji Pythona i zależności, uruchomienie aplikacji. |
| `Graj.bat` | Jednoklikowy launcher Windows. |
| `requirements.txt` | Zależności uruchomieniowe. |
| `requirements-dev.txt` | Zależności do testów i kontroli statycznej. |
| `pyproject.toml` | Wspólna konfiguracja Ruff dla projektu. |
| `test_launch.py` | Testy silnika, MIDI, sekwencera, UI i Zapamiętywanie ustawień. |
| `GEMINI.md` | Historia rozwoju projektu. |
| `test_v16.py` | Testy konfiguracji, mapowań, języków i regresji MIDI. |
| `test_pitch_mapping.py` | Strojenie, środek kółka, kanały, profile i wyłączanie przypisań. |
| `feedback.py`, `test_feedback.py` | Polityka mowy źródeł i regresje rzeczywistych zmian/końcowej wartości. |
| `build_release.py` | Powtarzalna kompilacja portable, z pracą poza źródłami. |
| `Installfiles/` | Lokalne aktualne portable; ignorowane przez Git. |

`po.ini` pojawia się po zatwierdzeniu pierwszej konfiguracji. Pliki `.po15` i
`.wav` są tworzone wyłącznie w lokalizacji wskazanej przez użytkownika.

## Testy i kontrola jakości

Uruchom pełny zestaw:

```powershell
python -B -m unittest -v
```

Testy obejmują między innymi:

- wszystkie pięć głównych instrumentów;
- generowanie nut, warstw i release;
- wpływ gałki B każdej warstwy oraz każdego efektu na audio;
- wszystkie trzynaście efektów;
- wszystkie osiem historycznych głosów perkusyjnych i reakcję każdego z nich
  na obie gałki;
- pełny stos 14 warstw, 13 efektów i 8 bębnów przy skrajnych nastawach;
- eksport poprawnego WAV bez mutowania żywych głosów;
- start wątku i odtwarzanie sekwencera;
- poprawny pierwszy cykl po ponownym zatrzymaniu i starcie sekwencera;
- zapis/odczyt patternów oraz skalowanie czasu przy zmianie BPM;
- MIDI velocity i pedał sustain;
- zgodność starszego API syntezatora;
- utworzenie okna wxPython;
- Zapamiętywanie ustawień ustawień, parametrów per-element i sekwencera;
- serializację projektu przez prawdziwy JSON;
- atomowe odrzucenie uszkodzonego projektu bez częściowej zmiany sesji.

Kontrola statyczna:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pip check
```

Test prawdziwego wyjścia audio wymaga urządzenia i jest wykonywany osobno przez
utworzenie `MainFrame` z `auto_start=True`.

Kompilacja portable na Windows:

```powershell
python build_release.py --work-dir D:\work\Workspace\8bit\release-build
```

Wynik: `Installfiles/PocketOperator-mobile`. Skrypt nie nadpisuje wcześniejszego
wydania. Instalator Pythona nie jest potrzebny do uruchomienia wyniku.

## Rozwiązywanie problemów

### Brak biblioteki przy starcie

```powershell
python -m pip install -r requirements.txt
```

Upewnij się, że `pip` i `python` dotyczą tej samej instalacji:

```powershell
python --version
python -m pip --version
```

### Brak dźwięku

1. Otwórz `Audio` → `Wybierz wyjście audio...`.
2. Wybierz urządzenie z kanałami wyjściowymi.
3. Sprawdź mikser głośności Windows.
4. Użyj `Alt+Lewo`, aby przywrócić głośność 20%.
5. Użyj `Ctrl+Shift+Escape`, aby usunąć ewentualne wiszące głosy.

Jeżeli zapisane urządzenie przestało istnieć, v15 pomija je, zachowuje pozostałe
ustawienia i próbuje uruchomić domyślne wyjście.

### Brak portu MIDI

- sprawdź, czy urządzenie jest widoczne w systemie;
- wybierz `MIDI` → `Odśwież MIDI`;
- upewnij się, że inna aplikacja nie otworzyła portu w trybie wyłącznym;
- wykonaj `python -m pip install python-rtmidi`.

### Uszkodzony `po.ini`

Uszkodzona sekcja sekwencera jest pomijana bez utraty poprawnych ustawień.
Całkowity reset można wykonać przez `Ctrl+Shift+Delete`. Starsze konfiguracje
bez sekcji v15 nadal są odczytywane z wartościami domyślnymi dla nowych pól.

### Program działa, ale czytnik ekranu milczy

Sprawdź instalację:

```powershell
python -m pip install accessible-output2
```

Program celowo nie zatrzymuje syntezatora po awarii sterownika mowy — komunikaty
są wtedy drukowane w konsoli.

## Zgodność ze starszymi wersjami

Silnik v15 zachowuje zarówno aktualne, jak i historyczne nazwy API, między
innymi `set_vol`/`set_volume`, `vol`/`volume`, `layers`/`active_layers`,
`fx`/`active_fx`, `sus`/`sustain_enabled`, `glide`/`glide_enabled`,
`trigger_drum`/`trig_drum`, `set_fx_a`, `set_fx_b`, `set_layer_knob_a` i
`set_layer_knob_b`.

Pozwala to uruchamiać narzędzia przygotowane dla starszych wariantów bez
cofania całego silnika do ich ograniczeń.

## Historia konsolidacji

W katalogu początkowo znajdowało się sześć linii rozwojowych:

- v5.0 Factory — najbardziej czytelna baza i pełne algorytmy ośmiu bębnów;
- v8.2 — wiele warstw, Sinusoida subbasowa i rozbudowane menu edycji;
- v9.0 Router — pierwszy routing parametrów, ale liczne puste metody;
- v11.0 Matrix — macierz wyboru celów;
- v13.0 Full Save — zapis wartości per element, ale pusty eksport WAV;
- v14.1 Stable — najszerszy Zapamiętywanie ustawień, lecz rozłączone API sekwencera/MIDI.

v15 zachowuje najlepsze elementy każdej z nich i naprawia ich wspólne błędy.
Zgodnie z aktualnymi zasadami artefakty robocze, pamięć projektu i archiwalia
są centralizowane poza repozytorium. Na badanym komputerze dawny `trash` był pusty
i został przeniesiony do `D:\work\Trash\8bit\legacy-local-trash`.

## Dane i prywatność

Aplikacja działa lokalnie. Nie wysyła audio, projektów, konfiguracji ani danych
MIDI do sieci. Zapisuje tylko `po.ini` obok programu oraz pliki `.po15`/`.wav`
wskazane przez użytkownika.
