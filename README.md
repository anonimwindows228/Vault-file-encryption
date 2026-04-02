# WinVFE (Vault file encryption)

WinVFE is a lightweight, modern encryption utility designed to keep your sensitive files private using AES-256-GCM.

Thank you very much to @Kflone5 for help with UI development!!

<img width="150" height="100" alt="Снимок экрана 2026-04-01 185812" src="https://github.com/user-attachments/assets/fec3f644-752f-436a-a46d-45492652b91c" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185816" src="https://github.com/user-attachments/assets/c7365259-e04f-4388-ad17-9caeb9a29646" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185822" src="https://github.com/user-attachments/assets/6ae54d2b-c98a-48d4-991c-539a520a5fd6" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185827" src="https://github.com/user-attachments/assets/e2516577-63ea-4ef3-bf2a-a4a080946870" />
<img width="150" height="100" alt="Снимок экрана 2026-04-01 185833" src="https://github.com/user-attachments/assets/7533e9b1-756e-4e40-9b17-60f781e72913" />


What's new:

- _Renamed_ to WinVFE (Windows Vault file encryptor).
- _Added_ Blowfish encryption algorithm (decryption too).
- Added zlib compression feature.
- _Added_ zlib decompression feature.
- _Added_ UI changes: Drag & Drop files, Wizard UI slightly changed (combined with info tab).
- _Removed_ minor UI features in order to improve speed and reduce clutter.
- _Added_ files saving with untraceable name instead of previously file name being kept with .vault extension being added.
 
Algorithms:
```
# Encryption

AES-256-GCM
Blowfish-CBC

# Compression

zlib
zstd (coming soon)
lz4 (coming soon)
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
