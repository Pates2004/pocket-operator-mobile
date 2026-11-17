"""Keyboard-accessible MIDI mapping editor and one-shot hardware learning."""

import wx

import midi_mapping
import ui_support
from localization import tr


class MidiMappingDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=tr("MIDI mappings"), size=(760, 700))
        self.owner = parent
        self.mapper = parent.mapper
        self._editing_index = None
        self._has_source = False
        self._updating_form = False
        self._apply_timer = None
        self._alive = True
        self._last_monitor = None
        layout = wx.BoxSizer(wx.VERTICAL)
        self.entries = wx.ListBox(self)
        self.entries.SetName(tr("Saved MIDI mappings"))
        layout.Add(self.entries, 1, wx.EXPAND | wx.ALL, 10)
        self.entries.Bind(wx.EVT_LISTBOX, self.on_select)
        grid = wx.FlexGridSizer(cols=2, vgap=7, hgap=10)
        grid.AddGrowableCol(1)

        def row(label, control):
            grid.Add(wx.StaticText(self, label=tr(label)), 0, wx.ALIGN_CENTER_VERTICAL)
            control.SetName(tr(label))
            grid.Add(control, 1, wx.EXPAND)
            return control

        self.types = (
            "cc",
            "note",
            "program",
            "pitch",
            "pressure",
            "mmc",
            "start",
            "continue",
            "stop",
        )
        self.kind = row("Message type", wx.Choice(self, choices=list(self.types)))
        self.kind.SetSelection(0)
        self.channel = row(
            "Channel",
            wx.Choice(self, choices=[tr("Any channel"), *map(str, range(1, 17))]),
        )
        self.channel.SetSelection(0)
        self.number = row(
            "CC / note / program / MMC number", wx.SpinCtrl(self, min=0, max=127)
        )
        self.actions = sorted(midi_mapping.ACTIONS)
        self.action = row(
            "Action", wx.Choice(self, choices=[tr(value) for value in self.actions])
        )
        self.action.SetStringSelection(tr("main_a"))
        self.mode = row(
            "Controller mode",
            wx.Choice(self, choices=[tr(value) for value in midi_mapping.MODES]),
        )
        self.mode.SetSelection(0)
        self.step = row(
            "Relative step (%)",
            wx.SpinCtrlDouble(self, min=0.01, max=100, initial=1, inc=0.5),
        )
        self.invert = row("Reverse direction", wx.CheckBox(self, label=tr("Enabled")))
        self.enabled = row(
            "Assignment enabled", wx.CheckBox(self, label=tr("Assignment enabled"))
        )
        self.enabled.SetValue(True)
        layout.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        self.monitor = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.monitor.SetName(tr("Last MIDI message"))
        layout.Add(self.monitor, 0, wx.EXPAND | wx.ALL, 10)
        self.live_apply = wx.CheckBox(self, label=tr("Apply changes immediately"))
        self.live_apply.SetName(tr("Apply changes immediately"))
        self.live_apply.SetValue(parent.midi_live_apply)
        self.live_apply.Bind(wx.EVT_CHECKBOX, self.on_live_toggle)
        layout.Add(self.live_apply, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls = wx.WrapSizer()
        for label, callback in (
            ("Learn next control", self.on_learn),
            ("Save mapping", self.on_save),
            ("Delete selected mapping", self.on_delete),
            ("Load controller profile", self.on_profile),
        ):
            button = wx.Button(self, label=tr(label))
            button.Bind(wx.EVT_BUTTON, callback)
            controls.Add(button, 0, wx.ALL, 4)
        layout.Add(controls, 0, wx.EXPAND | wx.ALL, 5)
        close = wx.Button(self, wx.ID_CLOSE, tr("Close"))
        close.Bind(wx.EVT_BUTTON, self.on_close)
        layout.Add(close, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizer(layout)
        self.mapper.monitor = self.on_message
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_monitor, self.timer)
        self.timer.Start(100)
        self.refresh_entries()
        for control in (self.kind, self.channel, self.action, self.mode):
            control.Bind(wx.EVT_CHOICE, self.on_field_change)
        for control, spin_event in (
            (self.number, wx.EVT_SPINCTRL),
            (self.step, wx.EVT_SPINCTRLDOUBLE),
        ):
            control.Bind(spin_event, self.on_field_change)
            control.Bind(wx.EVT_TEXT, self.on_field_change)
        for control in (self.invert, self.enabled):
            control.Bind(wx.EVT_CHECKBOX, self.on_field_change)
        ui_support.apply_theme(self)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def refresh_entries(self, selection=None):
        if selection is None:
            selection = self.entries.GetSelection()
        self.entries.Set(
            [
                f"{item['type']} {item['number']} / {tr('Channel')} "
                f"{item['channel'] + 1 if item['channel'] is not None else '*'} → "
                f"{tr(item['action'])} ({tr(item['mode'])})"
                f" — {tr('Enabled') if item['enabled'] else tr('Disabled')}"
                for item in self.mapper.export_state()
            ]
        )
        if self.entries.GetCount() and selection != wx.NOT_FOUND:
            self.entries.SetSelection(min(selection, self.entries.GetCount() - 1))

    def on_select(self, event):
        index = self.entries.GetSelection()
        if index == wx.NOT_FOUND:
            return
        self.flush_pending()
        self.entries.SetSelection(index)
        self._editing_index = index
        self._has_source = True
        item = self.mapper.export_state()[index]
        self._updating_form = True
        try:
            self.load_fields(item)
        finally:
            self._updating_form = False

    def load_fields(self, item):
        self.kind.SetSelection(self.types.index(item["type"]))
        self.channel.SetSelection(
            item["channel"] + 1 if item["channel"] is not None else 0
        )
        self.number.SetValue(item["number"])
        self.action.SetSelection(self.actions.index(item["action"]))
        self.mode.SetSelection(midi_mapping.MODES.index(item["mode"]))
        self.step.SetValue(item["step"] * 100)
        self.invert.SetValue(item["invert"])
        self.enabled.SetValue(item["enabled"])

    def cancel_pending(self):
        if self._apply_timer is not None:
            self._apply_timer.Stop()
            self._apply_timer = None

    def flush_pending(self):
        if self._apply_timer is not None:
            self.cancel_pending()
            self.apply_mapping(report_errors=False, announce=False)

    def on_field_change(self, event):
        event.Skip()
        if (
            self._alive
            and not self._updating_form
            and self.live_apply.GetValue()
            and self._has_source
        ):
            self.cancel_pending()
            self._apply_timer = wx.CallLater(180, self.flush_pending)

    def on_live_toggle(self, event):
        self.cancel_pending()
        previous = self.owner.midi_live_apply
        self.owner.midi_live_apply = self.live_apply.GetValue()
        try:
            self.owner.save_settings()
        except OSError as error:
            self.owner.midi_live_apply = previous
            self.live_apply.SetValue(previous)
            ui_support.message_box(
                str(error), "MIDI mapping error", wx.OK | wx.ICON_ERROR
            )
            return
        if self.live_apply.GetValue() and self._has_source:
            self.apply_mapping(report_errors=False, announce=False)

    def on_message(self, source, value):
        channel = source[1] + 1 if source[1] is not None else "*"
        self._last_monitor = (
            f"{source[0]} / {tr('Channel')} {channel} / {source[2]} = {value}"
        )

    def update_monitor(self, event):
        if self._last_monitor:
            self.monitor.ChangeValue(self._last_monitor)
            self._last_monitor = None

    def on_learn(self, event):
        self.flush_pending()
        self.monitor.ChangeValue(tr("Move a knob or press a MIDI button now."))
        self.owner.speaker.say(tr("Move a knob or press a MIDI button now."))
        self.mapper.learn_callback = lambda source: wx.CallAfter(self.learned, source)

    def learned(self, source):
        if not self._alive:
            return
        kind, channel, number = source
        self.cancel_pending()
        self._editing_index = next(
            (
                index
                for index, item in enumerate(self.mapper.export_state())
                if (item["type"], item["channel"], item["number"]) == source
            ),
            None,
        )
        self._has_source = True
        self._updating_form = True
        self.kind.SetSelection(self.types.index(kind))
        self.channel.SetSelection(channel + 1 if channel is not None else 0)
        self.number.SetValue(number)
        self.enabled.SetValue(True)
        self._updating_form = False
        self.monitor.ChangeValue(
            tr("Control learned. Select its action and mode, then save.")
        )
        self.owner.speaker.say(self.monitor.GetValue())
        self.action.SetFocus()
        if self.live_apply.GetValue():
            self.apply_mapping(report_errors=False, announce=False)

    def on_save(self, event):
        self.cancel_pending()
        self.apply_mapping(report_errors=True, announce=True)

    def apply_mapping(self, *, report_errors, announce):
        try:
            return self.save_mapping(announce=announce)
        except (TypeError, ValueError, OSError) as error:
            if report_errors:
                ui_support.message_box(
                    str(error), "MIDI mapping error", wx.OK | wx.ICON_ERROR
                )
            else:
                self.monitor.ChangeValue(
                    tr("Changes not applied: {error}", error=tr(str(error)))
                )
            return False

    def save_mapping(self, *, announce):
        try:
            number = int(self.number.GetTextValue())
        except ValueError as error:
            raise ValueError("MIDI number must be 0..127") from error
        try:
            step = float(self.step.GetTextValue().replace(",", ".")) / 100
        except ValueError as error:
            raise ValueError(
                "MIDI step must be greater than zero and at most one"
            ) from error
        item = {
            "type": self.types[self.kind.GetSelection()],
            "channel": self.channel.GetSelection() - 1
            if self.channel.GetSelection()
            else None,
            "number": number,
            "action": self.actions[self.action.GetSelection()],
            "mode": midi_mapping.MODES[self.mode.GetSelection()],
            "step": step,
            "invert": self.invert.GetValue(),
            "enabled": self.enabled.GetValue(),
        }
        previous = self.mapper.export_state()
        initialized = self.owner.midi_profile_initialized
        index = self.mapper.add(item, replace_index=self._editing_index)
        if not announce and previous == self.mapper.export_state():
            self._editing_index = index
            self._has_source = True
            return True
        try:
            self.owner.save_midi_mappings()
        except OSError:
            self.mapper.import_state(previous)
            self.owner.midi_profile_initialized = initialized
            raise
        self._editing_index = index
        self._has_source = True
        self.refresh_entries(index)
        self.monitor.ChangeValue(tr("MIDI mapping saved"))
        if announce:
            self.owner.speaker.say(tr("MIDI mapping saved"))
        return True

    def on_delete(self, event):
        self.cancel_pending()
        index = self.entries.GetSelection()
        if index != wx.NOT_FOUND:
            entries = self.mapper.export_state()
            entries.pop(index)
            if not self.replace_mappings(entries):
                return
            self._editing_index = None
            self._has_source = False
            self.refresh_entries(index)
            if self.entries.GetCount():
                self.on_select(None)

    def on_profile(self, event):
        self.cancel_pending()
        profiles = ("akm322", "ni_absolute", "ni_relative", "ni_offset", "generic")
        with wx.SingleChoiceDialog(
            self,
            tr("Select a controller template. This replaces the mapping list."),
            tr("Controller profile"),
            [
                "MIDIPLUS AKM322",
                tr("NI CC14–21 Absolute"),
                tr("NI CC14–21 Relative"),
                tr("NI CC14–21 Relative Offset"),
                tr("CC14–21 absolute"),
            ],
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            entries = midi_mapping.profile(profiles[dialog.GetSelection()])
        if not self.replace_mappings(entries):
            return
        self._editing_index = None
        self._has_source = False
        self.refresh_entries(0)
        self.on_select(None)

    def replace_mappings(self, entries):
        previous = self.mapper.export_state()
        initialized = self.owner.midi_profile_initialized
        try:
            self.mapper.import_state(entries)
            self.owner.save_midi_mappings()
        except (TypeError, ValueError, OSError) as error:
            self.mapper.import_state(previous)
            self.owner.midi_profile_initialized = initialized
            ui_support.message_box(
                str(error), "MIDI mapping error", wx.OK | wx.ICON_ERROR
            )
            return False
        return True

    def detach(self):
        if self._alive:
            self._alive = False
            self.mapper.monitor = None
            self.mapper.learn_callback = None
            self.cancel_pending()
            self.timer.Stop()

    def on_close(self, event):
        self.flush_pending()
        self.detach()
        self.EndModal(wx.ID_OK)

    def Destroy(self):
        self.detach()
        return super().Destroy()
