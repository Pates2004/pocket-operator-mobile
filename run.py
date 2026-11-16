import faulthandler
import importlib.util
import sys
import traceback

from app_paths import APP_DIR

MINIMUM_PYTHON = (3, 10)
REQUIRED_MODULES = ("wx", "numpy", "sounddevice", "mido", "scipy")


def launch():
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
    from ui_support import ensure_setup

    print(
        f"Uruchamianie {APP_NAME} v{APP_VERSION} w Pythonie {sys.version.split()[0]}..."
    )
    app = wx.App()
    try:
        if ensure_setup() is None:
            return 0
    except Exception as error:
        wx.MessageBox(str(error), "Configuration / Konfiguracja", wx.OK | wx.ICON_ERROR)
        return 1
    frame = MainFrame()
    frame.Show()
    app.MainLoop()
    return 0


def main():
    log_dir = APP_DIR / "logs"
    try:
        log_dir.mkdir(exist_ok=True)
        with (log_dir / "startup.log").open("a", encoding="utf-8") as log:
            from datetime import datetime

            log.write(f"\n{datetime.now().isoformat()} Python {sys.version}\n")
            log.write(f"Executable: {sys.executable}\n")
            log.flush()
            faulthandler.enable(file=log, all_threads=True)
            try:
                result = launch()
                log.write(f"Application exited: {result}\n")
                return result
            except Exception:
                traceback.print_exc(file=log)
                raise
            finally:
                faulthandler.disable()
    except Exception as error:
        message = (
            f"Startup error / Błąd uruchamiania:\n{error}\n\n{log_dir / 'startup.log'}"
        )
        if sys.stderr:
            print(message, file=sys.stderr)
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "Pocket Operator mobile", 0x10
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
