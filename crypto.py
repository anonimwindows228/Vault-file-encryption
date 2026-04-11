import os
import struct
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.exceptions import InvalidTag

SALT_SIZE  = 32
NONCE_SIZE = 12
ITERATIONS = 600_000

LARGE_FILE_THRESHOLD = 256 * 1024 * 1024

_MAGIC_AES    = b"VAULTAE2"   # AES-256-GCM  v2
_MAGIC_CHACHA = b"VAULTCH1"   # ChaCha20-Poly1305
_MAGIC_AES_V1 = b"VAULTAES"   # AES-256-GCM  v1 (legacy read only)
MAGIC_SIZE = 8

ENCRYPT_ALGORITHMS = ["AES-256-GCM", "ChaCha20-Poly1305"]


# Key deruvation

def _derive_aes_key(password: str, salt: bytes, length: int = 32) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=length,
                     salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode())


def derive_key(password: str, salt: bytes) -> bytes:

    return _derive_aes_key(password, salt)

def _encode_filename(name: str) -> bytes:
    encoded = name.encode("utf-8")[:255]
    return struct.pack("<H", len(encoded)) + encoded


def _decode_filename(data: bytes, offset: int):
    length = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    name = data[offset: offset + length].decode("utf-8", errors="replace")
    return name, offset + length


# Output path

def safe_output_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def encrypt_file(input_path: str, output_path: str, password: str,
                 progress=None, algorithm: str = "AES-256-GCM"):

    if algorithm == "ChaCha20-Poly1305":
        _encrypt_chacha(input_path, output_path, password, progress)
    else:
        _encrypt_aes(input_path, output_path, password, progress)


def decrypt_file(input_path: str, output_dir: str, password: str,
                 progress=None, algorithm: str | None = None) -> str:

    with open(input_path, "rb") as f:
        magic = f.read(MAGIC_SIZE)

    if magic == _MAGIC_CHACHA:
        return _decrypt_chacha(input_path, output_dir, password, progress)
    # default: AES-256-GCM (covers _MAGIC_AES, _MAGIC_AES_V1, and bare-salt legacy)
    return _decrypt_aes(input_path, output_dir, password, progress, magic)


# AES algorithm

def _encrypt_aes(input_path, output_path, password, progress):
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        plaintext = f.read()

    p(0.15, "Generating salt & nonce…")
    salt  = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key   = _derive_aes_key(password, salt)

    p(0.80, "Encrypting…")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

    p(0.95, "Writing output file…")
    fname_bytes = _encode_filename(os.path.basename(input_path))
    with open(output_path, "wb") as f:
        f.write(_MAGIC_AES + fname_bytes + salt + nonce + ciphertext)

    p(1.00, "Done.")


def _decrypt_aes(input_path, output_dir, password, progress, magic: bytes) -> str:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        data = f.read()

    offset = MAGIC_SIZE

    if magic == _MAGIC_AES:
        original_name, offset = _decode_filename(data, offset)
        salt       = data[offset: offset + SALT_SIZE]
        nonce      = data[offset + SALT_SIZE: offset + SALT_SIZE + NONCE_SIZE]
        ciphertext = data[offset + SALT_SIZE + NONCE_SIZE:]
    elif magic == _MAGIC_AES_V1:
        original_name = os.path.splitext(os.path.basename(input_path))[0]
        salt       = data[offset: offset + SALT_SIZE]
        nonce      = data[offset + SALT_SIZE: offset + SALT_SIZE + NONCE_SIZE]
        ciphertext = data[offset + SALT_SIZE + NONCE_SIZE:]
    else:
        # very old bare-salt format
        original_name = os.path.splitext(os.path.basename(input_path))[0]
        salt       = data[0: SALT_SIZE]
        nonce      = data[SALT_SIZE: SALT_SIZE + NONCE_SIZE]
        ciphertext = data[SALT_SIZE + NONCE_SIZE:]

    out_path = safe_output_path(os.path.join(output_dir, original_name))
    key = _derive_aes_key(password, salt)

    p(0.80, "Decrypting & verifying…")
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("Wrong password, or the file has been tampered with.")

    p(0.95, "Writing output file…")
    with open(out_path, "wb") as f:
        f.write(plaintext)

    p(1.00, "Done.")
    return out_path

# Poly algortihm

def _encrypt_chacha(input_path, output_path, password, progress):
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        plaintext = f.read()

    p(0.15, "Generating salt & nonce…")
    salt  = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key   = _derive_aes_key(password, salt, length=32)

    p(0.80, "Encrypting with ChaCha20-Poly1305…")
    ciphertext = ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)

    p(0.95, "Writing output file…")
    fname_bytes = _encode_filename(os.path.basename(input_path))
    with open(output_path, "wb") as f:
        f.write(_MAGIC_CHACHA + fname_bytes + salt + nonce + ciphertext)

    p(1.00, "Done.")


def _decrypt_chacha(input_path, output_dir, password, progress) -> str:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        data = f.read()

    offset = MAGIC_SIZE
    original_name, offset = _decode_filename(data, offset)
    salt       = data[offset: offset + SALT_SIZE]
    nonce      = data[offset + SALT_SIZE: offset + SALT_SIZE + NONCE_SIZE]
    ciphertext = data[offset + SALT_SIZE + NONCE_SIZE:]

    out_path = safe_output_path(os.path.join(output_dir, original_name))
    key = _derive_aes_key(password, salt, length=32)

    p(0.80, "Decrypting & verifying (ChaCha20-Poly1305)…")
    try:
        plaintext = ChaCha20Poly1305(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("Wrong password, or the file has been tampered with.")

    p(0.95, "Writing output file…")
    with open(out_path, "wb") as f:
        f.write(plaintext)

    p(1.00, "Done.")
    return out_path
