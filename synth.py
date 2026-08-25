import threading

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

SAMPLE_RATE = 44_100
BLOCK_SIZE = 1_024
LAYER_TYPES = (
    "oct_down",
    "sub_sq",
    "sub_sin",
    "sub_oct",
    "fifth",
    "maj3",
    "min3",
    "oct_up",
    "detune",
    "noise",
    "digital",
    "harm",
    "organ",
    "vinyl",
)
EFFECT_TYPES = (
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
)


def _clamp(value, minimum, maximum, name="wartość"):
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"{name} musi być liczbą skończoną")
    return max(minimum, min(maximum, value))


class Oscillator:
    def __init__(
        self,
        target_freq,
        start_freq=None,
        waveform="square",
        layers=None,
        sample_rate=SAMPLE_RATE,
    ):
        self.target_freq = target_freq
        self.current_freq = start_freq if start_freq is not None else target_freq
        self.sample_rate = sample_rate
        self.waveform = waveform
        self.layers = set(layers or ())
        self.phase = 0.0
        self.playing = False
        self.volume = 0.5
        self.params = {
            "main_a": 0.5,
            "main_b": 0.5,
            "layer_a": 0.5,
            "layer_b": 0.5,
        }
        self.glide_step = 20.0
        self.sustain = True
        self.fix_rel = True
        self.releasing = False
        self.rel_fac = 1.0
        self.life = 0.0

    def get_samples(self, sample_count):
        sample_count = int(sample_count)
        if sample_count <= 0:
            return np.zeros(0, dtype=np.float32)
        if not self.playing and not self.releasing:
            return np.zeros(sample_count, dtype=np.float32)

        if self.current_freq != self.target_freq:
            difference = self.target_freq - self.current_freq
            if abs(difference) < self.glide_step:
                self.current_freq = self.target_freq
            else:
                self.current_freq += self.glide_step * np.sign(difference)

        phase_increment = self.current_freq / self.sample_rate
        sample_index = np.arange(sample_count)
        main_phase = sample_index * phase_increment + self.phase
        self.phase = (main_phase[-1] + phase_increment) % 1.0
        cycle = main_phase % 1.0

        def wave(waveform, phase, parameter):
            if waveform == "square":
                return np.where(phase < parameter, 1.0, -1.0)
            if waveform == "saw":
                parameter = max(0.01, min(0.99, parameter))
                return np.where(
                    phase < parameter,
                    phase * (2 / parameter) - 1,
                    (1 - phase) * (2 / (1 - parameter)) - 1,
                )
            if waveform == "triangle":
                raw = 2.0 * np.abs(2.0 * phase - 1.0) - 1.0
                drive = 1.0 + parameter * 10.0
                return np.tanh(raw * drive) / np.tanh(drive)
            if waveform == "noise":
                noise = np.random.uniform(-1, 1, sample_count)
                if parameter < 0.9:
                    width = min(
                        sample_count,
                        int(1 + (1.0 - parameter) * 20),
                    )
                    return np.convolve(
                        noise, np.ones(width) / width, mode="same"
                    )
                return noise
            return np.zeros(sample_count)

        signal = wave(self.waveform, cycle, self.params["main_a"])
        layer_power = 0.0
        for layer in self.layers:
            parameter = self.params.get(
                f"{layer}_a", self.params.get("layer_a", 0.5)
            )
            mix_parameter = self.params.get(
                f"{layer}_b", self.params.get("layer_b", 0.2)
            )
            layer_signal = np.zeros(sample_count)
            if layer in {"oct_down", "sub_oct"}:
                layer_signal = wave(
                    self.waveform, (main_phase * 0.5) % 1.0, parameter
                )
            elif layer == "sub_sq":
                layer_signal = np.where(
                    ((main_phase * 0.5) % 1.0) < parameter, 1.0, -1.0
                )
            elif layer == "sub_sin":
                raw_sine = np.sin(2 * np.pi * ((main_phase * 0.5) % 1.0))
                drive = 1.0 + parameter * 5.0
                layer_signal = np.tanh(raw_sine * drive) / np.tanh(drive)
            elif layer == "fifth":
                layer_signal = np.where(
                    ((main_phase * 1.4983) % 1.0) < parameter, 1.0, -1.0
                )
            elif layer == "maj3":
                layer_signal = np.where(
                    ((main_phase * 1.2599) % 1.0) < parameter, 1.0, -1.0
                )
            elif layer == "min3":
                layer_signal = np.where(
                    ((main_phase * 1.1892) % 1.0) < parameter, 1.0, -1.0
                )
            elif layer == "oct_up":
                layer_signal = np.where(
                    ((main_phase * 2.0) % 1.0) < parameter, 1.0, -1.0
                )
            elif layer == "detune":
                detune = 1.005 + parameter * 0.02
                layer_signal = wave(
                    self.waveform, (main_phase * detune) % 1.0, parameter
                )
            elif layer == "noise":
                layer_signal = np.random.uniform(-1, 1, sample_count)
                if parameter < 0.9:
                    width = min(
                        sample_count,
                        int(1 + (1.0 - parameter) * 20),
                    )
                    layer_signal = np.convolve(
                        layer_signal,
                        np.ones(width) / width,
                        mode="same",
                    )
            elif layer == "digital":
                layer_signal = np.round(
                    np.where((main_phase % 1.0) < parameter, 1.0, -1.0) * 2.0
                ) / 2.0
            elif layer == "harm":
                layer_signal = (
                    np.sin(2 * np.pi * main_phase)
                    + parameter * np.sin(4 * np.pi * main_phase)
                    + parameter**2 * 0.75 * np.sin(6 * np.pi * main_phase)
                ) * 0.5
            elif layer == "organ":
                harmonic_level = 0.2 + parameter * 0.8
                layer_signal = (
                    np.sign(np.sin(2 * np.pi * main_phase))
                    + harmonic_level
                    * np.sign(np.sin(6 * np.pi * main_phase))
                ) * 0.5
            elif layer == "vinyl":
                probability = min(0.05, 0.001 * parameter)
                layer_signal = np.random.choice(
                    [0.0, -1.0, 1.0],
                    size=sample_count,
                    p=[1.0 - probability, probability / 2, probability / 2],
                )
            layer_volume = mix_parameter * 2.0
            signal += layer_signal * layer_volume
            layer_power += layer_volume**2

        if layer_power:
            signal /= np.sqrt(1.0 + layer_power)

        decay_time = 0.05 + self.params["main_b"] * 5.0
        amplitude = np.ones(sample_count)
        if self.releasing:
            amplitude = (
                np.exp(-(1.0 / decay_time) * (sample_index / self.sample_rate))
                * self.rel_fac
            )
            self.rel_fac = amplitude[-1]
            if self.rel_fac < 0.001:
                self.releasing = False
                self.playing = False
        elif not self.sustain:
            lifetime = sample_index / self.sample_rate + self.life
            amplitude = np.exp(-(1.0 / decay_time) * lifetime)
            self.life += sample_count / self.sample_rate
            if self.fix_rel:
                self.rel_fac = amplitude[-1]
            if amplitude[-1] < 0.001:
                self.playing = False

        return signal.astype(np.float32) * self.volume * amplitude


