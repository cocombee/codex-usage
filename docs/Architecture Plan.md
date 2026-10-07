# Codex Usage — Architecture Plan

Status: Proposed; research and planning only.
Updated: 7 October 2026.

## Intended behavior

Display a persistent usage bar in the Codex desktop experience, preferably above the message box. Preserve the reference's dark rounded container, pill shapes, muted labels, brighter numeric values, teal quota progress bars, and lightning indicator for speed.

The user's latest direction keeps 5-hour usage in the future plan only. It is omitted from the initial display, including any empty placeholder. This supersedes the earlier plan that included it in the initial bar.

Initial order: week, lightning tok/s, Context.
Future order if 5-hour usage is added: week, 5h, lightning tok/s, Context.
The weekly pill shows percentage used and time until reset; a future 5h pill would do the same. Omit all reset icons and reset actions. Always spell Context in full. A percentage represents used quota, not remaining quota.

## Verified foundations and unresolved dependencies

The public Codex repository contains app-server implementation. Official documentation provides account/rateLimits/read, account/rateLimits/updated, and thread/tokenUsage/updated. These are integration building blocks, not evidence of access from an ordinary plugin to the current desktop session.

Documented plugin UI surfaces include conversation panels and composer mentions. No permanent above-composer status-bar slot has been established. Do not call an implementation a native desktop plugin until its actual placement and data flow are exercised.

Before selecting a stack, inspect the target desktop version and demonstrate:
1. A supported or clearly characterized UI hosting path.
2. Read-only access to the intended signed-in account.
3. Accurate active-chat identification and event subscription.
4. An uninstall/recovery path.
5. Compatibility with host security boundaries.

A side panel, companion overlay, or separate open-source client changes the requested placement or product. Keep these alternatives in the ADR; do not silently substitute them.

## Module boundaries

| Module | Ownership | Dependencies |
| --- | --- | --- |
| Host adapter | Connection lifecycle, active account/chat binding, capabilities and raw events | Verified host interface |
| Quota adapter | Normalize account quota windows and reset timestamps | Host adapter |
| Thread metrics adapter | Current context and speed evidence for one chat/response | Host adapter and verified event schema |
| Metrics store | Read-only snapshots, freshness, identity isolation and derived presentation values | Both metric adapters |
| Status bar | Rendering, layout, accessibility and countdown presentation | Metrics store |
| Packaging | Installation, compatibility detection, disable/uninstall and release documentation | Chosen host integration |

Keep one small local integration. No database, hosted backend, or independently deployed service is planned.

## Data contract

Each snapshot includes a session-local account key, optional thread and turn identifiers, observedAt, sourceVersion, and per-metric availability: loading, available, stale, unavailable, or error. Unknown values are null; zero is a real reported value.

QuotaWindow contains the source bucket identity, windowDurationMins, usedPercent, and resetsAt. Select the appropriate account bucket explicitly; prefer rateLimitsByLimitId when present. For the initial release, match the weekly 10080-minute window by duration. Reserve matching a 300-minute window for the deferred 5h feature; do not assume primary always means 5h. If the expected duration is absent, show unavailable or the actual supported duration rather than relabeling another quota. The initial view does not render the deferred 5h field.

Display bars between 0 and 100%; preserve the raw source value for diagnostics. Reject malformed or negative values. Calculate countdown from the source reset timestamp and the current clock, using a known service-clock offset only when supplied. At expiry show Updating until fresh quota arrives; reaching a timestamp alone never proves the quota has reset.

ContextMetric contains the current effective context token count, verified usable context capacity, threadId, and basis. Establish the exact source fields and capacity semantics before calculating a percentage. Lifetime/account totals and cumulative pre-compaction tokens cannot stand in for current context. Rebind after compaction, model changes, and chat switches.

SpeedMetric contains turnId, output token count, measured interval, and basis: measured or estimated. Verify which generation interval and token counters are available. Do not present character counts or tool-runtime averages as exact token speed. If exact timing is unavailable, clearly label any validated estimate with an approximation marker; otherwise show a dash. Define idle and interrupted-turn behavior before enabling the live speed pill.

HostAdapter exposes connect, disconnect, readAccountLimits, subscribeAccountLimits, and subscribeThreadMetrics. These are proposed internal interfaces, not claims that the desktop exposes corresponding plugin APIs.

## Refresh, persistence, and recovery

Read quotas on connection and refresh from events. If polling is necessary, use a bounded fallback such as 60 seconds while visible, plus a debounced refresh on focus/reconnect; honor rate limits and back off on errors. Update displayed countdowns locally without making a network request per tick. Render stream metrics at a bounded rate.

Clear account-specific state immediately on account change or logout. Clear thread-specific values before subscribing to a different chat. Ignore late events that belong to the previous account, chat, or turn. Mark interrupted connections stale; reconnect, re-read, and re-subscribe before returning to available.

Keep authoritative metrics in memory. Persist only versioned presentation preferences if needed. Never persist tokens or private chat content in this repository, screenshots, frontend bundles, or diagnostic logs. Use the host's supported authentication boundary; do not extract browser cookies or assume access to desktop credentials.

