"""Native accessible controls, appearance setup, and translated UI boundaries."""

import wx

import preferences
from localization import set_language, tr

_theme = "system"


def apply_theme(window, theme=None):
    global _theme
    if theme is not None:
        _theme = theme
    if _theme == "dark":
        background, foreground = "#202020", "#f0f0f0"
    elif _theme == "light":
        background, foreground = "#ffffff", "#101010"
    else:
        background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
    window.SetBackgroundColour(background)
    window.SetForegroundColour(foreground)
    for child in window.GetChildren():
        apply_theme(child)
    window.Refresh()


def translate_menu(menu):
    for item in menu.GetMenuItems():
        if not item.IsSeparator():
            item.SetItemLabel(tr(item.GetItemLabel()))
        if item.GetSubMenu():
            translate_menu(item.GetSubMenu())


def message_box(message, caption="", *args, **kwargs):
    return wx.MessageBox(tr(message), tr(caption), *args, **kwargs)


def number_dialog(message, prompt, caption, *args, **kwargs):
    return wx.GetNumberFromUser(tr(message), tr(prompt), tr(caption), *args, **kwargs)


def file_dialog(parent, message, **kwargs):
    if "wildcard" in kwargs:
        kwargs["wildcard"] = tr(kwargs["wildcard"])
    return wx.FileDialog(parent, tr(message), **kwargs)


def choice_dialog(parent, message, caption, choices):
    return wx.SingleChoiceDialog(parent, tr(message), tr(caption), choices)


class AppearanceDialog(wx.Dialog):
    def __init__(self, parent=None, language=None, theme=None):
        super().__init__(parent, title="Language / Język — Theme / Motyw")
        self.language_codes = preferences.LANGUAGES
        self.theme_codes = preferences.THEMES
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label="Language / Język:"), 0, wx.ALL, 10)
        self.language = wx.Choice(self, choices=["Polski", "English"])
        self.language.SetSelection(wx.NOT_FOUND)
        self.language.SetName("Language / Język")
        layout.Add(self.language, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        layout.Add(wx.StaticText(self, label="Theme / Motyw:"), 0, wx.ALL, 10)
        self.theme = wx.Choice(
            self, choices=["System / Systemowy", "Light / Jasny", "Dark / Ciemny"]
        )
        self.theme.SetSelection(wx.NOT_FOUND)
        self.theme.SetName("Theme / Motyw")
        layout.Add(self.theme, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self.confirm = wx.Button(self, wx.ID_OK, "Continue / Dalej")
        self.cancel = wx.Button(self, wx.ID_CANCEL, "Exit / Zamknij")
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(self.confirm, 0, wx.ALL, 10)
        buttons.Add(self.cancel, 0, wx.ALL, 10)
        layout.Add(buttons)
        self.SetSizerAndFit(layout)
        self.SetMinSize((390, 240))
        if language in self.language_codes:
            self.language.SetSelection(self.language_codes.index(language))
        if theme in self.theme_codes:
            self.theme.SetSelection(self.theme_codes.index(theme))
        self.confirm.SetDefault()
        self.language.Bind(wx.EVT_CHOICE, self.on_change)
        self.theme.Bind(wx.EVT_CHOICE, self.on_change)
        self.confirm.Bind(wx.EVT_BUTTON, self.on_confirm)
        self.on_change()
        self.language.SetFocus()
        apply_theme(self, theme if theme in self.theme_codes else "system")

    def on_change(self, event=None):
        self.confirm.Enable(
            self.language.GetSelection() != wx.NOT_FOUND
            and self.theme.GetSelection() != wx.NOT_FOUND
        )

    def on_confirm(self, event):
        self.on_change()
        if self.confirm.IsEnabled():
            self.EndModal(wx.ID_OK)

    def selection(self):
        if not self.confirm.IsEnabled():
            raise ValueError("Both appearance fields are required")
        return (
            self.language_codes[self.language.GetSelection()],
            self.theme_codes[self.theme.GetSelection()],
        )


def ensure_setup(path=preferences.CONFIG_PATH, parent=None, force=False):
    language, theme, complete = preferences.appearance(path)
    if complete and not force:
        set_language(language)
        return language, theme
    with AppearanceDialog(parent, language, theme) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        language, theme = dialog.selection()
    preferences.save_appearance(language, theme, path)
    set_language(language)
    return language, theme


def current_theme():
    return _theme


def busy_info(message):
    return wx.BusyInfo(tr(message))
