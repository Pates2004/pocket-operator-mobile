"""Source-specific spoken change feedback with bounded MIDI chatter."""

import time
from contextlib import contextmanager


class ChangeFeedback:
    def __init__(self, speak, schedule, clock=time.monotonic):
        self.speak = speak
        self.schedule = schedule
        self.clock = clock
        self.enabled = {"keyboard": True, "midi": True}
        self._source = "keyboard"
        self._continuous = False
        self._last_spoken = float("-inf")
        self._pending = None
        self._timer = None
        self._closed = False

    @property
    def source(self):
        return self._source

    @contextmanager
    def using_source(self, source, *, continuous=False):
        if source not in self.enabled:
            raise ValueError("Unknown feedback source")
        previous = self._source, self._continuous
        self._source, self._continuous = source, continuous
        try:
            yield
        finally:
            self._source, self._continuous = previous

    def set_enabled(self, source, enabled):
        if source not in self.enabled:
            raise ValueError("Unknown feedback source")
        self.enabled[source] = bool(enabled)
        if self._pending and self._pending[0] == source and not enabled:
            self.cancel_pending()

    def announce(self, text, *, continuous=None):
        source = self._source
        if continuous is None:
            continuous = self._continuous
        if self._closed or not self.enabled[source]:
            return
        if not continuous or source != "midi":
            self.cancel_pending()
            self._say(source, text)
            return
        self.cancel_pending()
        if self.clock() - self._last_spoken >= 0.7:
            self._say(source, text)
        else:
            self._pending = (source, text)
            self._timer = self.schedule(220, self.flush)

    def _say(self, source, text):
        self._last_spoken = self.clock()
        self.speak(text)

    def flush(self):
        pending = self._pending
        self._pending = None
        if self._timer is not None:
            self._timer.Stop()
        self._timer = None
        if pending and not self._closed and self.enabled[pending[0]]:
            self._say(*pending)

    def cancel_pending(self):
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None
        self._pending = None

    def close(self):
        self.cancel_pending()
        self._closed = True
