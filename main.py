import configparser
import json
import math
from pathlib import Path

import sounddevice as sd
import wx

import midi_handler
import midi_mapping
import preferences
import sequencer
import synth
import ui_support
from app_paths import APP_DIR
from feedback import ChangeFeedback
from localization import tr
from midi_dialog import MidiMappingDialog

try:
    from accessible_output2.outputs.auto import Auto

    SPEECH_AVAILABLE = True
except ImportError:
    Auto = None
    SPEECH_AVAILABLE = False


APP_NAME = "Pocket Operator mobile"
APP_VERSION = "17.0"
PROJECT_FORMAT = "pocket-operator-mobile-project"
BASE_DIR = APP_DIR
CONFIG_PATH = BASE_DIR / "po.ini"
BASE_FREQ_C4 = 261.63

KEY_OFFSET_MAP = {
    ord("Z"): 0,
    ord("S"): 1,
    ord("X"): 2,
    ord("D"): 3,
    ord("C"): 4,
    ord("V"): 5,
    ord("G"): 6,
    ord("B"): 7,
    ord("H"): 8,
    ord("N"): 9,
    ord("J"): 10,
    ord("M"): 11,
    ord(","): 12,
    ord("L"): 13,
    ord("."): 14,
    ord(";"): 15,
    ord("/"): 16,
    ord("Q"): 12,
    ord("2"): 13,
    ord("W"): 14,
    ord("3"): 15,
    ord("E"): 16,
    ord("4"): 17,
    ord("R"): 17,
    ord("5"): 18,
    ord("T"): 19,
    ord("6"): 20,
    ord("Y"): 21,
    ord("7"): 22,
    ord("U"): 23,
}

BLACK_KEYS = {
    ord("S"),
    ord("D"),
    ord("G"),
    ord("H"),
    ord("J"),
    ord("L"),
    ord(";"),
    ord("2"),
    ord("3"),
    ord("5"),
    ord("6"),
    ord("7"),
}

# Windows reports VK_OEM codes instead of ASCII for punctuation keys.
KEY_CODE_ALIASES = {
    186: ord(";"),
    187: ord("="),
    188: ord(","),
    189: ord("-"),
    190: ord("."),
    191: ord("/"),
    192: ord("`"),
    220: ord("\\"),
}


class Speaker:
    def __init__(self):
        self.driver = None
        if SPEECH_AVAILABLE:
            try:
                self.driver = Auto()
            except Exception as error:  # noqa: BLE001 - optional external speech driver
                print(f"Nie udało się uruchomić mowy: {error}")

    def say(self, text):
        text = tr(text)
        if self.driver:
            try:
                self.driver.output(str(text), True)
                return
            except Exception as error:  # noqa: BLE001 - speech failures must not stop audio
                print(f"Błąd syntezy mowy: {error}")
        print(f"[SAY] {text}")


class ShortcutsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=tr("Skróty"), size=(650, 550))
        text = wx.TextCtrl(
            self,
            value=tr("help"),
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        button = wx.Button(self, wx.ID_OK, "OK")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(text, 1, wx.EXPAND | wx.ALL, 10)
        layout.Add(button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        self.SetSizer(layout)
        ui_support.apply_theme(self)
        text.SetFocus()


class DrumEditorDialog(wx.Dialog):
    def __init__(self, parent, sequencer_instance):
        super().__init__(parent, title=tr("Edytor perkusji"), size=(420, 180))
        self.seq = sequencer_instance
        self.speaker = parent.speaker
        self.feedback = parent.feedback
        self.instruments = list(sequencer.DRUM_INSTRUMENTS)
        self.instrument_index = 0
        self.step = 0

        panel = wx.Panel(self, style=wx.WANTS_CHARS)
        self.label = wx.StaticText(panel, label="")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.label, 1, wx.EXPAND | wx.ALL, 20)
        panel.SetSizer(layout)
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key)
        ui_support.apply_theme(self)
        self.update_view(speak=True)
        panel.SetFocus()

    def update_view(self, speak=False):
        instrument = self.instruments[self.instrument_index]
        active = self.seq.drum_tracks[instrument][self.step]
        state = "włączony" if active else "pusty"
        message = f"{instrument}, krok {self.step + 1}, {state}"
        self.label.SetLabel(tr(message))
        if speak:
            self.feedback.announce(message)

    def on_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RIGHT:
            self.step = (self.step + 1) % 16
            self.update_view(speak=True)
        elif key == wx.WXK_LEFT:
            self.step = (self.step - 1) % 16
            self.update_view(speak=True)
        elif key == wx.WXK_DOWN:
            self.instrument_index = (self.instrument_index + 1) % len(self.instruments)
            self.update_view(speak=True)
        elif key == wx.WXK_UP:
            self.instrument_index = (self.instrument_index - 1) % len(self.instruments)
            self.update_view(speak=True)
        elif key == wx.WXK_SPACE:
            active = self.seq.toggle_drum(
                self.instruments[self.instrument_index], self.step
            )
            self.feedback.announce("Włączony" if active else "Wyłączony")
            self.update_view()
        elif key == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()


