import os
import struct
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

try:
    from Cryptodome.Cipher import Blowfish as _Blowfish
    from Cryptodome.Util.Padding import pad as _pad, unpad as _unpad
except ModuleNotFoundError:
    try:
        from Crypto.Cipher import Blowfish as _Blowfish
        from Crypto.Util.Padding import pad as _pad, unpad as _unpad
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Blowfish support requires pycryptodomex or pycryptodome.\n"
            "Run:  pip install pycryptodomex"
        ) from exc

SALT_SIZE  = 32
NONCE_SIZE = 12
BF_IV_SIZE = 8
ITERATIONS = 600_000

LARGE_FILE_THRESHOLD = 256 * 1024 * 1024  # 256 MB

_MAGIC_AES    = b"VAULTAE2"
_MAGIC_BF     = b"VAULTBL2"
_MAGIC_AES_V1 = b"VAULTAES"
_MAGIC_BF_V1  = b"VAULTBLF"
MAGIC_SIZE = 8

def _derive_aes_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode())

def _derive_bf_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=16,
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
    if algorithm == "Blowfish-CBC":
        _encrypt_blowfish(input_path, output_path, password, progress)
    else:
        _encrypt_aes(input_path, output_path, password, progress)


def decrypt_file(input_path: str, output_dir: str, password: str,
                 progress=None, algorithm: str | None = None) -> str:
    with open(input_path, "rb") as f:
        magic = f.read(MAGIC_SIZE)

    if algorithm is None:
        if magic in (_MAGIC_BF, _MAGIC_BF_V1):
            algorithm = "Blowfish-CBC"
        else:
            algorithm = "AES-256-GCM"

    if algorithm == "Blowfish-CBC":
        return _decrypt_blowfish(input_path, output_dir, password, progress, magic)
    else:
        return _decrypt_aes(input_path, output_dir, password, progress, magic)

def _encrypt_aes(input_path, output_path, password, progress):
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        plaintext = f.read()

    p(0.15, "Generating salt & nonce…")
    salt  = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)

    key = _derive_aes_key(password, salt)

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

def _encrypt_blowfish(input_path, output_path, password, progress):
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        plaintext = f.read()

    p(0.15, "Generating salt & IV…")
    salt = os.urandom(SALT_SIZE)
    iv   = os.urandom(BF_IV_SIZE)

    key = _derive_bf_key(password, salt)

    p(0.80, "Encrypting with Blowfish-CBC…")
    cipher     = _Blowfish.new(key, _Blowfish.MODE_CBC, iv)
    ciphertext = cipher.encrypt(_pad(plaintext, _Blowfish.block_size))

    p(0.95, "Writing output file…")
    fname_bytes = _encode_filename(os.path.basename(input_path))
    with open(output_path, "wb") as f:
        f.write(_MAGIC_BF + fname_bytes + salt + iv + ciphertext)

    p(1.00, "Done.")


def _decrypt_blowfish(input_path, output_dir, password, progress, magic: bytes) -> str:
    def p(v, m=""): progress and progress(v, m)

    p(0.05, "Reading file…")
    with open(input_path, "rb") as f:
        data = f.read()

    offset = MAGIC_SIZE

    if magic == _MAGIC_BF:
        original_name, offset = _decode_filename(data, offset)
    else:
        # v1 legacy
        original_name = os.path.splitext(os.path.basename(input_path))[0]

    salt       = data[offset: offset + SALT_SIZE]
    iv         = data[offset + SALT_SIZE: offset + SALT_SIZE + BF_IV_SIZE]
    ciphertext = data[offset + SALT_SIZE + BF_IV_SIZE:]

    out_path = safe_output_path(os.path.join(output_dir, original_name))

    key = _derive_bf_key(password, salt)

    p(0.80, "Decrypting with Blowfish-CBC…")
    try:
        cipher    = _Blowfish.new(key, _Blowfish.MODE_CBC, iv)
        plaintext = _unpad(cipher.decrypt(ciphertext), _Blowfish.block_size)
    except (ValueError, KeyError):
        raise ValueError("Wrong password, or the file has been tampered with.")

    p(0.95, "Writing output file…")
    with open(out_path, "wb") as f:
        f.write(plaintext)

    p(1.00, "Done.")
    return out_path
