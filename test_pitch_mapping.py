"""Native pitch, factory presets and persistent disabled-controller regressions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mido
import numpy as np
import wx
from scipy.io import wavfile

import main
import midi_handler
import midi_mapping
import sequencer
import synth
from midi_dialog import MidiMappingDialog


class PitchEngineTests(unittest.TestCase):
    def test_pitch_changes_current_and_future_channel_voices_and_returns_exactly(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.note_on(69, 440)
        engine.note_on(("midi", 1, 69), 440)
        engine.note_on((90, 0), 440)
        self.assertTrue(engine.set_pitch_bend(2, 0))
        self.assertAlmostEqual(engine.oscs[69].pitch_ratio, 2 ** (2 / 12))
        self.assertEqual(engine.oscs[("midi", 1, 69)].pitch_ratio, 1)
        self.assertEqual(engine.oscs[(90, 0)].pitch_ratio, 1)
        engine.note_on(70, 466.16)
        self.assertAlmostEqual(engine.oscs[70].pitch_ratio, 2 ** (2 / 12))
        self.assertTrue(engine.set_pitch_bend(0, 0))
        self.assertEqual(engine.oscs[69].pitch_ratio, 1)
        self.assertEqual(engine.oscs[70].pitch_ratio, 1)
        self.assertFalse(engine.set_pitch_bend(0, 0))
        self.assertEqual(engine.oscs[69].target_freq, 440)

    def test_pitch_changes_generated_frequency_without_accumulating_drift(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.note_on(69, 440)

        def frequency():
            audio = engine.generate_block(synth.SAMPLE_RATE)
            return np.count_nonzero((audio[:-1] <= 0) & (audio[1:] > 0))

        self.assertAlmostEqual(frequency(), 440, delta=1)
        engine.set_pitch_bend(2)
        self.assertAlmostEqual(frequency(), 440 * 2 ** (2 / 12), delta=1)
        engine.set_pitch_bend(-2)
        self.assertAlmostEqual(frequency(), 440 * 2 ** (-2 / 12), delta=1)
        for _ in range(100):
            engine.set_pitch_bend(2)
            engine.set_pitch_bend(0)
        self.assertAlmostEqual(frequency(), 440, delta=1)
        engine.set_pitch_bend(2)
        engine.all_notes_off(immediate=True)
        self.assertFalse(engine.pitch_bends)

    def test_invalid_pitch_and_port_close_reset(self):
        engine = synth.Synthesizer(create_stream=False)
        with self.assertRaises(ValueError):
            engine.set_pitch_bend(float("nan"))
        with self.assertRaises(ValueError):
            engine.set_pitch_bend(2, 16)
        engine.set_pitch_bend(2)
        midi_handler.MidiInputHandler(engine).stop()
        self.assertFalse(engine.pitch_bends)


class FactoryMappingTests(unittest.TestCase):
    def test_pitch_normalization_preserves_center_and_both_endpoints(self):
        received = []
        mapper = midi_mapping.MidiMapper(
            lambda *args: None, pitch_callback=lambda *args: received.append(args)
        )
        mapper.import_state(midi_mapping.profile("akm322"))
        for raw, value in [(-8192, 0), (0, 0.5), (8191, 1)]:
            self.assertTrue(
                mapper.process(mido.Message("pitchwheel", channel=3, pitch=raw))
            )
            self.assertEqual(received[-1], (3, value))

    def test_factory_profiles_and_ni_port_detection(self):
        for name in ("akm322", "ni_absolute", "ni_relative", "ni_offset", "generic"):
            entries = midi_mapping.profile(name)
            self.assertTrue(
                any(
                    item["type"] == "pitch" and item["action"] == "pitch_bend"
                    for item in entries
                )
            )
            midi_mapping.MidiMapper(lambda *args: None).import_state(entries)
        for name in (
            "KOMPLETE KONTROL M32 MIDI 0",
            "Native Instruments S61 MIDI",
            "Kontrol A49",
        ):
            self.assertEqual(midi_mapping.detect_profile(name), "ni_absolute")
        self.assertEqual(
            midi_mapping.preferred_port(
                ["KOMPLETE KONTROL DAW 0", "KOMPLETE KONTROL MIDI 1"]
            ),
            "KOMPLETE KONTROL MIDI 1",
        )
        self.assertIsNone(midi_mapping.detect_profile("Other keyboard"))
        self.assertEqual(
            midi_mapping.preferred_port(["KOMPLETE KONTROL DAW 0", "Other keyboard"]),
            "Other keyboard",
        )

    def test_disabled_mapping_consumes_input_and_persists_state(self):
        received = []
        mapper = midi_mapping.MidiMapper(lambda *args: received.append(args))
        item = midi_mapping.binding(("cc", 10), "main_a")
        item["enabled"] = False
        mapper.import_state([item])
        self.assertTrue(
            mapper.process(mido.Message("control_change", control=10, value=100))
        )
        self.assertFalse(received)
        restored = midi_mapping.MidiMapper(lambda *args: received.append(args))
        restored.import_state(json.loads(json.dumps(mapper.export_state())))
        self.assertFalse(restored.export_state()[0]["enabled"])
        item["enabled"] = True
        restored.add(item)
        restored.process(mido.Message("control_change", control=10, value=100))
        self.assertEqual(len(received), 1)

    def test_legacy_migration_only_upgrades_unmodified_akm_profile_once(self):
        legacy = [
            item for item in midi_mapping.profile("akm322") if item["type"] != "pitch"
        ]
        for item in legacy:
            item.pop("enabled")
        upgraded = midi_mapping.upgrade_legacy_profile(legacy, "AKM322 0", 1)
        self.assertTrue(any(item["type"] == "pitch" for item in upgraded))
        deleted = [item for item in upgraded if item["type"] != "pitch"]
        self.assertEqual(
            midi_mapping.upgrade_legacy_profile(deleted, "AKM322 0", 2), deleted
        )
        custom = [dict(legacy[0], action="main_b")]
        self.assertEqual(
            len(midi_mapping.upgrade_legacy_profile(custom, "AKM322 0", 1)), 1
        )
        self.assertFalse(midi_mapping.upgrade_legacy_profile([], "AKM322 0", 1))


class PitchRecordingTests(unittest.TestCase):
    def test_pitch_recording_roundtrip_playback_and_offline_wav(self):
        engine = synth.Synthesizer(create_stream=False)
        player = sequencer.Sequencer(engine)
        state = {
            "melody": [
                {
                    "time": 0,
                    "type": "pitch_bend",
                    "note": {"channel": 0, "semitones": 2},
                },
                {
                    "time": 0,
                    "type": "note_on",
                    "note": {"key": 69, "freq": 440, "wave": "square"},
                },
                {
                    "time": 200,
                    "type": "pitch_bend",
                    "note": {"channel": 0, "semitones": 0},
                },
                {"time": 300, "type": "note_off", "note": {"key": 69}},
            ]
        }
        player.import_state(json.loads(json.dumps(state)))
        player._play_melody_event(player.melody_track[0])
        player._play_melody_event(player.melody_track[1])
        self.assertAlmostEqual(engine.oscs[69].pitch_ratio, 2 ** (2 / 12))
        exported = player.export_state()
        restored = sequencer.Sequencer(engine)
        restored.import_state(json.loads(json.dumps(exported)))
        self.assertEqual(restored.melody_track[0]["note"]["semitones"], 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pitch.wav"
            engine.render_to_wav(path, restored.snapshot()[0], {}, 120, 1)
            rate, audio = wavfile.read(path)
            self.assertEqual(rate, synth.SAMPLE_RATE)
            sample = audio[: int(rate * 0.15)]
            measured = np.count_nonzero((sample[:-1] <= 0) & (sample[1:] > 0)) / 0.15
            self.assertAlmostEqual(measured, 440 * 2 ** (2 / 12), delta=8)
        player.stop()
        self.assertFalse(engine.pitch_bends)


class PitchInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_disable_wheel_resets_bend_drops_queued_events_and_survives_restart(self):
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
                    frame.synth.note_on(69, 440)
                    frame.midi._handle_message(mido.Message("pitchwheel", pitch=8191))
                    wx.YieldIfNeeded()
                    self.assertEqual(frame.synth.get_pitch_bend(), 2)
                    frame.midi._handle_message(mido.Message("pitchwheel", pitch=-8192))
                    with MidiMappingDialog(frame) as dialog:
                        index = next(
                            i
                            for i, item in enumerate(frame.mapper.bindings)
                            if item["type"] == "pitch"
                        )
                        dialog.entries.SetSelection(index)
                        dialog.on_select(None)
                        dialog.enabled.SetValue(False)
                        dialog.on_save(None)
                    wx.YieldIfNeeded()
                    self.assertEqual(frame.synth.get_pitch_bend(), 0)
                    frame.midi._handle_message(mido.Message("pitchwheel", pitch=8191))
                    wx.YieldIfNeeded()
                    self.assertEqual(frame.synth.get_pitch_bend(), 0)
                    self.assertEqual(frame.project_state()["schema"], 2)
                    frame.load_settings()
                    self.assertFalse(
                        next(
                            item
                            for item in frame.mapper.bindings
                            if item["type"] == "pitch"
                        )["enabled"]
                    )
                    frame.mapper.import_state([])
                    frame.save_midi_mappings()
                    frame.load_settings()
                    frame.initialize_midi_profile("AKM322 0")
                    self.assertFalse(frame.mapper.bindings)
                finally:
                    frame._skip_save = True
                    frame.on_close()

    def test_recorded_midi_notes_include_pitch_state_and_legacy_projects_still_load(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "po.ini"
            with (
                mock.patch.object(main, "CONFIG_PATH", path),
                mock.patch.object(main, "SPEECH_AVAILABLE", False),
            ):
                frame = main.MainFrame(
                    synth.Synthesizer(create_stream=False), False, False, False
                )
                try:
                    frame.mapper.import_state(midi_mapping.profile("akm322"))
                    frame.seq.recording = True
                    frame.record_midi_event(
                        "note_on", {"key": 69, "freq": 440, "wave": "square"}
                    )
                    self.assertEqual(frame.seq.melody_track[0]["type"], "pitch_bend")
                    frame.handle_pitch_bend(0, 1)
                    self.assertEqual(frame.seq.melody_track[-1]["note"]["semitones"], 2)
                    frame.seq.recording = False
                    state = frame.project_state()
                    state["schema"] = 1
                    frame.apply_project_state(state)
                finally:
                    frame._skip_save = True
                    frame.on_close()


if __name__ == "__main__":
    unittest.main()