No user-data migration is planned. If settings are introduced, add versioned defaults and a tested fallback for unreadable older settings. Disabling or uninstalling must remove only this integration and preserve chats and credentials. App modification, if later selected explicitly, needs a verified backup and rollback design before installation.

## Responsive design contract

Use the status bar's container width, not the full display width. An open sidebar or panel can leave a narrow composer on a large monitor. Prefer container queries or an equivalent native layout mechanism after the hosting technology is verified.

The latest user preference supersedes the initial medium two-column and narrow stacked layouts: shrink in place first, progressing from bar shrinking to text shrinking.

Preferred fitting sequence:
1. Keep all three initial pills on one row (four only if the future 5h feature is enabled) and let the outer bar follow the available composer/container width.
2. Let the weekly progress track shrink first (and the 5h track if added later). Their visual width is flexible; percentage and countdown text remain visible. At extreme widths the track may collapse while retaining textual and accessible usage information.
3. Reduce gaps and pill padding proportionally.
4. Reduce text size smoothly within a readable range, initially targeting approximately 16 CSS px down to 12 CSS px. Preserve full labels, percentages, units and countdowns.
5. Wrap only when a single row cannot fit at readable text size and minimum spacing, or when accessibility text scaling requires reflow. This is a last-resort fallback, not an automatic medium-width layout.

Keep order stable. Never truncate Context to ctx or hide a metric's value/countdown. Use tabular numerals so digit changes do not cause avoidable movement. Do not scale the entire component with a CSS transform: the component's measured layout must actually fit its container.

Choose fitting thresholds from rendered measurements with the longest valid content, rather than untested fixed breakpoints. Recompute on container resize and text scaling; prefer container queries and flexible layout where possible, and avoid resize-observer feedback loops. Preserve a clear layout contract that works without hover.

Start with approximately #222 outer surface, #333 pill surface, #555 track, #73BFC1 fill, muted gray labels and near-white values. Treat these as reference-matching targets; verify contrast in the final host theme. Keep generous rounded corners and proportionate spacing, reducing padding before reducing readable text size.

Use normal-flow layout in a supported host. The bar must not cover the editor, send button, attachments, menus, voice controls, or text selection. Preserve keyboard navigation and focus. Add accessible metric labels, progress semantics, and explanatory tooltip/focus text where useful. Avoid announcing every countdown tick to screen readers. Avoid essential hover-only information and respect reduced motion.

## Implementation slices and acceptance

1. Feasibility spike — demonstrate the intended account/chat binding, hosting position, and one real quota response. Record actual interfaces and unsupported capabilities in the ADR. Stop choosing an implementation stack until this dependency is resolved.
2. Quotas — connect the real account data, normalize the weekly window, and verify percentage semantics and countdown rollover.
3. Responsive UI — build the reference design against clearly fictional fixtures, exercise wide and narrow fitting stages, and retain all metrics without overflow.
4. Thread metrics — add only verified context and token-speed calculations; demonstrate compaction and chat-switch behavior.
5. Composition — exercise the actual host, real reads, disconnect/reconnect, account switching, stale events, and disable/uninstall.
6. Deferred 5h usage — retain its data contract and future position after weekly, but implement/render it only in a later expressly requested feature slice.
7. Public release — document supported hosts and versions, installation and rollback, known limitations, and the chosen license. Public repository creation is authorized; application publishing or installation is not implied by this planning request.

Acceptance evidence must include 320, 375, 480, 768, 900, and 1280 px container widths, intermediate widths around each content-fitting threshold, a narrow composer with the sidebar open, and 200% text/browser zoom where supported. Confirm tracks shrink before text and wrapping is used only after the readable one-row layout cannot fit. Check initial order weekly → speed → Context, absence of a 5h pill/placeholder, and the future reserved order weekly → 5h → speed → Context. Check 0%, 100%, missing/error/stale data, long countdowns, and changing digits. Verify no horizontal overflow, cropped labels, hidden countdowns, or obstruction of composer controls.

Adapter tests cover malformed payloads, swapped window order, extra quota buckets, reset expiry, clock changes, reconnect, and identity isolation. Integration checks must show UI values agreeing with the authoritative source. A fixture or passing unit test alone cannot establish desktop integration.

## Public repository boundaries

Repository name: codex-usage. Display name: Codex Usage.
Initial feature set: weekly usage, token speed, Context. 5-hour usage is planned only and absent from the initial UI.
Start with this plan and a README that clearly says planning stage. Publish only project-owned source and documentation; exclude credentials, account identifiers, private transcripts, machine paths, and local caches. Select and record a license before describing released code as licensed open source.

## Sources

- [Codex repository](https://github.com/openai/codex)
- [Open-source components](https://learn.chatgpt.com/docs/open-source)
- [App Server protocol and usage endpoints](https://learn.chatgpt.com/docs/app-server)
- [Plugin extensions and supported UI surfaces](https://developers.openai.com/plugins/build/extensions)
