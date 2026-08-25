import importlib.util
import sys

MINIMUM_PYTHON = (3, 10)
REQUIRED_MODULES = ("wx", "numpy", "sounddevice", "mido", "scipy")


def main():
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(f"BŁĄD: wymagany jest Python {required} lub nowszy (jest {current}).")
        return 1

    missing = [
        module
        for module in REQUIRED_MODULES
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print("BŁĄD: brakuje bibliotek: " + ", ".join(missing))
        print("Uruchom: python -m pip install -r requirements.txt")
        return 1

    import wx

    from main import APP_NAME, APP_VERSION, MainFrame

    print(
        f"Uruchamianie {APP_NAME} v{APP_VERSION} "
        f"w Pythonie {sys.version.split()[0]}..."
    )
    app = wx.App()
    frame = MainFrame()
    frame.Show()
    app.MainLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
