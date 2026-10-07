# Security

Codex Usage Bar modifies a local desktop application and runs with access to that application's usual profile. Its source pins, integrity checks, signing checks and recovery behavior are part of the security boundary.

## Report a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/cocombee/codex-usage-bar/security/advisories/new), or open the repository's **Security** tab and choose **Report a vulnerability**. Do not post exploit details, credentials, personal data or working exploits in public issues.

A useful private report describes the affected commit/platform, the security impact, minimal reproduction steps and any relevant sanitized evidence. Please allow time to investigate before publishing exploit details.

For ordinary installation errors and compatibility requests, follow the bug-report guidance in [CONTRIBUTING.md](CONTRIBUTING.md#report-a-bug).

## Supported scope

Security fixes are considered for the latest repository code and its explicitly pinned host versions. This is an experimental project; compatibility with a newer Codex release is not implied.

Relevant reports include:

- Bypassing version, source-signature or integrity checks.
- Writing outside the intended installation or recovery locations.
- Unsafe handling of local paths, command arguments or concurrent installers.
- Exposure of credentials, account data or chat content.
- Installing or launching an unverified candidate through a recovery failure.

The macOS candidate is locally signed; the changed Windows launcher is unsigned. Neither has OpenAI's original publisher identity. Native archive-integrity validation remains enabled. See the [macOS guide](docs/Installation.md) and [Windows guide](docs/Windows%20Port.md) for their platform-specific behavior.

## Share diagnostics carefully

Before sharing logs or screenshots, remove tokens, account identifiers, private repository names, chat contents and personal paths. Do not upload application bundles, extracted vendor assets, profile directories, Keychain data or complete local diagnostic archives.

Do not disable operating-system security policy, archive validation or source checks to work around an installation failure. Keep the verified recovery copy and local receipts available while investigating.
