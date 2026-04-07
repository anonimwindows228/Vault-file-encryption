# WinVFE (Vault file encryption)

WinVFE is a lightweight, modern encryption utility designed to keep your sensitive files private using AES-256-GCM.

Thank you very much to @Kflone5 for help with UI development!!

<img width="150" height="100" alt="Снимок экрана 2026-04-01 185812" src="https://github.com/user-attachments/assets/fec3f644-752f-436a-a46d-45492652b91c" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185816" src="https://github.com/user-attachments/assets/c7365259-e04f-4388-ad17-9caeb9a29646" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185822" src="https://github.com/user-attachments/assets/6ae54d2b-c98a-48d4-991c-539a520a5fd6" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185827" src="https://github.com/user-attachments/assets/e2516577-63ea-4ef3-bf2a-a4a080946870" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185833" src="https://github.com/user-attachments/assets/7533e9b1-756e-4e40-9b17-60f781e72913" />

Lates version:

**WinVFE v1.5.1**

_06.04.2026_

### New features
- **Right-click context menu** - Encrypt, Decrypt, Compress, Decompress with WinVFE now appear when right-clicking any file in Windows Explorer. Installed automatically via the Inno Setup installer.
- **Windows installer** - `WinVFE_Setup_v1.5.1.exe` built with Inno Setup. Installs to Program Files, writes registry keys, creates Start Menu and desktop shortcuts, includes a working uninstaller.
- **Encrypted ZIP support** - ZIP archives can now be password-protected using AES-256 encryption via `pyzipper`. Requires `pip install pyzipper`.
- **Open folder button** -After any compress/encrypt/decrypt operation, a button appears next to the result label to open the output folder directly in Explorer.
- **Progress popup** -Replaced the inline progress bar with a progress bar that appears during long operations.
- **Wizard** - Now wizard features app information.
- **New versions** - WinVFE now features new version checker, which will trigger a pop up if new release published on github.

**Compression changes**
- Removed the custom `.vz` format from the Compress tab -Compress now produces real `.zip` or `.7z` files that open in any archive tool.
- `.vz` files can still be decompressed (legacy support kept in `decompress_file`).
- Removed zlib, zstd, lz4 algorithm options from the Compress tab.
- Removed the metadata note feature from the Compress tab.

### Bug fixes
- Decompress browse filter now accepts `.zip` and `.7z` in addition to `.vz`.
- Multi-file ZIP compression no longer double-wraps (was bundling into a temp zip then recompressing into `.vz`).
- Output filenames now use the correct extension (`.zip` / `.7z`) instead of always `.vz`.
 
Algorithms:
```
# Encryption

AES-256-GCM
Blowfish-CBC

# Compression

zip
7z
vz
```


Beutiful UI: A clean interface with an easily navigatable and aesthetic UI, includes a wizard.

Portable: Available as a single standalone .exe for Windows.

Encrypt: Select a file, enter a strong password, and click "Encrypt File". This creates a .vault version of your file.
Decrypt: Select your .vault file, enter the original passphrase, and click "Decrypt File" to recover your data.

```
Language: Python 3.10_
Library: Tkinter / Cryptography_
Release Date: 29.03.2026_
```
