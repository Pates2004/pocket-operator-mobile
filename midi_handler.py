import threading

try:
    import mido

    MIDI_LIB_PRESENT = True
except ImportError:
    mido = None
    MIDI_LIB_PRESENT = False


class MidiInputHandler:
    def __init__(
        self,
        synth_instance,
        waveform_callback=None,
        event_callback=None,
        mapper=None,
    ):
        self.synth = synth_instance
        self.waveform_callback = waveform_callback
        self.event_callback = event_callback
        self.mapper = mapper
        self.input_port = None
        self.running = False
        self.listen_thread = None
        self.current_port_name = None
        self.sustain_pedal = False
        self.deferred_note_offs = set()
        self.active_notes = set()
        self.sustain_channels = set()
        self.last_error = ""
        self.stop_event = threading.Event()

    def get_ports(self):
        if not MIDI_LIB_PRESENT:
            return []
        try:
            return list(mido.get_input_names())
        except Exception as error:  # noqa: BLE001 - MIDI backend depends on external drivers
            print(f"Błąd odczytu portów MIDI: {error}")
            return []

    def open_port(self, port_name=None):
        if not MIDI_LIB_PRESENT:
            return False

        self.stop()
        ports = self.get_ports()
        if not ports:
            return False

        if port_name and port_name not in ports:
            self.last_error = f"MIDI port unavailable: {port_name}"
            return False
        target_name = port_name or ports[0]
        try:
            self.input_port = mido.open_input(target_name)
            self.current_port_name = target_name
            self.last_error = ""
            self.running = True
            self.stop_event = threading.Event()
            self.listen_thread = threading.Thread(
                target=self._listen_loop,
                args=(self.input_port, self.stop_event),
                name="PocketOperatorMIDI",
                daemon=True,
            )
            self.listen_thread.start()
            print(f"Otwarto port MIDI: {target_name}")
            return True
        except Exception as error:  # noqa: BLE001 - MIDI backend depends on external drivers
            self.last_error = str(error)
            print(f"Błąd otwierania portu MIDI {target_name}: {error}")
            self.input_port = None
            self.current_port_name = None
            return False

    def _handle_message(self, message):
        channel = getattr(message, "channel", 0)
        note_key = None
        if message.type in {"note_on", "note_off"}:
            note_key = message.note if channel == 0 else ("midi", channel, message.note)
        if self.mapper and self.mapper.process(message):
            if note_key in self.active_notes and (
                message.type == "note_off"
                or (message.type == "note_on" and message.velocity == 0)
            ):
                self._release_note(note_key)
            return
        if message.type == "note_on" and message.velocity > 0:
            frequency = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            waveform = self.waveform_callback() if self.waveform_callback else "square"
            velocity = max(0.0, min(1.0, message.velocity / 127.0))
            self.deferred_note_offs.discard(note_key)
            self.active_notes.add(note_key)
            self.synth.note_on(note_key, frequency, waveform, velocity)
            if self.event_callback:
                self.event_callback(
                    "note_on",
                    {
                        "key": note_key,
                        "freq": frequency,
                        "wave": waveform,
                        "velocity": velocity,
                    },
                )
        elif message.type == "note_off" or (
            message.type == "note_on" and message.velocity == 0
        ):
            if channel in self.sustain_channels:
                self.deferred_note_offs.add(note_key)
            else:
                self._release_note(note_key)
        elif message.type == "control_change" and message.control == 64:
            pedal_down = message.value >= 64
            if channel in self.sustain_channels and not pedal_down:
                for note in tuple(self.deferred_note_offs):
                    if self._channel_of(note) == channel:
                        self._release_note(note)
                        self.deferred_note_offs.discard(note)
            if pedal_down:
                self.sustain_channels.add(channel)
            else:
                self.sustain_channels.discard(channel)
            self.sustain_pedal = 0 in self.sustain_channels
        elif message.type == "control_change" and message.control in {120, 123}:
            for note in tuple(self.active_notes):
                if self._channel_of(note) == channel:
                    self._release_note(note)
                    self.deferred_note_offs.discard(note)
                    if message.control == 120 and hasattr(self.synth, "silence_note"):
                        self.synth.silence_note(note)

    @staticmethod
    def _channel_of(note):
        return note[1] if isinstance(note, tuple) and note[0] == "midi" else 0

    def _release_note(self, note):
        self.synth.note_off(note)
        self.active_notes.discard(note)
        if self.event_callback:
            self.event_callback("note_off", {"key": note})

    def panic(self, immediate=True):
        for note in tuple(self.active_notes):
            self._release_note(note)
        self.deferred_note_offs.clear()
        self.sustain_pedal = False
        self.sustain_channels.clear()
        self.synth.all_notes_off(immediate=immediate)

    def reset_controls(self):
        for note in tuple(self.deferred_note_offs):
            self._release_note(note)
        self.deferred_note_offs.clear()
        self.sustain_channels.clear()
        self.sustain_pedal = False
        if hasattr(self.synth, "reset_pitch_bend"):
            self.synth.reset_pitch_bend()

    def _listen_loop(self, port, stop_event):
        while not stop_event.is_set():
            try:
                for message in port.iter_pending():
                    if stop_event.is_set():
                        break
                    self._handle_message(message)
            except Exception as error:  # noqa: BLE001 - keep the listener alive after backend errors
                print(f"Błąd odczytu MIDI: {error}")
            stop_event.wait(0.001)

    def stop(self):
        self.running = False
        self.stop_event.set()
        port = self.input_port
        self.input_port = None
        thread = self.listen_thread
        self.listen_thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        for note in tuple(self.active_notes):
            self._release_note(note)
        if port:
            try:
                port.close()
            except Exception as error:  # noqa: BLE001 - best-effort device shutdown
                print(f"Błąd zamykania portu MIDI: {error}")
        self.sustain_pedal = False
        self.sustain_channels.clear()
        self.deferred_note_offs.clear()
        self.active_notes.clear()
        self.current_port_name = None
        self.reset_controls()
