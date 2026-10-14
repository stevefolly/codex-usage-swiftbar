# Contributing

Bug reports, documentation fixes, and pull requests are welcome.

## Reporting bugs

Include the steps to reproduce the problem, expected and actual behaviour, and your macOS, Python, SwiftBar, and Codex CLI versions. Include the error message where useful, after removing personal information.

Do not attach authentication files, tokens, or account caches. For security concerns, see [SECURITY.md](SECURITY.md).

## Making changes

1. Fork the repository and create a branch for your change.
2. Keep changes focused and preserve support for Python 3.10 or later.
3. Check Python syntax:

   ```sh
   python3 -m py_compile codex-usage.1m.py
   ```

4. For behaviour changes, test the plugin in SwiftBar on macOS. Check both fresh and cached output where relevant. Running `python3 codex-usage.1m.py` contacts Codex through your local CLI and updates the usage cache.
5. Update the README or changelog when appropriate, then open a pull request describing the change and how you checked it.

The GitHub workflow checks syntax only; it does not authenticate to Codex or verify live usage retrieval.

Contributions are provided under the repository's [MIT licence](LICENSE).
