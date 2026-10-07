# Codex Usage

A planned responsive status bar for the Codex desktop experience.

The bar is intended to show **5-hour usage**, **weekly usage**, **token speed**, and **Context usage**, using dark rounded pills and teal progress bars. Quota countdowns stay visible; reset icons and reset actions are excluded. "Context" is always written in full.

## Status

**Planning stage. No working plugin or installer exists yet.**

Placement above the desktop message box and access to its active-session metrics require a feasibility check. The public Codex app-server exposes relevant account and thread APIs, but that does not prove an ordinary plugin can access the desktop session or extend its composer.

## Plan

- [Architecture and implementation plan](docs/Architecture%20Plan.md)
- [Integration decision](docs/ADR%20001%20Integration.md)

Responsive behavior is part of the initial implementation: keep one row while shrinking progress tracks first, then gaps/padding and text. Wrap only when the content cannot remain readable. Adapt to the bar's available width rather than the screen width.

## References

- [Codex source](https://github.com/openai/codex)
- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Plugin extensions](https://developers.openai.com/plugins/build/extensions)

This is an independent project, not an official OpenAI product. Repository publication does not indicate implementation, installation, or verified desktop integration.
