# Codex Usage Architecture Plan

Accepted desktop modification. The prior supported-side-panel option was superseded by the user's request for a fixed row above the chat input.

## Current slice

Render Weekly, the native Files changed control, estimated token speed and Context in a row of native-styled pills. Preserve native chat input, plans, environment progress and additional fixed-content portals. Files changed is embedded only when the existing in-progress native control would be shown; its completed transcript representation remains owned by Codex.

Codex owns account/model quota state, selected chat token usage, native diff state and all actions. Codex Usage owns only presentation, per-chat portal registration and a bounded in-memory timing estimate. The usage row precedes the native Goal/utility group. Native positioning and geometry remain unchanged. A measured overflow reserve in the composer stack prevents the native absolute utility strip from overlapping Usage; the native strip remains attached to the composer. Usage adopts the native rail width/inset. The composer passes only the normalized core account quota bucket. Both number and fill derive from remaining quota. The native turn component retains its existing selectors and diff component, redirecting that component into the matching host/chat portal. It falls back to native placement if the bar is absent.

The UI inherits the native chat font. At full width, 70% of spare width extends the 100 logical CSS px Weekly track; the remainder is evenly distributed per object gap and horizontal end inset. Fitting uses three groups, with only necessary reductions inside each: (1) tighten spacing and shrink the track toward 16 px, then remove `left` and extra countdown units; (2) pair `token/s` → `tok/s` with `Context` → `Ctx` and hide Weekly, then hide the speed icon/tighten spacing if needed; (3) apply 14/12 px text caps if needed. Once days are gone, hours appear alone in every layout; below one hour, minutes remain visible. Restoration requires an 8 logical CSS px buffer. The percentage, track and metric order remain intact on a single row. Each chip follows the native Files changed surface and rounded-3xl corners; the row has no extra outer container or padding. Weekly colors use existing semantic tokens: normal above 20%, yellow above 10% through 20%, red at 10% or below remaining. The gap from Usage to the native group (or composer when absent) is 8 CSS px. Zoom-aware measurements prioritize Goal and preserve its native inset when no rail is visible without altering native Apps/Goal/composer geometry.

No new persistence, network endpoint, credentials, durable telemetry or message submission path. Speed samples are bounded to ten model-response segments and 256 host/chat entries. Account switches and counter resets clear them. Version/hash gates protect the inspected app patch.

## Acceptance evidence

- Unit checks: weekly window slots, unknown versus zero, current-context totals, timing aggregation, duplicate events, account isolation, portal cleanup and warning threshold.
- Isolated renderer checks: existing React, native font sizes 12/14/18/20/24, seven widths from 320 to 1280, 188 px effective reflow, track visibility, native chip corners, absent outer frame, utility-strip spacing, input gap, unknown/zero/expired states, diff click/keyboard, native fallback and retained plan row.
- Candidate checks: unique source anchors, generated-module syntax, archive readback, unchanged unrelated entries, updated archive/header/dictionary/native integrity, preserved fuses, and strict deep signature verification after dependency-ordered signing.
- Pending: installed live account metrics, actual native diff opening and tooltip, native font/theme changes, cloud/remote behavior, and user visual acceptance. A fixture is not proof of these live flows.

## Deferred five-hour usage

Five-hour quota stays in the plan only. A future opt-in implementation selects the existing 300-minute window by duration, retains unknown/reset behavior and native usage color rules, and uses the same responsive and account/model ownership. It belongs between Weekly and token speed in the metric priority; the accepted Files changed slot remains adjacent to Weekly. Final ordering and enablement need an explicit future product decision. No five-hour pill or reset icon is rendered now.

## Delivery and recovery

One exact `Safe Build` and one replaceable `New Build`, both local and excluded from Git. Build and verify the complete batch before installation. Installation needs an app quit/relaunch boundary; other active chats must be accounted for. Preserve the Safe Build unchanged. New Build retains the complete previous verified mod after promotion; failed startup recovers by atomic exchange to that mod, followed by one recovery launch. A finite independent Terminal worker records installation and process health. Normal user quit/relaunch and native UI acceptance remain separate evidence. Refuse unreviewed app updates. Source publication is a separate Git action.

## Startup and signing prevention

Future desktop-mod builds must follow [Startup And Signing Prevention](Startup%20And%20Signing%20Prevention.md) and the repository's [AGENTS.md](../AGENTS.md). These requirements supersede older startup/signing guidance. Static integrity/signature checks and process health are separate from rendered UI and normal quit/reopen verification of the exact installed app.

Recording the prevention handoff alone does not authorize implementation or restart; later explicit user requests authorize the current implementation and delivery.

## Single-row responsive correction

The latest user instruction forbids wrapping. Actual pill contents, native diff counts, font size and available row width trigger the fitting sequence: progress track shrinks, spacing tightens, compact labels/countdown appear, the speed icon disappears, Weekly disappears, then text reduces within the readable minimum. Context cannot move to a second row. Fitting reruns when native diff content, metrics, font or container size changes. At widths below the irreducible readable content width, only the usage shell scrolls horizontally; all metrics remain on one row and the native composer/page do not overflow. The prevention-note push contained documentation only. Later user instructions authorized implementation and installation; source publication remains separate.


## Public installation entry point

`setup.py` owns one-command Terminal orchestration and compatibility checks; `mod.py` owns candidate construction and atomic exchange; `signing.py` owns separate vendor-source and local-candidate policies; `integrity.py` owns hash/native-digest validation; `install_once.py` owns durable lifecycle receipts and bounded launch/recovery. The install lock spans build through startup. A valid pinned vendor source is accepted without applying ad-hoc entitlement rules to its existing signature. Those vendor claims are removed only in the local candidate. Apps initially closed are supported without signalling PID 0. Build timeout terminates its process group before quitting Codex. A stuck quit cannot trigger replacement. Detailed flow and pending clean-install acceptance are in [Installation](Installation.md).


The latest user-approved chat/composer-width thresholds are Stage 1 at 620 px, Stage 2 at 580 px and Stage 3 at 490 px, all logical CSS pixels. Native composer width determines these triggers, independently of whole-window width and the narrower Goal/Usage rail. Stage 1 removes `left` and extra countdown units; Stage 2 pairs compact token/context labels and hides Weekly; Stage 3 applies readable text caps. Content fitting still prevents wrapping, and restoration has an 8 px buffer. At every fit level, width left after natural content and minimum/standard spacing is split 70% to the track and 30% equally per object gap and horizontal end inset. The repository publishes original source, installer, tests and documentation; app binaries, extracted vendor assets and local operational data are excluded.


## Future stable signing

The current installer uses the tested local ad-hoc signing policy. Preserve account data and existing permissions; never reset TCC, alter trust stores, spoof the vendor identity or grant permissions automatically to hide a prompt. A future optional persistent signing identity should use the user's own certificate, keep the signing identity consistent across updates, verify the same designated requirement across two different builds, and preserve all current integrity/runtime checks. Certificate access, first migration and macOS authorization can still require user interaction; do not advertise zero prompts until tested on actual updates. Keep identity selection and signing receipts local, without publishing personal certificate metadata or private keys. See [Apple TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements).
