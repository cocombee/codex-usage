# Codex Usage Handoff

## Current delivery

Source is a version-pinned local desktop mod, with a one-command installer: `python3 scripts/setup.py` in macOS Terminal. Supported app: Apple Silicon desktop `26.930.61225` at `/Applications/ChatGPT.app`. See [Installation](Installation.md). A changed version must be inspected; never bypass the version/hash or signing guards.

The accepted row is Weekly → native Files changed → estimated token speed → Context. Five-hour usage stays in the plan. Individual pills follow the native Files changed design with no shared outer frame. Usage matches Goal rail edges and preserves its native inset when Goal is absent. Native Apps/Goal/composer geometry remains unchanged; the native Goal owner gets a reference attribute only. The gap above the native group is 8 logical CSS px. The Weekly progress track is 5.6 logical CSS px tall (30% less than 8 px) and remains vertically centered by the pill's existing alignment.

Weekly percentage and fill both show remaining account quota. Core account state owns the value; model-specific state cannot silently substitute. Speed remains an estimate marked `~`, using a weighted last-ten response aggregate that includes first-token waiting and excludes the union of observed tool intervals. Context uses current context usage. Native diff state owns Files changed counts, actions and tooltip.

## Accepted responsive behavior

Weekly's preferred 100 px full-width progress track receives 70% of spare width at every fit level; the remaining 30% is evenly shared per object-to-object gap and horizontal end inset. Chat/composer width selects the three groups at 620, 580 and 490 logical CSS px. Native composer width is measured separately from the narrower Goal/Usage rail, so app sidebars and window zoom do not substitute whole-window width. Measure the complete Goal or utility frame, ignoring false-framed attributes and narrower child items. Effective CSS zoom converts rendered widths to logical pixels; native rails are never resized to match the mod.

| Layout | Chat/composer width |
|---|---:|
| Full | Above 620 px |
| Stage 1 | Above 580 through 620 px |
| Stage 2 | Above 490 through 580 px |
| Stage 3 | 490 px or below |

1. Stage 1: tighten spacing/shrink the track, remove `left` and extra countdown units. Hours remain when they are the largest remaining unit.
2. Stage 2: `token/s` → `tok/s`, `Context` → `Ctx`, and hide Weekly together. If needed, hide the speed icon and tighten spacing further.
3. Stage 3: reduce text within 14/12 px caps only if needed. Below the irreducible readable width, scroll locally; never wrap or overflow the page.

Fitting can make further reductions sooner if unusually large content would otherwise overflow. All fit levels reserve 70% of width left after natural content and minimum/standard spacing for the track; the remaining 30% is shared equally per object gap and horizontal end inset. Fuller groups restore only after 8 logical CSS px of clearance beyond the boundary. These thresholds supersede the earlier measured content-only example ranges.

## Installation and recovery ownership

`setup.py`: prerequisites, exclusive lock, bounded build and direct progress. `mod.py`: candidate validation and atomic bundle exchange. `integrity.py`: actual archive/header/native digest and enabled fuses. `signing.py`: valid vendor source versus scoped local candidate signatures. `install_once.py`: exact process boundary, durable receipt, one normal candidate launch and at most one recovery launch. `startup_health.py`: fresh main/helper crash reports and kernel-mapped main/framework inode proof, including helper crashes while the main process remains alive. Refuse other Codex copies before replacement; attach to an already reopened exact candidate rather than issuing a duplicate launch. Terminal displays progress and startup trace records process identities.

Follow [Startup And Signing Prevention](Startup%20And%20Signing%20Prevention.md). Restricted vendor claims are removed from local candidates; Hardened Runtime/JIT remain. The library-loading exception is limited to verified executable hosts. No Gatekeeper/quarantine, user-data or Keychain reset. Native digest synchronization precedes signing. Changed helpers → framework seal → main app.

The original archive stays protected in Safe Build. New Build retains the complete previous verified app after promotion. Failed startup restores that previous app, without looping through candidate launches. A timeout, unsupported version, invalid signature, unrecognized candidate or unprovable process boundary stops with an explicit result rather than guessing. Logs, receipts, locks, app bundles and extracted vendor code are local and excluded from Git.

## Evidence and remaining acceptance

Rendered fixture checks cover 35 width/font layouts and 60 zoom/reference layouts, Goal fallback, equal gaps, 70% spare-track allocation, paired labels, no wrapping, restoration buffering, native diff interaction and warning colors. Unit/policy checks cover metrics, integrity tampering, local/vendor signing boundaries, real atomic toy exchanges, failed startup recovery, initially closed apps, stuck quit refusal, concurrency, build-timeout cleanup and fresh helper-crash detection.

The final 5.6 px track build reached process_healthy_ui_pending with one normal launch, matching installed archive and mapped executable/framework inodes, and no recovery error. This supersedes the earlier failed attempt that recovered the previous build. Native visual acceptance, live metrics/diff actions, normal user quit/reopen and a clean vendor-app end-to-end installation remain unverified. Computer-use access to the host app was refused; do not bypass that restriction through another UI automation route.

The release review found three defects: premature recovery-slot deletion during a pending rebuild, surviving build descendants after timeout, and missing refits when inherited font metrics change. The responsive source now observes intrinsic content sizes so inherited font changes and delayed font loading trigger fitting. The source regression suite covers both at wide and compact widths without idle refit loops. Pending updates preserve a separately verified protected recovery bundle before reusing the candidate slot. Explicit acceptance remains a separate attestation tied to the exact installed bundle and running image; a request to update does not fabricate UI acceptance. Timeout cleanup kills surviving original-group descendants even after the leader exits. Unsupported platforms reject before POSIX imports or signal setup. The Python suite passed 48 unittest cases plus atomic-exchange and worker scenarios, including protected recovery through repeated updates and accepted-version rollover. All 12 JS tests, 35 base layouts, 60 zoom/reference layouts and four font regressions passed. Build validation, installation/process health and native UI acceptance are recorded separately in excluded local receipts. The approved release uses 620 / 580 / 490 px stages and a 70/30 spare-width split. At the screenshot-like 662 px width, the render checks confirm days and hours remain visible; hours appear alone when no days remain. Never mark installed acceptance from test fixtures or process health. The user authorized publication of the reviewed original source, installer, tests and documentation in one new final commit. Vendor bundles and local operational data remain excluded.

The reported macOS warning was traced to App Management denying the host's native launch-services-helper after reopening. The original startup code contains app/Dock icon operations; the exact denied target operation was not recorded. This is separate from the successful bundle exchange. The mod must not grant permissions, alter TCC or disable security to suppress the warning. Windows installation is unsupported until a Windows bundle and independent installation/recovery path have been inspected and tested.
