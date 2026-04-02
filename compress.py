import io
import json
import os
import struct
import zlib

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

try:
    import zstandard as zstd
    _ZSTD_OK = True
except ModuleNotFoundError:
    _ZSTD_OK = False

try:
    import lz4.frame as _lz4
    _LZ4_OK = True
except ModuleNotFoundError:
    _LZ4_OK = False

MAGIC      = b"VAULTVZ1"
MAGIC_SIZE = 8
SALT_SIZE  = 32
NONCE_SIZE = 12
ITERATIONS = 600_000

ALGORITHMS = ["zlib", "zstd", "lz4"]

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode())

def _compress(data: bytes, algorithm: str) -> bytes:
    if algorithm == "zstd":
        if not _ZSTD_OK:
            raise RuntimeError("zstandard not installed — run: pip install zstandard")
        return zstd.ZstdCompressor(level=9).compress(data)
    if algorithm == "lz4":
        if not _LZ4_OK:
            raise RuntimeError("lz4 not installed — run: pip install lz4")
        return _lz4.compress(data, compression_level=_lz4.COMPRESSIONLEVEL_MAX)
    return zlib.compress(data, level=9)


def _decompress(data: bytes, algorithm: str) -> bytes:
    if algorithm == "zstd":
        if not _ZSTD_OK:
            raise RuntimeError("zstandard not installed — run: pip install zstandard")
        return zstd.ZstdDecompressor().decompress(data)
    if algorithm == "lz4":
        if not _LZ4_OK:
            raise RuntimeError("lz4 not installed — run: pip install lz4")
        return _lz4.decompress(data)
    return zlib.decompress(data)


def available_algorithms() -> list[str]:
    out = ["zlib"]
    if _ZSTD_OK: out.append("zstd")
    if _LZ4_OK:  out.append("lz4")
    return out

def compress_file(input_path: str, output_path: str,
                  algorithm: str = "zlib",
                  password: str = "",
                  metadata: dict | None = None,
                  progress=None) -> None:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        raw = f.read()

    meta = {
        "original_name": os.path.basename(input_path),
        "original_size": len(raw),
        "algorithm":     algorithm,
        "encrypted":     bool(password),
    }
    if metadata:
        meta.update(metadata)

    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    meta_len   = struct.pack("<I", len(meta_bytes))   # 4-byte LE

    p(0.20, f"Compressing with {algorithm}…")
    compressed = _compress(raw, algorithm)

    if password:
        p(0.60, "Deriving key — this takes a moment…")
        salt  = os.urandom(SALT_SIZE)
        nonce = os.urandom(NONCE_SIZE)
        key   = _derive_key(password, salt)
        p(0.80, "Encrypting compressed data…")
        payload = salt + nonce + AESGCM(key).encrypt(nonce, compressed, None)
    else:
        payload = compressed

    p(0.95, "Writing output file…")
    with open(output_path, "wb") as f:
        f.write(MAGIC + meta_len + meta_bytes + payload)

    p(1.00, "Done.")


def decompress_file(input_path: str, output_dir: str,
                    password: str = "",
                    progress=None) -> tuple[str, dict]:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        data = f.read()

    if data[:MAGIC_SIZE] != MAGIC:
        raise ValueError("Not a valid .vz file (unrecognised magic bytes).")

    offset   = MAGIC_SIZE
    meta_len = struct.unpack_from("<I", data, offset)[0]
    offset  += 4
    meta     = json.loads(data[offset: offset + meta_len].decode("utf-8"))
    offset  += meta_len
    payload  = data[offset:]

    algorithm     = meta.get("algorithm", "zlib")
    encrypted     = meta.get("encrypted", False)
    original_name = meta.get("original_name", os.path.splitext(
                                os.path.basename(input_path))[0])

    if encrypted:
        if not password:
            raise ValueError("This archive is encrypted — please enter a password.")
        p(0.20, "Deriving key — this takes a moment…")
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
    if header[:MAGIC_SIZE] != MAGIC:
        raise ValueError("Not a valid .vz file.")
    meta_len = struct.unpack_from("<I", header, MAGIC_SIZE)[0]
    with open(input_path, "rb") as f:
        f.seek(MAGIC_SIZE + 4)
        raw = f.read(meta_len)
    return json.loads(raw.decode("utf-8"))