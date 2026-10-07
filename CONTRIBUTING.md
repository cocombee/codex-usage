# Contributing to Codex Usage Bar

Bug reports, documentation fixes and focused pull requests are welcome. For a new platform or a large integration change, open an issue first so the version pins, recovery behavior and verification scope can be agreed on.

## Report a bug

Use [GitHub Issues](https://github.com/cocombee/codex-usage-bar/issues) for reproducible bugs and compatibility requests. Include:

- OS version, architecture and exact Codex application version.
- Repository commit and the command or interaction that failed.
- Expected behavior, actual behavior and short reproduction steps.
- Whether the issue occurred during checking, building, installation, launch or normal use.

Review any attached output first. Remove account details, tokens, chat contents, private paths and unrelated process information. Share a small relevant excerpt rather than complete profiles or diagnostic archives. Report exploitable security problems through [SECURITY.md](SECURITY.md).

## Set up

Clone the repository and use a focused branch. Shared JavaScript checks need Node.js 20+. Python checks use the standard library; use Python 3.10+ when working across both platform adapters.

```sh
git clone https://github.com/cocombee/codex-usage-bar.git
cd codex-usage-bar
git switch -c your-change
```

The shared JavaScript tests do not require a local desktop application. Building a candidate requires the exact supported host version, architecture and platform prerequisites listed in the [README](README.md#compatibility).

## Run checks

Use Node.js 22 and Python 3.11 to match the [CI workflow](.github/workflows/ci.yml). It runs the shared checks below on macOS and Windows, plus each platform's Python suites. These synthetic checks require no vendor app or package installation; rendered-fixture and native acceptance checks remain separate.

### Shared JavaScript

```sh
node --test tests/diff-slot.test.mjs tests/metrics.test.mjs tests/speed.test.mjs
```

This covers metrics, speed estimation and diff-slot lifecycle behavior.

### macOS installer checks

From macOS, run these suites. Each command stops on failure:

```sh
python3 -B tests/signing.test.py || exit 1
python3 -B tests/startup_health.test.py || exit 1
python3 -B tests/integrity.test.py || exit 1
python3 -B tests/acceptance.test.py || exit 1
python3 -B tests/launch_identity.test.py || exit 1
python3 -B tests/install.test.py || exit 1
python3 -B tests/protected_recovery.test.py || exit 1
python3 -B tests/worker.test.py || exit 1
python3 -B tests/setup.test.py || exit 1
```

Process-group, native signing and atomic-exchange behavior require macOS. A platform-specific skip is not a passing result for that platform.

### Windows adapter checks

From PowerShell on Windows:

```powershell
python -B tests/windows.test.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -B tests/signing.test.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

The macOS suite does not establish Windows compatibility. Windows file-locking and launcher behavior need Windows checks.

### Rendered fixture

The fixture requires a **locally built, verified candidate**, Node.js 20+, Playwright and Chrome. It loads host React from the candidate and supplies fictional metrics; it does not connect to the running application.

On macOS, set the absolute path to a `node_modules` directory containing Playwright:

```sh
export CODEX_USAGE_NODE_MODULES="/absolute/path/to/node_modules"
node tests/render.mjs
```

On Windows:

```powershell
$env:CODEX_USAGE_NODE_MODULES = 'C:\path\to\node_modules'
$env:CODEX_USAGE_PYTHON = 'C:\path\to\python.exe'
node tests/render.mjs
```

Set `CODEX_USAGE_BROWSER` to an absolute Chrome executable path if it is not in the platform's default location. Use `python3 scripts/preview.py` on macOS or `python scripts/preview.py --windows` on Windows for the interactive loopback fixture.

For UI changes, check widths, font sizes, theme behavior and keyboard interaction. Installer changes also need the relevant failure and recovery tests. Native rendering, live metrics, real diff interactions and normal quit/reopen still need observation on the exact installed build; fixture results cannot substitute for that acceptance.

## Keep changes focused

The main areas are:

| Area | Responsibility |
| --- | --- |
| `src/` | Presentation, metrics, timing, responsive behavior and native UI composition |
| `scripts/setup.py`, `scripts/mod.py` | macOS installation and version-pinned patching |
| `scripts/windows_setup.py`, `scripts/windows_patch.py` | Windows installation and version-pinned patching |
| `scripts/*integrity.py`, `scripts/signing.py` | Archive/native integrity and signing policy |
| `tests/` | Unit, recovery and rendered-fixture checks |
| `docs/` | Installation, design decisions and acceptance evidence |

Read [AGENTS.md](AGENTS.md) and [Startup and Signing Prevention](docs/Startup%20And%20Signing%20Prevention.md) before changing build, signing, installation or recovery behavior.

Preserve the host's native controls and existing account data. Keep unknown data distinct from zero. Do not bypass source pins, integrity validation or platform guards to support a new build. New versions need inspected inputs and updated validation.

Commit only original source, tests and documentation. Keep app bundles, extracted vendor files, profiles, local receipts, logs and generated build artifacts out of pull requests.

## Open a pull request

Explain the problem, the resulting behavior and any remaining limits. Include the checks you ran and their platform; clearly distinguish automated results from native acceptance. For UI changes, include a sanitized image when it helps reviewers assess the change.

Keep pending acceptance visible. Do not claim a new platform or application version works based only on fixture tests.
