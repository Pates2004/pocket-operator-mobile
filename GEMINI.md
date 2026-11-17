# Historia projektu "Pocket Operator mobile"

Dokumentacja rozwoju aplikacji syntezatora 8-bitowego, stworzonej w Pythonie (wxPython + NumPy + SoundDevice) z myślą o pełnej dostępności (screen-reader friendly).

## Faza 1: Incepcja i Prototyp
**Cel:** Stworzenie prostego generatora dźwięku sterowanego klawiaturą.
- Utworzono szkielet aplikacji w `main.py` z użyciem `wxPython`.
- Zaimplementowano podstawowy silnik audio w `synth.py` (fala kwadratowa).
- Dodano obsługę klawiatury PC (mapowanie Z, X, C... na nuty).

## Faza 2: Rozbudowa Brzmienia
**Cel:** Dodanie zmiennych parametrów i typów fal.
- Dodano fale: Sawtooth (Piła), Triangle (Trójkąt), Noise (Szum).
- Wprowadzono Gałki A i B (Knob A/B) zmieniające parametry brzmienia (wypełnienie, decay).
- Zaimplementowano prosty sekwencer krokowy (Perkusja).

## Faza 3: Dostępność i MIDI
**Cel:** Uczynienie aplikacji użyteczną dla osób niewidomych i obsługa zewnętrznych kontrolerów.
- Integracja biblioteki `accessible_output2` do komunikatów głosowych.
- Dodano obsługę MIDI (wejście) w `midi_handler.py`.
- Wprowadzono plik konfiguracyjny `po.ini` do zapisu stanu.

## Faza 4: Efekty Punch-In i Perkusja
**Cel:** Emulacja charakteru Pocket Operatorów.
- Dodano efekty "Punch-In" (trzymasz klawisz = efekt działa): LPF, HPF, BitCrush, Distortion, Stutter, itd.
- Zaimplementowano zestaw perkusyjny (Kick, Snare, HiHat, Cowbell...) pod klawiszami funkcyjnymi i globalnie (`Ctrl+Shift`).

## Faza 5: Refaktoryzacja i Stabilizacja (v3.x - v4.x)
**Cel:** Naprawa błędów i uporządkowanie kodu.
- Naprawiono liczne błędy `AttributeError` i `SyntaxError` wynikające z edycji dużych plików.
- Przebudowano system skrótów klawiszowych (Drzewo Skrótów).
- Dodano obsługę zmiany oktaw (`Ctrl + Strzałki`).
- Uporządkowano menu.

## Faza 6: Warstwy (Layers) (v6.x)
**Cel:** Pogrubienie brzmienia.
- Dodano silnik "Multi-Layer" w `synth.py`.
- Możliwość łączenia głównego instrumentu z dodatkowymi warstwami: Sub Bass, Fifth (Kwinta), Detune, Noise.
- Skróty `Alt + 1..=` do włączania warstw.

## Faza 7: Matrix Control i Routing (v9.x - v12.x)
**Cel:** Zaawansowana kontrola nad parametrami.
- Rozdzielono gałki: Instrument (Main), Warstwy (Layer), Efekty (FX).
- Wprowadzono "Control Matrix" na klawiaturze numerycznej (`Ctrl + NumPad`).
- Możliwość wyboru, czy gałki sterują wszystkimi warstwami naraz, czy tylko wybranymi.
- Inteligentne UI: blokowanie sterowania nieaktywnymi elementami.

## Faza 8: Total Recall (v14.0)
**Cel:** Profesjonalna praca i zapisywanie wszystkiego.
- Zapisywanie stanu WSZYSTKICH przełączników (Sustain, Chord, Glide, itd.).
- Zapisywanie pozycji gałek dla każdej warstwy i każdego efektu osobno.
- Zapisywanie głośności głównej i portu MIDI.
- Pełna stabilizacja kodu i poprawki składniowe (f-strings).

