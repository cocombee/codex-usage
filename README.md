# Codex Usage Bar

See your weekly quota, changed files, response speed and context usage just above the Codex chat input.

Codex Usage Bar is a community desktop modification that uses Codex's existing account state, theme and chat-font settings. It adds one compact row while preserving the native composer, Goal controls and Files changed action.

**Weekly → Files changed → Token speed → Context**

[macOS setup](#macos) · [Windows preview](#windows-preview) · [Documentation](#documentation) · [Contributing](CONTRIBUTING.md)

## What it shows

| Metric | Behavior |
| --- | --- |
| **Weekly** | Account quota remaining and its reset countdown. The progress track shows the same remaining percentage. |
| **Files changed** | The selected chat's native control, with its existing diff action. |
| **Token speed** | An approximate, per-chat tokens-per-second estimate, marked `~`, during a running turn. It clears to `—` when the turn finishes or the chat becomes idle. |
| **Context** | Context usage from the selected conversation's existing token-usage state. |

Missing data appears as `—`, never a fabricated zero. The row adapts to narrow composer widths by shortening labels and spacing; it keeps one row and follows the host's theme and font. Five-hour usage is not implemented.

## Compatibility

**This is an experimental local modification, not an official OpenAI plugin.** Installers accept only the inspected versions below and reject unknown versions or changed source files.

| Platform | Pinned application | Status |
| --- | --- | --- |
| Apple Silicon macOS | Desktop `26.930.61225` | Local installer with validation and recovery; full installed-app acceptance remains pending. |
| Windows x64 | Store package `26.1002.7124.0`, renderer `26.1002.52244` | Experimental local preview; native rendering observed, full acceptance pending. |

A desktop update needs fresh compatibility review. Changing a version number or bypassing a hash check is not a supported upgrade path.

## Installation

Clone the source, then follow the instructions for your platform:

```sh
git clone https://github.com/cocombee/codex-usage-bar.git
cd codex-usage-bar
```

### macOS

Requires **Apple Silicon**, **Python 3.9+**, **Node.js 20+**, and the pinned desktop version at `/Applications/ChatGPT.app`. Keep this checkout on the same disk as `/Applications`, with space for the candidate and recovery copies.

Run in **macOS Terminal, outside Codex**:

```sh
# Check compatibility without building or installing.
python3 scripts/setup.py --check

# Build, verify, install and launch once.
python3 scripts/setup.py
```

Keep Terminal open. Codex stays open during the build; installation closes and reopens it. The installer validates the source, signs the local candidate, preserves a verified recovery copy and stops on unsupported input.

The modified app uses local ad-hoc signing. Account data and Keychain are preserved, but macOS may request authorization for the changed app. The installer does not use sudo or change system security settings.

After installation, check the rendered row and normally quit/reopen the installed app. Follow the [macOS installation guide](docs/Installation.md) to record acceptance or diagnose a failed install.

### Windows preview

Requires **x64 Windows**, **Python 3.10+**, the exact current-user Store package above and approximately **6 GB free space**.

Run in PowerShell from this checkout:

```powershell
python scripts/windows_setup.py --check
python scripts/windows_setup.py --build
$build = (Get-Content -Raw .local-windows/latest.json | ConvertFrom-Json).build
python scripts/windows_setup.py --install "$build"
```

Quit all ChatGPT/Codex desktop windows normally, then open **Codex Usage (local mod)** from the Start menu. Keep the Python executable used for installation available.

The mod installs a separate copy under `%LOCALAPPDATA%\OpenAI\CodexUsage`; the Store app stays intact. Its launcher uses the usual profile and refuses concurrent desktop instances. The changed launcher is **unsigned**. Integrity validation remains enabled, and no certificate trust or Windows security policy is changed.

Read the [Windows guide](docs/Windows%20Port.md) for recovery, acceptance and the host's chat-ownership requirement for setting Goals.

## Validation and limitations

Automated checks cover metric calculations, responsive layouts, native diff composition, archive integrity, signing policy and installer recovery. Fixture tests use fictional values in an isolated loopback page.

Native application checks are tracked separately:

- **macOS:** the latest installed candidate still needs rendered-UI and normal quit/reopen acceptance; a clean vendor-app end-to-end installation remains unverified.
- **Windows:** the row rendered in chats and on new-chat screens, and Weekly matched the core account quota. Live token speed, actual diff interaction, full display-scaling checks and two normal shared-profile launches remain pending.
- **Both platforms:** token speed is an estimate from desktop lifecycle events, not provider API timing. Passing tests or a healthy process does not establish every live-app behavior.

This repository contains original source, tests and documentation. App binaries, extracted vendor assets, account profiles and local operational logs are not distributed.

## Development

The shared JavaScript tests require Node.js 20+ and no application installation:

```sh
node --test tests/diff-slot.test.mjs tests/metrics.test.mjs tests/speed.test.mjs
```

The [CI workflow](.github/workflows/ci.yml) runs shared and platform-specific synthetic tests on macOS and Windows with Node.js 22 and Python 3.11. Native installed-app acceptance is tracked separately.

Installer tests use Python's standard library; platform-specific cases need their target OS. UI fixture tests additionally need a local verified candidate, Playwright and Chrome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, test commands and what to include in a pull request.

## Documentation

| Guide | Purpose |
| --- | --- |
| [macOS installation](docs/Installation.md) | Requirements, installation, recovery and acceptance |
| [Windows preview](docs/Windows%20Port.md) | Version pins, installation, launcher behavior and remaining validation |
| [Architecture](docs/Architecture%20Plan.md) | Module ownership, state sources and responsive behavior |
| [Desktop integration decision](docs/ADR%20002%20Desktop%20Mod.md) | Integration constraints and implementation choices |
| [Startup and signing](docs/Startup%20And%20Signing%20Prevention.md) | Required integrity, signing and launch checks |
| [Token-speed calculation](docs/Hermes%20Token%20Speed.md) | Timing method and its limitations |
| [Contributing](CONTRIBUTING.md) | Development workflow and reporting bugs |
| [Security](SECURITY.md) | Reporting vulnerabilities and handling sensitive diagnostics |

## License

The original code in this repository is available under the [MIT License](LICENSE). This license does not cover OpenAI's application, trademarks or other vendor materials. Those materials are not redistributed here.