class MainFrame(wx.Frame):
    LAYERS = (
        ("Octave Down", "oct_down", "`"),
        ("Sub Square", "sub_sq", "1"),
        ("Sub Octave", "sub_oct", "2"),
        ("Fifth", "fifth", "3"),
        ("Maj 3rd", "maj3", "4"),
        ("Min 3rd", "min3", "5"),
        ("Octave Up", "oct_up", "6"),
        ("Detune", "detune", "7"),
        ("Noise", "noise", "8"),
        ("Digital", "digital", "9"),
        ("Harmonics", "harm", "0"),
        ("Organ Stack", "organ", "-"),
        ("Vinyl", "vinyl", "="),
        ("Sub Sine", "sub_sin", "\\"),
    )
    EFFECTS = (
        ("Reverb", "verb", "`"),
        ("Low Pass", "lpf", "1"),
        ("High Pass", "hpf", "2"),
        ("BitCrush", "crush", "3"),
        ("Distortion", "dist", "4"),
        ("Chopper", "chop", "5"),
        ("Sidechain", "side", "6"),
        ("Tremolo", "trem", "7"),
        ("RingMod", "ring", "8"),
        ("Decimator", "deci", "9"),
        ("Fuzz", "fuzz", "0"),
        ("Glitch", "glit", "-"),
        ("Noise", "noiz", "="),
    )

    def __init__(
        self,
        synth_instance=None,
        auto_start=True,
        auto_midi=True,
        load_config=True,
    ):
        super().__init__(
            parent=None,
            title=f"{APP_NAME} v{APP_VERSION}",
            size=(680, 320),
        )
        self.speaker = Speaker()
        self.feedback = ChangeFeedback(self.speaker.say, wx.CallLater)
        self._closing = False
        self._skip_save = False
        self.audio_device = None
        self.audio_device_name = ""
        self.audio_error = None

        if synth_instance is not None:
            self.synth = synth_instance
        else:
            try:
                self.synth = synth.Synthesizer()
            except Exception as error:  # noqa: BLE001 - keep the application available without audio
                self.audio_error = error
                self.synth = synth.Synthesizer(create_stream=False)

        self.seq = sequencer.Sequencer(self.synth)
        self.mapper = midi_mapping.MidiMapper(
            lambda action, mode, value: self.queue_midi(
                self.handle_midi_action, action, mode, value
            ),
            pitch_callback=lambda channel, value: self.queue_midi(
                self.handle_pitch_bend, channel, value
            ),
            on_change=self.reset_midi_controls,
        )
        self.midi = midi_handler.MidiInputHandler(
            self.synth,
            lambda: self.waveform,
            self.record_midi_event,
            mapper=self.mapper,
        )
        self.waveform = "square"
        self.octave = 0
        self.bpm = 120
        self.pc_keyboard = True
        self.block_repeat = True
        self.global_drums = True
        self.chord_mode = False
        self.key_voices = {}
        self.punch_in_keys = {}
        self.recorded_notes = set()
        self.recorded_bend_channels = set()
        self.recorded_expression = False
        self.saved_midi = ""
        self.midi_profile_initialized = False
        self.midi_live_apply = False
        self.midi_gates = {}
        self.show_hints = True

        self.panel = wx.Panel(self, style=wx.WANTS_CHARS)
        self.main_label = wx.StaticText(
            self.panel,
            label=f"{APP_NAME} v{APP_VERSION}",
        )
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.main_label, 1, wx.ALIGN_CENTER | wx.ALL, 30)
        self.panel.SetSizer(layout)

        self.create_menu()
        self.panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.panel.Bind(wx.EVT_KEY_UP, self.on_key_up)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.CreateStatusBar()
        self._set_default_checks()

        if load_config:
            self.load_settings()
        language, theme, complete = preferences.appearance(CONFIG_PATH)
        ui_support.apply_theme(self, theme if complete else "system")
        self.update_hint()
        if auto_start:
            try:
                self.synth.start()
            except Exception as error:  # noqa: BLE001 - keep the application available without audio
                self.audio_error = error
            else:
                try:
                    default_output = int(sd.default.device[1])
                    if self.audio_device is None and default_output >= 0:
                        self.audio_device = default_output
                        self.audio_device_name = str(
                            sd.query_devices(default_output)["name"]
                        )
                except (IndexError, TypeError, ValueError, sd.PortAudioError) as error:
                    print(f"Nie udało się zapamiętać domyślnego audio: {error}")
        if auto_midi:
            self.open_saved_midi()

        self.update_status()
        wx.CallAfter(self.panel.SetFocus)
        if self.audio_error:
            wx.CallAfter(
                ui_support.message_box,
                f"Silnik działa bez wyjścia audio:\n{self.audio_error}",
                "Błąd audio",
                wx.OK | wx.ICON_WARNING,
            )
        self.speaker.say(f"{APP_NAME} gotowy")

    def create_menu(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        open_project_item = file_menu.Append(wx.ID_ANY, "Otwórz projekt v15...\tCtrl+O")
        save_project_item = file_menu.Append(
            wx.ID_ANY, "Zapisz projekt v15...\tCtrl+Shift+S"
        )
        file_menu.AppendSeparator()
        export_item = file_menu.Append(wx.ID_ANY, "Eksport WAV...\tCtrl+Shift+E")
        file_menu.AppendSeparator()
        reset_item = file_menu.Append(wx.ID_ANY, "Reset fabryczny\tCtrl+Shift+Del")
        exit_item = file_menu.Append(wx.ID_EXIT, "Wyjdź\tAlt+F4")
        self.Bind(wx.EVT_MENU, self.open_project, open_project_item)
        self.Bind(wx.EVT_MENU, self.save_project, save_project_item)
        self.Bind(wx.EVT_MENU, self.export_wav, export_item)
        self.Bind(wx.EVT_MENU, self.factory_reset, reset_item)
        self.Bind(wx.EVT_MENU, self.on_close, exit_item)

        instrument_menu = wx.Menu()
        self.wave_items = {}
        waveforms = [
            ("Square", "square", "F1"),
            ("Saw", "saw", "F2"),
            ("Triangle", "triangle", "F3"),
            ("Noise", "noise", "F4"),
            ("DrumKit", "drum_kit", "F5"),
        ]
        for name, code, key in waveforms:
            item = instrument_menu.Append(
                wx.ID_ANY,
                f"{name}\tCtrl+{key}",
                kind=wx.ITEM_RADIO,
            )
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=code: self.set_waveform(value),
                item,
            )
            self.wave_items[code] = item
        instrument_menu.AppendSeparator()
        for parameter, label in (
            ("brightness", "Brightness (filter)..."),
            ("vibrato", "Vibrato depth..."),
        ):
            item = instrument_menu.Append(wx.ID_ANY, label)
            self.Bind(
                wx.EVT_MENU, lambda event, key=parameter: self.ask_expression(key), item
            )

        layer_menu = wx.Menu()
        clear_layers = layer_menu.Append(
            wx.ID_ANY, "Wyłącz wszystkie\tCtrl+Shift+Backspace"
        )
        self.Bind(wx.EVT_MENU, self.clear_layers, clear_layers)
        layer_menu.AppendSeparator()
        self.layer_items = {}
        self.layer_control_items = {}
        for name, code, key in self.LAYERS:
            item = layer_menu.Append(
                wx.ID_ANY,
                f"{name}\tAlt+{key}",
                kind=wx.ITEM_CHECK,
            )
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=code: self.toggle_layer(value),
                item,
            )
            self.layer_items[code] = item

        effects_menu = wx.Menu()
        clear_effects = effects_menu.Append(
            wx.ID_ANY, "Wyłącz wszystkie\tAlt+Shift+Backspace"
        )
        self.Bind(wx.EVT_MENU, self.clear_effects, clear_effects)
        effects_menu.AppendSeparator()
        self.effect_items = {}
        self.effect_control_items = {}
        for name, code, key in self.EFFECTS:
            item = effects_menu.Append(
                wx.ID_ANY,
                f"{name} (stały; Punch-In Ctrl+Shift+{key})",
                kind=wx.ITEM_CHECK,
            )
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=code: self.toggle_effect(value),
                item,
            )
            self.effect_items[code] = item

        control_menu = wx.Menu()
        layer_control_menu = wx.Menu()
        all_layers = layer_control_menu.Append(
            wx.ID_ANY, "Przełącz wszystkie (Ctrl+NumDel)"
        )
        self.Bind(wx.EVT_MENU, self.toggle_all_layer_targets, all_layers)
        layer_control_menu.AppendSeparator()
        for name, code, _ in self.LAYERS:
            item = layer_control_menu.Append(
                wx.ID_ANY, f"Steruj: {name}", kind=wx.ITEM_CHECK
            )
            item.Enable(False)
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=code: self.toggle_layer_target(value),
                item,
            )
            self.layer_control_items[code] = item
        control_menu.AppendSubMenu(layer_control_menu, "Cel gałek warstw")

        effect_control_menu = wx.Menu()
        all_effects = effect_control_menu.Append(
            wx.ID_ANY, "Przełącz wszystkie (Ctrl+Shift+NumDel)"
        )
        self.Bind(wx.EVT_MENU, self.toggle_all_effect_targets, all_effects)
        effect_control_menu.AppendSeparator()
        for name, code, _ in self.EFFECTS:
            item = effect_control_menu.Append(
                wx.ID_ANY, f"Steruj: {name}", kind=wx.ITEM_CHECK
            )
            item.Enable(False)
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=code: self.toggle_effect_target(value),
                item,
            )
            self.effect_control_items[code] = item
        control_menu.AppendSubMenu(effect_control_menu, "Cel gałek efektów")

        settings_menu = wx.Menu()
        self.feedback_midi_item = settings_menu.Append(
            wx.ID_ANY, "Speak MIDI changes\tCtrl+Alt+Shift+F9", kind=wx.ITEM_CHECK
        )
        self.feedback_keyboard_item = settings_menu.Append(
            wx.ID_ANY,
            "Speak computer keyboard changes\tCtrl+Alt+Shift+F10",
            kind=wx.ITEM_CHECK,
        )
        self.feedback_midi_item.Check(self.feedback.enabled["midi"])
        self.feedback_keyboard_item.Check(self.feedback.enabled["keyboard"])
        self.Bind(
            wx.EVT_MENU,
            lambda event: self.toggle_feedback("midi"),
            self.feedback_midi_item,
        )
        self.Bind(
            wx.EVT_MENU,
            lambda event: self.toggle_feedback("keyboard"),
            self.feedback_keyboard_item,
        )
        settings_menu.AppendSeparator()
        appearance_item = settings_menu.Append(wx.ID_ANY, "Language and theme...")
        self.Bind(wx.EVT_MENU, self.change_appearance, appearance_item)
        self.hints_item = settings_menu.Append(
            wx.ID_ANY, "Show usage hints", kind=wx.ITEM_CHECK
        )
        self.hints_item.Check(self.show_hints)
        self.Bind(wx.EVT_MENU, self.toggle_hints, self.hints_item)
        settings_menu.AppendSeparator()
        self.sustain_item = settings_menu.Append(
            wx.ID_ANY, "Sustain\tCtrl+S", kind=wx.ITEM_CHECK
        )
        self.glide_item = settings_menu.Append(
            wx.ID_ANY, "Glide\tCtrl+G", kind=wx.ITEM_CHECK
        )
        self.chord_item = settings_menu.Append(
            wx.ID_ANY, "Akordy\tCtrl+H", kind=wx.ITEM_CHECK
        )
        self.global_drums_item = settings_menu.Append(
            wx.ID_ANY, "Globalne bębny\tCtrl+Shift+P", kind=wx.ITEM_CHECK
        )
        self.release_item = settings_menu.Append(
            wx.ID_ANY, "Wyrównany release", kind=wx.ITEM_CHECK
        )
        self.pc_keyboard_item = settings_menu.Append(
            wx.ID_ANY, "Klawiatura PC", kind=wx.ITEM_CHECK
        )
        self.block_repeat_item = settings_menu.Append(
            wx.ID_ANY, "Blokada powtórzeń\tCtrl+B", kind=wx.ITEM_CHECK
        )
        for item, callback in (
            (self.sustain_item, self.on_sustain),
            (self.glide_item, self.on_glide),
            (self.chord_item, self.on_chord),
            (self.global_drums_item, self.on_global_drums),
            (self.release_item, self.on_release),
            (self.pc_keyboard_item, self.on_pc_keyboard),
            (self.block_repeat_item, self.on_block_repeat),
        ):
            self.Bind(wx.EVT_MENU, callback, item)

        audio_menu = wx.Menu()
        audio_item = audio_menu.Append(wx.ID_ANY, "Wybierz wyjście audio...")
        self.Bind(wx.EVT_MENU, self.select_audio_device, audio_item)

        midi_menu = wx.Menu()
        midi_select = midi_menu.Append(wx.ID_ANY, "Wybierz wejście MIDI...")
        midi_refresh = midi_menu.Append(wx.ID_ANY, "Odśwież MIDI")
        midi_mapping_item = midi_menu.Append(wx.ID_ANY, "MIDI mappings...")
        self.Bind(wx.EVT_MENU, self.select_midi_device, midi_select)
        self.Bind(wx.EVT_MENU, self.refresh_midi, midi_refresh)
        self.Bind(wx.EVT_MENU, self.open_midi_mappings, midi_mapping_item)

        play_menu = wx.Menu()
        play_item = play_menu.Append(wx.ID_ANY, "Start/Stop\tSpace")
        record_item = play_menu.Append(wx.ID_ANY, "Nagrywanie\tCtrl+R")
        drum_editor = play_menu.Append(wx.ID_ANY, "Edytor perkusji\tCtrl+E")
        set_bpm = play_menu.Append(wx.ID_ANY, "Ustaw BPM...")
        set_octave = play_menu.Append(wx.ID_ANY, "Ustaw oktawę...")
        self.Bind(wx.EVT_MENU, self.toggle_playback, play_item)
        self.Bind(wx.EVT_MENU, self.toggle_recording, record_item)
        self.Bind(wx.EVT_MENU, self.open_drum_editor, drum_editor)
        self.Bind(wx.EVT_MENU, self.ask_bpm, set_bpm)
        self.Bind(wx.EVT_MENU, self.ask_octave, set_octave)

        edit_menu = wx.Menu()
        knob_commands = (
            ("Ustaw gałkę instrumentu A...", "main", "a"),
            ("Ustaw gałkę instrumentu B...", "main", "b"),
            ("Ustaw gałkę warstw A...", "layer", "a"),
            ("Ustaw gałkę warstw B...", "layer", "b"),
            ("Ustaw gałkę efektów A...", "fx", "a"),
            ("Ustaw gałkę efektów B...", "fx", "b"),
        )
        for label, target, parameter in knob_commands:
            item = edit_menu.Append(wx.ID_ANY, label)
            self.Bind(
                wx.EVT_MENU,
                lambda event, selected_target=target, selected_parameter=parameter: (
                    self.ask_knob(
                        selected_target,
                        selected_parameter,
                    )
                ),
                item,
            )
        edit_menu.AppendSeparator()
        clear_melody = edit_menu.Append(wx.ID_ANY, "Wyczyść melodię")
        clear_drums = edit_menu.Append(wx.ID_ANY, "Wyczyść patterny perkusji")
        clear_sequence = edit_menu.Append(wx.ID_ANY, "Wyczyść cały sekwencer")
        edit_menu.AppendSeparator()
        panic_item = edit_menu.Append(
            wx.ID_ANY, "PANIC — wycisz wszystko\tCtrl+Shift+Esc"
        )
        self.Bind(
            wx.EVT_MENU,
            lambda event: self.clear_sequencer("melody"),
            clear_melody,
        )
        self.Bind(
            wx.EVT_MENU,
            lambda event: self.clear_sequencer("drums"),
            clear_drums,
        )
        self.Bind(
            wx.EVT_MENU,
            lambda event: self.clear_sequencer("all"),
            clear_sequence,
        )
        self.Bind(wx.EVT_MENU, self.panic, panic_item)

        tempo_menu = wx.Menu()
        custom_tempo = tempo_menu.Append(wx.ID_ANY, "Ustaw własne BPM...")
        self.Bind(wx.EVT_MENU, self.ask_bpm, custom_tempo)
        tempo_menu.AppendSeparator()
        for preset in (60, 80, 100, 120, 140, 160, 180):
            item = tempo_menu.Append(wx.ID_ANY, f"{preset} BPM")
            self.Bind(
                wx.EVT_MENU,
                lambda event, value=preset: self.set_bpm(value),
                item,
            )

        help_menu = wx.Menu()
        shortcuts_item = help_menu.Append(wx.ID_ANY, "Skróty\tF1")
        about_item = help_menu.Append(wx.ID_ABOUT, "O programie")
        self.Bind(
            wx.EVT_MENU,
            lambda event: ShortcutsDialog(self).ShowModal(),
            shortcuts_item,
        )
        self.Bind(wx.EVT_MENU, self.show_about, about_item)

        for menu, title in (
            (file_menu, "&Plik"),
            (instrument_menu, "&Instrument"),
            (layer_menu, "&Warstwy"),
            (effects_menu, "&Efekty"),
            (control_menu, "&Sterowanie"),
            (settings_menu, "&Ustawienia"),
            (audio_menu, "&Audio"),
            (midi_menu, "&MIDI"),
            (play_menu, "&Gra"),
            (edit_menu, "&Edycja"),
            (tempo_menu, "&Tempo"),
            (help_menu, "&Pomoc"),
        ):
            menu_bar.Append(menu, title)
        self.SetMenuBar(menu_bar)
        for index in range(menu_bar.GetMenuCount()):
            ui_support.translate_menu(menu_bar.GetMenu(index))
            menu_bar.SetMenuLabel(index, tr(menu_bar.GetMenuLabel(index)))

    def update_hint(self):
        hint = "\n" + tr("Alt = menu, F1 = pomoc") if self.show_hints else ""
        self.main_label.SetLabel(f"{APP_NAME} v{APP_VERSION}{hint}")

    def toggle_hints(self, event):
        self.show_hints = event.IsChecked()
        self.update_hint()

    def change_appearance(self, event=None):
        selection = ui_support.ensure_setup(CONFIG_PATH, self, force=True)
        if selection is None:
            return
        self.feedback.cancel_pending()
        self.SetMenuBar(None)
        self.create_menu()
        for code, item in self.layer_items.items():
            item.Check(code in self.synth.layers)
        for code, item in self.effect_items.items():
            item.Check(code in self.synth.fx)
        self._set_default_checks()
        self._update_control_ui()
        ui_support.apply_theme(self, selection[1])
        self.update_hint()
        self.update_status()
        self.save_settings()

    def open_midi_mappings(self, event=None):
        with MidiMappingDialog(self) as dialog:
            dialog.ShowModal()

    def reset_midi_controls(self):
        if self._closing:
            return
        self.feedback.cancel_pending()
        self.mapper.invalidate_pending()
        previous_bends = dict(self.synth.pitch_bends)
        if hasattr(self, "midi"):
            self.midi.reset_controls()
        else:
            self.synth.reset_pitch_bend()
        if self.seq.recording:
            for channel in previous_bends:
                self.seq.record_event(
                    "pitch_bend", {"channel": channel, "semitones": 0.0}
                )
        for action, was_active in self.midi_gates.items():
            group, code = action.split(":")
            active = self.synth.layers if group == "layer" else self.synth.fx
            items = self.layer_items if group == "layer" else self.effect_items
            if not was_active:
                active.discard(code)
            items[code].Check(code in active)
        self.midi_gates.clear()
        self._update_control_ui()

    def queue_midi(self, callback, *args):
        wx.CallAfter(self.apply_queued_midi, self.mapper.generation, callback, args)

    def apply_queued_midi(self, generation, callback, args):
        if not self._closing and generation == self.mapper.generation:
            callback(*args)

    def handle_pitch_bend(self, channel, value):
        if self._closing:
            return
        semitones = (float(value) - 0.5) * 4.0
        if self.synth.set_pitch_bend(semitones, channel):
            if self.seq.recording:
                self.recorded_bend_channels.add(channel)
                self.seq.record_event(
                    "pitch_bend", {"channel": channel, "semitones": semitones}
                )
            with self.feedback.using_source("midi", continuous=True):
                self.feedback.announce(
                    tr(
                        "Pitch Bend, channel {channel}: {value} semitones",
                        channel=channel + 1,
                        value=f"{semitones:+.2f}",
                    )
                )

    def save_midi_mappings(self):
        self.midi_profile_initialized = True
        self.save_settings()

    def toggle_feedback(self, source):
        enabled = not self.feedback.enabled[source]
        self.feedback.set_enabled(source, enabled)
        item = (
            self.feedback_midi_item if source == "midi" else self.feedback_keyboard_item
        )
        item.Check(enabled)
        label = tr("MIDI") if source == "midi" else tr("Computer keyboard")
        state = tr("Enabled") if enabled else tr("Disabled")
        self.speaker.say(tr("{source} speech: {state}", source=label, state=state))
        self.save_settings()

    def cycle_feedback(self):
        modes = ((True, True), (False, True), (True, False), (False, False))
        current = self.feedback.enabled["keyboard"], self.feedback.enabled["midi"]
        keyboard, midi = modes[(modes.index(current) + 1) % len(modes)]
        for source, enabled in (("keyboard", keyboard), ("midi", midi)):
            self.feedback.set_enabled(source, enabled)
        self.feedback_keyboard_item.Check(keyboard)
        self.feedback_midi_item.Check(midi)
        labels = {
            (True, True): "Speech: keyboard and MIDI",
            (False, True): "Speech: MIDI only",
            (True, False): "Speech: computer keyboard only",
            (False, False): "Change speech disabled",
        }
        self.speaker.say(tr(labels[(keyboard, midi)]))
        self.save_settings()

    def handle_midi_action(self, action, mode, value):
        if self._closing:
            return
        with self.feedback.using_source(
            "midi", continuous=mode in {"absolute", "relative"}
        ):
            self._apply_midi_action(action, mode, value)

    def _apply_midi_action(self, action, mode, value):
        relative = mode == "relative"
        if action == "pitch_bend":
            self.handle_pitch_bend(0, value)
        elif action == "wave_select":
            waves = list(self.wave_items)
            index = (
                (waves.index(self.waveform) + (1 if value > 0 else -1)) % len(waves)
                if relative
                else min(len(waves) - 1, int(value * len(waves)))
            )
            self.set_waveform(waves[index])
        elif action in {"brightness", "vibrato"}:
            current = self.synth.values[action]
            self.set_expression(action, current + value if relative else value)
        elif action in {"main_a", "main_b", "layer_a", "layer_b", "fx_a", "fx_b"}:
            target, parameter = action.rsplit("_", 1)
            if relative:
                self.change_knob(target, parameter, delta=value)
            else:
                self.change_knob(target, parameter, absolute=value)
        elif action == "volume":
            previous = self.synth.vol
            self.synth.set_vol(self.synth.vol + value if relative else value)
            if self.synth.vol != previous:
                self.feedback.announce(f"Głośność {int(self.synth.vol * 100)} procent")
        elif action == "bpm":
            bpm = self.bpm + round(value * 280) if relative else 20 + round(value * 280)
            self.set_bpm(max(20, min(300, bpm)))
        elif action.startswith(("layer:", "effect:")):
            parts = action.split(":")
            group, code = parts[:2]
            if len(parts) == 3:
                key = f"{code}_{parts[2]}"
                current = self.synth.values[key]
                updated = max(0, min(1, current + value if relative else value))
                self.synth.restore_values({key: updated})
                if current != self.synth.values[key]:
                    self.announce_knob(
                        f"{group}:{code}:{parts[2]}", self.synth.values[key]
                    )
            else:
                active = self.synth.layers if group == "layer" else self.synth.fx
                items = self.layer_items if group == "layer" else self.effect_items
                was_active = code in active
                if mode == "gate":
                    if value:
                        self.midi_gates.setdefault(action, code in active)
                        active.add(code)
                    elif action in self.midi_gates and not self.midi_gates.pop(action):
                        active.discard(code)
                elif code in active:
                    active.remove(code)
                else:
                    active.add(code)
                items[code].Check(code in active)
                self._update_control_ui()
                if was_active != (code in active):
                    self.feedback.announce(
                        tr(
                            "{name}: {state}",
                            name=tr(action),
                            state=tr("Enabled") if code in active else tr("Disabled"),
                        )
                    )
        elif action.startswith("drum:"):
            self.synth.trigger_drum(action.split(":", 1)[1])
            self.feedback.announce(tr(action))
        elif action == "play":
            was_running = self.seq.running
            self.seq.play()
            if not was_running:
                self.feedback.announce("Start")
        elif action == "stop":
            was_running = self.seq.running
            self._close_recorded_notes()
            self.seq.stop()
            if was_running:
                self.feedback.announce("Stop")
        elif action == "record":
            self.toggle_recording()
        elif action == "play_toggle":
            self.toggle_playback()
        elif action == "panic":
            self.panic()
        elif action == "feedback_midi":
            self.toggle_feedback("midi")
        elif action == "feedback_keyboard":
            self.toggle_feedback("keyboard")
        elif action == "feedback_cycle":
            self.cycle_feedback()
        elif action in {"octave_up", "octave_down"}:
            self.set_octave(self.octave + (1 if action == "octave_up" else -1))
        elif action == "wave_next":
            waves = list(self.wave_items)
            self.set_waveform(waves[(waves.index(self.waveform) + 1) % len(waves)])
        elif action in {"sustain", "glide", "chord"}:
            item, callback = {
                "sustain": (self.sustain_item, self.on_sustain),
                "glide": (self.glide_item, self.on_glide),
                "chord": (self.chord_item, self.on_chord),
            }[action]
            self._toggle_menu_item(item, callback)
        self.update_status()

    def _set_default_checks(self):
        self.wave_items[self.waveform].Check(True)
        self.sustain_item.Check(self.synth.sus)
        self.glide_item.Check(self.synth.glide)
        self.chord_item.Check(self.chord_mode)
        self.global_drums_item.Check(self.global_drums)
        self.release_item.Check(self.synth.fix_rel)
        self.pc_keyboard_item.Check(self.pc_keyboard)
        self.block_repeat_item.Check(self.block_repeat)

    @staticmethod
    def _checked(event, item):
        if event is not None and hasattr(event, "IsChecked"):
            return event.IsChecked()
        return item.IsChecked()

    def _toggle_menu_item(self, item, callback):
        item.Check(not item.IsChecked())
        callback(item)

    def set_waveform(self, waveform):
        if waveform not in self.wave_items:
            return
        previous = self.waveform
        self.waveform = waveform
        self.wave_items[waveform].Check(True)
        if previous != waveform:
            self.feedback.announce(f"Instrument {waveform}")
        self.update_status()

    def set_octave(self, octave):
        previous = self.octave
        self.octave = max(-3, min(3, int(octave)))
        if previous != self.octave:
            self.feedback.announce(f"Oktawa {self.octave}")
        self.update_status()

    def set_volume(self, delta=0.0, reset=False):
        previous = self.synth.vol
        value = 0.2 if reset else self.synth.vol + delta
        self.synth.set_vol(value)
        if previous != self.synth.vol:
            self.feedback.announce(f"Głośność {int(self.synth.vol * 100)} procent")
        self.update_status()

    def ask_expression(self, parameter):
        value = ui_support.number_dialog(
            "Set value from 0 to 100",
            "Value (%):",
            parameter,
            int(self.synth.values[parameter] * 100),
            0,
            100,
            parent=self,
        )
        if value != -1:
            self.set_expression(parameter, value / 100)

    def record_expression_state(self):
        if self.seq.recording and not self.recorded_expression:
            for parameter in ("brightness", "vibrato"):
                self.seq.record_event(
                    "expression",
                    {"parameter": parameter, "value": self.synth.values[parameter]},
                )
            self.recorded_expression = True

    def set_expression(self, parameter, value):
        previous = self.synth.values[parameter]
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Invalid expression value")
        value = max(0.0, min(1.0, value))
        if previous != value:
            self.record_expression_state()
            self.synth.restore_values({parameter: value})
            if self.seq.recording:
                self.seq.record_event(
                    "expression", {"parameter": parameter, "value": value}
                )
            self.feedback.announce(
                tr(
                    "{parameter}: {value} percent",
                    parameter=tr(parameter),
                    value=int(value * 100),
                )
            )

    def set_bpm(self, bpm):
        previous = self.bpm
        self.seq.set_bpm(bpm)
        self.bpm = int(bpm)
        if previous != self.bpm:
            self.feedback.announce(f"Tempo {self.bpm}")
        self.update_status()

    def update_status(self):
        state = tr("GRA") if self.seq.running else "STOP"
        if self.seq.recording:
            state += " REC"
        self.SetStatusText(
            f"{state} | BPM:{self.bpm} | {tr('Okt')}:{self.octave} | "
            f"A:{int(self.synth.values['main_a'] * 100)} "
            f"B:{int(self.synth.values['main_b'] * 100)} | "
            f"Vol:{int(self.synth.vol * 100)}% | "
            f"{tr('Warstwy')}:{len(self.synth.layers)} FX:{len(self.synth.fx)} | "
            f"{tr('Krok')}:{self.seq.current_step + 1}/16"
        )

    def toggle_layer(self, layer):
        if layer in self.synth.layers:
            self.synth.layers.remove(layer)
            self.layer_items[layer].Check(False)
            self.feedback.announce(f"Wyłączono warstwę {layer}")
        else:
            self.synth.layers.add(layer)
            self.layer_items[layer].Check(True)
            self.feedback.announce(f"Włączono warstwę {layer}")
        self._update_control_ui()

    def toggle_effect(self, effect):
        if effect in self.synth.fx:
            self.synth.fx.remove(effect)
            self.effect_items[effect].Check(False)
            self.feedback.announce(f"Wyłączono efekt {effect}")
        else:
            self.synth.fx.add(effect)
            self.effect_items[effect].Check(True)
            self.feedback.announce(f"Włączono efekt {effect}")
        self._update_control_ui()

    def clear_layers(self, event=None):
        self.synth.layers.clear()
        self.synth.targets_layer.clear()
        for item in self.layer_items.values():
            item.Check(False)
        self._update_control_ui()
        self.feedback.announce("Wyłączono wszystkie warstwy")

    def clear_effects(self, event=None):
        self.synth.fx.clear()
        self.synth.targets_fx.clear()
        for item in self.effect_items.values():
            item.Check(False)
        self._update_control_ui()
        self.feedback.announce("Wyłączono wszystkie efekty")

    def toggle_layer_target(self, layer):
        if layer not in self.synth.layers:
            self.feedback.announce(f"Warstwa {layer} nie jest aktywna")
            return
        if layer in self.synth.targets_layer:
            self.synth.targets_layer.remove(layer)
            selected = False
        else:
            self.synth.targets_layer.add(layer)
            selected = True
        self.layer_control_items[layer].Check(selected)
        self.feedback.announce(f"{'Zaznaczono' if selected else 'Odznaczono'} {layer}")

    def toggle_effect_target(self, effect):
        if effect not in self.synth.fx:
            self.feedback.announce(f"Efekt {effect} nie jest aktywny")
            return
        if effect in self.synth.targets_fx:
            self.synth.targets_fx.remove(effect)
            selected = False
        else:
            self.synth.targets_fx.add(effect)
            selected = True
        self.effect_control_items[effect].Check(selected)
        self.feedback.announce(f"{'Zaznaczono' if selected else 'Odznaczono'} {effect}")

    def toggle_all_layer_targets(self, event=None):
        available = set(self.synth.layers)
        if not available:
            self.feedback.announce("Brak aktywnych warstw")
            return
        if self.synth.targets_layer == available:
            self.synth.targets_layer.clear()
            message = "Odznaczono wszystkie warstwy"
        else:
            self.synth.targets_layer.update(available)
            message = "Zaznaczono wszystkie warstwy"
        self._update_control_ui()
        self.feedback.announce(message)

    def toggle_all_effect_targets(self, event=None):
        available = set(self.synth.fx)
        if not available:
            self.feedback.announce("Brak aktywnych efektów")
            return
        if self.synth.targets_fx == available:
            self.synth.targets_fx.clear()
            message = "Odznaczono wszystkie efekty"
        else:
            self.synth.targets_fx.update(available)
            message = "Zaznaczono wszystkie efekty"
        self._update_control_ui()
        self.feedback.announce(message)

    def _update_control_ui(self):
        self.synth.targets_layer.intersection_update(self.synth.layers)
        self.synth.targets_fx.intersection_update(self.synth.fx)
        for _, code, _ in self.LAYERS:
            active = code in self.synth.layers
            item = self.layer_control_items[code]
            item.Enable(active)
            item.Check(active and code in self.synth.targets_layer)
        for _, code, _ in self.EFFECTS:
            active = code in self.synth.fx
            item = self.effect_control_items[code]
            item.Enable(active)
            item.Check(active and code in self.synth.targets_fx)

    def change_knob(self, target, parameter, delta=None, absolute=None):
        previous = dict(self.synth.values)
        if target == "main":
            current = self.synth.values[f"main_{parameter}"]
        elif target == "layer":
            current = self.synth.get_layer_val(parameter)
        else:
            current = self.synth.get_fx_val(parameter)
        value = absolute if absolute is not None else current + delta
        value = max(0.0, min(1.0, value))

        if target == "main":
            if parameter == "a":
                self.synth.set_knob_a(value)
            else:
                self.synth.set_knob_b(value)
        elif target == "layer":
            self.synth.set_layer_knob(parameter, value)
        else:
            self.synth.set_fx_knob(parameter, value)

        if target == "main":
            value = self.synth.values[f"main_{parameter}"]
        elif target == "layer":
            value = self.synth.get_layer_val(parameter)
        else:
            value = self.synth.get_fx_val(parameter)

        if previous != self.synth.values:
            self.announce_knob(f"{target}_{parameter}", value)
        self.update_status()

    def announce_knob(self, action, value):
        text = tr("{name}: {value} percent", name=tr(action), value=int(value * 100))
        self.feedback.announce(text)

    def toggle_playback(self, event=None):
        if self.seq.running:
            self._close_recorded_notes()
            self.seq.stop()
            message = "Stop"
        else:
            self.seq.play()
            message = "Start"
        self.feedback.announce(message)
        self.update_status()

    def toggle_recording(self, event=None):
        enabled = not self.seq.recording
        if not enabled:
            self._close_recorded_notes()
        self.seq.set_recording(enabled)
        if enabled:
            self.recorded_bend_channels.clear()
            self.recorded_expression = False
        self.feedback.announce(
            "Nagrywanie włączone" if enabled else "Nagrywanie wyłączone"
        )
        self.update_status()

    def trigger_note(self, physical_key, semitone, velocity=1.0):
        frequency = BASE_FREQ_C4 * math.pow(2, (semitone + self.octave * 12) / 12.0)
        note_key = (physical_key, semitone)
        self.synth.note_on(note_key, frequency, self.waveform, velocity)
        self.record_expression_state()
        self.seq.record_event(
            "note_on",
            {
                "key": note_key,
                "freq": frequency,
                "wave": self.waveform,
                "velocity": velocity,
            },
        )
        if self.seq.recording:
            self.recorded_notes.add(note_key)

    def release_note(self, physical_key, semitone):
        note_key = (physical_key, semitone)
        self.synth.note_off(note_key)
        if note_key in self.recorded_notes:
            self.seq.record_event("note_off", {"key": note_key})
            self.recorded_notes.discard(note_key)

    def play_physical_key(self, key):
        if key in self.key_voices:
            if self.block_repeat:
                return
            self.release_physical_key(key)

        base = KEY_OFFSET_MAP[key]
        voices = [base]
        if self.chord_mode:
            voices.extend([base + (3 if key in BLACK_KEYS else 4), base + 7])
        self.key_voices[key] = voices
        for semitone in voices:
            self.trigger_note(key, semitone)

    def release_physical_key(self, key):
        for semitone in self.key_voices.pop(key, []):
            self.release_note(key, semitone)

    def record_midi_event(self, event_type, note):
        note_key = note.get("key")
        if event_type == "note_on":
            self.record_expression_state()
            channel = self.synth.midi_channel_for_key(note_key)
            if (
                self.seq.recording
                and channel is not None
                and channel not in self.recorded_bend_channels
            ):
                self.recorded_bend_channels.add(channel)
                self.seq.record_event(
                    "pitch_bend",
                    {
                        "channel": channel,
                        "semitones": self.synth.get_pitch_bend(channel),
                    },
                )
            self.seq.record_event(event_type, note)
            if self.seq.recording:
                self.recorded_notes.add(note_key)
        elif note_key in self.recorded_notes:
            self.seq.record_event(event_type, note)
            self.recorded_notes.discard(note_key)

    def _close_recorded_notes(self):
        if not self.seq.recording:
            return
        for note_key in tuple(self.recorded_notes):
            self.seq.record_event("note_off", {"key": note_key})
        self.recorded_notes.clear()

    def begin_punch_in(self, key, effect):
        if key in self.punch_in_keys:
            return
        was_active = effect in self.synth.fx
        self.punch_in_keys[key] = (effect, was_active)
        if not was_active:
            self.synth.fx.add(effect)
            self.effect_items[effect].Check(True)
            self._update_control_ui()
        self.feedback.announce(f"Punch-In {effect}")

    def end_punch_in(self, key):
        punch = self.punch_in_keys.pop(key, None)
        if punch is None:
            return
        effect, was_active = punch
        if not was_active:
            self.synth.fx.discard(effect)
            self.effect_items[effect].Check(False)
            self._update_control_ui()

    def panic(self, event=None):
        self.reset_midi_controls()
        for key in tuple(self.punch_in_keys):
            self.end_punch_in(key)
        for key in tuple(self.key_voices):
            self.release_physical_key(key)
        self.midi.panic(immediate=True)
        self.synth.all_notes_off(immediate=True)
        self.speaker.say("Panic. Wszystkie dźwięki wyciszone")
        self.update_status()

    def on_sustain(self, event):
        self.synth.sus = self._checked(event, self.sustain_item)
        self.feedback.announce(
            f"Sustain {'włączony' if self.synth.sus else 'wyłączony'}"
        )

    def on_glide(self, event):
        self.synth.glide = self._checked(event, self.glide_item)
        self.feedback.announce(
            f"Glide {'włączony' if self.synth.glide else 'wyłączony'}"
        )

    def on_chord(self, event):
        self.chord_mode = self._checked(event, self.chord_item)
        self.feedback.announce(
            f"Akordy {'włączone' if self.chord_mode else 'wyłączone'}"
        )

    def on_global_drums(self, event):
        self.global_drums = self._checked(event, self.global_drums_item)
        self.feedback.announce(
            f"Globalne bębny {'włączone' if self.global_drums else 'wyłączone'}"
        )

    def on_release(self, event):
        self.synth.fix_rel = self._checked(event, self.release_item)
        self.feedback.announce(
            f"Wyrównany release {'włączony' if self.synth.fix_rel else 'wyłączony'}"
        )

    def on_pc_keyboard(self, event):
        self.pc_keyboard = self._checked(event, self.pc_keyboard_item)
        self.feedback.announce(
            f"Klawiatura PC {'włączona' if self.pc_keyboard else 'wyłączona'}"
        )

    def on_block_repeat(self, event):
        self.block_repeat = self._checked(event, self.block_repeat_item)
        self.feedback.announce(
            f"Blokada powtórzeń {'włączona' if self.block_repeat else 'wyłączona'}"
        )

    def _matrix_index(self, key):
        if key == wx.WXK_DIVIDE:
            return 0
        if wx.WXK_NUMPAD1 <= key <= wx.WXK_NUMPAD9:
            return key - wx.WXK_NUMPAD1 + 1
        if key == wx.WXK_NUMPAD0:
            return 10
        if key == wx.WXK_MULTIPLY:
            return 11
        if key == wx.WXK_SUBTRACT:
            return 12
        if key in {wx.WXK_DECIMAL, wx.WXK_NUMPAD_DELETE}:
            return 13
        return None

    def on_key_down(self, event):
        raw_key = event.GetKeyCode()
        key = KEY_CODE_ALIASES.get(raw_key, raw_key)
        control = event.ControlDown()
        shift = event.ShiftDown()
        alt = event.AltDown()

        if control and shift and alt and key in {wx.WXK_F9, wx.WXK_F10}:
            self.toggle_feedback("midi" if key == wx.WXK_F9 else "keyboard")
            return

        if control and shift and key == wx.WXK_ESCAPE:
            self.panic()
            return

        if control and key == wx.WXK_NUMPAD_DELETE:
            if shift:
                self.toggle_all_effect_targets()
            else:
                self.toggle_all_layer_targets()
            return
        if control:
            matrix_index = self._matrix_index(key)
            if matrix_index is not None:
                collection = self.EFFECTS if shift else self.LAYERS
                if matrix_index >= len(collection):
                    self.speaker.say("Brak przypisania dla tego klawisza")
                    return
                code = collection[matrix_index][1]
                if shift:
                    self.toggle_effect_target(code)
                else:
                    self.toggle_layer_target(code)
                return

        if control and not alt and not shift:
            if key == wx.WXK_UP:
                self.set_octave(self.octave + 1)
                return
            if key == wx.WXK_DOWN:
                self.set_octave(self.octave - 1)
                return
            if key == wx.WXK_LEFT:
                self.set_octave(0)
                return
            if key == ord("-"):
                self.set_octave(self.octave - 1)
                return
            if key == ord("="):
                self.set_octave(self.octave + 1)
                return
            if key == ord("0"):
                self.set_octave(0)
                return
            if wx.WXK_F1 <= key <= wx.WXK_F5:
                self.set_waveform(
                    ["square", "saw", "triangle", "noise", "drum_kit"][key - wx.WXK_F1]
                )
                return
            if key == wx.WXK_PAGEUP:
                self.change_knob("main", "a", absolute=0.99)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("main", "a", absolute=0.01)
                return
            if key == wx.WXK_HOME:
                self.change_knob("main", "b", absolute=1.0)
                return
            if key == wx.WXK_END:
                self.change_knob("main", "b", absolute=0.0)
                return
            if key == wx.WXK_DELETE:
                self.change_knob("main", "a", absolute=0.5)
                return
            if key == wx.WXK_BACK:
                self.change_knob("main", "b", absolute=0.2)
                return
            setting_shortcuts = {
                ord("S"): (self.sustain_item, self.on_sustain),
                ord("G"): (self.glide_item, self.on_glide),
                ord("H"): (self.chord_item, self.on_chord),
                ord("B"): (self.block_repeat_item, self.on_block_repeat),
            }
            if key in setting_shortcuts:
                self._toggle_menu_item(*setting_shortcuts[key])
                return

        if not control and not shift and not alt:
            if key == wx.WXK_PAGEUP:
                self.change_knob("main", "a", delta=0.05)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("main", "a", delta=-0.05)
                return
            if key == wx.WXK_HOME:
                self.change_knob("main", "b", delta=0.05)
                return
            if key == wx.WXK_END:
                self.change_knob("main", "b", delta=-0.05)
                return
            if key == wx.WXK_DELETE:
                self.change_knob("main", "a", absolute=0.5)
                return
            if key == wx.WXK_BACK:
                self.change_knob("main", "b", absolute=0.2)
                return
            if wx.WXK_F5 <= key <= wx.WXK_F12:
                self.synth.trigger_drum(sequencer.DRUM_INSTRUMENTS[key - wx.WXK_F5])
                return

        if control and shift and alt:
            if key == wx.WXK_PAGEUP:
                self.change_knob("layer", "a", absolute=0.99)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("layer", "a", absolute=0.01)
                return
            if key == wx.WXK_HOME:
                self.change_knob("layer", "b", absolute=1.0)
                return
            if key == wx.WXK_END:
                self.change_knob("layer", "b", absolute=0.0)
                return
            if key == wx.WXK_DELETE:
                self.change_knob("layer", "a", absolute=0.5)
                return
            if key == wx.WXK_BACK:
                self.change_knob("layer", "b", absolute=0.2)
                return

        if control and alt and not shift:
            if key == wx.WXK_PAGEUP:
                self.change_knob("layer", "a", delta=0.05)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("layer", "a", delta=-0.05)
                return
            if key == wx.WXK_HOME:
                self.change_knob("layer", "b", delta=0.05)
                return
            if key == wx.WXK_END:
                self.change_knob("layer", "b", delta=-0.05)
                return
            if key == wx.WXK_DELETE:
                self.change_knob("layer", "a", absolute=0.5)
                return
            if key == wx.WXK_BACK:
                self.change_knob("layer", "b", absolute=0.2)
                return

        if alt and not control and not shift:
            if key == wx.WXK_PAGEUP:
                self.change_knob("fx", "a", delta=0.05)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("fx", "a", delta=-0.05)
                return
            if key == wx.WXK_HOME:
                self.change_knob("fx", "b", delta=0.05)
                return
            if key == wx.WXK_END:
                self.change_knob("fx", "b", delta=-0.05)
                return
            if key == wx.WXK_DELETE:
                self.change_knob("fx", "a", absolute=0.5)
                return
            if key == wx.WXK_BACK:
                self.change_knob("fx", "b", absolute=0.5)
                return
            if key == wx.WXK_UP:
                self.set_volume(0.05)
                return
            if key == wx.WXK_DOWN:
                self.set_volume(-0.05)
                return
            if key == wx.WXK_LEFT:
                self.set_volume(reset=True)
                return
            layer_keys = {ord(item[2]): item[1] for item in self.LAYERS}
            if key in layer_keys:
                self.toggle_layer(layer_keys[key])
                return

        if control and shift and not alt:
            if key == ord("P"):
                self._toggle_menu_item(self.global_drums_item, self.on_global_drums)
                return
            if key == wx.WXK_PAGEUP:
                self.change_knob("fx", "a", delta=0.05)
                return
            if key == wx.WXK_PAGEDOWN:
                self.change_knob("fx", "a", delta=-0.05)
                return
            if key == wx.WXK_HOME:
                self.change_knob("fx", "b", delta=0.05)
                return
            if key == wx.WXK_END:
                self.change_knob("fx", "b", delta=-0.05)
                return
            effect_keys = {ord(item[2]): item[1] for item in self.EFFECTS}
            if key in effect_keys:
                self.begin_punch_in(key, effect_keys[key])
                return
            if key == wx.WXK_BACK:
                self.clear_layers()
                return
            if key == wx.WXK_DELETE:
                self.factory_reset()
                return
            if self.global_drums:
                drum = {
                    ord("Z"): "kick",
                    ord("X"): "snare",
                    ord("C"): "hihat",
                    ord("V"): "tom",
                    ord("B"): "clap",
                    ord("N"): "cowbell",
                    ord("M"): "crash",
                    ord(","): "laser",
                }.get(key)
                if drum:
                    self.synth.trigger_drum(drum)
                    return

        if alt and shift and not control and key == wx.WXK_BACK:
            self.clear_effects()
            return
        if key == wx.WXK_SPACE and not control and not alt:
            self.toggle_playback()
            return
        if key == ord("R") and control and not alt:
            self.toggle_recording()
            return
        if self.pc_keyboard and key in KEY_OFFSET_MAP and not control and not alt:
            self.play_physical_key(key)
            return
        event.Skip()

    def on_key_up(self, event):
        raw_key = event.GetKeyCode()
        key = KEY_CODE_ALIASES.get(raw_key, raw_key)
        self.end_punch_in(key)
        self.release_physical_key(key)
        event.Skip()

    def open_drum_editor(self, event=None):
        dialog = DrumEditorDialog(self, self.seq)
        dialog.ShowModal()
        dialog.Destroy()

    def ask_bpm(self, event=None):
        value = ui_support.number_dialog(
            "Podaj tempo 20–300 BPM",
            "BPM:",
            "Tempo",
            self.bpm,
            20,
            300,
            self,
        )
        if value != -1:
            self.set_bpm(value)

    def ask_octave(self, event=None):
        with wx.NumberEntryDialog(
            self,
            tr("Podaj oktawę od -3 do 3"),
            tr("Oktawa:"),
            tr("Oktawa"),
            self.octave,
            -3,
            3,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.set_octave(dialog.GetValue())

    def ask_knob(self, target, parameter):
        if target == "main":
            current = self.synth.values[f"main_{parameter}"]
        elif target == "layer":
            current = self.synth.get_layer_val(parameter)
        else:
            current = self.synth.get_fx_val(parameter)
        minimum = 1 if parameter == "a" and target in {"main", "layer"} else 0
        maximum = 99 if parameter == "a" and target in {"main", "layer"} else 100
        value = ui_support.number_dialog(
            f"Podaj wartość gałki {parameter.upper()} od {minimum} do {maximum}",
            "Wartość procentowa:",
            f"Gałka {target}",
            round(current * 100),
            minimum,
            maximum,
            self,
        )
        if value != -1:
            self.change_knob(target, parameter, absolute=value / 100.0)

    def clear_sequencer(self, scope):
        labels = {
            "melody": "nagraną melodię",
            "drums": "wszystkie patterny perkusji",
            "all": "cały sekwencer",
        }
        if scope not in labels:
            raise ValueError(f"Nieznany zakres czyszczenia: {scope}")
        answer = ui_support.message_box(
            f"Czy wyczyścić {labels[scope]}?",
            "Czyszczenie sekwencera",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if answer != wx.YES:
            return
        if scope == "melody":
            self.seq.clear_melody()
            self.recorded_bend_channels.clear()
            self.recorded_expression = False
        elif scope == "drums":
            self.seq.clear_drums()
        else:
            self.seq.clear_all()
            self.recorded_bend_channels.clear()
            self.recorded_expression = False
        self.speaker.say(f"Wyczyszczono {labels[scope]}")

    def show_about(self, event=None):
        ui_support.message_box(
            f"{APP_NAME} v{APP_VERSION}\n\n"
            + tr("Accessible 8-bit synthesizer, sequencer and looper for Windows."),
            "O programie",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _export_sequencer_state(self):
        if self.seq.bpm != self.bpm:
            self.seq.set_bpm(self.bpm)
        return self.seq.export_state()

    def _import_sequencer_state(self, state):
        if not isinstance(state, dict):
            raise TypeError("Niepoprawny stan sekwencera")
        normalized = dict(state)
        # Session BPM is authoritative. Older versions could persist a stale
        # value in the sequencer section.
        normalized["bpm"] = self.bpm
        self.seq.import_state(normalized)

    def project_state(self):
        return {
            "format": PROJECT_FORMAT,
            "schema": 3,
            "app_version": APP_VERSION,
            "settings": {
                "waveform": self.waveform,
                "bpm": self.bpm,
                "octave": self.octave,
                "sustain": self.synth.sus,
                "glide": self.synth.glide,
                "chord": self.chord_mode,
                "pc_keyboard": self.pc_keyboard,
                "block_repeat": self.block_repeat,
                "global_drums": self.global_drums,
                "fixed_release": self.synth.fix_rel,
                "volume": self.synth.vol,
                "layers": sorted(self.synth.layers),
                "effects": sorted(self.synth.fx),
                "layer_targets": sorted(self.synth.targets_layer),
                "effect_targets": sorted(self.synth.targets_fx),
                "midi": self.midi.current_port_name or self.saved_midi,
                "audio_device": self.audio_device,
                "audio_device_name": self.audio_device_name,
            },
            "values": dict(self.synth.values),
            "sequencer": self._export_sequencer_state(),
            "midi_mappings": self.mapper.export_state(),
        }

    def _validate_project_state(self, state):
        if not isinstance(state, dict) or state.get("format") != PROJECT_FORMAT:
            raise ValueError(f"To nie jest projekt {APP_NAME}")
        try:
            schema = int(state.get("schema", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("Niepoprawna wersja formatu projektu") from error
        if schema not in {1, 2, 3}:
            raise ValueError("Nieobsługiwana wersja formatu projektu")

        settings = state.get("settings", {})
        values = state.get("values", {})
        sequencer_state = state.get("sequencer", {})
        if not isinstance(settings, dict) or not isinstance(values, dict):
            raise TypeError("Projekt ma niepoprawną strukturę")
        if not isinstance(sequencer_state, dict):
            raise TypeError("Projekt ma niepoprawny stan sekwencera")

        waveform = settings.get("waveform", "square")
        if waveform not in self.wave_items:
            raise ValueError(f"Nieznany instrument: {waveform}")
        bpm = int(settings.get("bpm", 120))
        if not 20 <= bpm <= 300:
            raise ValueError("BPM projektu musi mieścić się w zakresie 20–300")
        octave = int(settings.get("octave", 0))
        if not -3 <= octave <= 3:
            raise ValueError("Oktawa projektu musi mieścić się w zakresie -3–3")

        for field in ("layers", "effects", "layer_targets", "effect_targets"):
            entries = settings.get(field, [])
            if not isinstance(entries, list):
                raise TypeError(f"Pole {field} musi być listą")
            if any(not isinstance(entry, str) for entry in entries):
                raise TypeError(f"Pole {field} może zawierać tylko nazwy")

        validator = synth.Synthesizer(create_stream=False)
        validator.set_vol(settings.get("volume", 0.2))
        validator.restore_values(values)
        sequence_validator = sequencer.Sequencer(validator, bpm=bpm)
        normalized_sequence = dict(sequencer_state)
        normalized_sequence["bpm"] = bpm
        sequence_validator.import_state(normalized_sequence)
        mapping_validator = midi_mapping.MidiMapper(lambda *args: None)
        mapping_validator.import_state(state.get("midi_mappings", []))
        return settings, values

    def apply_project_state(self, state, restore_devices=False):
        settings, values = self._validate_project_state(state)

        if self.seq.running:
            self.seq.stop()
        for key in tuple(self.punch_in_keys):
            self.end_punch_in(key)
        self.key_voices.clear()
        self.recorded_notes.clear()
        self.synth.all_notes_off(immediate=True)
        waveform = settings.get("waveform", "square")
        self.waveform = waveform
        self.wave_items[waveform].Check(True)
        self.set_bpm(int(settings.get("bpm", 120)))
        self.octave = int(settings.get("octave", 0))
        self.synth.sus = bool(settings.get("sustain", True))
        self.synth.glide = bool(settings.get("glide", False))
        self.chord_mode = bool(settings.get("chord", False))
        self.pc_keyboard = bool(settings.get("pc_keyboard", True))
        self.block_repeat = bool(settings.get("block_repeat", True))
        self.global_drums = bool(settings.get("global_drums", True))
        self.synth.fix_rel = bool(settings.get("fixed_release", True))
        self.synth.set_vol(float(settings.get("volume", 0.2)))

        valid_layers = set(self.layer_items)
        valid_effects = set(self.effect_items)
        self.synth.layers = set(settings.get("layers", ())) & valid_layers
        self.synth.fx = set(settings.get("effects", ())) & valid_effects
        self.synth.targets_layer = (
            set(settings.get("layer_targets", ())) & self.synth.layers
        )
        self.synth.targets_fx = set(settings.get("effect_targets", ())) & self.synth.fx
        self.synth.restore_values(values)
        self._import_sequencer_state(state.get("sequencer", {}))
        if "midi_mappings" in state:
            self.mapper.import_state(state["midi_mappings"])
            self.midi_profile_initialized = True
        self.saved_midi = str(settings.get("midi", "") or "")

        if restore_devices and settings.get("audio_device") is not None:
            selected_device = self._resolve_audio_device(
                settings.get("audio_device"),
                settings.get("audio_device_name", ""),
            )
            self.synth.change_output_device(selected_device)
            self.audio_device = selected_device
            self.audio_device_name = str(sd.query_devices(selected_device)["name"])

        for code, item in self.layer_items.items():
            item.Check(code in self.synth.layers)
        for code, item in self.effect_items.items():
            item.Check(code in self.synth.fx)
        self._set_default_checks()
        self._update_control_ui()
        self.update_status()

    def save_project(self, event=None):
        dialog = ui_support.file_dialog(
            self,
            "Zapisz projekt v15",
            wildcard=f"Projekt {APP_NAME} (*.po15)|*.po15",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        finally:
            dialog.Destroy()
        if path.suffix.lower() != ".po15":
            path = path.with_suffix(".po15")
        try:
            path.write_text(
                json.dumps(self.project_state(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.speaker.say(f"Zapisano projekt {path.name}")
        except Exception as error:  # noqa: BLE001 - user file write boundary
            ui_support.message_box(str(error), "Błąd zapisu", wx.OK | wx.ICON_ERROR)

    def open_project(self, event=None):
        dialog = ui_support.file_dialog(
            self,
            "Otwórz projekt v15",
            wildcard=f"Projekt {APP_NAME} (*.po15)|*.po15",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        finally:
            dialog.Destroy()
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            self.apply_project_state(state, restore_devices=False)
            self.speaker.say(f"Wczytano projekt {path.name}")
        except Exception as error:  # noqa: BLE001 - validate the complete user project
            ui_support.message_box(str(error), "Błąd projektu", wx.OK | wx.ICON_ERROR)

    def export_wav(self, event=None):
        dialog = ui_support.file_dialog(
            self,
            "Zapisz WAV",
            wildcard="WAV (*.wav)|*.wav",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        finally:
            dialog.Destroy()

        if path.suffix.lower() != ".wav":
            path = path.with_suffix(".wav")
        loops = ui_support.number_dialog(
            "Ile pętli wyeksportować?",
            "Liczba:",
            "Eksport WAV",
            4,
            1,
            99,
            self,
        )
        if loops == -1:
            return
        melody, drums = self.seq.snapshot()
        try:
            with ui_support.busy_info("Eksportowanie dźwięku..."):
                self.synth.render_to_wav(str(path), melody, drums, self.bpm, loops)
            ui_support.message_box("Zapisano plik WAV.", "Eksport", wx.OK)
        except Exception as error:  # noqa: BLE001 - report export failures in the interface
            ui_support.message_box(str(error), "Błąd eksportu", wx.OK | wx.ICON_ERROR)

    def select_audio_device(self, event=None):
        try:
            devices = sd.query_devices()
            output_indexes = [
                index
                for index, device in enumerate(devices)
                if device["max_output_channels"] > 0
            ]
        except Exception as error:  # noqa: BLE001 - backend PortAudio
            ui_support.message_box(str(error), "Błąd audio", wx.OK | wx.ICON_ERROR)
            return
        if not output_indexes:
            ui_support.message_box("Brak urządzeń wyjściowych audio.")
            return

        choices = [f"{index}: {devices[index]['name']}" for index in output_indexes]
        dialog = ui_support.choice_dialog(
            self, "Wybierz urządzenie:", "Wyjście audio", choices
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            selected = output_indexes[dialog.GetSelection()]
        finally:
            dialog.Destroy()
        try:
            self.synth.change_output_device(selected)
            if not self.synth.running:
                self.synth.start()
            self.audio_device = selected
            self.audio_device_name = str(devices[selected]["name"])
            self.speaker.say(f"Wyjście audio {devices[selected]['name']}")
        except Exception as error:  # noqa: BLE001 - backend PortAudio
            ui_support.message_box(str(error), "Błąd audio", wx.OK | wx.ICON_ERROR)

    def open_saved_midi(self):
        ports = self.midi.get_ports()
        selected = self.saved_midi or midi_mapping.preferred_port(ports)
        self.initialize_midi_profile(selected)
        self.midi.open_port(selected or None)
        if self.midi.last_error:
            self.speaker.say(self.midi.last_error)

    def initialize_midi_profile(self, port_name):
        if not self.midi_profile_initialized:
            name = midi_mapping.detect_profile(port_name)
            if name:
                self.mapper.import_state(midi_mapping.profile(name))
                self.midi_profile_initialized = True

    @staticmethod
    def _resolve_audio_device(saved_index, saved_name=""):
        devices = sd.query_devices()
        if saved_name:
            for index, device in enumerate(devices):
                if device["max_output_channels"] > 0 and device["name"] == saved_name:
                    return index
        index = int(saved_index)
        if not 0 <= index < len(devices):
            raise ValueError("Zapisany indeks urządzenia audio jest poza zakresem")
        if devices[index]["max_output_channels"] <= 0:
            raise ValueError("Zapisane urządzenie nie ma kanałów wyjściowych")
        return index

    def select_midi_device(self, event=None):
        ports = self.midi.get_ports()
        if not ports:
            ui_support.message_box("Brak dostępnych wejść MIDI.")
            return
        dialog = ui_support.choice_dialog(self, "Wybierz wejście:", "MIDI", ports)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            selected = dialog.GetStringSelection()
        finally:
            dialog.Destroy()
        if self.midi.open_port(selected):
            self.reset_midi_controls()
            self.saved_midi = selected
            self.initialize_midi_profile(selected)
            self.speaker.say(f"MIDI {selected}")
        else:
            ui_support.message_box("Nie udało się otworzyć wejścia MIDI.")

    def refresh_midi(self, event=None):
        port = self.saved_midi or self.midi.current_port_name
        if self.midi.open_port(port):
            self.reset_midi_controls()
            self.saved_midi = self.midi.current_port_name or ""
            self.initialize_midi_profile(self.saved_midi)
            self.speaker.say("MIDI odświeżone")
        else:
            self.speaker.say("Brak wejścia MIDI")

    def load_settings(self):
        if not CONFIG_PATH.exists():
            return
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read(CONFIG_PATH, encoding="utf-8")
            settings = config["SETTINGS"]
            for source in ("keyboard", "midi"):
                self.feedback.set_enabled(
                    source, config.getboolean("FEEDBACK", source, fallback=True)
                )
            self.feedback_keyboard_item.Check(self.feedback.enabled["keyboard"])
            self.feedback_midi_item.Check(self.feedback.enabled["midi"])
            waveform = settings.get("wave", "square")
            if waveform in self.wave_items:
                self.waveform = waveform
                self.wave_items[waveform].Check(True)
            self.set_bpm(settings.getint("bpm", 120))
            self.octave = max(-3, min(3, settings.getint("oct", 0)))
            self.synth.set_vol(settings.getfloat("vol", 0.2))
            self.synth.sus = settings.getboolean("sus", True)
            self.synth.glide = settings.getboolean("glide", False)
            self.synth.fix_rel = settings.getboolean("lrel", True)
            self.chord_mode = settings.getboolean("chord", False)
            self.pc_keyboard = settings.getboolean("pc", True)
            self.block_repeat = settings.getboolean("br", True)
            self.global_drums = settings.getboolean("gd", True)
            self.show_hints = settings.getboolean("hints", True)
            self.hints_item.Check(self.show_hints)
            self.saved_midi = settings.get("midi", "")

            valid_layers = set(self.layer_items)
            valid_effects = set(self.effect_items)
            self.synth.layers = {
                value
                for value in settings.get("lays", "").split(",")
                if value in valid_layers
            }
            self.synth.fx = {
                value
                for value in settings.get("fx", "").split(",")
                if value in valid_effects
            }
            self.synth.targets_layer = {
                value
                for value in settings.get("tgt_l", "").split(",")
                if value in self.synth.layers
            }
            self.synth.targets_fx = {
                value
                for value in settings.get("tgt_f", "").split(",")
                if value in self.synth.fx
            }

            if "VALUES" in config:
                self.synth.restore_values(dict(config["VALUES"]))

            if config.has_option("MIDI_MAPPINGS", "bindings"):
                state = json.loads(config["MIDI_MAPPINGS"]["bindings"])
                version = config.getint("MIDI_MAPPINGS", "version", fallback=1)
                state = midi_mapping.upgrade_legacy_profile(
                    state, self.saved_midi, version
                )
                self.mapper.import_state(state)
                self.midi_profile_initialized = config.getboolean(
                    "MIDI_MAPPINGS", "initialized", fallback=True
                )
                self.midi_live_apply = config.getboolean(
                    "MIDI_MAPPINGS", "live_apply", fallback=False
                )

            if "SEQUENCER" in config and config["SEQUENCER"].get("state"):
                try:
                    self._import_sequencer_state(
                        json.loads(config["SEQUENCER"].get("state"))
                    )
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    print(f"Pominięto uszkodzony stan sekwencera: {error}")

            audio_device = settings.get("audio", "")
            if audio_device:
                try:
                    selected_device = self._resolve_audio_device(
                        audio_device, settings.get("audio_name", "")
                    )
                    self.synth.change_output_device(selected_device)
                    self.audio_device = selected_device
                    self.audio_device_name = str(
                        sd.query_devices(selected_device)["name"]
                    )
                except (TypeError, ValueError, sd.PortAudioError) as error:
                    print(f"Pominięto niedostępne urządzenie audio: {error}")

            for code, item in self.layer_items.items():
                item.Check(code in self.synth.layers)
            for code, item in self.effect_items.items():
                item.Check(code in self.synth.fx)
            self._set_default_checks()
            self._update_control_ui()
        except Exception as error:  # noqa: BLE001 - legacy configuration compatibility
            print(f"Błąd odczytu konfiguracji: {error}")
            self.speaker.say("Nie udało się wczytać konfiguracji")

    def save_settings(self):
        config = configparser.ConfigParser(interpolation=None)
        if CONFIG_PATH.exists():
            config.read(CONFIG_PATH, encoding="utf-8")
        config["SETTINGS"] = {
            "version": APP_VERSION,
            "wave": self.waveform,
            "bpm": str(self.bpm),
            "oct": str(self.octave),
            "sus": str(self.synth.sus),
            "glide": str(self.synth.glide),
            "chord": str(self.chord_mode),
            "pc": str(self.pc_keyboard),
            "br": str(self.block_repeat),
            "gd": str(self.global_drums),
            "hints": str(self.show_hints),
            "lrel": str(self.synth.fix_rel),
            "vol": str(self.synth.vol),
            "lays": ",".join(sorted(self.synth.layers)),
            "fx": ",".join(sorted(self.synth.fx)),
            "tgt_l": ",".join(sorted(self.synth.targets_layer)),
            "tgt_f": ",".join(sorted(self.synth.targets_fx)),
            "midi": self.midi.current_port_name or self.saved_midi,
            "audio": "" if self.audio_device is None else str(self.audio_device),
            "audio_name": self.audio_device_name,
        }
        config["VALUES"] = {key: str(value) for key, value in self.synth.values.items()}
        config["SEQUENCER"] = {
            "state": json.dumps(
                self._export_sequencer_state(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        }
        config["MIDI_MAPPINGS"] = {
            "version": "3",
            "initialized": str(self.midi_profile_initialized),
            "live_apply": str(self.midi_live_apply),
            "bindings": json.dumps(self.mapper.export_state(), ensure_ascii=False),
        }
        config["FEEDBACK"] = {
            source: str(enabled) for source, enabled in self.feedback.enabled.items()
        }
        preferences.atomic_write(config, CONFIG_PATH)

    def factory_reset(self, event=None):
        answer = ui_support.message_box(
            "Usunąć wszystkie zapisane ustawienia?",
            "Reset fabryczny",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if answer != wx.YES:
            return
        self._skip_save = True
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        self.speaker.say("Ustawienia fabryczne przywrócone")
        self.Close()

    def on_close(self, event=None):
        if self._closing:
            return
        self._closing = True
        self.feedback.close()
        for key in tuple(self.punch_in_keys):
            self.end_punch_in(key)
        self._close_recorded_notes()
        try:
            if not self._skip_save:
                self.save_settings()
        except Exception as error:  # noqa: BLE001 - shutdown must reach final cleanup
            print(f"Błąd zapisu konfiguracji: {error}")
        finally:
            self.seq.stop()
            self.midi.stop()
            self.synth.stop()
            self.Destroy()

    # Preserve names used by older integration scripts.
    kd = on_key_down
    ku = on_key_up
    ply = toggle_playback
    rec = toggle_recording
    cl = on_close
    load = load_settings
    mi = open_saved_midi


if __name__ == "__main__":
    import run

    raise SystemExit(run.main())