## Faza 9: Finalna Stabilizacja (v14.1)
**Cel:** Eliminacja błędów wykonawczych i spójność kodu.
- Naprawiono krytyczny błąd `ValueError` w `synth.py` (zastąpienie *list comprehension* jawną pętlą przy miksowaniu oscylatorów).
- Przywrócono brakujące metody w `main.py` (`on_export_wav`, `midi_init`, etc.), które zginęły przy minifikacji.
- Ostateczna weryfikacja zapisu stanu ("Total Recall").

## Faza 10: Naprawa integracji i konsolidacja (v14.2)
**Cel:** Przywrócenie rzeczywistego działania funkcji, które były obecne w UI, ale rozłączone między modułami.
- Naprawiono uruchamianie i zatrzymywanie wątku sekwencera oraz zgodność jego API z silnikiem bębnów.
- Naprawiono wejście MIDI, nagrywanie nut i zwalnianie wszystkich głosów akordu.
- Usunięto zakleszczenie przy regulacji parametrów warstw.
- Eksport WAV działa na osobnej kopii stanu i nie narusza dźwięku granego na żywo.
- Przywrócono edytor perkusji, pełną pomoc, globalne bębny i wybór urządzeń MIDI/audio.
- Naprawiono reset fabryczny, zapis Total Recall i uruchamianie na Pythonie 3.10 lub nowszym.

## Faza 11: Pełna konsolidacja (v15.0)
**Cel:** Połączenie wszystkich wartościowych funkcji historycznych wersji w jeden kompletny i testowalny produkt.
- Przywrócono warstwę Sub Sine oraz pełne algorytmy ośmiu głosów perkusyjnych z v5/v8.
- Parametr B warstw i parametr B każdego efektu otrzymały rzeczywisty wpływ na audio.
- Dodano prawdziwy momentary Punch-In, PANIC oraz pełną obsługę ośmiu ścieżek perkusji.
- Sekwencer zapisuje patterny i melodię, skaluje timing przy zmianie BPM i nie dubluje nut nagrywanych na żywo.
- MIDI obsługuje velocity, pedał sustain, All Notes Off oraz nagrywanie do loopera.
- Total Recall obejmuje sekwencer i wartości per warstwa/efekt; dodano przenośny format projektu `.po15`.
- Przywrócono dokładne dialogi sześciu grup gałek, presety tempa i historyczne aliasy API.
- Dodano szczegółowe `README.md` oraz testy automatyczne silnika, UI, projektów, MIDI i sekwencera.

## Faza 12: Kontrolery, języki i przenośne uruchamianie (v16.0)

- Dodano mapowania CC, nut-przycisków, Program Change, Pitch Bend, Channel Pressure,
  komunikatów realtime i MMC SysEx; naukę kontrolera i natywny edytor.
- Profil AKM322 oparto na rzeczywistym przechwyceniu: CC10, CC21–23, CC1 i MMC.
- Dodano trzy tryby enkoderów względnych oraz szablony dla konfiguracji NI.
- Oddzielono nuty i sustain poszczególnych kanałów MIDI i poprawiono zamykanie wejścia.
- Dodano kompletne katalogi polski/angielski `langs/*.lng`, wybór motywu i opcję podpowiedzi.
- Pierwszy start wymaga zatwierdzenia obu wyborów; anulowanie nie kończy konfiguracji.
- Zachowano jeden `po.ini` obok programu i atomowy zapis wszystkich sekcji.
- Naprawiono natywną awarię zamykania okna mapowania przez odpinanie timera przed Destroy.
- Poprawiono wybór oktawy -1 i nieobsługiwane przez wx nazwy akceleratorów.
- Dodano portable Windows i przygotowanie bibliotek przez launcher źródłowy.

## Faza 13: Spójna informacja głosowa (v16.1)

- Dodano wspólny tor informacji o zmianach dla MIDI i klawiatury komputerowej.
- Dwa niezależne przełączniki w menu, skróty F9/F10 z Ctrl+Alt+Shift i akcje MIDI
  zapisują wybór obu źródeł, jednego źródła albo wyciszenia w sekcji FEEDBACK.
