import threading
import time

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
    ):
        self.synth = synth_instance
        self.waveform_callback = waveform_callback
        self.event_callback = event_callback
        self.input_port = None
        self.running = False
        self.listen_thread = None
        self.current_port_name = None
        self.sustain_pedal = False
        self.deferred_note_offs = set()
        self.active_notes = set()

    def get_ports(self):
        if not MIDI_LIB_PRESENT:
            return []
        try:
            return list(mido.get_input_names())
        except Exception as error:  # noqa: BLE001 - backend MIDI zależy od sterownika
            print(f"Błąd odczytu portów MIDI: {error}")
            return []

    def open_port(self, port_name=None):
        if not MIDI_LIB_PRESENT:
            return False

        self.stop()
        ports = self.get_ports()
        if not ports:
            return False

        target_name = port_name if port_name in ports else ports[0]
        try:
            self.input_port = mido.open_input(target_name)
            self.current_port_name = target_name
            self.running = True
            self.listen_thread = threading.Thread(
                target=self._listen_loop,
                name="PocketOperatorMIDI",
                daemon=True,
            )
            self.listen_thread.start()
            print(f"Otwarto port MIDI: {target_name}")
            return True
        except Exception as error:  # noqa: BLE001 - backend MIDI zależy od sterownika
            print(f"Błąd otwierania portu MIDI {target_name}: {error}")
            self.input_port = None
            self.current_port_name = None
            return False

    def _handle_message(self, message):
        if message.type == "note_on" and message.velocity > 0:
            frequency = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            waveform = (
                self.waveform_callback() if self.waveform_callback else "square"
            )
            velocity = max(0.0, min(1.0, message.velocity / 127.0))
            self.deferred_note_offs.discard(message.note)
            self.active_notes.add(message.note)
            self.synth.note_on(message.note, frequency, waveform, velocity)
            if self.event_callback:
                self.event_callback(
                    "note_on",
                    {
                        "key": message.note,
                        "freq": frequency,
                        "wave": waveform,
                        "velocity": velocity,
                    },
                )
        elif message.type == "note_off" or (
            message.type == "note_on" and message.velocity == 0
        ):
            if self.sustain_pedal:
                self.deferred_note_offs.add(message.note)
            else:
                self._release_note(message.note)
        elif message.type == "control_change" and message.control == 64:
            pedal_down = message.value >= 64
            if self.sustain_pedal and not pedal_down:
                for note in tuple(self.deferred_note_offs):
                    self._release_note(note)
                self.deferred_note_offs.clear()
            self.sustain_pedal = pedal_down
        elif message.type == "control_change" and message.control in {120, 123}:
            self.deferred_note_offs.clear()
            for note in tuple(self.active_notes):
                self._release_note(note)
            self.synth.all_notes_off(immediate=message.control == 120)

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
        self.synth.all_notes_off(immediate=immediate)

    def _listen_loop(self):
        while self.running and self.input_port:
            try:
                for message in self.input_port.iter_pending():
                    self._handle_message(message)
            except Exception as error:  # noqa: BLE001 - wątek nie może zakończyć aplikacji
                print(f"Błąd odczytu MIDI: {error}")
            time.sleep(0.001)

    def stop(self):
        self.running = False
        for note in tuple(self.active_notes):
            self._release_note(note)
        port = self.input_port
        self.input_port = None
        if port:
            try:
                port.close()
            except Exception as error:  # noqa: BLE001 - bezpieczne zamykanie urządzenia
                print(f"Błąd zamykania portu MIDI: {error}")
        thread = self.listen_thread
        self.listen_thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=0.25)
        self.sustain_pedal = False
        self.deferred_note_offs.clear()
        self.active_notes.clear()
        self.current_port_name = None
