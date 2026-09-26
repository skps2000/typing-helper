# Typing Helper

> 🌐 **English** · [한국어](README.ko.md)

**A lightweight personal autocomplete for Windows that learns from what _you_ actually type** — and completes your own phrases anywhere (browsers, editors, chat) via a small popup right above the caret. Press `Tab` to fill.

Built first-class for **Korean (Dubeolsik) typing** — it composes Hangul from physical keys (`dkssud → 안녕`) — and adds **snippet / abbreviation expansion**, a **quick phrase search**, and **real‑time suggestions from your last hour of typing**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/skps2000/typing-helper)](https://github.com/skps2000/typing-helper/releases)
[![Tests](https://github.com/skps2000/typing-helper/actions/workflows/tests.yml/badge.svg)](https://github.com/skps2000/typing-helper/actions/workflows/tests.yml)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

<!-- TODO: add docs/screenshot.png and a short demo GIF -->

## Why

Generic autocomplete doesn't know how *you* phrase things. Typing Helper collects your own typing **locally**, lets you curate a phrase list, and then completes those phrases **everywhere** — anchored to the text caret, not tied to any single app.

## Highlights

- **Learns from your typing** — a global keyboard hook records what you type (with **Dubeolsik Hangul composition**) and clipboard paste. Your curated phrases live in a plain `phrases.txt`.
- **Caret‑anchored suggestions** — a popup appears right above the cursor while you type. `↑`/`↓` to move, `Tab` to fill, `Esc` to dismiss (stays hidden until you type again). Works even in Chromium/Electron apps via **UI Automation** caret tracking.
- **Snippets & abbreviation expansion** — manage `상용구.txt` as `alias=phrase`. Type the alias + `Space/Enter` to **expand in place** (e.g. `ㄱㅅ` → "감사합니다…"); use `{..}` placeholders to jump‑select after insert. Press **`` ` `` (backtick)** anywhere to open a **search box** and pick a phrase.
- **Recent‑hour suggestions** — whatever you typed in the last hour is offered automatically (most‑used first), so repeated phrasing in a session completes instantly.
- **Typing is never blocked** — keystroke handling only updates a buffer; all matching runs on a **dedicated worker thread**. File writes are batched in the background.
- **Smart matching** — Hangul composition + initial‑consonant search (`ㅂㄹㅍ → 브리핑…`) + fuzzy typo tolerance (RapidFuzz) + word‑boundary/suffix backoff. Frequently accepted phrases rank higher over time.
- **Stays out of the way** — per‑app on/off (disable in your code editor/terminal), quick toggle hotkey `Ctrl + Alt + Space`, password fields skipped, tray icon, single instance, optional run‑at‑startup.
- **Modern dashboard** (CustomTkinter) — a compact window with just **Collect / Autocomplete** toggles up front; everything else folds under **More**. Bilingual UI (auto‑detects Korean/English, with a manual toggle).

## Install

1. Download **`TypingHelper.exe`** from the [Releases](https://github.com/skps2000/typing-helper/releases) page.
2. Run it — no installation. A dashboard window opens and it starts collecting.

> Windows may warn about an unsigned executable (SmartScreen) — this is expected for an unsigned open‑source build. You can review the source and [build it yourself](#build-from-source).

## Usage

1. Type normally for a while so it collects data.
2. (Optional) Use **More → Guide** to get a correction prompt, and paste your `typing_*.txt` into any AI to clean it up.
3. Put the resulting phrases (one per line) into **More → Phrases** (`phrases.txt`) and save.
4. Now as you type, a **suggestion list appears above the caret** — `↑`/`↓` to choose, **`Tab`** to fill, `Esc` to close.
5. Add frequently used phrases/snippets under **More → Phrases / Snippets**.
6. Press **`` ` ``** anytime to search phrases/snippets and insert with `Enter`.

## Privacy & Security

**Typing Helper is a global keystroke logger by design** — that's how it learns your phrases. It is built to keep this **local and transparent**:

- **Everything is stored locally** under `%LOCALAPPDATA%\TypingHelper\` and is **never sent anywhere** by the app. (Logs leave your machine only if *you* choose to send a file to an AI for correction.)
- **Password fields are skipped** — when UI Automation reports `IsPassword`, both collection and suggestions are turned off. (Field detection takes a few dozen ms, so the first character or two may still be recorded — not a hard guarantee.)
- **Long digit runs** (card/account/phone‑like, including separators) are **not recorded** from the clipboard.
- Typing into the app's **own dashboard is never collected**.
- Deleted phrases go to `phrases_trash.txt` (a recoverable trash), not immediate deletion.

Please only use this on machines you own, and don't put secrets into the phrase files. See [SECURITY.md](SECURITY.md).

## How it works

- **Dubeolsik composition** — reconstructs Hangul syllables from QWERTY physical keys.
- **Global hook** — `pynput` low‑level keyboard hook; the raw hook stays minimal so it never delays keystrokes.
- **Caret tracking** — `comtypes` + UI Automation reads the caret rectangle (and, only when needed, the text before the caret) to place the popup and correct desyncs. Heavy UIA text reads are skipped during normal typing.
- **Matching** — runs off the input thread on a worker; pool = recent + snippets + saved phrases, with cached word boundaries.
- **UI** — CustomTkinter dashboard + a lightweight Tk overlay/picker; `pystray` tray icon.

## Data location

`%LOCALAPPDATA%\TypingHelper\` (via `platformdirs`):

| File | Purpose |
|---|---|
| `typing_YYYY-MM-DD.txt` | Composed, human‑readable typing log + pasted text |
| `raw_YYYY-MM-DD.txt` | Raw key backup |
| `phrases.txt` | Autocomplete source (your curated phrases) |
| `상용구.txt` | Snippets / abbreviations (`alias=phrase`) |
| `usage.json`, `settings.json`, `pinned.json` | Usage learning, settings, pins |
| `phrases_trash.txt` | Recoverable trash for deleted phrases |

## Build from source

Requires Windows + Python 3.12.

```bat
pip install -r requirements.txt
python tests\test_core.py

pyinstaller --onefile --noconsole ^
  --collect-all tkinter --collect-all comtypes --collect-all rapidfuzz ^
  --collect-all customtkinter --collect-all darkdetect ^
  --hidden-import platformdirs --collect-submodules platformdirs ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  --hidden-import pystray._win32 --hidden-import comtypes.stream ^
  --name TypingHelper typing_helper.py
```

The build outputs `dist\TypingHelper.exe`. Releases are also built automatically on tag push (see `.github/workflows/release.yml`); the repo keeps **source only** (the exe is not committed).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). All core logic (Hangul composition, matching, snippets, settings, security filters) is covered by `tests/test_core.py` (138 cases): `python tests/test_core.py`.

## License

[MIT](LICENSE) © Typing Helper contributors
