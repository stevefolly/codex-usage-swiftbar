# Contributing

Bug reports, documentation fixes, GitHub pull requests, and GitLab merge requests are welcome. Use the platform where you found the repository; please avoid submitting the same issue or change on both platforms.

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
5. Update the README or changelog when appropriate, then open a pull request on GitHub or a merge request on GitLab describing the change and how you checked it.

The GitHub Actions workflow and GitLab CI pipeline check syntax only; neither authenticates to Codex or verifies live usage retrieval. GitLab CI uses a Python 3.10 container on GitLab.com's shared Linux runners (`saas-linux-small-amd64`); instance runners must be enabled for the project. It runs on pushes, merge requests, and manual web runs, avoiding duplicate push pipelines for branches with an open merge request.

Contributions are provided under the repository's [MIT licence](LICENSE).
