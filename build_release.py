"""Build the current Windows portable release with external working files."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work == ROOT or ROOT in work.parents:
        raise ValueError("Build workspace must be outside the source tree")
    work.mkdir(parents=True, exist_ok=True)
    target = ROOT / "Installfiles" / "PocketOperator-mobile"
    if target.exists():
        raise FileExistsError("Move the previous release before replacing it")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "PocketOperator-mobile",
        "--distpath",
        str(ROOT / "Installfiles"),
        "--workpath",
        str(work / "build"),
        "--specpath",
        str(work),
        "--add-data",
        f"{ROOT / 'langs'};langs",
        "--collect-all",
        "accessible_output2",
        "--collect-all",
        "libloader",
        "--hidden-import",
        "mido.backends.rtmidi",
        "--version-file",
        str(ROOT / "windows_version.txt"),
        str(ROOT / "run.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    # Keep editable catalogs beside the executable, rather than in the runtime.
    (target / "_internal" / "langs").rename(target / "langs")
    for document in ("README.md", "README.en.md"):
        shutil.copy2(ROOT / document, target / document)
    print(target)


if __name__ == "__main__":
    main()
