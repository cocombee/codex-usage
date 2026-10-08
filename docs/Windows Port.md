# Windows Port

Windows support is unfinished. The current Codex Usage Bar installer supports only its inspected Apple Silicon macOS build. Run this port and its installation tests on the Windows PC before advertising a usable Windows release. The browser UI modules can be reused, but the macOS app layout, source hashes, native integrity parser, signing and installation code cannot establish Windows compatibility.

## Official package

OpenAI distributes the Windows desktop app through the Microsoft Store and provides Store-signed x64 and Arm64 MSIX downloads. Its deployment guide says standalone MSI and non-Store EXE packages are unavailable. Use the [official Windows setup](https://learn.chatgpt.com/docs/windows/windows-app) and [Windows deployment guide](https://learn.chatgpt.com/docs/enterprise/windows-deployment) to obtain the app appropriate for the PC.

The official x64 download headers inspected on 8 October 2026 reported package identity `OpenAI.Codex` and version `26.930.7945.0`. This was metadata inspection only: the Windows package contents were not downloaded or verified, and those latest-download links can change. Discover the actual installed version below.

## Read-only discovery on the Windows PC

Open PowerShell under the account that installed the app. These commands inspect installation metadata and filenames; they do not launch, close, patch or reinstall the app:

```powershell
$packages = @(Get-AppxPackage -Name 'OpenAI.Codex')
$packages | Select-Object Name, Version, Architecture, PackageFamilyName, InstallLocation
if ($packages.Count -ne 1) {
    throw 'Expected one current-user OpenAI.Codex package. Inspect this installation before proceeding.'
}
$codexPackage = $packages[0]
Get-AppxPackageManifest -Package $codexPackage.PackageFullName
Get-ChildItem -LiteralPath $codexPackage.InstallLocation -Recurse -File -Filter 'app.asar' |
    Select-Object FullName, Length
```

An access error is a discovery result. Do not take ownership of WindowsApps, change its ACLs or bypass policy to continue. Do not collect account data, credentials, chat history or the whole user profile. Keep package copies, extracted vendor code and diagnostic reports local and excluded from Git; share only the minimum relevant metadata after reviewing it.

## Implementation gates

1. Inspect the actual manifest, architecture, app executable, ASAR and unpacked native resources. Record exact version and hashes. Verify the source package signature on Windows. Locate the renderer assets and validate every patch anchor and host binding against this Windows build.
2. Inspect the enabled Electron fuses and embedded ASAR integrity metadata. Electron documents a Windows executable resource of type `Integrity`, named `ElectronAsar`; its ASAR header hash must agree with the rebuilt archive. Inspect this app for additional validation instead of assuming the macOS native digest format applies. Keep validation enabled. See [Electron ASAR integrity](https://www.electronjs.org/docs/latest/tutorial/asar-integrity).
3. Design a legitimate Windows packaging/signing route before modifying an installation. MSIX signatures cover package contents, and Windows can enforce runtime package integrity. Replacing `app.asar` inside a Store installation is not a complete installation strategy. Do not spoof OpenAI's publisher, disable integrity checks or silently change certificate trust/security policy. See [MSIX signing](https://learn.microsoft.com/en-us/windows/msix/package/sign-app-package-using-signtool) and [package integrity enforcement](https://learn.microsoft.com/en-us/windows/msix/desktop/tamper-protection).
4. Implement a separate Windows backend for discovery, locking, process identity, bounded cancellation, backup, deployment, rollback and launch verification. Preserve the original app and user data. Reject unknown builds before mutation. Keep macOS behavior covered by its existing tests.

## Acceptance and continuation

Clone this repository on the Windows PC and start a Codex chat in that checkout. Ask it to continue this document's discovery and porting gates using the actual installed package. Source review and pure JavaScript tests can proceed immediately; the current macOS installer and render harness are not Windows installation tests.

A Windows release requires evidence for a clean install, duplicate-install rejection, interrupted/failed deployment and recovery, exact installed-build launch, rendered native row, live metrics, native diff interaction and normal quit/reopen. Check narrow widths, font changes and Windows display scaling. Record tested Windows version, app version, architecture and distribution route. Passing source or synthetic tests alone does not establish supported Windows installation.
