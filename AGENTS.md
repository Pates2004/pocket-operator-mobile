# Pocket Operator mobile

Scope: this repository, a Windows wxPython synthesizer and MIDI sequencer.
Source root: `D:\8bit`. User documentation: [README.md](README.md).

## Always on start or resume

- Follow the current global instruction index and its applicable modules in
  `D:\work\Forme\.codex\agent-rules`.
- Read the current checkpoint and relevant requirements in
  [the project audit](D:/work/Forme/8bit/checkpoint.md).
- Inspect Git status before changes. Preserve unrelated user changes.

## Implementation and verification

- `main.py`: wxPython UI and session state; `synth.py`: DSP and audio;
  `sequencer.py`: scheduling; `midi_handler.py`: MIDI input.
- Run `python -B -m unittest -v` and `python -m ruff check . --no-cache`.
  Hardware and NVDA checks supplement automated tests; record their limits.
- Preserve keyboard access, Polish/English catalogs, project compatibility,
  and application data stored beside the program. Write source identifiers
  and developer comments in English.
- Current portable releases belong in `/Installfiles/` (ignored by Git).
  Internal evidence and work files belong in `D:\work\Workspace\8bit`;
  project memory in `D:\work\Forme\8bit`; discarded artifacts in
  `D:\work\Trash\8bit`. Keep user documentation and source tests here.
- Before committing/pushing, read the global `git-identity.md` module and
  verify author and committer attribution to `Pates2004` on GitHub.
