import copy
import math
import threading
import time

DRUM_INSTRUMENTS = (
    "kick",
    "snare",
    "hihat",
    "tom",
    "clap",
    "cowbell",
    "crash",
    "laser",
)
NOTE_WAVEFORMS = {"square", "saw", "triangle", "noise", "drum_kit"}


class Sequencer:
    def __init__(self, synth_instance, bpm=120):
        self.synth = synth_instance
        self.bpm = int(bpm)
        if not 20 <= self.bpm <= 300:
            raise ValueError("BPM musi mieścić się w zakresie 20–300")
        self.running = False
        self.recording = False
        self.steps = 16
        self.current_step = 0
        self.drum_tracks = {
            instrument: [False] * self.steps for instrument in DRUM_INSTRUMENTS
        }
        self.melody_track = []
        self.loop_duration_ms = self._loop_duration_ms()
        self.start_time = 0.0
        self.thread = None
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self._event_counter = 0

    def _loop_duration_ms(self):
        return 60.0 / self.bpm * 4 * 1_000

    def toggle_drum(self, instrument, step_index):
        with self.lock:
            if instrument not in self.drum_tracks:
                return False
            if not 0 <= step_index < self.steps:
                return False
            self.drum_tracks[instrument][step_index] = not self.drum_tracks[instrument][
                step_index
            ]
            return self.drum_tracks[instrument][step_index]

    def clear_drums(self):
        with self.lock:
            for instrument in self.drum_tracks:
                self.drum_tracks[instrument] = [False] * self.steps

    def clear_melody(self):
        with self.lock:
            self.melody_track.clear()

    def clear_all(self):
        self.clear_drums()
        self.clear_melody()

    def record_event(self, event_type, note, waveform=None):
        if not self.recording:
            return
        if event_type not in {"note_on", "note_off", "pitch_bend"}:
            raise ValueError(f"Nieobsługiwany typ zdarzenia: {event_type}")

        now = time.monotonic() * 1_000
        with self.lock:
            if not self.start_time:
                self.start_time = now
            elapsed_total = max(0.0, now - self.start_time)
            cycle = int(elapsed_total // self.loop_duration_ms)
            elapsed = elapsed_total % self.loop_duration_ms
            self._event_counter += 1
            event = {
                "time": elapsed,
                "type": event_type,
                "note": copy.deepcopy(note),
                "waveform": waveform,
                "_id": self._event_counter,
                # Live monitoring already played this event in its recording cycle.
                "_skip_cycle": cycle,
            }
            self.melody_track.append(event)
            self.melody_track.sort(key=lambda item: item["time"])

    def set_bpm(self, bpm):
        bpm = int(bpm)
        if not 20 <= bpm <= 300:
            raise ValueError("BPM musi mieścić się w zakresie 20–300")
        with self.lock:
            old_duration = self.loop_duration_ms
            self.bpm = bpm
            self.loop_duration_ms = self._loop_duration_ms()
            if old_duration > 0:
                scale = self.loop_duration_ms / old_duration
                for event in self.melody_track:
                    event["time"] = float(event.get("time", 0.0)) * scale
            if self.running:
                now = time.monotonic() * 1_000
                old_elapsed = max(0.0, now - self.start_time)
                old_cycle = int(old_elapsed // old_duration)
                old_position = old_elapsed % old_duration
                normalized = old_position / old_duration
                self.start_time = now - (old_cycle + normalized) * self.loop_duration_ms

    def play(self):
        with self.lock:
            if self.running:
                return
            # _skip_cycle avoids repeating live monitored events in their recording
            # cycle. Restarting resets the cycle counter to zero, so stale markers
            # must not survive a restart.
            seen_event_ids = set()
            for event in self.melody_track:
                event["_skip_cycle"] = -1
                event_id = event.get("_id")
                if event_id is None or event_id in seen_event_ids:
                    self._event_counter += 1
                    event_id = self._event_counter
                    event["_id"] = event_id
                seen_event_ids.add(event_id)
            self.running = True
            self.current_step = 0
            self.start_time = time.monotonic() * 1_000
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._loop,
                name="PocketOperatorSequencer",
                daemon=True,
            )
            self.thread.start()

    def stop(self):
        with self.lock:
            self.running = False
            self.recording = False
            self.stop_event.set()
            thread = self.thread
            self.thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        if hasattr(self.synth, "all_notes_off"):
            self.synth.all_notes_off()
        if hasattr(self.synth, "reset_pitch_bend"):
            self.synth.reset_pitch_bend()

    def set_recording(self, enabled):
        enabled = bool(enabled)
        if enabled and not self.running:
            self.play()
        self.recording = enabled

    @staticmethod
    def _public_event(event):
        return {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if not key.startswith("_")
        }

    def snapshot(self):
        with self.lock:
            melody = [self._public_event(event) for event in self.melody_track]
            return melody, copy.deepcopy(self.drum_tracks)

    def export_state(self):
        melody, drums = self.snapshot()
        return {
            "bpm": self.bpm,
            "steps": self.steps,
            "melody": melody,
            "drums": drums,
        }

    def import_state(self, state):
        if not isinstance(state, dict):
            raise TypeError("Niepoprawny stan sekwencera")

        raw_drums = state.get("drums", {})
        raw_melody = state.get("melody", [])
        if not isinstance(raw_drums, dict) or not isinstance(raw_melody, list):
            raise TypeError("Niepoprawne ścieżki sekwencera")

        state_bpm = int(state.get("bpm", self.bpm))
        if state_bpm != self.bpm:
            self.set_bpm(state_bpm)

        drums = {}
        for instrument in DRUM_INSTRUMENTS:
            pattern = raw_drums.get(instrument, [False] * self.steps)
            if not isinstance(pattern, list):
                raise TypeError(f"Niepoprawny pattern: {instrument}")
            normalized = [bool(value) for value in pattern[: self.steps]]
            normalized.extend([False] * (self.steps - len(normalized)))
            drums[instrument] = normalized

        melody = []
        for raw_event in raw_melody:
            if not isinstance(raw_event, dict):
                raise TypeError("Zdarzenie melodii musi być słownikiem")
            event_type = raw_event.get("type")
            note = raw_event.get("note")
            if event_type not in {
                "note_on",
                "note_off",
                "pitch_bend",
            } or not isinstance(note, dict):
                raise TypeError("Niepoprawne zdarzenie melodii")
            note = copy.deepcopy(note)
            if isinstance(note.get("key"), list):
                note["key"] = tuple(note["key"])
            if event_type == "pitch_bend":
                channel = note.get("channel")
                semitones = float(note.get("semitones", 0.0))
                if type(channel) is not int or not 0 <= channel <= 15:
                    raise ValueError("MIDI channel must be 0..15")
                if not math.isfinite(semitones) or not -48 <= semitones <= 48:
                    raise ValueError("Invalid recorded Pitch Bend")
                note = {"channel": channel, "semitones": semitones}
            else:
                if "key" not in note:
                    raise ValueError("Zdarzenie melodii nie zawiera klucza nuty")
                try:
                    hash(note["key"])
                except TypeError as error:
                    raise TypeError("Klucz nuty musi być hashowalny") from error

            if event_type == "note_on":
                frequency = float(note.get("freq", 0.0))
                if not math.isfinite(frequency) or frequency <= 0:
                    raise ValueError("Częstotliwość nuty musi być dodatnia")
                waveform = note.get("wave", raw_event.get("waveform"))
                if waveform not in NOTE_WAVEFORMS:
                    raise ValueError("Niepoprawny instrument zdarzenia melodii")
                velocity = float(note.get("velocity", 1.0))
                if not math.isfinite(velocity):
                    raise ValueError("Velocity nuty musi być liczbą skończoną")
                note["freq"] = frequency
                note["wave"] = waveform
                note["velocity"] = max(0.0, min(1.0, velocity))

            event_time = float(raw_event.get("time", 0.0))
            if not math.isfinite(event_time):
                raise ValueError("Czas zdarzenia musi być liczbą skończoną")
            self._event_counter += 1
            melody.append(
                {
                    "time": max(
                        0.0,
                        min(
                            event_time,
                            max(0.0, self.loop_duration_ms - 0.001),
                        ),
                    ),
                    "type": event_type,
                    "note": note,
                    "waveform": raw_event.get("waveform"),
                    "_id": self._event_counter,
                    "_skip_cycle": -1,
                }
            )
        melody.sort(key=lambda item: item["time"])

        with self.lock:
            self.drum_tracks = drums
            self.melody_track = melody
            self.current_step = 0

    def _play_melody_event(self, event):
        note = event.get("note")
        if not note:
            return
        if event.get("type") == "note_on":
            self.synth.note_on(
                note["key"],
                note["freq"],
                note["wave"],
                note.get("velocity", 1.0),
            )
        elif event.get("type") == "note_off":
            self.synth.note_off(note["key"])
        elif event.get("type") == "pitch_bend":
            self.synth.set_pitch_bend(note["semitones"], note["channel"])

    def _loop(self):
        previous_step_token = None
        previous_cycle = -1
        played_event_ids = set()

        while self.running and not self.stop_event.is_set():
            now_ms = time.monotonic() * 1_000
            with self.lock:
                loop_duration = self.loop_duration_ms
                elapsed = max(0.0, now_ms - self.start_time)
                cycle = int(elapsed // loop_duration)
                loop_position = elapsed % loop_duration
                step = min(
                    self.steps - 1,
                    int(loop_position / loop_duration * self.steps),
                )
                step_token = (cycle, step)
                tracks = None
                if step_token != previous_step_token:
                    tracks = {
                        instrument: pattern[step]
                        for instrument, pattern in self.drum_tracks.items()
                    }
                    self.current_step = step
                    previous_step_token = step_token
                if cycle != previous_cycle:
                    played_event_ids.clear()
                    previous_cycle = cycle
                events = list(self.melody_track)

            if tracks:
                for instrument, active in tracks.items():
                    if active:
                        self.synth.trigger_drum(instrument)

            for event in events:
                event_id = event.get("_id")
                if (
                    event_id not in played_event_ids
                    and event.get("_skip_cycle") != cycle
                    and event["time"] <= loop_position
                ):
                    try:
                        self._play_melody_event(event)
                    except (KeyError, TypeError, ValueError) as error:
                        print(f"Pominięto niepoprawne zdarzenie melodii: {error}")
                    played_event_ids.add(event_id)

            self.stop_event.wait(0.001)
