"""Audio-level expression controls, recording/export and localized names."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mido
import numpy as np
import wx
from scipy.io import wavfile

import localization
import main
import midi_mapping
import sequencer
import synth


class ExpressionAudioTests(unittest.TestCase):
    def test_filter_changes_audio_and_preserves_state_across_blocks(self):
        def engine():
            result = synth.Synthesizer(create_stream=False)
            result.restore_values({"brightness": 0.1})
            result.note_on(69, 440, "triangle")
            return result

        continuous, split = engine(), engine()
        expected = continuous.generate_block(4096)
        actual = np.concatenate([split.generate_block(256) for _ in range(16)])
        np.testing.assert_allclose(actual, expected, atol=1e-6)
        neutral = synth.Synthesizer(create_stream=False)
        neutral.note_on(69, 440, "triangle")
        self.assertGreater(np.std(neutral.generate_block(4096)), np.std(expected) * 1.5)
        split.all_notes_off(immediate=True)
        self.assertFalse(np.any(split.generate_block(256)))

    def test_vibrato_modulates_pitch_and_zero_restores_constant_period(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.note_on(69, 440)
        engine.restore_values({"vibrato": 1})
        samples = engine.generate_block(synth.SAMPLE_RATE)
        crossings = np.flatnonzero((samples[:-1] <= 0) & (samples[1:] > 0))
        frequencies = synth.SAMPLE_RATE / np.diff(crossings)
        self.assertGreater(frequencies.max(), 449)
        self.assertLess(frequencies.min(), 431)
        self.assertEqual(engine.oscs[69].target_freq, 440)
        engine.restore_values({"vibrato": 0})
        samples = engine.generate_block(synth.SAMPLE_RATE)
        crossings = np.flatnonzero((samples[:-1] <= 0) & (samples[1:] > 0))
        self.assertLess(np.ptp(synth.SAMPLE_RATE / np.diff(crossings)), 5)

    def test_expression_events_roundtrip_and_change_exported_audio(self):
        engine = synth.Synthesizer(create_stream=False)
        player = sequencer.Sequencer(engine)
        melody = [
            {
                "time": 0,
                "type": "expression",
                "note": {"parameter": "brightness", "value": 0.1},
            },
            {
                "time": 0,
                "type": "expression",
                "note": {"parameter": "vibrato", "value": 1},
            },
            {
                "time": 0,
                "type": "note_on",
                "note": {"key": 69, "freq": 440, "wave": "square"},
            },
        ]
        player.import_state({"melody": melody})
        state = json.loads(json.dumps(player.export_state()))
        player.import_state(state)
        for event in player.melody_track[:2]:
            player._play_melody_event(event)
        self.assertEqual(engine.values["vibrato"], 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expression.wav"
            engine.render_to_wav(path, player.melody_track, {}, 120, 1)
            _, audio = wavfile.read(path)
            self.assertGreater(np.std(audio), 0)
            engine.restore_values({"brightness": 1, "vibrato": 0})
            neutral_path = Path(directory) / "neutral.wav"
            engine.render_to_wav(neutral_path, player.melody_track[2:], {}, 120, 1)
            _, neutral = wavfile.read(neutral_path)
            self.assertFalse(np.array_equal(audio, neutral))
        with self.assertRaises(ValueError):
            player.import_state(
                {"melody": [dict(melody[0], note={"parameter": "volume", "value": 1})]}
            )


class ExpressionInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_factory_controls_choose_instruments_filter_and_vibrato_and_record(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(main, "CONFIG_PATH", Path(directory) / "po.ini"),
            mock.patch.object(main, "SPEECH_AVAILABLE", False),
        ):
            frame = main.MainFrame(
                synth.Synthesizer(create_stream=False), False, False, False
            )
            try:
                frame.mapper.import_state(midi_mapping.profile("akm322"))
                for value, wave in [
                    (0, "square"),
                    (30, "saw"),
                    (60, "triangle"),
                    (90, "noise"),
                    (127, "drum_kit"),
                ]:
                    frame.midi._handle_message(
                        mido.Message("control_change", control=10, value=value)
                    )
                    wx.YieldIfNeeded()
                    self.assertEqual(frame.waveform, wave)
                frame.seq.recording = True
                for cc in (23, 1):
                    frame.midi._handle_message(
                        mido.Message("control_change", control=cc, value=100)
                    )
                wx.YieldIfNeeded()
                self.assertAlmostEqual(frame.synth.values["brightness"], 100 / 127)
                self.assertAlmostEqual(frame.synth.values["vibrato"], 100 / 127)
                self.assertEqual(len(frame.seq.melody_track), 4)
                frame.seq.recording = False
                state = json.loads(json.dumps(frame.project_state()))
                frame.apply_project_state(state)
                self.assertAlmostEqual(frame.synth.values["vibrato"], 100 / 127)
            finally:
                frame._skip_save = True
                frame.on_close()

    def test_polish_names_cover_menus_runtime_waves_layers_effects_and_drums(self):
        old = localization.get_language()
        try:
            localization.set_language("pl")
            self.assertEqual(localization.tr("square"), "Prostokąt")
            self.assertEqual(localization.tr("Instrument saw"), "Instrument Piła")
            self.assertEqual(localization.tr("Triangle"), "Trójkąt")
            self.assertEqual(localization.tr("Sub Sine"), "Sinusoida subbasowa")
            for name in (
                "Square",
                "Saw",
                "Noise",
                "DrumKit",
                "Reverb",
                "Low Pass",
                "Distortion",
                "Sub Square",
                "kick",
                "snare",
            ):
                self.assertNotEqual(localization.tr(name), name)
            localization.set_language("en")
            self.assertEqual(localization.tr("Triangle"), "Triangle")
            self.assertEqual(localization.tr("square"), "Square")
        finally:
            localization.set_language(old)


if __name__ == "__main__":
    unittest.main()
