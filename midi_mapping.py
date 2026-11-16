"""Validated MIDI bindings, device profiles and relative encoder decoding."""

import copy
import math
import threading

import synth

MODES = (
    "absolute",
    "relative_twos",
    "relative_offset",
    "relative_sign",
    "button",
    "momentary",
)
CONTINUOUS_ACTIONS = {
    "main_a",
    "main_b",
    "layer_a",
    "layer_b",
    "fx_a",
    "fx_b",
    "volume",
    "bpm",
}
BUTTON_ACTIONS = {
    "play",
    "stop",
    "record",
    "play_toggle",
    "panic",
    "octave_up",
    "octave_down",
    "wave_next",
    "sustain",
    "glide",
    "chord",
}
for _layer in synth.LAYER_TYPES:
    BUTTON_ACTIONS.add(f"layer:{_layer}")
    CONTINUOUS_ACTIONS.update({f"layer:{_layer}:a", f"layer:{_layer}:b"})
for _effect in synth.EFFECT_TYPES:
    BUTTON_ACTIONS.add(f"effect:{_effect}")
    CONTINUOUS_ACTIONS.update({f"effect:{_effect}:a", f"effect:{_effect}:b"})
for _drum in ("kick", "snare", "hihat", "tom", "clap", "cowbell", "crash", "laser"):
    BUTTON_ACTIONS.add(f"drum:{_drum}")
ACTIONS = CONTINUOUS_ACTIONS | BUTTON_ACTIONS


def source_of(message):
    kind = message.type
    channel = getattr(message, "channel", None)
    if kind == "control_change":
        return ("cc", channel, message.control), message.value
    if kind in {"note_on", "note_off"}:
        value = message.velocity if kind == "note_on" else 0
        return ("note", channel, message.note), value
    if kind == "program_change":
        return ("program", channel, message.program), 127
    if kind == "pitchwheel":
        return ("pitch", channel, 0), message.pitch + 8192
    if kind == "aftertouch":
        return ("pressure", channel, 0), message.value
    if kind in {"start", "continue", "stop"}:
        return (kind, None, 0), 127
    if kind == "sysex":
        data = tuple(message.data)
        if len(data) == 4 and data[0] == 127 and data[2] == 6:
            return ("mmc", None, data[3]), 127
    return None


def validate_binding(raw):
    if not isinstance(raw, dict):
        raise TypeError("MIDI binding must be an object")
    binding = copy.deepcopy(raw)
    kind = binding.get("type")
    if kind not in {
        "cc",
        "note",
        "program",
        "pitch",
        "pressure",
        "start",
        "continue",
        "stop",
        "mmc",
    }:
        raise ValueError("Unsupported MIDI message type")
    channel = binding.get("channel")
    if channel is not None and (type(channel) is not int or not 0 <= channel <= 15):
        raise ValueError("MIDI channel must be 0..15 or null")
    number = binding.get("number", 0)
    if type(number) is not int or not 0 <= number <= 127:
        raise ValueError("MIDI number must be 0..127")
    mode, action = binding.get("mode", "absolute"), binding.get("action")
    if mode not in MODES or action not in ACTIONS:
        raise ValueError("Unsupported MIDI action or mode")
    if action in BUTTON_ACTIONS and mode not in {"button", "momentary"}:
        raise ValueError("Button actions require button or momentary mode")
    if mode == "momentary" and not action.startswith(("effect:", "layer:")):
        raise ValueError("Momentary mode is for layers and effects")
    if action in CONTINUOUS_ACTIONS and mode in {"button", "momentary"}:
        raise ValueError("Continuous actions require an encoder mode")
    step = float(binding.get("step", 0.01))
    if not math.isfinite(step) or not 0 < step <= 1:
        raise ValueError("MIDI step must be greater than zero and at most one")
    return {
        "type": kind,
        "channel": channel,
        "number": number,
        "mode": mode,
        "action": action,
        "step": step,
        "invert": bool(binding.get("invert", False)),
    }


def binding(source, action, mode="absolute", channel=None):
    kind, number = source
    return validate_binding(
        {
            "type": kind,
            "number": number,
            "channel": channel,
            "action": action,
            "mode": mode,
        }
    )


