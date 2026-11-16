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
        self.source = None
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
        ui_support.apply_theme(self)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def refresh_entries(self):
        self.entries.Set(
            [
                f"{item['type']} {item['number']} / {tr('Channel')} "
                f"{item['channel'] + 1 if item['channel'] is not None else '*'} → "
                f"{tr(item['action'])} ({tr(item['mode'])})"
                f" — {tr('Enabled') if item['enabled'] else tr('Disabled')}"
                for item in self.mapper.export_state()
            ]
        )

    def on_select(self, event):
        index = self.entries.GetSelection()
        if index == wx.NOT_FOUND:
            return
        item = self.mapper.export_state()[index]
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
        self.monitor.ChangeValue(tr("Move a knob or press a MIDI button now."))
        self.owner.speaker.say(tr("Move a knob or press a MIDI button now."))
        self.mapper.learn_callback = lambda source: wx.CallAfter(self.learned, source)

    def learned(self, source):
        if not self._alive:
            return
        kind, channel, number = source
        self.kind.SetSelection(self.types.index(kind))
        self.channel.SetSelection(channel + 1 if channel is not None else 0)
        self.number.SetValue(number)
        self.enabled.SetValue(True)
        self.monitor.ChangeValue(
            tr("Control learned. Select its action and mode, then save.")
        )
        self.owner.speaker.say(self.monitor.GetValue())
        self.action.SetFocus()

    def on_save(self, event):
        item = {
            "type": self.types[self.kind.GetSelection()],
            "channel": self.channel.GetSelection() - 1
            if self.channel.GetSelection()
            else None,
            "number": self.number.GetValue(),
            "action": self.actions[self.action.GetSelection()],
            "mode": midi_mapping.MODES[self.mode.GetSelection()],
            "step": self.step.GetValue() / 100,
            "invert": self.invert.GetValue(),
            "enabled": self.enabled.GetValue(),
        }
        try:
            self.mapper.add(item)
            self.owner.save_midi_mappings()
            self.refresh_entries()
            self.owner.speaker.say(tr("MIDI mapping saved"))
        except (ValueError, OSError) as error:
            ui_support.message_box(
                str(error), "MIDI mapping error", wx.OK | wx.ICON_ERROR
            )

    def on_delete(self, event):
        index = self.entries.GetSelection()
        if index != wx.NOT_FOUND:
            entries = self.mapper.export_state()
            entries.pop(index)
            self.mapper.import_state(entries)
            self.owner.save_midi_mappings()
            self.refresh_entries()

    def on_profile(self, event):
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
            self.mapper.import_state(
                midi_mapping.profile(profiles[dialog.GetSelection()])
            )
        self.owner.save_midi_mappings()
        self.refresh_entries()

    def detach(self):
        if self._alive:
            self._alive = False
            self.mapper.monitor = None
            self.mapper.learn_callback = None
            self.timer.Stop()

    def on_close(self, event):
        self.detach()
        self.EndModal(wx.ID_OK)

    def Destroy(self):
        self.detach()
        return super().Destroy()
