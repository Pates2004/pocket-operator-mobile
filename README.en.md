# Pocket Operator mobile v16.2

[Polska dokumentacja](README.md)

An accessible Windows synthesizer, drum machine, 16-step sequencer and melody
looper. Version 16 adds MIDI control mapping and learning, controller buttons,
relative encoders, Polish/English catalogs, themes and mandatory first-run setup.
It preserves the musical features consolidated in v15 from six historical lines.

Version 16.1 adds consistent spoken change feedback for MIDI and computer
keyboard controls, with independent persistent switches for both sources.
Version 16.2 adds musical ±2-semitone Pitch Bend, bend recording and individually
disableable assignments. AKM322 and NI presets are bundled in GitHub source
and portable releases.

## Portable startup

1. Download the latest Windows ZIP from [GitHub Releases](https://github.com/Pates2004/pocket-operator-mobile/releases).
2. Extract the entire directory to a writable location.
3. Run `PocketOperator-mobile.exe`. No Python installation is required.
4. Select both language and theme, then activate **Continue**.

Both choices initially have no selection. Continue remains disabled until both
are selected. Cancel or the window close button exits without completing setup;
the next launch asks again. Older settings without completed setup also require
these choices. Nothing is saved merely by opening the dialog.

Change either choice later through **Settings → Language and theme...**.
Themes: System, Light and Dark. Native Windows controls retain platform-specific
rendering. Usage hints can be disabled under **Settings → Show usage hints**;
essential labels, errors and explicitly opened help remain available.

## Running from source

Windows 10/11 and Python 3.10+ are required for the source version.

```powershell
python -m pip install -r requirements.txt
python run.py
```

`Graj.bat` uses an existing portable build in `Installfiles` first. Otherwise
`Start.ps1` creates a local `.venv`, installs missing dependencies and runs the
program. This preparation requires an installed Python and internet access.
Python 3.12 is preferred when available. The portable release avoids these steps.
`python main.py` also goes through mandatory setup.

The startup failure diagnosed on the development PC was missing wxPython, NumPy,
SoundDevice, Mido and SciPy in its system Python. The old launcher selected
interpreters without preparing their dependencies. Windows' chosen audio output
is retained: a virtual cable is a valid output, but hearing its signal requires
the corresponding routing. Select another output from Audio if desired.

Dependencies: wxPython (native UI), NumPy (DSP), sounddevice (PortAudio),
mido/python-rtmidi (MIDI), SciPy (WAV) and accessible-output2 (screen-reader speech).

## Instruments and notes

| Instrument | Shortcut | Knob A |
| --- | --- | --- |
| Square | Ctrl+F1 | Pulse width |
| Saw | Ctrl+F2 | Breakpoint |
| Triangle | Ctrl+F3 | Saturation |
| Noise | Ctrl+F4 | Smoothing/color |
| DrumKit | Ctrl+F5 | Drum pitch/color |

Instrument B controls decay/release. Sustain holds melodic voices until release;
when disabled, the same control determines automatic decay. Smooth release
preserves the current envelope level when changing from decay to release;
disabling it retains legacy behavior. Glide starts the next note at the previous
frequency. PANIC resets held notes, drum shots, delay and glide history.

The lower PC row starts at C4:

```text
Z S X D C V G B H N J M , L . ; /
```

The upper row continues the scale:

```text
Q 2 W 3 E 4 R 5 T 6 Y 7 U
```

Ctrl+Up/Down changes octave; Ctrl+Left resets it. Range: -3 through +3.
Ctrl+H enables triads: major on white keys, minor on black keys. Releasing a key
releases every voice in its chord. Ctrl+B blocks operating-system key repeats.
Windows punctuation key codes are normalized alongside ASCII codes.

## Layers

Every new note copies the current layer set, so changing layers does not cut off
an existing voice. Each layer has independent A (timbre) and B (mix level).

| Layer | Toggle | Character |
| --- | --- | --- |
| Octave Down | Alt+Backtick | Main waveform one octave lower |
| Sub Square | Alt+1 | Square sub-bass |
| Sub Octave | Alt+2 | Main waveform one octave lower |
| Fifth | Alt+3 | Perfect fifth |
| Maj 3rd | Alt+4 | Major third |
| Min 3rd | Alt+5 | Minor third |
| Octave Up | Alt+6 | Square one octave higher |
| Detune | Alt+7 | Detuned second oscillator |
| Noise | Alt+8 | Colored noise |
| Digital | Alt+9 | Quantized square |
| Harmonics | Alt+0 | Additional harmonic content |
| Organ Stack | Alt+- | Organ-like harmonic stack |
| Vinyl | Alt+= | Bipolar crackles |
| Sub Sine | Alt+Backslash | Saturated sine sub-bass |

With no selected target, layer knobs affect active layers and the global value.
With explicit targets in Control, they affect only those targets. With no active
layers, values seed the inactive layer catalog. Disabling a layer removes its
target selection. Ctrl+NumDel selects all active targets; pressing again clears
them. Ctrl+Shift+Backspace disables all layers.

## Effects and Punch-In

The processing order is Noise, Fuzz, Distortion, BitCrush, Decimator, RingMod,
Tremolo, Chopper, Sidechain, LPF, HPF, Reverb, Glitch.

| Effect | Hold with Ctrl+Shift | A | B |
| --- | --- | --- | --- |
| Reverb | Backtick | Wet/dry | Feedback/length |
| Low Pass | 1 | Filter amount | Wet/dry |
| High Pass | 2 | Low-frequency removal | Wet/dry |
| BitCrush | 3 | Quantization | Wet/dry |
| Distortion | 4 | Drive | Wet/dry |
| Chopper | 5 | Gate rate | Depth |
| Sidechain | 6 | Pumping rate | Depth |
| Tremolo | 7 | Rate | Depth |
| RingMod | 8 | Modulator frequency | Wet/dry |
| Decimator | 9 | Sample-and-hold length | Wet/dry |
| Fuzz | 0 | Gain | Wet/dry |
| Glitch | - | Chunk count | Wet/dry |
| Noise | = | Noise level | Intensity |

Hold the Punch-In shortcut to activate its effect temporarily. Release restores
the earlier state, including effects already latched on through the Effects menu.
Alt+Shift+Backspace disables all effects. Effect targets use the same selection
rules as layers; Ctrl+Shift+NumDel toggles all active effect targets.

## Control matrix and knobs

With Ctrl, numpad `/ 1 2 3 4 5 6 7 8 9 0 * - .` select layers in the table order
above. With Ctrl+Shift they select effects in their table order, ending at `-`;
`.` has no effect assignment. NumLock can affect native keyboard codes.
Inactive layers/effects cannot be selected and this is announced.

| Knobs | Increase/decrease A | Increase/decrease B |
| --- | --- | --- |
| Instrument | PgUp/PgDn | Home/End |
| Layers | Ctrl+Alt+PgUp/PgDn | Ctrl+Alt+Home/End |
| Effects | Alt+PgUp/PgDn | Alt+Home/End |

Each step is five percentage points. Ctrl+PgUp/PgDn and Ctrl+Home/End set
instrument A/B extremes. Delete and Backspace reset instrument A/B to 50%/20%;
the Ctrl variants also work. Ctrl+Alt+Delete/Backspace resets layers;
Alt+Delete/Backspace resets effects. Precise values for all six groups are in Edit.
Instrument/layer A ranges from 1–99%; other knobs range from 0–100%.

Legacy aliases: Ctrl+-/= /0 lower, raise or reset octave;
Ctrl+Shift+PgUp/PgDn/Home/End changes FX smoothly;
Ctrl+Shift+Alt+PgUp/PgDn/Home/End sets layer extremes;
Ctrl+Shift+Alt+Delete/Backspace resets layer A/B.

## Drums, sequencer and recording

F5–F12 trigger Kick, Snare, HiHat, Tom, Clap, Cowbell, Crash and Laser.
The corresponding global shortcuts are Ctrl+Shift+Z/X/C/V/B/N/M/comma.
Ctrl+Shift+P toggles global drums. DrumKit chooses voices modulo eight.
Instrument A changes drum tone/pitch; B changes decay. Each drum has its own
algorithm; Crash includes a controllable metallic component.

Space starts/stops one 16-step 4/4 bar. Ctrl+R toggles recording and starts the
loop if necessary. PC and MIDI notes are recorded with releases and velocity.
Live-monitored events are not duplicated in the recording cycle. Restarting plays
the first loop correctly. BPM changes scale melody timing to retain beat position.
Stop releases voices. Edit can clear melody, drums or the complete sequencer,
after confirmation. Tempo presets and custom BPM are available in the menus.

Ctrl+E opens the drum editor: Left/Right selects a step, Up/Down a drum,
Space toggles it and Escape closes the editor. The screen reader receives
instrument, step and state.

## MIDI control mapping

### Spoken change feedback

Settings contains two independent switches: **Speak MIDI changes**
(`Ctrl+Alt+Shift+F9`) and **Speak computer keyboard changes**
(`Ctrl+Alt+Shift+F10`). Enable both, either one or neither. Both default to enabled,
including when migrating an older INI. The choice saves immediately in the
`FEEDBACK` section of `po.ini`. Errors, readiness and confirmation of the feedback
mode itself remain available.

MIDI buttons can map to **Toggle MIDI change speech**, **Toggle computer keyboard
change speech**, or **Cycle change speech sources**, using Button mode. Cycle
selects both, MIDI only, computer keyboard only, then off.

Knobs announce the actual parameter name and value. Unmapped controls, unchanged
values and already-reached limits remain silent. Rapid MIDI movement is coalesced
without a speech backlog, retaining the final value when movement stops.
Computer keyboard changes are announced immediately.

### Learning and editing

Select an input through MIDI, then open **MIDI → MIDI mappings...**.

1. Activate **Learn next control**.
2. Move a hardware knob or press a button.
3. Select its action and controller mode.
4. Activate **Save mapping**.

Learning identifies the source; saving is a separate deliberate action. You can
also enter type, channel and number manually. Channels are 1–16 in the interface,
0–15 in JSON; Any channel is `null`. Saving an existing source replaces its entry.
Delete selected mapping removes that entry only. Changes are saved immediately.
The read-only monitor shows the most recent incoming control message.

To disable an entry temporarily, select it, clear **Assignment enabled** and
activate **Save mapping**. Its disabled state remains visible and persists after
restart. Re-enable and save to restore it. Disabled entries consume their MIDI
source, including note pads; deleting an entry instead restores ordinary MIDI
handling for its note/pedal. Empty lists and deleted assignments are not
automatically recreated. Explicitly loading a controller profile replaces the
list with that profile's enabled defaults.

### Musical Pitch Bend

Factory profiles map the pitch wheel/strip to ±2 semitones with an exact neutral
center. It affects existing and future MIDI notes on the matching channel,
including Glide, without bending computer keyboard notes or other MIDI channels.
Bend movements are recorded in the looper, saved in projects and rendered to WAV.
Stop, PANIC, port close and editing/disabling a mapping restore neutral pitch;
disabling the wheel mid-bend cannot leave notes detuned.

You can disable, delete or remap it. The musical Pitch Bend action requires
Absolute mode; NI relative-knob presets still use Absolute mode for the wheel.

Supported sources: CC, Note On/Off, Program Change, Pitch Bend, Channel Pressure,
Start/Continue/Stop and Universal Realtime MIDI Machine Control SysEx. Mapped notes
become buttons; other notes continue playing. CC64 sustain and CC120/123 retain
their standard behavior unless explicitly remapped. Separate MIDI channels keep
independent note and sustain state. Missing saved ports are reported instead of
silently choosing another controller.

| Mode | Meaning |
| --- | --- |
| Absolute | Normal 0–127 knob/slider; Pitch Bend uses all 14 bits |
| Relative 1/127 | Positive 1, negative 127; NI Relative |
| Relative 65/63 | Center 64, positive 65, negative 63; NI Relative Offset |
| Relative 1/65 | Sign/magnitude, positive 1, negative 65 |
| Button | One action per press; release does not trigger again |
| Momentary | Layer/effect active while held; restores its earlier state |

Relative modes have configurable step size and inversion. A single MIDI byte
does not identify an encoder mode reliably; choose the hardware's configured mode.

Targets include all six knob groups, individual A/B for every layer/effect,
volume, BPM, playback, recording, PANIC, octave, next instrument, Sustain, Glide,
chords, individual layer/effect toggles and all eight drums. No C# rewrite is
needed for these standard MIDI messages.

### MIDIPLUS AKM322

The default AKM322 profile follows a real physical-control capture:

| Control | Message | Action |
| --- | --- | --- |
| DATA encoder | CC10, observed absolute | Instrument A |
| Left spring-centered wheel | Pitch Bend | MIDI note pitch ±2 semitones |
| Knob 1 | CC21 | Instrument B |
| Knob 2 | CC22 | Layers A |
| Knob 3 | CC23 | Effects A |
| Modulation wheel | CC1 | Effects B |
| Optional volume control | CC7, standard, not observed in this capture | Volume |
| Play / Stop / Record | MMC 2 / 1 / 6 | Play / Stop / Record |

If only DATA seems audible, check the other controls' targets: knob 1 controls
decay/release (with Sustain, hear it after releasing a note), knob 2 controls
active layers and knob 3 active effects. Enable Sub Square with Alt+1, play a
new note and turn knob 2. Enable an effect from Effects before turning knob 3.
Knob movement does not activate layers/effects automatically. With an inactive
group it updates stored parameters for later use.

The profile loads on first detection, or can be loaded manually from the mapping
dialog. If the keyboard was reprogrammed, use Learn. Some buttons operate only
inside the keyboard and send nothing to the PC; software cannot intercept those.
The [official AKM322 manual](https://www.midiplus.com.tw/cn/MIDIPLUS-Download-detail/0/Manual_Of_AKM322_EN/)
describes editing the encoder, knobs and transport buttons.

An unmodified v16.0/v16.1 AKM322 preset is upgraded with the missing wheel.
Custom lists are preserved: use Learn to add the wheel or explicitly reload the
profile if needed. Once using v16.2, disabled/deleted bindings are not restored.

### Native Instruments

Use ordinary MIDI mode. The manufacturer's combinations are SHIFT+MIDI/PLUG-IN
for M32, A-Series and S-Series MK2, and SHIFT+INSTANCE for S-Series MK1. MK3 uses
the model/firmware's MIDI settings. See the
[official MIDI mode instructions](https://support.native-instruments.com/support/solutions/articles/69000880031-native-instruments-switching-your-controller-to-midi-mode).

NI CC14–21 Relative and NI CC14–21 Relative Offset are configurable eight-control
templates, not a claim about every NI model's factory CC assignments. Configure
CC14–21 in NI's editor or learn the numbers in your current template. The relative
encodings follow the [NI MIDI control documentation](https://docs.native-instruments.com/online-guides/komplete-kontrol-manual/en/automation-and-midi-control.html).
NKS, display/LED feedback and proprietary DAW/HID integration are not implemented.
NI hardware was not connected during validation; decoding and routing have tests.

New configurations recognize KOMPLETE/KONTROL/Native Instruments port names and
choose **NI CC14–21 Absolute**, preferring a musical input over a DAW endpoint.
The eight knobs control instrument A/B, layers A/B, effects A/B, volume and BPM;
CC1 controls FX B, Pitch Bend controls note pitch and realtime/MMC controls
transport. The [official M32 manual](https://docs.native-instruments.com/pdf-guides/komplete_kontrol/KOMPLETE_KONTROL_M32_Manual_English_200127.pdf)
shows the CC14–21 layout. These are ready-to-use starting presets rather than
recognition of arbitrary edited NI templates. Saved custom or deliberately empty
mappings take priority over automatic profile detection.

## Preferences, projects and WAV

`po.ini` is beside the executable in portable, or beside main.py in source.
The first confirmed setup writes INTERFACE with language, theme and completion.
Session saving preserves that section and includes instrument, BPM, octave,
volume, toggles, hints, active layers/effects, selected targets, every A/B value,
audio/MIDI devices, all drum patterns, melody and MIDI mappings. Writes use a
temporary file and atomic replacement. Own application data never falls back to
AppData; use a writable application directory. Startup diagnostics are in
`logs/startup.log` beside the program.

Ctrl+Shift+Delete asks for confirmation, removes preferences and exits without
recreating them. The next start requires setup again.

Ctrl+O opens a project; Ctrl+Shift+S saves readable `.po15` JSON. The extension
is retained for v15 compatibility; new mapping fields are optional in older
projects. Identifier: `pocket-operator-mobile-project`. V16.2 writes schema 2 and
also reads schema 1. The new schema prevents older releases from treating
disabled mappings as active. A project stores
musical state and mappings; language/theme remain application preferences.
Opening a project preserves current hardware selection. Invalid structures or
unsupported schemas are rejected before changing the session.

Ctrl+Shift+E exports 1–99 loops as mono, 44.1 kHz, 16-bit PCM WAV. Events are
placed at sample positions. A separate offline engine renders notes, all drums,
layers and effects without mutating live voices, delay or audio-device state.
Non-silent output is normalized. Projects and WAV files are written only to
locations chosen by the user.

## Accessibility and troubleshooting

Menus, choices, mapping lists, buttons and dialogs are native wxPython controls,
usable by keyboard. Alt accesses menus; F1 opens the full shortcut help.
accessible-output2 provides announcements; without its driver they go to the
console. Essential control names and errors are not hidden by disabling hints.
Direct validation with NVDA requires a running reader; automated native-control
checks alone do not certify actual spoken output.

No sound: select Audio → Select audio output, check Windows routing/volume,
use Alt+Left to restore 20% volume, and Ctrl+Shift+Escape for PANIC. The selected
Windows default is retained even when it is a virtual cable.

No MIDI: check Windows device presence, close other software holding the port,
select/refresh the input, and inspect the mapping monitor. A local-only keyboard
button cannot be learned. NI controllers must send standard MIDI rather than
remaining in a proprietary DAW mode.

Source import failure: install requirements using the same interpreter as run.py,
or use portable. Invalid settings: inspect po.ini, retain needed musical data,
or use confirmed factory reset. A malformed sequencer section is skipped.

## Development and release

```powershell
python -m pip install -r requirements-dev.txt
python -B -m unittest -v
python -m ruff check . --no-cache
python -m pip check
python build_release.py --work-dir D:\work\Workspace\8bit\release-build
```

The build goes to `Installfiles/PocketOperator-mobile`, refuses to overwrite an
existing release, and keeps build intermediates in the explicitly supplied work
directory. Editable UTF-8 JSON catalogs are `langs/pl.lng` and `langs/en.lng`.
Both catalogs must contain the same keys and compatible template placeholders.

Source modules: main.py (window/session), synth.py (audio), sequencer.py (timing),
midi_handler.py (ports/notes), midi_mapping.py (routing), midi_dialog.py (editor),
preferences.py/app_paths.py (portable state), localization.py/ui_support.py
(language/setup/theme), run.py/Start.ps1/Graj.bat (startup).
test_launch.py covers the original engine and test_v16.py covers new behavior.
feedback.py and test_feedback.py implement and verify source-specific speech,
real parameter changes and coalescing of the final MIDI value.

Historical public compatibility aliases remain: set_vol/set_volume, vol/volume,
layers/active_layers, fx/active_fx, sus/sustain_enabled, glide/glide_enabled,
trigger_drum/trig_drum, set_fx_a/b and set_layer_knob_a/b.

The application runs locally. It does not send audio, projects, configuration or
MIDI to the network. Dependency installation and downloading releases are separate
network operations. Internal project evidence and discarded build files are kept
outside the source repository under the workstation's central work directories.
