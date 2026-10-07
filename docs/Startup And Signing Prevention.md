# Startup And Signing Prevention

Recorded 8 October 2026, Asia/Kuala_Lumpur, from the user's confirmed prevention handoff.

This is documentation for future Codex Usage builds. It does not authorize a repair agent, installer, app modification, installation, launch, or restart now. The background repair agent was stopped at the user's request. Bars and UI are outside this note's scope.

## Confirmed failures

The handoff confirms three separate startup failures:

- A rebuilt `app.asar` left the native ASAR integrity digest stale.
- Restricted vendor entitlements on an ad-hoc signature caused AMFI `-424`.
- A launcher/framework signing-team mismatch caused a `dlopen` abort.

Matching archive metadata and passing static signature checks alone are insufficient evidence of a successful normal launch.

## Future build contract

1. Finalize the current ASAR, validate its contents and hashes, and recompute `ElectronAsarIntegrity` from its actual header. Synchronize the native `__asar_integrity` digest **before signing**. Discover the native slot dynamically; reject an ambiguous or unsupported structure. Keep native validation and integrity fuses enabled.

2. For local/ad-hoc signing, remove these unsupported vendor claims from the relevant signing entitlements:

   - `com.apple.application-identifier`
   - `com.apple.developer.aps-environment`
   - `com.apple.developer.team-identifier`
   - `com.apple.security.application-groups`
   - `keychain-access-groups`

   Preserve supported JIT/runtime capabilities. Never spoof OpenAI's identity or reset user data or Keychain. Do not blindly preserve the vendor entitlement set when replacing the vendor signature with a local signature.

3. The user approved `com.apple.security.cs.disable-library-validation=true` **only for locally signed main/helper executable hosts that need to load Codex Framework**. Scope it to those hosts. Preserve Hardened Runtime. Do not change Gatekeeper, quarantine, or system-wide security.

4. Sign changed leaf executables/helpers first, then their containing framework seals, then the main app. Verify each relevant host's expected entitlements, deep/strict signatures, actual ASAR hashes, and matching native digest. Confirm launcher/framework loading compatibility rather than treating a successful `codesign` command as runtime proof.

5. Before declaring a future installation successful, verify a normal launch and rendered UI, then quit and normally reopen the exact installed `/Applications/ChatGPT.app`. A candidate launch, process remaining alive, or static guard cannot substitute for this installed-app verification. Retain the last verified working mod and restore it if the installation fails.

## Evidence and ownership

The dynamic digest helper is `native_integrity_sync.py`; signing/crash evidence and scoped user approval are retained in the local `normal-launch-repair/` investigation. Machine-specific paths and private receipts are omitted from this public note.

This note records the supplied findings and authorization scope; no new runtime verification was performed for it. It supersedes earlier startup guidance that preserves restricted vendor claims during ad-hoc signing or accepts installation based only on static checks/process health. It does not claim that every requirement is implemented in the current builder.

For future work, report build verification, installed-bundle verification, rendered UI verification, and normal installed-app quit/reopen verification separately. Leave authentication and security prompts to the user.
