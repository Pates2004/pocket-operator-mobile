"""Regression tests for mandatory setup, MIDI control and localization."""

import configparser
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mido
import wx

import localization
import main
import midi_handler
import midi_mapping
import preferences
import synth
import ui_support
from midi_dialog import MidiMappingDialog


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.mapper = midi_mapping.MidiMapper(lambda *args: self.calls.append(args))

    def test_actual_akm322_messages_drive_knobs_and_mmc(self):
        self.mapper.import_state(midi_mapping.profile("akm322"))
        for cc, value, action in [
            (10, 127, "main_a"),
            (21, 64, "main_b"),
            (22, 80, "layer_a"),
            (23, 90, "fx_a"),
        ]:
            self.assertTrue(
                self.mapper.process(
                    mido.Message("control_change", control=cc, value=value)
                )
            )
            self.assertEqual(self.calls[-1][0], action)
        for command, action in [(2, "play"), (1, "stop"), (6, "record")]:
            self.mapper.process(mido.Message("sysex", data=[127, 127, 6, command]))
            self.assertEqual(self.calls[-1], (action, "trigger", 1.0))

    def test_relative_encoders_match_ni_modes_and_direction(self):
        for mode, positive, negative in [
            ("relative_twos", 1, 127),
            ("relative_offset", 65, 63),
            ("relative_sign", 1, 65),
        ]:
            self.mapper.import_state([midi_mapping.binding(("cc", 14), "main_a", mode)])
            for value, delta in [(positive, 0.01), (negative, -0.01)]:
                self.mapper.process(
                    mido.Message("control_change", control=14, value=value)
                )
                self.assertEqual(self.calls[-1], ("main_a", "relative", delta))

    def test_learn_consumes_note_and_button_release_does_not_retrigger(self):
        learned = []
        self.mapper.learn_callback = learned.append
        self.assertTrue(
            self.mapper.process(mido.Message("note_on", note=40, velocity=127))
        )
        self.assertEqual(learned, [("note", 0, 40)])
        self.mapper.add(midi_mapping.binding(("note", 40), "play_toggle", "button"))
        for kind, velocity in [("note_on", 127), ("note_on", 127), ("note_off", 0)]:
            self.mapper.process(mido.Message(kind, note=40, velocity=velocity))
        self.assertEqual(self.calls, [("play_toggle", "trigger", 1.0)])

    def test_binding_validation_is_atomic_and_channel_specific(self):
        self.mapper.import_state([midi_mapping.binding(("cc", 1), "main_a", channel=1)])
        state = self.mapper.export_state()
        with self.assertRaises(ValueError):
            self.mapper.import_state([{**state[0], "step": float("nan")}])
        self.assertEqual(state, self.mapper.export_state())
        self.assertFalse(
            self.mapper.process(mido.Message("control_change", control=1, channel=0))
        )
        self.assertTrue(
            self.mapper.process(mido.Message("control_change", control=1, channel=1))
        )

    def test_midi_channels_and_sustain_do_not_release_each_other(self):
        engine = synth.Synthesizer(create_stream=False)
        handler = midi_handler.MidiInputHandler(engine)
        for channel in [0, 1]:
            handler._handle_message(mido.Message("note_on", channel=channel, note=60))
        self.assertEqual(len(engine.oscs), 2)
        handler._handle_message(mido.Message("control_change", control=64, value=127))
        handler._handle_message(mido.Message("note_off", note=60))
        handler._handle_message(mido.Message("note_off", note=60, channel=1))
        self.assertFalse(engine.oscs[60].releasing)
        self.assertTrue(engine.oscs[("midi", 1, 60)].releasing)
        handler._handle_message(mido.Message("control_change", control=64, value=0))
        self.assertTrue(engine.oscs[60].releasing)


