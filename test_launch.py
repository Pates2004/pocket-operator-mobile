import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import wx
from scipy.io import wavfile

import main
import midi_handler
import sequencer
import synth


class FakeSynth:
    def __init__(self):
        self.notes_on = []
        self.notes_off = []
        self.drums = []
        self.all_off_calls = 0

    def note_on(self, key, frequency, waveform, velocity=1.0):
        self.notes_on.append((key, frequency, waveform, velocity))

    def note_off(self, key):
        self.notes_off.append(key)

    def trigger_drum(self, drum):
        self.drums.append(drum)

    def all_notes_off(self, immediate=False):
        self.all_off_calls += 1


class FakeKeyEvent:
    def __init__(self, key, control=False, shift=False, alt=False):
        self.key = key
        self.control = control
        self.shift = shift
        self.alt = alt
        self.skipped = False

    def GetKeyCode(self):
        return self.key

    def ControlDown(self):
        return self.control

    def ShiftDown(self):
        return self.shift

    def AltDown(self):
        return self.alt

    def Skip(self):
        self.skipped = True


class EngineTests(unittest.TestCase):
    def test_ui_and_engine_catalogs_match(self):
        self.assertEqual(
            {code for _, code, _ in main.MainFrame.LAYERS},
            set(synth.LAYER_TYPES),
        )
        self.assertEqual(
            {code for _, code, _ in main.MainFrame.EFFECTS},
            set(synth.EFFECT_TYPES),
        )

    def test_all_main_instruments_generate_their_expected_voice(self):
        for waveform in ("square", "saw", "triangle", "noise"):
            np.random.seed(1500)
            engine = synth.Synthesizer(create_stream=False)
            engine.note_on("note", 440.0, waveform)
            block = engine.generate_block(2_048)
            self.assertTrue(np.isfinite(block).all(), waveform)
            self.assertGreater(float(np.max(np.abs(block))), 0.0, waveform)

        drum_kit = synth.Synthesizer(create_stream=False)
        drum_kit.note_on(("key", 7), 440.0, "drum_kit")
        self.assertEqual(drum_kit.shots[-1].type, "laser")

    def test_tiny_blocks_and_invalid_numeric_input_are_safe(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.fx.update({"lpf", "hpf"})
        engine.note_on("note", 440.0, "noise")
        self.assertEqual(engine.generate_block(1).shape, (1,))
        self.assertEqual(engine.generate_block(0).shape, (0,))
        with self.assertRaises(ValueError):
            engine.set_vol(float("nan"))
        with self.assertRaises(ValueError):
            engine.note_on("bad", float("inf"), "square")

    def test_note_layers_effects_and_release(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.layers.update({"sub_sq", "fifth", "detune"})
        engine.targets_layer.add("sub_sq")
        engine.set_layer_knob("a", 0.7)
        engine.fx.update({"dist", "verb", "trem"})
        engine.targets_fx.add("dist")
        engine.set_fx_knob("a", 0.6)
        engine.note_on((1, 0), 440.0, "square")

        block = engine.generate_block(2_048)
        self.assertEqual(block.shape, (2_048,))
        self.assertTrue(np.isfinite(block).all())
        self.assertGreater(float(np.max(np.abs(block))), 0.0)

        engine.note_off((1, 0))
        for _ in range(450):
            engine.generate_block(1_024)
            if not engine.oscs:
                break
        self.assertFalse(engine.oscs)

    def test_panic_clears_notes_drums_and_reverb(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.note_on("note", 440.0, "square")
        engine.trigger_drum("crash")
        engine.delay_buffer.fill(1.0)
        engine.last_freq = 440.0
        engine.fx_time = 12.0
        engine.all_notes_off(immediate=True)
        self.assertFalse(engine.oscs)
        self.assertFalse(engine.shots)
        self.assertFalse(np.any(engine.delay_buffer))
        self.assertIsNone(engine.last_freq)
        self.assertEqual(engine.fx_time, 0.0)

    def test_all_effects_return_finite_audio(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.fx.update(
            {
                "lpf",
                "hpf",
                "verb",
                "crush",
                "dist",
                "chop",
                "side",
                "trem",
                "ring",
                "deci",
                "fuzz",
                "glit",
                "noiz",
            }
        )
        engine.note_on("a", 261.63, "triangle")
        block = engine.generate_block(2_048)
        self.assertTrue(np.isfinite(block).all())

    def test_full_stack_at_extreme_settings_stays_finite_and_clipped(self):
        np.random.seed(1500)
        engine = synth.Synthesizer(create_stream=False)
        engine.layers.update(synth.LAYER_TYPES)
        engine.fx.update(synth.EFFECT_TYPES)
        engine.set_knob_a(0.99)
        engine.set_knob_b(1.0)
        engine.set_layer_knob("a", 0.99)
        engine.set_layer_knob("b", 1.0)
        engine.set_fx_knob("a", 1.0)
        engine.set_fx_knob("b", 1.0)
        engine.set_vol(1.0)
        for index, waveform in enumerate(
            ("square", "saw", "triangle", "noise")
        ):
            engine.note_on(index, 110.0 * (index + 1), waveform)
        for drum in sequencer.DRUM_INSTRUMENTS:
            engine.trigger_drum(drum)

        block = np.concatenate(
            [engine.generate_block(1_024) for _ in range(20)]
        )
        self.assertTrue(np.isfinite(block).all())
        self.assertLessEqual(float(np.max(np.abs(block))), 1.0)
        self.assertGreater(float(np.max(np.abs(block))), 0.0)

        output = np.empty((256, 1), dtype=np.float32)
        engine.audio_callback(output, 256, None, None)
        self.assertTrue(np.isfinite(output).all())

    def test_all_historic_drum_voices_generate_audio(self):
        for drum in sequencer.DRUM_INSTRUMENTS:
            engine = synth.Synthesizer(create_stream=False)
            engine.trigger_drum(drum)
            block = engine.generate_block(2_048)
            self.assertTrue(np.isfinite(block).all(), drum)
            self.assertGreater(float(np.max(np.abs(block))), 0.0, drum)

    def test_every_drum_responds_to_both_main_knobs(self):
        for drum in sequencer.DRUM_INSTRUMENTS:
            variations = {}
            for label, parameters in {
                "a_low": (0.1, 0.5),
                "a_high": (0.9, 0.5),
                "b_low": (0.5, 0.0),
                "b_high": (0.5, 1.0),
            }.items():
                np.random.seed(1500)
                shot = synth.OneShot(
                    drum,
                    synth.SAMPLE_RATE,
                    *parameters,
                )
                variations[label] = shot.get_samples(16_384)
            self.assertFalse(
                np.allclose(variations["a_low"], variations["a_high"]),
                f"Bęben {drum} nie reaguje na gałkę A",
            )
            self.assertFalse(
                np.allclose(variations["b_low"], variations["b_high"]),
                f"Bęben {drum} nie reaguje na gałkę B",
            )

    def test_legacy_synth_api_is_compatible(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.set_volume(0.4)
        engine.set_layer_knob_a(0.6)
        engine.set_layer_knob_b(0.3)
        engine.active_layers = {"sub_sin"}
        engine.active_fx = {"dist"}
        engine.set_fx_a(0.7)
        engine.set_fx_b(0.2)
        engine.sustain_enabled = False
        engine.glide_enabled = True
        engine.fix_release = False
        self.assertEqual(engine.volume, 0.4)
        self.assertEqual(engine.layer_knob_a, 0.6)
        self.assertEqual(engine.active_layers, {"sub_sin"})
        self.assertEqual(engine.active_fx, {"dist"})
        self.assertAlmostEqual(engine.fx_param_a, 0.7)
        self.assertFalse(engine.sustain_enabled)
        self.assertTrue(engine.glide_enabled)

    def test_layer_and_effect_b_parameters_change_audio(self):
        quiet_layer = synth.Synthesizer(create_stream=False)
        quiet_layer.layers.add("sub_sin")
        quiet_layer.values["sub_sin_b"] = 0.0
        quiet_layer.note_on("note", 220.0, "square")
        quiet = quiet_layer.generate_block(2_048)

        loud_layer = synth.Synthesizer(create_stream=False)
        loud_layer.layers.add("sub_sin")
        loud_layer.values["sub_sin_b"] = 1.0
        loud_layer.note_on("note", 220.0, "square")
        loud = loud_layer.generate_block(2_048)
        self.assertFalse(np.allclose(quiet, loud))

        dry_effect = synth.Synthesizer(create_stream=False)
        dry_effect.fx.add("dist")
        dry_effect.values["dist_a"] = 1.0
        dry_effect.values["dist_b"] = 0.0
        dry_effect.note_on("note", 220.0, "triangle")
        dry = dry_effect.generate_block(2_048)

        wet_effect = synth.Synthesizer(create_stream=False)
        wet_effect.fx.add("dist")
        wet_effect.values["dist_a"] = 1.0
        wet_effect.values["dist_b"] = 1.0
        wet_effect.note_on("note", 220.0, "triangle")
        wet = wet_effect.generate_block(2_048)
        self.assertFalse(np.allclose(dry, wet))

    def test_every_layer_and_effect_b_parameter_changes_audio(self):
        for layer in synth.LAYER_TYPES:
            rendered = []
            for level in (0.0, 1.0):
                np.random.seed(1500)
                engine = synth.Synthesizer(create_stream=False)
                engine.layers.add(layer)
                engine.values[f"{layer}_b"] = level
                engine.note_on("note", 220.0, "square")
                rendered.append(engine.generate_block(4_096))
            self.assertFalse(
                np.allclose(*rendered),
                f"Gałka B warstwy {layer} nie zmienia audio",
            )

        for effect in synth.EFFECT_TYPES:
            rendered = []
            for level in (0.0, 1.0):
                np.random.seed(1500)
                engine = synth.Synthesizer(create_stream=False)
                engine.fx.add(effect)
                engine.values[f"{effect}_a"] = 0.85
                engine.values[f"{effect}_b"] = level
                engine.note_on("note", 220.0, "triangle")
                rendered.append(
                    np.concatenate(
                        [engine.generate_block(1_024) for _ in range(16)]
                    )
                )
            self.assertFalse(
                np.allclose(*rendered),
                f"Gałka B efektu {effect} nie zmienia audio",
            )

    def test_global_knobs_seed_inactive_layers_and_effects(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.set_layer_knob("a", 0.66)
        engine.set_layer_knob("b", 0.77)
        engine.set_fx_knob("a", 0.22)
        engine.set_fx_knob("b", 0.33)
        for layer in synth.LAYER_TYPES:
            self.assertAlmostEqual(engine.values[f"{layer}_a"], 0.66)
            self.assertAlmostEqual(engine.values[f"{layer}_b"], 0.77)
        for effect in synth.EFFECT_TYPES:
            self.assertAlmostEqual(engine.values[f"{effect}_a"], 0.22)
            self.assertAlmostEqual(engine.values[f"{effect}_b"], 0.33)

    def test_wav_export_does_not_mutate_live_voices(self):
        engine = synth.Synthesizer(create_stream=False)
        engine.layers.add("fifth")
        engine.fx.add("dist")
        engine.note_on("live", 220.0, "saw")
        melody = [
            {
                "time": 0.0,
                "type": "note_on",
                "note": {"key": "export", "freq": 440.0, "wave": "square"},
            },
            {
                "time": 100.0,
                "type": "note_off",
                "note": {"key": "export"},
            },
        ]
        drums = {
            "kick": [True] + [False] * 15,
            "snare": [False] * 16,
            "hihat": [False] * 16,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "test.wav"
            engine.render_to_wav(target, melody, drums, bpm=300, loops=1)
            rate, audio = wavfile.read(target)
            self.assertEqual(rate, synth.SAMPLE_RATE)
            self.assertGreater(len(audio), 0)
            self.assertGreater(int(np.max(np.abs(audio.astype(np.int32)))), 0)
        self.assertIn("live", engine.oscs)


class SequencerAndMidiTests(unittest.TestCase):
    def test_sequencer_starts_thread_and_plays_tracks(self):
        fake = FakeSynth()
        player = sequencer.Sequencer(fake, bpm=300)
        player.drum_tracks["kick"][0] = True
        player.melody_track.append(
            {
                "time": 0.0,
                "type": "note_on",
                "note": {"key": "n", "freq": 440.0, "wave": "square"},
            }
        )
        player.play()
        time.sleep(0.03)
        player.stop()
        self.assertIn("kick", fake.drums)
        self.assertTrue(fake.notes_on)
        self.assertEqual(fake.all_off_calls, 1)

    def test_sequencer_state_and_tempo_scaling(self):
        source = sequencer.Sequencer(FakeSynth(), bpm=120)
        source.drum_tracks["laser"][15] = True
        source.melody_track = [
            {
                "time": 1_000.0,
                "type": "note_on",
                "note": {
                    "key": (90, 0),
                    "freq": 261.63,
                    "wave": "square",
                    "velocity": 0.8,
                },
                "_id": 1,
                "_skip_cycle": -1,
            }
        ]
        source.set_bpm(60)
        self.assertEqual(source.melody_track[0]["time"], 2_000.0)
        state = source.export_state()

        restored = sequencer.Sequencer(FakeSynth(), bpm=60)
        restored.import_state(state)
        self.assertTrue(restored.drum_tracks["laser"][15])
        self.assertEqual(restored.melody_track[0]["note"]["key"], (90, 0))

    def test_sequencer_restart_and_state_validation(self):
        fake = FakeSynth()
        player = sequencer.Sequencer(fake, bpm=300)
        player.melody_track = [
            {
                "time": 0.0,
                "type": "note_on",
                "note": {"key": "n", "freq": 440.0, "wave": "square"},
                "_id": 1,
                "_skip_cycle": 0,
            }
        ]
        for _ in range(2):
            player.play()
            time.sleep(0.02)
            player.stop()
        self.assertEqual(len(fake.notes_on), 2)

        with self.assertRaises(ValueError):
            sequencer.Sequencer(fake, bpm=0)
        with self.assertRaises(ValueError):
            player.import_state(
                {
                    "melody": [
                        {
                            "time": float("nan"),
                            "type": "note_on",
                            "note": {
                                "key": "bad",
                                "freq": 440.0,
                                "wave": "square",
                            },
                        }
                    ]
                }
            )

    def test_midi_note_on_and_off_use_synth_api(self):
        fake = FakeSynth()
        midi = midi_handler.MidiInputHandler(fake, lambda: "saw")
        midi._handle_message(
            SimpleNamespace(type="note_on", velocity=100, note=69)
        )
        midi._handle_message(
            SimpleNamespace(type="note_off", velocity=0, note=69)
        )
        self.assertEqual(fake.notes_on[0][:3], (69, 440.0, "saw"))
        self.assertAlmostEqual(fake.notes_on[0][3], 100 / 127)
        self.assertEqual(fake.notes_off, [69])

    def test_midi_sustain_pedal_defers_note_off(self):
        fake = FakeSynth()
        midi = midi_handler.MidiInputHandler(fake, lambda: "square")
        midi._handle_message(
            SimpleNamespace(type="control_change", control=64, value=127)
        )
        midi._handle_message(
            SimpleNamespace(type="note_off", velocity=0, note=60)
        )
        self.assertEqual(fake.notes_off, [])
        midi._handle_message(
            SimpleNamespace(type="control_change", control=64, value=0)
        )
        self.assertEqual(fake.notes_off, [60])


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    def test_window_and_total_recall(self):
        engine = synth.Synthesizer(create_stream=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "po.ini"
            with (
                mock.patch.object(main, "CONFIG_PATH", config_path),
                mock.patch.object(main, "SPEECH_AVAILABLE", False),
            ):
                frame = main.MainFrame(
                    synth_instance=engine,
                    auto_start=False,
                    auto_midi=False,
                    load_config=False,
                )
                frame.waveform = "saw"
                frame.bpm = 144
                frame.octave = 2
                frame.chord_mode = False
                frame.synth.layers.update({"fifth", "sub_sin"})
                frame.synth.fx.add("dist")
                frame.synth.targets_layer.add("fifth")
                frame.synth.values["dist_a"] = 0.73
                frame.synth.values["fifth_b"] = 0.81
                frame.saved_midi = "Port 100% MIDI"
                frame.begin_punch_in(ord("1"), "lpf")
                self.assertIn("lpf", frame.synth.fx)
                frame.end_punch_in(ord("1"))
                self.assertNotIn("lpf", frame.synth.fx)
                frame.toggle_recording()
                frame.play_physical_key(ord("X"))
                frame.toggle_recording()
                event_types = [
                    event["type"] for event in frame.seq.melody_track
                ]
                self.assertEqual(event_types, ["note_on", "note_off"])
                frame.release_physical_key(ord("X"))
                frame.seq.clear_melody()
                frame.seq.stop()
                frame.synth.all_notes_off(immediate=True)
                frame.chord_mode = True
                frame.seq.drum_tracks["laser"][15] = True
                frame.seq.melody_track = [
                    {
                        "time": 250.0,
                        "type": "note_on",
                        "note": {
                            "key": (90, 0),
                            "freq": 261.63,
                            "wave": "square",
                        },
                        "_id": 1,
                        "_skip_cycle": -1,
                    }
                ]
                frame.play_physical_key(ord("Z"))
                self.assertEqual(len(frame.synth.oscs), 3)
                frame.release_physical_key(ord("Z"))
                self.assertTrue(
                    all(voice.releasing for voice in frame.synth.oscs.values())
                )
                frame.save_settings()
                frame._skip_save = True
                frame.on_close()

                restored_engine = synth.Synthesizer(create_stream=False)
                restored = main.MainFrame(
                    synth_instance=restored_engine,
                    auto_start=False,
                    auto_midi=False,
                    load_config=True,
                )
                self.assertEqual(restored.waveform, "saw")
                self.assertEqual(restored.bpm, 144)
                self.assertEqual(restored.octave, 2)
                self.assertTrue(restored.chord_mode)
                self.assertEqual(restored.synth.layers, {"fifth", "sub_sin"})
                self.assertEqual(restored.synth.fx, {"dist"})
                self.assertEqual(restored.synth.targets_layer, {"fifth"})
                self.assertAlmostEqual(restored.synth.values["dist_a"], 0.73)
                self.assertAlmostEqual(restored.synth.values["fifth_b"], 0.81)
                self.assertEqual(restored.saved_midi, "Port 100% MIDI")
                self.assertTrue(restored.seq.drum_tracks["laser"][15])
                self.assertEqual(
                    restored.seq.melody_track[0]["note"]["key"], (90, 0)
                )
                project = json.loads(
                    json.dumps(restored.project_state(), ensure_ascii=False)
                )
                restored.apply_project_state(project)
                self.assertEqual(project["app_version"], "15.0")
                self.assertEqual(project["format"], main.PROJECT_FORMAT)
                self.assertEqual(
                    restored.seq.melody_track[0]["note"]["key"], (90, 0)
                )
                corrupted = json.loads(json.dumps(project))
                corrupted["settings"]["waveform"] = "triangle"
                corrupted["settings"]["bpm"] = 90
                corrupted["sequencer"]["drums"]["laser"] = "broken"
                with self.assertRaises(TypeError):
                    restored.apply_project_state(corrupted)
                self.assertEqual(restored.waveform, "saw")
                self.assertEqual(restored.bpm, 144)

                corrupted = json.loads(json.dumps(project))
                corrupted["settings"]["waveform"] = "triangle"
                corrupted["settings"]["bpm"] = 90
                corrupted["settings"]["layers"] = [{}]
                with self.assertRaises(TypeError):
                    restored.apply_project_state(corrupted)
                self.assertEqual(restored.waveform, "saw")
                self.assertEqual(restored.bpm, 144)
                restored._skip_save = True
                restored.on_close()

    def test_keyboard_routes_historic_and_v15_shortcuts(self):
        engine = synth.Synthesizer(create_stream=False)
        with (
            mock.patch.object(main, "SPEECH_AVAILABLE", False),
            mock.patch.object(main, "CONFIG_PATH", Path("unused-test.ini")),
        ):
            frame = main.MainFrame(
                synth_instance=engine,
                auto_start=False,
                auto_midi=False,
                load_config=False,
            )
            frame.on_key_down(
                FakeKeyEvent(wx.WXK_F2, control=True)
            )
            self.assertEqual(frame.waveform, "saw")

            frame.on_key_down(FakeKeyEvent(220, alt=True))
            self.assertIn("sub_sin", frame.synth.layers)
            frame.toggle_layer("fifth")
            frame.synth.targets_layer.add("sub_sin")
            frame.toggle_all_layer_targets()
            self.assertEqual(
                frame.synth.targets_layer, {"sub_sin", "fifth"}
            )
            frame.toggle_all_layer_targets()
            self.assertFalse(frame.synth.targets_layer)

            frame.on_key_down(
                FakeKeyEvent(ord("1"), control=True, shift=True)
            )
            self.assertIn("lpf", frame.synth.fx)
            frame.on_key_up(FakeKeyEvent(ord("1")))
            self.assertNotIn("lpf", frame.synth.fx)

            frame.on_key_down(FakeKeyEvent(wx.WXK_F12))
            self.assertEqual(frame.synth.shots[-1].type, "laser")

            frame.on_key_down(
                FakeKeyEvent(
                    wx.WXK_PAGEUP,
                    control=True,
                    shift=True,
                    alt=True,
                )
            )
            self.assertAlmostEqual(frame.synth.values["sub_sin_a"], 0.99)

            frame.on_key_down(
                FakeKeyEvent(wx.WXK_ESCAPE, control=True, shift=True)
            )
            self.assertFalse(frame.synth.shots)
            frame._skip_save = True
            frame.on_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
