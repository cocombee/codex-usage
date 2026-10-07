# Codex Usage Handoff

Continue this work in the existing Codex Usage project. This handoff records outstanding requirements; it does not claim the fixes are implemented.

## Weekly bar accuracy

The fill and the label must represent the same quantity: **quota remaining**.

Acceptance example: if the label says `91% left`, the filled portion must occupy 91% of the track, not 9%. Derive both from the same remaining-quota value. Preserve honest unknown and expired states rather than inventing zero or a reset.

The existing local implementation derives the label from remaining quota and the fill from consumed quota. Correct that inconsistency and update the associated tests and documentation.

## Warning colors

The requested critical threshold is **red at 10% remaining or below**.

A proposed warning threshold is **yellow above 10% through 20% remaining**, with the normal theme color above 20%. The yellow threshold is a recommendation to confirm, not a verified native OpenAI rule.

The existing local implementation has no yellow state and uses red below 20% remaining. Check exact boundaries, neighboring values, zero, and unknown data. Reuse the app's semantic color tokens.

## Layout and padding

The user's final correction is:

1. Usage row at the top.
2. Native Goal and create/check/select-folder or Apps/This computer controls beneath it.
3. Chat composer beneath the native controls.

Keep the native controls attached to the composer as their design intends. Preserve the existing padding, insets, typography, and geometry. Usage must not sit between a native bar and the composer. Prevent overlap when controls appear, disappear, animate, or wrap.

Preserve Files changed behavior and native actions. Verify wide and narrow windows, Goal present/absent, native controls present/absent, and transitions.

## Prevent recurring restart errors

A modified Electron archive can fail at startup when archive integrity metadata and the embedded native integrity digest are inconsistent. Updating only the archive or its header metadata is insufficient.

Update the build/install pipeline to:

- Finalize and validate the modified archive.
- Synchronize the archive integrity metadata and embedded native digest before signing.
- Locate binary structures dynamically rather than writing to a copied hardcoded offset.
- Preserve integrity validation and security protections.
- Sign and validate the completed bundle in dependency order.
- Reject an inconsistent candidate before replacing the installed app.
- Retain a verified working build and recover transactionally after a failed installation.
- Verify the exact installed app through an ordinary quit-and-relaunch, not just a separate candidate launch.

Preserve the protected backup, the user's usage mod, and user data. Do not claim complete restart recovery until normal relaunch verification passes.

## Completion evidence

Report source changes, focused tests, rendered layout/color checks, candidate verification, installed verification, and normal restart verification separately. No code changes were made by the handoff sender.

The detailed machine-specific investigation remains in the local project handoff. This public version omits private paths, process identifiers, account information, and security fingerprints.
