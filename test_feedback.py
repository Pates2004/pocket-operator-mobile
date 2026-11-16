"""Regression tests for actual MIDI changes and spoken input-source policies."""

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import mido
import numpy as np
import wx

import main
import midi_mapping
import preferences
import synth
from feedback import ChangeFeedback
from test_launch import FakeKeyEvent


class FakeTimer:
    def __init__(self, callback):
        self.callback = callback
        self.stopped = False

    def Stop(self):
        self.stopped = True

    def fire(self):
        if not self.stopped:
            self.callback()


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.spoken = []
        self.timers = []
        self.now = 0.0

        def schedule(delay, callback):
            timer = FakeTimer(callback)
            self.timers.append(timer)
            return timer

        self.feedback = ChangeFeedback(self.spoken.append, schedule, lambda: self.now)

    def test_all_four_input_policies(self):
        for keyboard, midi in [
            (True, True),
            (False, True),
            (True, False),
            (False, False),
        ]:
            self.spoken.clear()
            self.feedback.set_enabled("keyboard", keyboard)
            self.feedback.set_enabled("midi", midi)
            for source in ("keyboard", "midi"):
                with self.feedback.using_source(source):
                    self.feedback.announce(source)
            self.assertEqual(
                self.spoken,
                (["keyboard"] if keyboard else []) + (["midi"] if midi else []),
            )

    def test_fast_knob_motion_speaks_first_and_final_values_without_backlog(self):
        with self.feedback.using_source("midi", continuous=True):
            for value in range(100):
                self.now = value / 1000
                self.feedback.announce(f"Knob A: {value}")
        self.assertEqual(self.spoken, ["Knob A: 0"])
        for timer in self.timers:
            timer.fire()
        self.assertEqual(self.spoken, ["Knob A: 0", "Knob A: 99"])

    def test_disabled_or_closed_source_cannot_deliver_stale_feedback(self):
        with self.feedback.using_source("midi", continuous=True):
            self.feedback.announce("first")
            self.feedback.announce("pending")
        self.feedback.set_enabled("midi", False)
        for timer in self.timers:
            timer.fire()
        self.assertEqual(self.spoken, ["first"])
        self.feedback.close()
        self.feedback.announce("closed")
        self.assertEqual(self.spoken, ["first"])

    def test_keyboard_change_cancels_stale_midi_and_context_restores_on_error(self):
        with self.feedback.using_source("midi", continuous=True):
            self.feedback.announce("first")
            self.feedback.announce("pending")
        self.feedback.announce("keyboard")
        for timer in self.timers:
            timer.fire()
        self.assertEqual(self.spoken, ["first", "keyboard"])
        with self.assertRaises(RuntimeError), self.feedback.using_source("midi"):
            raise RuntimeError("test")
        self.assertEqual(self.feedback.source, "keyboard")


class MidiFeedbackIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    @contextmanager
    def frame(self):
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
                spoken = []
                frame.feedback.speak = spoken.append
                try:
                    yield frame, spoken, path
                finally:
                    frame._skip_save = True
                    frame.on_close()

    def send(self, frame, control, value):
        frame.midi._handle_message(
            mido.Message("control_change", control=control, value=value)
        )
        wx.YieldIfNeeded()
        frame.feedback.flush()

    def test_each_akm322_knob_changes_assigned_values_and_announces_them(self):
        with self.frame() as (frame, spoken, _):
            for control, key in [
                (10, "main_a"),
                (21, "main_b"),
                (22, "layer_a"),
                (23, "fx_a"),
                (1, "fx_b"),
            ]:
                before = len(spoken)
                self.send(frame, control, 100)
                self.assertAlmostEqual(frame.synth.values[key], 100 / 127)
                self.assertEqual(len(spoken), before + 1, key)
                self.assertIn("78", spoken[-1])
            self.assertFalse(frame.synth.layers)
            self.assertFalse(frame.synth.fx)

    def test_unmapped_and_unchanged_controls_stay_silent(self):
        with self.frame() as (frame, spoken, _):
            self.send(frame, 90, 100)
            self.assertFalse(spoken)
            self.send(frame, 10, 100)
            count = len(spoken)
            self.send(frame, 10, 100)
            self.assertEqual(len(spoken), count)
            frame.change_knob("main", "a", absolute=100 / 127)
            self.assertEqual(len(spoken), count)
            frame.change_knob("main", "a", absolute=0.99)
            count = len(spoken)
            frame.change_knob("main", "a", delta=0.05)
            self.assertEqual(len(spoken), count)

    def test_source_switches_persist_and_can_be_operated_from_midi(self):
        with self.frame() as (frame, spoken, path):
            frame.toggle_feedback("midi")
            spoken.clear()
            self.send(frame, 10, 100)
            self.assertFalse(spoken)
            frame.change_knob("main", "a", absolute=0.3)
            self.assertEqual(len(spoken), 1)
            frame.handle_midi_action("feedback_keyboard", "trigger", 1)
            spoken.clear()
            frame.change_knob("main", "a", absolute=0.4)
            self.assertFalse(spoken)
            state = preferences.read_config(path)
            self.assertFalse(state.getboolean("FEEDBACK", "midi"))
            self.assertFalse(state.getboolean("FEEDBACK", "keyboard"))
            frame.load_settings()
            self.assertFalse(frame.feedback.enabled["midi"])
            self.assertFalse(frame.feedback.enabled["keyboard"])
            frame.handle_midi_action("feedback_cycle", "trigger", 1)
            self.assertTrue(frame.feedback.enabled["midi"])
            self.assertTrue(frame.feedback.enabled["keyboard"])

    def test_physical_midi_button_and_keyboard_shortcuts_toggle_independently(self):
        with self.frame() as (frame, _, _):
            frame.mapper.add(
                midi_mapping.binding(("cc", 33), "feedback_midi", "button")
            )
            self.send(frame, 33, 127)
            self.assertFalse(frame.feedback.enabled["midi"])
            self.assertTrue(frame.feedback.enabled["keyboard"])
            self.send(frame, 33, 0)
            self.assertFalse(frame.feedback.enabled["midi"])
            frame.on_key_down(
                FakeKeyEvent(wx.WXK_F10, control=True, shift=True, alt=True)
            )
            self.assertFalse(frame.feedback.enabled["keyboard"])
            frame.on_key_down(
                FakeKeyEvent(wx.WXK_F9, control=True, shift=True, alt=True)
            )
            self.assertTrue(frame.feedback.enabled["midi"])
            self.assertTrue(frame.feedback_midi_item.IsChecked())
            self.assertFalse(frame.feedback_keyboard_item.IsChecked())

    def test_returning_to_a_previously_spoken_value_after_mute_is_announced(self):
        with self.frame() as (frame, spoken, _):
            self.send(frame, 10, 100)
            frame.toggle_feedback("midi")
            self.send(frame, 10, 10)
            frame.toggle_feedback("midi")
            spoken.clear()
            self.send(frame, 10, 100)
            self.assertEqual(len(spoken), 1)
            self.assertIn("78", spoken[0])

    def test_assigned_knobs_change_actual_release_layer_and_effect_audio(self):
        with self.frame() as (frame, _, _):
            frame.synth.layers.add("sub_sq")
            frame.synth.fx.add("dist")

            def audio(control, value):
                self.send(frame, control, value)
                renderer = frame.synth._offline_copy()
                renderer.note_on("test", 220, "square")
                if control == 21:
                    renderer.note_off("test")
                return renderer.generate_block(8192)

            for control in (21, 22, 23):
                low, high = audio(control, 10), audio(control, 110)
                self.assertFalse(
                    np.allclose(low, high), f"CC{control} has no audible effect"
                )


if __name__ == "__main__":
    unittest.main()
