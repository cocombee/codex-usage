# ADR 001 — Desktop Integration

Status: Proposed; feasibility unresolved.
Date: 7 October 2026.

## Context

Codex Usage should initially display weekly quota, token speed, and Context usage in that order with the supplied reference styling. 5-hour usage stays in the future plan only; if added later, it belongs after weekly and before token speed. Its intended location is inside the Codex desktop app above the message box. Responsive behavior and a public GitHub repository are required. The preferred responsive sequence shrinks progress tracks first, then spacing and text, preserving one row until readable fitting is impossible.

The public app-server provides usage APIs, but API availability does not establish access to the active desktop session or a composer UI extension point.

## Decision

Make integration feasibility the first implementation gate. Keep metrics normalization and presentation independent of the host adapter. No implementation technology is selected until the real hosting and event path is demonstrated.

Do not assume that lifecycle hooks, an MCP tool result, or a separately launched app-server can automatically observe the currently open desktop chat.

## Alternatives

| Option | Advantage | Consequence |
| --- | --- | --- |
| Supported desktop extension | Best maintenance path and intended host | Permanent composer placement and active-session metrics are unverified |
| Plugin conversation panel | Documented UI surface | Changes the intended placement; metrics access still needs verification |
| Companion overlay | Can reproduce visual positioning | Separate process, window tracking, accessibility and overlap problems |
| Separate client using public app-server | Owns its UI and event stream | Replaces the desktop experience rather than extending it |
| Local desktop modification | Might permit exact native placement | Unverified, version-sensitive, and requires a tested backup/recovery route |

## Consequences and evidence required

No option is a working solution yet. A changed placement or separate client requires an explicit product decision. Keep unsupported features visible in the plan instead of reporting a prototype as an installed plugin.

Complete the feasibility slice by recording host version, concrete interfaces, data identity binding, screenshot evidence of placement, and disable/uninstall behavior. Supersede this ADR with the verified chosen route and its tradeoffs before release.

## Sources

- [App Server](https://learn.chatgpt.com/docs/app-server)
- [Plugin extensions](https://developers.openai.com/plugins/build/extensions)
