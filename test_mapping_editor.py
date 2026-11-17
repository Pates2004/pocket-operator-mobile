"""Stable MIDI editor rows, live routing, persistence and failed edit recovery."""

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import mido
import wx

import main
import midi_mapping
import preferences
import synth
from midi_dialog import MidiMappingDialog


class MappingOrderTests(unittest.TestCase):
    def test_existing_sources_keep_order_and_source_edits_are_atomic(self):
        mapper = midi_mapping.MidiMapper(lambda *args: None)
        mapper.import_state(midi_mapping.profile("akm322"))
        original = mapper.export_state()
        self.assertEqual(mapper.add(dict(original[0], action="volume")), 0)
        self.assertEqual(mapper.export_state()[1:], original[1:])
        self.assertEqual(mapper.bindings[0]["action"], "volume")
        self.assertEqual(mapper.add(dict(original[0], number=31), replace_index=0), 0)
        self.assertEqual(mapper.bindings[0]["number"], 31)
        self.assertEqual(len(mapper.bindings), len(original))
        before = mapper.export_state()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            mapper.add(dict(before[0], number=21), replace_index=0)
        self.assertEqual(mapper.export_state(), before)
        generation = mapper.generation
        mapper.add(before[0])
        self.assertEqual(mapper.generation, generation)

    def test_factory_upgrade_preserves_custom_disabled_and_deleted_sources(self):
        expected = midi_mapping.profile("akm322")
        self.assertEqual(
            [item["action"] for item in expected[:3]],
            ["wave_select", "main_a", "main_b"],
        )
        legacy = json.loads(json.dumps(expected))
        for item, action in zip(
            legacy[:3], ("main_a", "main_b", "layer_a"), strict=True
        ):
            item["action"] = action
        legacy[3]["action"] = "fx_a"
        legacy[4]["action"] = "fx_b"
        self.assertEqual(
            midi_mapping.upgrade_legacy_profile(legacy, "AKM322 0", 2), expected
        )
        self.assertEqual(
            midi_mapping.upgrade_legacy_profile(legacy, "AKM322 0", 3), legacy
        )
        for changed in (legacy[:-1], [dict(legacy[0], enabled=False), *legacy[1:]]):
            self.assertEqual(
                midi_mapping.upgrade_legacy_profile(changed, "AKM322 0", 2), changed
            )


class LiveEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    @contextmanager
    def editor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "po.ini"
            with (
                mock.patch.object(main, "CONFIG_PATH", path),
                mock.patch.object(main, "SPEECH_AVAILABLE", False),
            ):
                frame = main.MainFrame(
                    synth.Synthesizer(create_stream=False), False, False, False
                )
                frame.mapper.import_state(midi_mapping.profile("akm322"))
                frame.midi_profile_initialized = True
                try:
                    with MidiMappingDialog(frame) as dialog:
                        yield frame, dialog, path
                finally:
                    frame._skip_save = True
                    frame.on_close()

    def select(self, dialog, index=0):
        dialog.entries.SetSelection(index)
        dialog.on_select(None)

    def live(self, dialog):
        dialog.live_apply.SetValue(True)
        dialog.on_live_toggle(None)

    def change(self, control, binder):
        event = wx.CommandEvent(binder.typeId, control.GetId())
        event.SetEventObject(control)
        control.ProcessWindowEvent(event)

    def drain(self):
        loop = wx.GUIEventLoop()
        activator = wx.EventLoopActivator(loop)
        timer = wx.CallLater(250, loop.Exit)
        loop.Run()
        timer.Stop()
        del activator

    def test_manual_save_keeps_selected_row_and_repeated_edits_replace_it(self):
        with self.editor() as (frame, dialog, _):
            self.select(dialog)
            original = frame.mapper.export_state()
            for action in ("volume", "main_a", "main_b"):
                dialog.action.SetSelection(dialog.actions.index(action))
                dialog.on_save(None)
                self.assertEqual(dialog.entries.GetSelection(), 0)
                self.assertEqual(frame.mapper.bindings[0]["action"], action)
                self.assertEqual(frame.mapper.export_state()[1:], original[1:])
            dialog.number.SetValue(31)
            dialog.on_save(None)
            self.assertEqual(frame.mapper.bindings[0]["number"], 31)
            self.assertEqual(len(frame.mapper.bindings), len(original))

    def test_live_action_routes_without_save_and_option_survives_reload(self):
        with self.editor() as (frame, dialog, path):
            self.select(dialog)
            self.live(dialog)
            dialog.action.SetSelection(dialog.actions.index("volume"))
            self.change(dialog.action, wx.EVT_CHOICE)
            self.drain()
            frame.midi._handle_message(
                mido.Message("control_change", control=10, value=100)
            )
            wx.YieldIfNeeded()
            self.assertAlmostEqual(frame.synth.vol, 100 / 127)
            self.assertEqual(dialog.entries.GetSelection(), 0)
            state = preferences.read_config(path)
            self.assertTrue(state.getboolean("MIDI_MAPPINGS", "live_apply"))
            self.assertEqual(
                json.loads(state["MIDI_MAPPINGS"]["bindings"])[0]["action"], "volume"
            )
            frame.midi_live_apply = False
            frame.load_settings()
            self.assertTrue(frame.midi_live_apply)

    def test_live_disabled_wheel_neutralizes_pitch_and_persists(self):
        with self.editor() as (frame, dialog, path):
            self.select(dialog, 9)
            self.live(dialog)
            frame.handle_pitch_bend(0, 1)
            dialog.enabled.SetValue(False)
            self.change(dialog.enabled, wx.EVT_CHECKBOX)
            self.drain()
            self.assertEqual(frame.synth.get_pitch_bend(), 0)
            frame.midi._handle_message(mido.Message("pitchwheel", pitch=8191))
            wx.YieldIfNeeded()
            self.assertEqual(frame.synth.get_pitch_bend(), 0)
            self.assertFalse(
                json.loads(preferences.read_config(path)["MIDI_MAPPINGS"]["bindings"])[
                    9
                ]["enabled"]
            )

    def test_manual_mode_waits_for_save_and_selection_does_not_modify_map(self):
        with self.editor() as (frame, dialog, _):
            self.select(dialog)
            before = frame.mapper.export_state()
            dialog.action.SetSelection(dialog.actions.index("volume"))
            self.change(dialog.action, wx.EVT_CHOICE)
            self.drain()
            self.assertEqual(frame.mapper.export_state(), before)
            self.live(dialog)
            frame.synth.set_pitch_bend(1)
            with mock.patch.object(frame, "save_settings") as save:
                self.select(dialog, 1)
                self.drain()
                self.assertFalse(save.called)
            self.assertEqual(frame.synth.get_pitch_bend(), 1)

    def test_incomplete_and_duplicate_edits_do_not_replace_valid_binding(self):
        with self.editor() as (frame, dialog, _):
            self.select(dialog)
            self.live(dialog)
            before = frame.mapper.export_state()
            dialog.step.SetValue(0)
            self.change(dialog.step, wx.EVT_SPINCTRLDOUBLE)
            self.drain()
            self.assertEqual(frame.mapper.export_state(), before)
            dialog.step.SetValue(1)
            dialog.number.SetValue(21)
            self.change(dialog.number, wx.EVT_SPINCTRL)
            self.drain()
            self.assertEqual(frame.mapper.export_state(), before)
            self.assertEqual(dialog.entries.GetSelection(), 0)
            dialog.number.SetValue(31)
            self.change(dialog.number, wx.EVT_SPINCTRL)
            self.drain()
            self.assertEqual(frame.mapper.bindings[0]["number"], 31)

    def test_pending_changes_flush_on_selection_and_learn_adds_new_source(self):
        with self.editor() as (frame, dialog, _):
            self.select(dialog)
            self.live(dialog)
            dialog.action.SetSelection(dialog.actions.index("volume"))
            self.change(dialog.action, wx.EVT_CHOICE)
            self.select(dialog, 1)
            self.assertEqual(frame.mapper.bindings[0]["action"], "volume")
            self.assertEqual(dialog.entries.GetSelection(), 1)
            original = frame.mapper.export_state()
            dialog.learned(("cc", 0, 31))
            self.assertEqual(frame.mapper.export_state()[: len(original)], original)
            self.assertEqual(frame.mapper.bindings[-1]["number"], 31)
            self.assertEqual(len(frame.mapper.bindings), len(original) + 1)

    def test_write_failure_rolls_back_live_map_and_delete(self):
        with self.editor() as (frame, dialog, _):
            self.select(dialog)
            self.live(dialog)
            before = frame.mapper.export_state()
            dialog.action.SetSelection(dialog.actions.index("volume"))
            with mock.patch.object(
                frame, "save_midi_mappings", side_effect=OSError("read only")
            ):
                self.assertFalse(
                    dialog.apply_mapping(report_errors=False, announce=False)
                )
                self.assertEqual(frame.mapper.export_state(), before)
                with mock.patch("midi_dialog.ui_support.message_box") as error:
                    dialog.on_delete(None)
                    error.assert_called_once()
                self.assertEqual(frame.mapper.export_state(), before)


if __name__ == "__main__":
    unittest.main()