class OneShot:
    def __init__(self, drum_type, sample_rate, parameter_a, parameter_b):
        self.type = drum_type
        self.sample_rate = sample_rate
        self.position = 0
        self.finished = False
        self.volume = 0.6
        self.parameter_a = parameter_a
        self.parameter_b = parameter_b

    def get_samples(self, sample_count):
        sample_count = int(sample_count)
        if sample_count <= 0:
            return np.zeros(0, dtype=np.float32)
        if self.finished:
            return np.zeros(sample_count, dtype=np.float32)

        time_axis = np.arange(
            self.position, self.position + sample_count
        ) / self.sample_rate
        signal = np.zeros(sample_count)
        duration_multiplier = 0.2 + self.parameter_b * 1.8

        if self.type == "kick":
            duration = 0.2 * duration_multiplier
            phase = (
                (50 + self.parameter_a * 150)
                * time_axis
                * np.exp(-10 * time_axis)
            )
            signal = np.tanh(
                np.sin(2 * np.pi * phase)
                * np.maximum(0, 1 - time_axis / duration)
                * 5.0
            )
        elif self.type == "snare":
            duration = 0.15 * duration_multiplier
            decay = np.maximum(0, 1 - time_axis / duration)
            signal = (
                np.sin(
                    2
                    * np.pi
                    * (150 + self.parameter_a * 200)
                    * time_axis
                )
                * 0.3
                + np.random.uniform(-1, 1, sample_count) * 0.7
            ) * decay
        elif self.type == "hihat":
            duration = 0.05 * duration_multiplier
            signal = (
                np.random.uniform(-1, 1, sample_count)
                * np.maximum(0, 1 - time_axis / duration)
                * (0.5 + self.parameter_a * 0.5)
            )
        elif self.type == "tom":
            duration = 0.25 * duration_multiplier
            start_frequency = 100 + self.parameter_a * 300
            phase = (
                start_frequency
                * time_axis
                * np.exp(-5 * time_axis)
            )
            signal = np.sin(2 * np.pi * phase) * np.maximum(
                0, 1 - time_axis / duration
            )
        elif self.type == "clap":
            duration = 0.2 * duration_multiplier
            burst_rate = 30 + self.parameter_a * 20
            envelope = np.maximum(0, 1 - time_axis / duration)
            burst = np.abs(np.sin(2 * np.pi * burst_rate * time_axis))
            signal = (
                np.random.uniform(-1, 1, sample_count) * envelope * burst
            )
        elif self.type == "cowbell":
            duration = 0.3 * duration_multiplier
            base_frequency = 540 + self.parameter_a * 500
            envelope = np.maximum(0, 1 - time_axis / duration)
            tone_one = np.sign(
                np.sin(2 * np.pi * base_frequency * time_axis)
            )
            tone_two = np.sign(
                np.sin(2 * np.pi * base_frequency * 1.5 * time_axis)
            )
            signal = (tone_one + tone_two) * envelope * 0.5
        elif self.type == "crash":
            duration = 1.5 * duration_multiplier
            envelope = np.maximum(0, 1 - time_axis / duration)
            noise = np.random.uniform(-1, 1, sample_count)
            brightness = self.parameter_a
            metallic = (
                np.sin(2 * np.pi * (2_300 + brightness * 1_200) * time_axis)
                + np.sin(
                    2 * np.pi * (3_710 + brightness * 1_900) * time_axis
                )
                + np.sin(
                    2 * np.pi * (5_840 + brightness * 2_400) * time_axis
                )
            ) / 3.0
            signal = (
                noise * (1.0 - brightness * 0.45)
                + metallic * brightness * 0.45
            ) * envelope * 0.8
        elif self.type == "laser":
            duration = 0.2 * duration_multiplier
            start_frequency = 1_000 + self.parameter_a * 2_000
            end_frequency = 50
            sweep = (end_frequency - start_frequency) / duration
            phase = (
                start_frequency * time_axis
                + sweep / 2 * time_axis**2
            )
            signal = np.sign(np.sin(2 * np.pi * phase)) * np.maximum(
                0, 1 - time_axis / duration
            )
        else:
            duration = 0.2 * duration_multiplier
            signal = np.random.uniform(-1, 1, sample_count) * np.maximum(
                0, 1 - time_axis / duration
            )

        self.position += sample_count
        if self.position / self.sample_rate >= duration:
            self.finished = True
        return signal.astype(np.float32) * self.volume


