import io
import json
import os
import struct
import subprocess
import zlib
import lzma

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

try:
    import pyzipper as _pyzipper
    _PYZIPPER_OK = True
except ModuleNotFoundError:
    _PYZIPPER_OK = False

MAGIC      = b"VAULTVZ1"
MAGIC_SIZE = 8
SALT_SIZE  = 32
NONCE_SIZE = 12
ITERATIONS = 600_000

ALGORITHMS = ["zip", "7z", "rar"]


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode())


def _decompress(data: bytes, algorithm: str) -> bytes:
    if algorithm == "7z":
        return lzma.decompress(data, format=lzma.FORMAT_XZ)
    return zlib.decompress(data)


def available_algorithms() -> list[str]:
    return ["zip", "7z", "rar"]


def compress_file(input_path: str, output_path: str,
                  algorithm: str = "zip",
                  password: str = "",
                  metadata: dict | None = None,
                  progress=None,
                  level: str = "best") -> None:
    import zipfile as _zf

    def p(v, m=""): progress and progress(v, m)

    # Map level string to numeric values
    zip_level  = 9 if level == "best" else 6
    lzma_preset = 9 if level == "best" else 6
    rar_method  = "-m5" if level == "best" else "-m3"

    if algorithm == "zip":
        p(0.05, "Reading file…")
        p(0.20, "Compressing with ZIP…")
        if password:
            if not _PYZIPPER_OK:
                raise RuntimeError(
                    "AES-encrypted ZIP requires pyzipper.\n"
                    "Run:  pip install pyzipper")
            with _pyzipper.AESZipFile(output_path, "w",
                                      compression=_pyzipper.ZIP_DEFLATED,
                                      encryption=_pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode("utf-8"))
                p(0.60, "Encrypting & writing…")
                zf.write(input_path, os.path.basename(input_path))
        else:
            with _zf.ZipFile(output_path, "w",
                             _zf.ZIP_DEFLATED, compresslevel=zip_level) as zf:
                zf.write(input_path, os.path.basename(input_path))
        p(1.00, "Done.")
        return

    if algorithm == "7z":
        p(0.05, "Reading file…")
        with open(input_path, "rb") as f:
            raw = f.read()
        p(0.30, "Compressing with LZMA/XZ…")
        compressed = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=lzma_preset)
        p(0.90, "Writing output file…")
        with open(output_path, "wb") as f:
            f.write(compressed)
        p(1.00, "Done.")
        return

    if algorithm == "rar":
        p(0.10, "Compressing with RAR…")
        cmd = ["rar", "a", rar_method, "-ep", output_path, input_path]
        try:
            result = subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            raise RuntimeError(
                "rar.exe not found. Make sure WinRAR is installed and rar.exe "
                "is on your PATH (e.g. C:\\Program Files\\WinRAR\\).")
        if result.returncode not in (0, 1):
            err = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"WinRAR error (code {result.returncode}):\n{err}")
        p(1.00, "Done.")
        return

    raise ValueError(f"Unsupported algorithm: {algorithm!r}. Use 'zip', '7z', or 'rar'.")