def profile(name):
    if name == "akm322":
        return [
            binding(("cc", 10), "main_a"),
            binding(("cc", 21), "main_b"),
            binding(("cc", 22), "layer_a"),
            binding(("cc", 23), "fx_a"),
            binding(("cc", 1), "fx_b"),
            binding(("cc", 7), "volume"),
            binding(("mmc", 2), "play", "button"),
            binding(("mmc", 1), "stop", "button"),
            binding(("mmc", 6), "record", "button"),
        ]
    if name not in {"generic", "ni_relative", "ni_offset"}:
        raise ValueError("Unknown MIDI profile")
    mode = {
        "generic": "absolute",
        "ni_relative": "relative_twos",
        "ni_offset": "relative_offset",
    }[name]
    result = [
        binding(("cc", number), action, mode)
        for number, action in zip(
            range(14, 22),
            ("main_a", "main_b", "layer_a", "layer_b", "fx_a", "fx_b", "volume", "bpm"),
            strict=True,
        )
    ]
    result.extend(
        [
            binding(("start", 0), "play", "button"),
            binding(("continue", 0), "play", "button"),
            binding(("stop", 0), "stop", "button"),
        ]
    )
    return result


def relative_delta(value, mode):
    if mode == "relative_twos":
        return value if value < 64 else value - 128
    if mode == "relative_offset":
        return value - 64
    if mode == "relative_sign":
        return -(value - 64) if value >= 64 else value
    raise ValueError("Unknown relative mode")


class MidiMapper:
    def __init__(self, dispatch):
        self.dispatch = dispatch
        self.bindings = []
        self.monitor = None
        self.learn_callback = None
        self.lock = threading.RLock()
        self._pressed = set()

    def export_state(self):
        with self.lock:
            return copy.deepcopy(self.bindings)

    def import_state(self, state):
        if not isinstance(state, list) or len(state) > 512:
            raise ValueError("MIDI bindings must be a list of at most 512 entries")
        normalized = [validate_binding(item) for item in state]
        identities = [
            (item["type"], item["channel"], item["number"]) for item in normalized
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate MIDI source")
        with self.lock:
            self.bindings = normalized
            self._pressed.clear()

    def add(self, item):
        item = validate_binding(item)
        identity = (item["type"], item["channel"], item["number"])
        with self.lock:
            updated = [
                entry
                for entry in self.bindings
                if (entry["type"], entry["channel"], entry["number"]) != identity
            ]
            self.import_state([*updated, item])

    def process(self, message):
        decoded = source_of(message)
        if decoded is None:
            return False
        source, value = decoded
        if self.monitor:
            self.monitor(source, value)
        with self.lock:
            if self.learn_callback:
                if source[0] == "note" and value == 0:
                    return True
                callback, self.learn_callback = self.learn_callback, None
                callback(source)
                return True
            matches = [
                item
                for item in self.bindings
                if (
                    item["type"] == source[0]
                    and item["number"] == source[2]
                    and item["channel"] in {None, source[1]}
                )
            ]
            if not matches:
                return False
            item = next(
                (entry for entry in matches if entry["channel"] == source[1]),
                matches[0],
            )
            mode = item["mode"]
            if mode in {"button", "momentary"}:
                pressed = value > 0
                # Stateless messages (MMC/PC/realtime) are complete button pulses.
                pulse = source[0] in {"mmc", "program", "start", "continue", "stop"}
                was_pressed = source in self._pressed
                if pressed and not pulse:
                    self._pressed.add(source)
                else:
                    self._pressed.discard(source)
                if mode == "momentary" or (pressed and (pulse or not was_pressed)):
                    self.dispatch(
                        item["action"],
                        "gate" if mode == "momentary" else "trigger",
                        float(pressed),
                    )
            elif mode == "absolute":
                maximum = 16383 if source[0] == "pitch" else 127
                normalized = value / maximum
                self.dispatch(
                    item["action"],
                    "absolute",
                    1 - normalized if item["invert"] else normalized,
                )
            else:
                delta = relative_delta(value, mode) * item["step"]
                if item["invert"]:
                    delta = -delta
                if delta:
                    self.dispatch(item["action"], "relative", delta)
        return True
