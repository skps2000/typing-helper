# Security & Privacy

Typing Helper is, by design, a **global keystroke logger** — it records what you type in order to learn your phrases. This document explains what it does with that data and how to report problems.

## What is collected, and where it goes

- Keystrokes (composed into Hangul) and clipboard copy/paste are written to plain‑text files under `%LOCALAPPDATA%\TypingHelper\`.
- **All data stays on your machine.** The application makes **no network requests** and does not transmit your logs anywhere. Data leaves your computer only if *you* choose to send a file (e.g. to an AI service for phrase correction).

## Built‑in safeguards

- **Password fields are skipped.** When UI Automation reports the focused control as a password field (`IsPassword`), both collection and suggestions are disabled. Detection takes a few dozen milliseconds, so the first character or two may still be recorded — treat this as best‑effort, not a guarantee.
- **Long digit sequences** (card/account/phone‑like, including space/dash separators) are not recorded from the clipboard.
- The app's **own dashboard input is never collected**.
- Deleted phrases are moved to a recoverable `phrases_trash.txt` rather than being wiped immediately.

## Your responsibility

- Only run this on machines **you own and control**. Running a keylogger on someone else's machine without their informed consent may be illegal in your jurisdiction.
- Don't put secrets (passwords, tokens, keys) into `phrases.txt` / `상용구.txt`.
- The generated logs may contain sensitive text you typed — protect the data folder like any other personal file, and clear it if needed (the dashboard has a log‑cleanup option).

## Reporting a vulnerability

If you find a security or privacy issue (e.g. a way data could leak off‑machine, or a safeguard that fails):

- **Please do not open a public issue for anything that could put users at risk.**
- Report privately to **skps2000@gmail.com** with steps to reproduce.

We'll acknowledge and work on a fix as soon as reasonably possible. There is no bug‑bounty program; this is a volunteer, best‑effort project provided under the MIT license with no warranty.
