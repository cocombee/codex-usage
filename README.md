# Codex Usage Bar

A local Codex desktop modification that adds a fixed usage row immediately above the chat input.

**Weekly → Files changed → Token speed → Context**

The row uses Codex's chat-font setting and theme tokens. Its weekly progress track shrinks before text and stays visible; pills stay on one row. Actual content fit triggers compact stages before overflow. Each chip follows the native Files changed surface: elevated secondary background, theme border, rounded-3xl corners and native inner padding. The row has no extra outer container, background or padding. Usage sits above the native Goal/utility group with an 8 CSS px gap. Native controls retain their attachment, size and inset; Usage follows the Goal rail width, retaining its native inset when Goal is absent. Without native controls, the gap to the composer stays 8 CSS px. Weekly uses semantic theme colors: normal above 20% remaining, yellow above 10% through 20%, red at 10% or below. Files changed reuses the existing native control and diff action.

No reset icon. Five-hour usage is deferred to the [architecture plan](docs/Architecture%20Plan.md).

## Implementation

- `src/bar.mjs`: presentation, existing font/color tokens, responsive layout.
- `src/metrics.mjs`: account weekly window, current context percentage and product warning boundaries.
- `src/speed.mjs`: in-memory token-count and streaming-time observer, isolated by host and chat.
- `src/diff-slot.mjs`: selected chat's portal target and subscription lifecycle.
- `src/native-fixed.mjs`: native Files changed composition; preserves native plans, extra portals and fallback.
- `src/responsive.mjs`: three fitting stages, 70% spare-track allocation and restoration buffer.
- `src/native-layout.mjs`: Goal-width alignment and native utility overflow reservation.
- `scripts/setup.py`: one-command Terminal installation with compatibility checks, build timeout and recovery.
- `scripts/mod.py`: exact-version patch, archive integrity validation, candidate packaging and reversible installation.

Weekly displays quota remaining, matching Codex’s “% left” wording; the internal track fills the same remaining percentage. The core account bucket is used, so a model-specific bucket cannot silently replace the account quota. Token speed is marked `~` because Codex supplies desktop lifecycle events rather than provider API duration. The weighted calculation follows [Hermes](docs/Hermes%20Token%20Speed.md). No credentials or message contents are retained by the observer. Missing data shows `—`.

This modification is version-pinned to desktop `26.930.61225`, using the inspected original archive hash. It is not a supported plugin extension point. A desktop update requires new inspection before patching. The exact original app is retained in `Safe Build`; the locally signed candidate occupies `New Build`. App binaries and extracted vendor code are excluded from publication. The builder dynamically synchronizes the enabled native archive digest before signing and rejects inconsistent candidates. After installation, New Build retains the previous verified mod for transactional recovery; Safe Build is never used as an automatic mod-removing fallback.

## Install

Requires Apple Silicon macOS, Python 3.9+, Node.js 20+, and the inspected Codex desktop **26.930.61225** at `/Applications/ChatGPT.app`. Keep the downloaded checkout on the same disk as `/Applications`. Windows is unsupported: it requires its own inspected bundle, installer and native installation/recovery tests; the macOS platform guard must not be bypassed.

From this repository, run in **macOS Terminal**, outside Codex:

```sh
python3 scripts/setup.py
```

The command prints three steps: compatibility checks, build/signature verification, then installation and one normal launch. Codex stays open while the candidate is built. Installation automatically closes and reopens Codex; keep Terminal open until it finishes. Unsupported versions, altered app bundles, missing prerequisites and duplicate installers stop before replacement. Build and external-command timeouts prevent unlimited waits. No sudo, security-setting changes or account reset is performed.

This release uses local ad-hoc signing. The updater preserves account data, Keychain and existing permission settings, and does not request sudo or reset permissions. macOS may still request authorization for the modified app; an update cannot promise to suppress operating-system prompts. A stable signing identity is a possible future improvement and requires its own migration and acceptance testing. See [Apple’s code identity explanation](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements).

A valid original vendor-signed app is checked before first installation. Locally signed candidates remove restricted vendor claims, preserve Hardened Runtime/JIT capabilities and scope the framework-loading exception to verified executable hosts. Native archive integrity is synchronized before signing. If candidate startup fails, the complete previously verified app is restored and gets one recovery launch; the failed candidate is not repeatedly relaunched. Durable local receipts distinguish build verification, installation and process health from visual acceptance.

Optional compatibility check, without building, quitting or installing:

```sh
python3 scripts/setup.py --check
```

After installation, confirm the usage row renders, then normally quit and reopen the installed app once. Record these checks using the acceptance command printed by the installer. When updating before acceptance, the installer preserves and verifies the previous working app in a separate protected recovery slot before reusing the candidate slot. Process health alone does not prove rendering or live metric accuracy. See [installation details](docs/Installation.md) and [Startup And Signing Prevention](docs/Startup%20And%20Signing%20Prevention.md).

## Windows

Windows support will be developed and tested on a Windows PC. The current installer supports Apple Silicon macOS only. See the [Windows port handoff](docs/Windows%20Port.md) for package inspection, platform boundaries and the checks required before a Windows release.

## Verification

Run `node --test tests/*.test.mjs` and the Python checks in `tests/*.test.py`. The atomic exchange test requires macOS. `tests/render.mjs` additionally uses Playwright, system Chrome and an isolated loopback fixture with host React and fictional values; it does not attach to the running app.

Current checks cover 35 font/width layouts and 60 zoom/reference layouts, equal object/end spacing, the 70% spare-track allocation, restoration buffering, portal interaction, integrity tampering, signing policy, atomic recovery, concurrent-install rejection, build-timeout cleanup and fresh helper-crash detection. The local mod has reopened after installation. A clean vendor-app end-to-end install, rendered native UI, live metrics and normal user quit/reopen remain separate acceptance evidence; synthetic signing tests cannot establish those results.

## Responsive layout

At full width, 70% of spare width extends Weekly's progress track; the rest is evenly shared per object gap and end inset. Three responsive groups apply only the reductions needed: (1) track/spacing, then `left` and extra countdown units; (2) `token/s` → `tok/s` and `Context` → `Ctx` together with the Weekly label hidden, then the speed icon; (3) readable text caps. Once days are gone, hours appear alone in every layout; below one hour, minutes remain visible. Fuller wording restores with an 8 CSS px buffer. Pills never wrap; exceptionally narrow layouts scroll inside the usage row.


The latest user-approved chat/composer-width thresholds are Stage 1 at 620 px, Stage 2 at 580 px and Stage 3 at 490 px, all logical CSS pixels. Native composer width determines these triggers, independently of whole-window width and the narrower Goal/Usage rail. Stage 1 removes `left` and extra countdown units; Stage 2 pairs compact token/context labels and hides Weekly; Stage 3 applies readable text caps. Content fitting still prevents wrapping, and restoration has an 8 px buffer. At every fit level, width left after natural content and minimum/standard spacing is split 70% to the track and 30% equally per object gap and horizontal end inset. The repository publishes original source, installer, tests and documentation; app binaries, extracted vendor assets and local operational data are excluded.