- Szybkie ruchy kontrolerów są łączone z zachowaniem odczytu wartości końcowej.
- Nieprzypisane kontrolery, identyczne wartości i osiągnięte granice milczą.
- Testy potwierdzają wpływ wszystkich gałek AKM322 na przypisane parametry,
  w tym dźwięk release, aktywnej warstwy i aktywnego efektu.

## Faza 14: Pitch Bend i zarządzanie przypisaniami (v16.2)

- Dodano muzyczny Pitch Bend ±2 półtony dla bieżących i kolejnych nut kanału MIDI,
  z dokładnym środkiem i zachowaniem bazowej częstotliwości podczas Glide.
- Dodano nagrywanie odstrojenia do loopera, zapis projektów i renderowanie WAV.
- Profile AKM322 i NI zawierają kółko; NI ma wariant bezwzględny i względne,
  wykrywane są porty muzyczne znanych kontrolerów.
- Przypisania można czasowo wyłączać, usuwać i przywracać; konfiguracja zachowuje
  te decyzje, a wyłączenie kółka przywraca normalny strój także podczas ruchu.
- Generacje kolejki zapobiegają wykonaniu zdarzeń starego przypisania po jego zmianie.
- Schemat projektu 2 zachowuje wyłączone mapowania; odczytywany jest też schemat 1.

## Faza 15: Edytor i ekspresja MIDI (v17.0)

- Edycja zachowuje pozycję i zaznaczenie; zmiany źródła i duplikaty są atomowe.
- Opcjonalne bieżące stosowanie mapowań z walidacją, zapisem INI i cofnięciem przy błędzie zapisu.
- AKM322: CC21/22 = instrument A/B, DATA CC10 = wybór brzmienia,
  CC23 = filtr jasności, CC1 = vibrato 5 Hz do ±0,5 półtonu.
- Filtr i vibrato działają w DSP, menu klawiaturowym, projektach, looperze i WAV.
- Pełne polskie nazwy fal, warstw, efektów i bębnów obejmują menu i komunikaty.
- Projekt zapisuje schemat 3, odczytuje również 1/2; własne mapowania pozostają.

## Struktura Projektu (v17.0)
- `main.py`: Główne okno, obsługa klawiatury, menu, logika UI.
- `synth.py`: Silnik audio (Oscylatory, Warstwy, Efekty DSP, Miksowanie).
- `sequencer.py`: Logika sekwencera perkusyjnego i nagrywania pętli.
- `midi_handler.py`: Obsługa wejścia MIDI.
- `po.ini`: Plik konfiguracyjny (generowany automatycznie).
- `Graj.bat`: Skrypt uruchomieniowy.
- `README.md`: Pełna instrukcja instalacji, funkcji, skrótów i diagnostyki.
- `test_launch.py`: Testy automatyczne v15.
- `test_v16.py`: Regresje konfiguracji, mapowania, języków i zamykania okien.
- `midi_mapping.py`, `midi_dialog.py`: Logika i interfejs kontrolerów.
- `langs/`, `localization.py`: Pliki językowe i tłumaczenia.
- `preferences.py`, `ui_support.py`, `app_paths.py`: INI, first run, motywy i ścieżki.
- `build_release.py`: Budowanie portable w lokalnym `Installfiles`.

## Kluczowe Skróty (v15.0)
- **Gra:** Spacja (Play), Z/X/C (Nuty).
- **Instrument:** PgUp/Dn, Home/End (Gałki).
- **Warstwy:** `Alt + 1..=` (Włącz), `Ctrl+Shift+Bksp` (Wyłącz wszystkie).
- **Efekty:** `Ctrl+Shift + 1..=` (Punch-In), `Alt+Shift+Bksp` (Wyłącz wszystkie).
- **Sterowanie:** `Ctrl + NumPad` (Wybór warstw do edycji).
- **Inne:** `Alt + Strzałki` (Głośność), `Ctrl + Strzałki` (Oktawy).
- **System:** `Ctrl + Shift + Delete` (Reset Fabryczny).
- **PANIC:** `Ctrl + Shift + Escape` (Natychmiastowe wyciszenie).
