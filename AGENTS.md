# Codex Usage Bar Project Instructions

## Startup and signing prevention

Read [Startup And Signing Prevention](docs/Startup%20And%20Signing%20Prevention.md) before future desktop-mod build, signing, installation, or recovery work. These requirements supersede older startup guidance.

- Finalize and validate ASAR contents, recompute `ElectronAsarIntegrity`, and dynamically synchronize the native `__asar_integrity` digest before signing. Preserve validation and integrity fuses.
- For local/ad-hoc signing, remove unsupported vendor claims: `com.apple.application-identifier`, `com.apple.developer.aps-environment`, `com.apple.developer.team-identifier`, `com.apple.security.application-groups`, and `keychain-access-groups`. Preserve supported JIT/runtime capabilities and Hardened Runtime; never spoof OpenAI's identity.
- Scope the user-approved `com.apple.security.cs.disable-library-validation=true` to locally signed main/helper executable hosts that need to load Codex Framework. Do not change Gatekeeper, quarantine, or system-wide security.
- Sign changed leaves/helpers, then containing framework seals, then the main app. Verify expected entitlements, deep/strict signatures, actual ASAR hashes, native digest, and launcher/framework loading compatibility.
- Require rendered UI and normal quit/reopen verification of the exact installed `/Applications/ChatGPT.app` before claiming installation success. Retain the last verified working mod and restore it if installation fails. Preserve user data and Keychain.

This prevention handoff authorizes documentation only. Do not start a repair agent, alter bars/UI, build an installer, install, launch, or restart the app merely to record or publish this note. Further implementation requires a user request.