class PreferencesTests(unittest.TestCase):
    def test_requires_both_choices_and_preserves_existing_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "po.ini"
            self.assertFalse(preferences.appearance(path)[2])
            config = configparser.ConfigParser(interpolation=None)
            config["SETTINGS"] = {"bpm": "144", "midi": "100% MIDI"}
            preferences.atomic_write(config, path)
            with self.assertRaises(ValueError):
                preferences.save_appearance("en", None, path)
            self.assertFalse(preferences.appearance(path)[2])
            preferences.save_appearance("en", "dark", path)
            self.assertEqual(preferences.appearance(path), ("en", "dark", True))
            self.assertEqual(preferences.read_config(path)["SETTINGS"]["bpm"], "144")
            config = preferences.read_config(path)
            config["INTERFACE"]["theme"] = "invalid"
            preferences.atomic_write(config, path)
            self.assertFalse(preferences.appearance(path)[2])

    def test_catalog_keys_and_runtime_templates_in_both_languages(self):
        pl = localization.load_catalog("pl")
        en = localization.load_catalog("en")
        self.assertEqual(set(pl), set(en))
        try:
            localization.set_language("en")
            self.assertEqual(
                localization.tr("Głośność 50 procent"), "Volume 50 percent"
            )
            self.assertEqual(localization.tr("Ctrl+R"), "Ctrl+R")
            self.assertIn("SHORTCUTS", localization.tr("help"))
        finally:
            localization.set_language("pl")


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_setup_cannot_continue_until_both_choices_are_selected(self):
        with ui_support.AppearanceDialog() as dialog:
            self.assertFalse(dialog.confirm.IsEnabled())
            dialog.language.SetSelection(1)
            dialog.on_change()
            self.assertFalse(dialog.confirm.IsEnabled())
            dialog.theme.SetSelection(2)
            dialog.on_change()
            self.assertTrue(dialog.confirm.IsEnabled())
            self.assertEqual(dialog.selection(), ("en", "dark"))

    def test_cancel_setup_will_show_it_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "po.ini"
            with mock.patch.object(
                ui_support.AppearanceDialog, "ShowModal", return_value=wx.ID_CANCEL
            ) as show:
                self.assertIsNone(ui_support.ensure_setup(path))
                self.assertIsNone(ui_support.ensure_setup(path))
                self.assertEqual(show.call_count, 2)
            self.assertFalse(path.exists())

    def test_midi_actions_change_audio_and_english_menu_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "po.ini"
            preferences.save_appearance("en", "light", path)
            localization.set_language("en")
            with (
                mock.patch.object(main, "CONFIG_PATH", path),
                mock.patch.object(main, "SPEECH_AVAILABLE", False),
            ):
                frame = main.MainFrame(
                    synth.Synthesizer(create_stream=False), False, False, False
                )
                try:
                    self.assertEqual(frame.GetMenuBar().GetMenuLabel(0), "&File")
                    menu = frame.GetMenuBar()
                    for index in range(menu.GetMenuCount()):
                        for item in menu.GetMenu(index).GetMenuItems():
                            self.assertNotRegex(item.GetItemLabel(), "[ąćęłńóśźż]")
                    frame.handle_midi_action("main_a", "absolute", 0.75)
                    self.assertEqual(frame.synth.values["main_a"], 0.75)
                    frame.handle_midi_action("main_a", "relative", -0.05)
                    self.assertAlmostEqual(frame.synth.values["main_a"], 0.70)
                    frame.handle_midi_action("effect:dist", "gate", 1)
                    self.assertIn("dist", frame.synth.fx)
                    frame.handle_midi_action("effect:dist", "gate", 0)
                    self.assertNotIn("dist", frame.synth.fx)
                    frame.mapper.import_state(midi_mapping.profile("akm322"))
                    frame.save_settings()
                    self.assertEqual(
                        preferences.appearance(path), ("en", "light", True)
                    )
                    encoded = preferences.read_config(path)["MIDI_MAPPINGS"]["bindings"]
                    self.assertEqual(json.loads(encoded), frame.mapper.export_state())
                    frame.apply_project_state(
                        json.loads(json.dumps(frame.project_state()))
                    )
                    with (
                        mock.patch.object(
                            wx.NumberEntryDialog, "ShowModal", return_value=wx.ID_OK
                        ),
                        mock.patch.object(
                            wx.NumberEntryDialog, "GetValue", return_value=-1
                        ),
                    ):
                        frame.ask_octave()
                    self.assertEqual(frame.octave, -1)
                    with MidiMappingDialog(frame) as dialog:
                        self.assertEqual(dialog.GetTitle(), "MIDI mappings")
                        self.assertEqual(dialog.kind.GetName(), "Message type")
                        dialog.learned(("cc", 0, 33))
                        dialog.action.SetSelection(dialog.actions.index("main_a"))
                        dialog.on_save(None)
                        self.assertTrue(
                            any(item["number"] == 33 for item in frame.mapper.bindings)
                        )
                    for _ in range(2):
                        with MidiMappingDialog(frame) as dialog:
                            close_timer = wx.CallLater(30, dialog.Close)
                            self.assertEqual(dialog.ShowModal(), wx.ID_OK)
                            close_timer.Stop()
                        wx.YieldIfNeeded()
                        self.assertEqual(
                            frame.GetTitle(), f"{main.APP_NAME} v{main.APP_VERSION}"
                        )
                        self.assertIsNone(frame.mapper.monitor)
                finally:
                    frame._skip_save = True
                    frame.on_close()
                    localization.set_language("pl")


if __name__ == "__main__":
    unittest.main()