def decompress_file(input_path: str, output_dir: str,
                    password: str = "",
                    progress=None) -> tuple[str, dict]:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        header = f.read(MAGIC_SIZE)

    if header[:4] == b"PK\x03\x04" or input_path.lower().endswith(".zip"):
        p(0.20, "Detected ZIP archive…")
        from crypto import safe_output_path
        extracted = []

        if _PYZIPPER_OK:
            opener = _pyzipper.AESZipFile(input_path, "r")
        else:
            import zipfile as _zf
            opener = _zf.ZipFile(input_path, "r")

        with opener as zf:
            if password:
                zf.setpassword(password.encode("utf-8"))
            names = zf.namelist()
            for i, name in enumerate(names):
                p(0.20 + 0.75 * i / max(len(names), 1), f"Extracting {name}…")
                out_path = safe_output_path(os.path.join(output_dir, name))
                with zf.open(name) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                extracted.append(out_path)
        p(1.00, "Done.")
        first = extracted[0] if extracted else output_dir
        return first, {"algorithm": "zip", "files": len(extracted)}

    if header[:6] == b"\xfd7zXZ\x00" or input_path.lower().endswith(".7z"):
        p(0.20, "Detected 7z/XZ archive…")
        from crypto import safe_output_path
        with open(input_path, "rb") as f:
            raw = lzma.decompress(f.read(), format=lzma.FORMAT_XZ)
        import zipfile as _zf
        if raw[:4] == b"PK\x03\x04":
            extracted = []
            with _zf.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
                for i, name in enumerate(names):
                    p(0.60 + 0.35 * i / max(len(names), 1), f"Extracting {name}…")
                    out_path = safe_output_path(os.path.join(output_dir, name))
                    with zf.open(name) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    extracted.append(out_path)
            p(1.00, "Done.")
            return extracted[0] if extracted else output_dir, \
                   {"algorithm": "7z", "files": len(extracted)}
        else:
            out_name = os.path.splitext(os.path.basename(input_path))[0]
            out_path = safe_output_path(os.path.join(output_dir, out_name))
            p(0.90, "Writing output file…")
            with open(out_path, "wb") as f:
                f.write(raw)
            p(1.00, "Done.")
            return out_path, {"algorithm": "7z"}

    if header[:MAGIC_SIZE] != MAGIC:
        raise ValueError("Unsupported file format. Supported: .zip, .7z, .vz")

    p(0.10, "Reading .vz file…")
    with open(input_path, "rb") as f:
        data = f.read()

    offset   = MAGIC_SIZE
    meta_len = struct.unpack_from("<I", data, offset)[0]
    offset  += 4
    meta     = json.loads(data[offset: offset + meta_len].decode("utf-8"))
    offset  += meta_len
    payload  = data[offset:]

    algorithm     = meta.get("algorithm", "zlib")
    encrypted     = meta.get("encrypted", False)
    original_name = meta.get("original_name",
                             os.path.splitext(os.path.basename(input_path))[0])

    if encrypted:
        if not password:
            raise ValueError("This archive is encrypted — please enter a password.")
        salt  = payload[:SALT_SIZE]
        nonce = payload[SALT_SIZE: SALT_SIZE + NONCE_SIZE]
        ct    = payload[SALT_SIZE + NONCE_SIZE:]
        key   = _derive_key(password, salt)
        p(0.60, "Decrypting…")
        try:
            compressed = AESGCM(key).decrypt(nonce, ct, None)
        except InvalidTag:
            raise ValueError("Wrong password, or the file has been tampered with.")
    else:
        compressed = payload

    p(0.80, f"Decompressing ({algorithm})…")
    try:
        raw = _decompress(compressed, algorithm)
    except Exception as exc:
        raise ValueError(f"Decompression failed: {exc}") from exc

    from crypto import safe_output_path
    out_path = safe_output_path(os.path.join(output_dir, original_name))
    p(0.95, "Writing output file…")
    with open(out_path, "wb") as f:
        f.write(raw)
    p(1.00, "Done.")
    return out_path, meta


def read_metadata(input_path: str) -> dict:
    with open(input_path, "rb") as f:
        header = f.read(MAGIC_SIZE + 4)
    if header[:4] == b"PK\x03\x04" or input_path.lower().endswith(".zip"):
        import zipfile as _zf
        try:
            with _zf.ZipFile(input_path) as zf:
                names = zf.namelist()
        except Exception:
            names = []
        return {"algorithm": "zip",
                "original_name": os.path.basename(input_path),
                "original_size": os.path.getsize(input_path),
                "files": names}
    if header[:6] == b"\xfd7zXZ\x00" or input_path.lower().endswith(".7z"):
        return {"algorithm": "7z",
                "original_name": os.path.basename(input_path),
                "original_size": os.path.getsize(input_path)}
    if header[:MAGIC_SIZE] != MAGIC:
        raise ValueError("Unsupported file format.")
    meta_len = struct.unpack_from("<I", header, MAGIC_SIZE)[0]
    with open(input_path, "rb") as f:
        f.seek(MAGIC_SIZE + 4)
        raw = f.read(meta_len)
    return json.loads(raw.decode("utf-8"))