class Synthesizer:
    def __init__(self, device=None, create_stream=True):
        self.oscs = {}
        self.shots = []
        self.lock = threading.RLock()
        self.last_freq = None
        self.glide = False
        self.sus = True
        self.fix_rel = True
        self.fx = set()
        self.fx_time = 0.0
        self.delay_buffer = np.zeros(int(SAMPLE_RATE * 0.5), dtype=np.float32)
        self.delay_index = 0
        self.layers = set()
        self.vol = 0.2
        self.running = False
        self.device = device
        self.stream = None

        self.values = {
            "main_a": 0.5,
            "main_b": 0.2,
            "layer_a": 0.5,
            "layer_b": 0.2,
            "fx_a": 0.5,
            "fx_b": 0.5,
        }
        for layer in LAYER_TYPES:
            self.values[f"{layer}_a"] = 0.5
            self.values[f"{layer}_b"] = 0.2
        for effect in EFFECT_TYPES:
            self.values[f"{effect}_a"] = 0.5
            self.values[f"{effect}_b"] = 0.5

        self.targets_fx = set()
        self.targets_layer = set()
        if create_stream:
            self._open_stream(device)

    def _open_stream(self, device=None):
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            callback=self.audio_callback,
            device=device,
        )
        self.device = device

    def start(self):
        if self.stream is None:
            self._open_stream(self.device)
        if not self.stream.active:
            self.stream.start()
        self.running = True

    def stop(self):
        self.running = False
        stream = self.stream
        self.stream = None
        if stream is None:
            return
        try:
            if stream.active:
                stream.stop()
        except Exception as error:  # noqa: BLE001 - bezpieczne zamykanie PortAudio
            print(f"Błąd zatrzymywania strumienia audio: {error}")
        try:
            stream.close()
        except Exception as error:  # noqa: BLE001 - bezpieczne zamykanie PortAudio
            print(f"Błąd zamykania strumienia audio: {error}")

    def change_output_device(self, device):
        old_device = self.device
        was_running = self.running
        self.stop()
        try:
            self._open_stream(device)
            if was_running:
                self.start()
        except Exception:
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception as close_error:  # noqa: BLE001 - backend PortAudio
                    print(f"Błąd zamykania nieudanego strumienia: {close_error}")
                self.stream = None
            self._open_stream(old_device)
            if was_running:
                self.start()
            raise

    def set_vol(self, value):
        self.vol = _clamp(value, 0.0, 1.0, "głośność")

    def restore_values(self, values):
        if not isinstance(values, dict):
            raise TypeError("Wartości syntezatora muszą być słownikiem")
        with self.lock:
            for key, raw_value in values.items():
                if key not in self.values:
                    continue
                minimum = 0.0
                maximum = 1.0
                if key in {"main_a", "layer_a"} or (
                    key.endswith("_a") and key[:-2] in LAYER_TYPES
                ):
                    minimum = 0.01
                    maximum = 0.99
                self.values[key] = _clamp(
                    raw_value, minimum, maximum, f"parametr {key}"
                )
            self._update_oscillators()

    # Publiczne aliasy utrzymują zgodność projektów i skryptów od v5 do v14.
    set_volume = set_vol

    @property
    def volume(self):
        return self.vol

    @volume.setter
    def volume(self, value):
        self.set_vol(value)

    @property
    def knob_a(self):
        return self.values["main_a"]

    @knob_a.setter
    def knob_a(self, value):
        self.set_knob_a(value)

    @property
    def knob_b(self):
        return self.values["main_b"]

    @knob_b.setter
    def knob_b(self, value):
        self.set_knob_b(value)

    @property
    def layer_knob_a(self):
        return self.values["layer_a"]

    @layer_knob_a.setter
    def layer_knob_a(self, value):
        self.set_layer_knob("a", value)

    @property
    def layer_knob_b(self):
        return self.values["layer_b"]

    @layer_knob_b.setter
    def layer_knob_b(self, value):
        self.set_layer_knob("b", value)

    @property
    def fx_param_a(self):
        return self.get_fx_val("a")

    @fx_param_a.setter
    def fx_param_a(self, value):
        self.set_fx_knob("a", value)

    @property
    def fx_param_b(self):
        return self.get_fx_val("b")

    @fx_param_b.setter
    def fx_param_b(self, value):
        self.set_fx_knob("b", value)

    @property
    def active_layers(self):
        return self.layers

    @active_layers.setter
    def active_layers(self, value):
        self.layers = set(value)

    @property
    def active_fx(self):
        return self.fx

    @active_fx.setter
    def active_fx(self, value):
        self.fx = set(value)

    @property
    def active_oscillators(self):
        return self.oscs

    @property
    def one_shots(self):
        return self.shots

    @property
    def sustain_enabled(self):
        return self.sus

    @sustain_enabled.setter
    def sustain_enabled(self, value):
        self.sus = bool(value)

    @property
    def glide_enabled(self):
        return self.glide

    @glide_enabled.setter
    def glide_enabled(self, value):
        self.glide = bool(value)

    @property
    def fix_release(self):
        return self.fix_rel

    @fix_release.setter
    def fix_release(self, value):
        self.fix_rel = bool(value)

    @property
    def current_layer(self):
        return min(self.layers) if self.layers else "none"

    @current_layer.setter
    def current_layer(self, value):
        self.layers = set() if value in {None, "none"} else {value}

    @property
    def current_fx(self):
        return min(self.fx) if self.fx else None

    @current_fx.setter
    def current_fx(self, value):
        self.fx = set() if value is None else {value}

    def set_knob_a(self, value):
        self.values["main_a"] = _clamp(
            value, 0.01, 0.99, "gałka instrumentu A"
        )
        self._update_oscillators()

    def set_knob_b(self, value):
        self.values["main_b"] = _clamp(
            value, 0.0, 1.0, "gałka instrumentu B"
        )
        self._update_oscillators()

    def set_layer_knob(self, parameter, value):
        if parameter not in {"a", "b"}:
            raise ValueError("Parametr warstw musi mieć nazwę 'a' albo 'b'")
        minimum = 0.01 if parameter == "a" else 0.0
        maximum = 0.99 if parameter == "a" else 1.0
        value = _clamp(value, minimum, maximum, f"gałka warstw {parameter}")
        targets = self.targets_layer or self.layers or set(LAYER_TYPES)
        with self.lock:
            if not self.targets_layer:
                self.values[f"layer_{parameter}"] = value
            for target in targets:
                self.values[f"{target}_{parameter}"] = value
            self._update_oscillators()

    def set_layer_knob_a(self, value):
        self.set_layer_knob("a", value)

    def set_layer_knob_b(self, value):
        self.set_layer_knob("b", value)

    def set_fx_knob(self, parameter, value):
        if parameter not in {"a", "b"}:
            raise ValueError("Parametr efektów musi mieć nazwę 'a' albo 'b'")
        value = _clamp(value, 0.0, 1.0, f"gałka efektów {parameter}")
        targets = self.targets_fx or self.fx or set(EFFECT_TYPES)
        with self.lock:
            self.values[f"fx_{parameter}"] = value
            for target in targets:
                self.values[f"{target}_{parameter}"] = value

    def set_fx_a(self, value):
        self.set_fx_knob("a", value)

    def set_fx_b(self, value):
        self.set_fx_knob("b", value)

    def get_layer_val(self, parameter):
        target = min(self.targets_layer) if self.targets_layer else "layer"
        return self.values.get(f"{target}_{parameter}", 0.5)

    def get_fx_val(self, parameter):
        targets = self.targets_fx or self.fx
        target = min(targets) if targets else "fx"
        return self.values.get(f"{target}_{parameter}", 0.5)

    def _update_oscillators(self):
        with self.lock:
            for oscillator in self.oscs.values():
                oscillator.params.update(self.values)

    # Zachowana nazwa z wcześniejszych wersji i plików konfiguracyjnych.
    _upd = _update_oscillators

    def trigger_drum(self, drum_type, params=None):
        parameter_a, parameter_b = (
            params
            if params is not None
            else (self.values["main_a"], self.values["main_b"])
        )
        with self.lock:
            self.shots.append(
                OneShot(
                    drum_type,
                    SAMPLE_RATE,
                    parameter_a,
                    parameter_b,
                )
            )

    # Alias naprawia zgodność z interfejsem v14.1.
    trig_drum = trigger_drum

    def note_on(self, key, frequency, waveform="square", velocity=1.0):
        frequency = float(frequency)
        if not np.isfinite(frequency) or frequency <= 0:
            raise ValueError("Częstotliwość nuty musi być dodatnia i skończona")
        velocity = _clamp(velocity, 0.0, 1.0, "velocity")
        if waveform == "drum_kit":
            note_number = key[1] if isinstance(key, tuple) else int(key)
            drum_types = (
                "kick",
                "snare",
                "hihat",
                "tom",
                "clap",
                "cowbell",
                "crash",
                "laser",
            )
            self.trigger_drum(drum_types[note_number % len(drum_types)])
            return

        with self.lock:
            start_frequency = (
                self.last_freq
                if self.glide and self.last_freq is not None
                else frequency
            )
            self.last_freq = frequency
            oscillator = Oscillator(
                frequency,
                start_frequency,
                waveform,
                self.layers.copy(),
            )
            oscillator.params.update(self.values)
            oscillator.sustain = self.sus
            oscillator.fix_rel = self.fix_rel
            oscillator.volume = 0.5 * velocity
            oscillator.playing = True
            self.oscs[key] = oscillator

    def note_off(self, key):
        with self.lock:
            oscillator = self.oscs.get(key)
            if oscillator is not None:
                oscillator.releasing = True

    def all_notes_off(self, immediate=False):
        with self.lock:
            if immediate:
                self.oscs.clear()
                self.shots.clear()
                self.delay_buffer.fill(0.0)
                self.delay_index = 0
                self.last_freq = None
                self.fx_time = 0.0
                return
            for oscillator in self.oscs.values():
                oscillator.releasing = True

    def audio_callback(self, output, frame_count, time_info, status):
        if status:
            print(f"Audio: {status}")
        output[:] = self.generate_block(frame_count).reshape(-1, 1)

    # Zachowana skrócona nazwa z v14.1.
    cb = audio_callback

    def generate_block(self, sample_count):
        sample_count = int(sample_count)
        if sample_count <= 0:
            return np.zeros(0, dtype=np.float32)
        mix = np.zeros(sample_count, dtype=np.float32)
        with self.lock:
            active_oscillators = {}
            for key, oscillator in self.oscs.items():
                mix += oscillator.get_samples(sample_count)
                if oscillator.playing or oscillator.releasing:
                    active_oscillators[key] = oscillator
            self.oscs = active_oscillators

            active_shots = []
            for shot in self.shots:
                mix += shot.get_samples(sample_count)
                if not shot.finished:
                    active_shots.append(shot)
            self.shots = active_shots
            if self.fx:
                mix = self._apply_effects(mix)
            self.fx_time += sample_count / SAMPLE_RATE
        return np.clip(mix * self.vol, -1.0, 1.0).astype(np.float32)

    # Zachowana skrócona nazwa z v14.1.
    gen = generate_block

    def _apply_effects(self, mix):
        sample_count = len(mix)
        time_axis = np.arange(sample_count) / SAMPLE_RATE + self.fx_time
        chain = (
            "noiz",
            "fuzz",
            "dist",
            "crush",
            "deci",
            "ring",
            "trem",
            "chop",
            "side",
            "lpf",
            "hpf",
            "verb",
            "glit",
        )
        for effect in chain:
            if effect not in self.fx:
                continue
            parameter_a = self.values.get(f"{effect}_a", 0.5)
            parameter_b = self.values.get(f"{effect}_b", 0.5)
            if effect == "lpf":
                width = min(
                    sample_count,
                    max(2, int(10 - parameter_a * 8)),
                )
                kernel = np.ones(width) / width
                filtered = np.convolve(mix, kernel, mode="same")
                mix = mix * (1.0 - parameter_b) + filtered * parameter_b
            elif effect == "verb":
                delay = int(SAMPLE_RATE * 0.1)
                indexes = (
                    np.arange(sample_count) + self.delay_index
                ) % len(self.delay_buffer)
                delayed = self.delay_buffer[
                    (indexes - delay) % len(self.delay_buffer)
                ]
                dry = mix
                mix = dry * (1.0 - parameter_a) + delayed * parameter_a
                self.delay_buffer[indexes] = dry + delayed * (
                    0.1 + parameter_b * 0.85
                )
                self.delay_index = (
                    self.delay_index + sample_count
                ) % len(self.delay_buffer)
            elif effect == "hpf":
                width = min(5, sample_count)
                smooth = np.convolve(
                    mix, np.ones(width) / width, mode="same"
                )
                filtered = (mix - smooth * parameter_a) * (
                    0.5 + parameter_a * 1.5
                )
                mix = mix * (1.0 - parameter_b) + filtered * parameter_b
            elif effect == "crush":
                resolution = 1.5 + parameter_a * 20.0
                crushed = np.round(mix * resolution) / resolution
                mix = mix * (1.0 - parameter_b) + crushed * parameter_b
            elif effect == "dist":
                distorted = np.tanh(mix * (1.0 + parameter_a * 49.0))
                mix = mix * (1.0 - parameter_b) + distorted * parameter_b
            elif effect == "chop":
                rate = 2.0 + parameter_a * 28.0
                gate = np.maximum(
                    0, np.sign(np.sin(2 * np.pi * rate * time_axis))
                )
                mix *= (1.0 - parameter_b) + parameter_b * gate
            elif effect == "side":
                rate = 1.0 + parameter_a * 9.0
                envelope = (time_axis * rate) % 1.0
                mix *= (1.0 - parameter_b) + parameter_b * envelope
            elif effect == "trem":
                rate = 1.0 + parameter_a * 15.0
                depth = parameter_b
                modulation = (1.0 - depth) + depth * (
                    0.5 + 0.5 * np.sin(2 * np.pi * rate * time_axis)
                )
                mix *= modulation
            elif effect == "ring":
                frequency = 50.0 + parameter_a * 1_000.0
                ringed = mix * np.sin(2 * np.pi * frequency * time_axis)
                mix = mix * (1.0 - parameter_b) + ringed * parameter_b
            elif effect == "deci":
                hold = int(2 + parameter_a * 20)
                usable = len(mix) - len(mix) % hold
                decimated = mix.copy()
                held = decimated[:usable].reshape(-1, hold)[:, 0].repeat(hold)
                decimated[: len(held)] = held
                mix = mix * (1.0 - parameter_b) + decimated * parameter_b
            elif effect == "fuzz":
                gain = 5.0 + parameter_a * 95.0
                fuzzed = np.clip(mix * gain, -0.8, 0.8)
                mix = mix * (1.0 - parameter_b) + fuzzed * parameter_b
            elif effect == "glit":
                chunks = int(2 + parameter_a * 30)
                usable = len(mix) - len(mix) % chunks
                if usable:
                    glitched = mix.copy()
                    shuffled = glitched[:usable].reshape(chunks, -1).copy()
                    np.random.shuffle(shuffled)
                    glitched[:usable] = shuffled.flatten()
                    mix = mix * (1.0 - parameter_b) + glitched * parameter_b
            elif effect == "noiz":
                volume = parameter_a * parameter_b * 0.5
                mix += np.random.uniform(-volume, volume, len(mix))
        return mix

    def apply_all_fx(self, audio, frames=None):
        with self.lock:
            return self._apply_effects(
                np.asarray(audio, dtype=np.float32).copy()
            )

    apply_fx = apply_all_fx

    def _offline_copy(self):
        offline = Synthesizer(create_stream=False)
        with self.lock:
            offline.glide = self.glide
            offline.sus = self.sus
            offline.fix_rel = self.fix_rel
            offline.fx = self.fx.copy()
            offline.layers = self.layers.copy()
            offline.vol = self.vol
            offline.values.update(self.values)
            offline.targets_fx = self.targets_fx.copy()
            offline.targets_layer = self.targets_layer.copy()
        return offline

    def render_to_wav(self, filename, melody_track, drum_tracks, bpm, loops=4):
        bpm = float(bpm)
        loops = int(loops)
        if not np.isfinite(bpm) or bpm <= 0 or loops <= 0:
            raise ValueError("BPM i liczba pętli muszą być dodatnie")

        renderer = self._offline_copy()
        loop_seconds = 60.0 / bpm * 4
        total_samples = int(loop_seconds * loops * SAMPLE_RATE)
        output = np.zeros(total_samples, dtype=np.float32)
        events = []
        step_seconds = 60.0 / bpm / 4.0

        for loop_index in range(loops):
            loop_offset = loop_index * loop_seconds
            for step in range(16):
                for instrument, pattern in drum_tracks.items():
                    if step < len(pattern) and pattern[step]:
                        events.append(
                            (
                                int((loop_offset + step * step_seconds) * SAMPLE_RATE),
                                "drum",
                                instrument,
                            )
                        )
            for event in melody_track:
                event_time = float(event.get("time", 0.0)) / 1_000.0
                events.append(
                    (
                        int((loop_offset + event_time) * SAMPLE_RATE),
                        event.get("type"),
                        event.get("note"),
                    )
                )

        events.sort(key=lambda event: event[0])
        event_index = 0
        block_size = BLOCK_SIZE
        for block_start in range(0, total_samples, block_size):
            block_end = min(block_start + block_size, total_samples)
            cursor = block_start
            while event_index < len(events) and events[event_index][0] < block_end:
                event_sample, event_type, payload = events[event_index]
                event_sample = max(cursor, event_sample)
                if event_sample > cursor:
                    output[cursor:event_sample] = renderer.generate_block(
                        event_sample - cursor
                    )
                    cursor = event_sample
                if event_type == "drum":
                    renderer.trigger_drum(payload)
                elif event_type == "note_on" and payload:
                    renderer.note_on(
                        payload["key"],
                        payload["freq"],
                        payload["wave"],
                        payload.get("velocity", 1.0),
                    )
                elif event_type == "note_off" and payload:
                    renderer.note_off(payload["key"])
                event_index += 1
            if cursor < block_end:
                output[cursor:block_end] = renderer.generate_block(block_end - cursor)

        peak = float(np.max(np.abs(output))) if len(output) else 0.0
        if peak > 0:
            output = output / peak
        wavfile.write(filename, SAMPLE_RATE, np.int16(output * 32_767))
