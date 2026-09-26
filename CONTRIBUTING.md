# Contributing to Typing Helper

Thanks for your interest! This is a small, focused Windows utility. Contributions of all sizes are welcome.

## Ground rules

- **Platform:** Windows + Python 3.12. The app relies on Win32 / UI Automation, so most features can only be verified on Windows.
- **Single source file:** the app lives in `typing_helper.py` by design (easy to read/audit for a keylogging tool). Please keep it that way unless there's a strong reason.
- **Privacy first:** this tool records keystrokes. Any change that touches collection, the clipboard, or the phrase files must preserve the safeguards (password‑field skip, long‑digit filtering, local‑only storage). Never add network calls that send user data anywhere.

## Dev setup

```bat
pip install -r requirements.txt
python tests\test_core.py
```

`tests/test_core.py` is a dependency‑light harness (no pytest required) covering the pure logic: Hangul composition, matching/backoff, usage learning, settings, security filters, snippets, recent‑hour candidates, and the suggestion worker. **Add or update tests for any logic change** and make sure all cases pass.

To run the app from source (note: it's a global key logger — avoid running it while typing sensitive things):

```bat
python typing_helper.py
```

## Building the exe

See the build command in the [README](README.md#build-from-source). Releases are produced by `.github/workflows/release.yml` on tag push.

## Pull requests

1. Fork and create a branch.
2. Keep changes focused; describe the user‑visible effect.
3. Run `python tests\test_core.py` (all green) and add tests for new logic.
4. Update `README.md` / `README.ko.md` if behavior or usage changes.
5. Bump `APP_VERSION` only if you're preparing a release (maintainers usually handle this).

## Reporting bugs / ideas

Use the issue templates. For anything security/privacy related, see [SECURITY.md](SECURITY.md).

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
