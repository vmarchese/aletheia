"""Encryption module for Aletheia session data security.

This module provides encryption and decryption functionality for sensitive
session data using Fernet (AES-128-CBC + HMAC) with PBKDF2 key derivation.

Security features:
- PBKDF2 key derivation with 100,000 iterations (default)
- Unique salt per session
- Authenticated encryption (prevents tampering)
- Session-scoped keys
"""

import base64
import json
import secrets
from pathlib import Path
from typing import Any, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""


class DecryptionError(EncryptionError):
    """Exception raised when decryption fails."""


def derive_session_key(password: str, salt: bytes, iterations: int = 100000) -> bytes:
    """Derive session key from password using PBKDF2.

    Args:
        password: User-provided password for key derivation
        salt: Unique salt for this session (should be 32 bytes)
        iterations: Number of PBKDF2 iterations (minimum 10000, default 100000)

    Returns:
        32-byte derived key suitable for Fernet encryption

    Raises:
        ValueError: If iterations < 10000 or salt is invalid

    Security:
        - Uses SHA-256 for hashing
        - Minimum 10,000 iterations required (OWASP recommendation)
        - Default 100,000 iterations provides strong security
        - Unique salt prevents rainbow table attacks
    """
    if iterations < 10000:
        raise ValueError("iterations must be at least 10000 for security")

    if not salt or len(salt) < 16:
        raise ValueError("salt must be at least 16 bytes")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256-bit key
        salt=salt,
        iterations=iterations,
    )

    key = kdf.derive(password.encode('utf-8'))
    return key


def create_session_encryption(password: str,
                              salt_size: int = 32,
                              iterations: int = 100000) -> Tuple[bytes, bytes]:
    """Create encryption key and salt for new session.

    Args:
        password: User-provided password
        salt_size: Size of salt in bytes (default 32)
        iterations: Number of PBKDF2 iterations (default 100000)

    Returns:
        Tuple of (key, salt) where both are bytes

    Security:
        - Generates cryptographically secure random salt
        - Salt size minimum 16 bytes, default 32 bytes
        - Each session gets unique salt
    """
    if salt_size < 16:
        raise ValueError("salt_size must be at least 16 bytes")

    salt = secrets.token_bytes(salt_size)
    key = derive_session_key(password, salt, iterations)
    return key, salt


def _get_fernet(key: bytes) -> Fernet:
    """Create Fernet cipher instance from key.

    Args:
        key: 32-byte key from derive_session_key

    Returns:
        Fernet cipher instance
    """
    # Fernet requires base64-encoded key
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_data(data: bytes, key: bytes) -> bytes:
    """Encrypt bytes data with Fernet.

    Args:
        data: Raw bytes to encrypt
        key: 32-byte encryption key

    Returns:
        Encrypted data as bytes

    Raises:
        EncryptionError: If encryption fails
    """
    try:
        cipher = _get_fernet(key)
        encrypted = cipher.encrypt(data)
        return encrypted
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
    """Decrypt bytes data with Fernet.

    Args:
        encrypted_data: Encrypted bytes from encrypt_data
        key: 32-byte encryption key (must match encryption key)

    Returns:
        Decrypted data as bytes

    Raises:
        DecryptionError: If decryption fails (wrong key, tampered data, etc.)
    """
    try:
        cipher = _get_fernet(key)
        decrypted = cipher.decrypt(encrypted_data)
        return decrypted
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {e}") from e


def encrypt_file(filepath: Path, key: bytes, output_path: Optional[Path] = None) -> Path:
    """Encrypt file with Fernet.

    Args:
        filepath: Path to file to encrypt
        key: 32-byte encryption key
        output_path: Optional output path (default: filepath with .encrypted suffix)

    Returns:
        Path to encrypted file

    Raises:
        EncryptionError: If encryption fails
        FileNotFoundError: If input file doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(filepath, 'rb') as f:
            plaintext = f.read()

        encrypted = encrypt_data(plaintext, key)

        if output_path is None:
            output_path = filepath.with_suffix(filepath.suffix + '.encrypted')

        with open(output_path, 'wb') as f:
            f.write(encrypted)

        return output_path
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"File encryption failed: {e}") from e


def decrypt_file(encrypted_filepath: Path,
                 key: bytes,
                 output_path: Optional[Path] = None) -> Path:
    """Decrypt file with Fernet.

    Args:
        encrypted_filepath: Path to encrypted file
        key: 32-byte encryption key
        output_path: Optional output path (default: remove .encrypted suffix)

    Returns:
        Path to decrypted file

    Raises:
        DecryptionError: If decryption fails
        FileNotFoundError: If encrypted file doesn't exist
    """
    if not encrypted_filepath.exists():
        raise FileNotFoundError(f"Encrypted file not found: {encrypted_filepath}")

    try:
        with open(encrypted_filepath, 'rb') as f:
            encrypted = f.read()

        decrypted = decrypt_data(encrypted, key)

        if output_path is None:
            # Remove .encrypted suffix
            name = encrypted_filepath.name
            if name.endswith('.encrypted'):
                name = name[:-10]  # Remove '.encrypted'
            output_path = encrypted_filepath.parent / name

        with open(output_path, 'wb') as f:
            f.write(decrypted)

        return output_path
    except DecryptionError as de:
        raise de
    except Exception as e:
        raise DecryptionError(f"File decryption failed: {e}") from e


def encrypt_json(data: Any, key: bytes) -> bytes:
    """Encrypt JSON-serializable data.

    Args:
        data: Any JSON-serializable Python object
        key: 32-byte encryption key

    Returns:
        Encrypted data as bytes

    Raises:
        EncryptionError: If encryption or JSON serialization fails
    """
    try:
        json_str = json.dumps(data, indent=2)
        json_bytes = json_str.encode('utf-8')
        return encrypt_data(json_bytes, key)
    except Exception as e:
        raise EncryptionError(f"JSON encryption failed: {e}") from e


def decrypt_json(encrypted_data: bytes, key: bytes) -> Any:
    """Decrypt JSON data.

    Args:
        encrypted_data: Encrypted bytes from encrypt_json
        key: 32-byte encryption key

    Returns:
        Deserialized Python object

    Raises:
        DecryptionError: If decryption or JSON deserialization fails
    """
    try:
        json_bytes = decrypt_data(encrypted_data, key)
        json_str = json_bytes.decode('utf-8')
        return json.loads(json_str)
    except DecryptionError:
        raise
    except Exception as e:
        raise DecryptionError(f"JSON decryption failed: {e}") from e


def encrypt_json_file(data: Any, filepath: Path, key: bytes) -> Path:
    """Encrypt JSON data and save to file.

    Args:
        data: JSON-serializable Python object
        filepath: Output file path
        key: 32-byte encryption key

    Returns:
        Path to encrypted file

    Raises:
        EncryptionError: If encryption fails
    """
    try:
        encrypted = encrypt_json(data, key)
        with open(filepath, 'wb') as f:
            f.write(encrypted)
        return filepath
    except Exception as e:
        raise EncryptionError(f"JSON file encryption failed: {e}") from e


def decrypt_json_file(filepath: Path, key: bytes) -> Any:
    """Decrypt JSON file.

    Args:
        filepath: Path to encrypted JSON file
        key: 32-byte encryption key

    Returns:
        Deserialized Python object

    Raises:
        DecryptionError: If decryption fails
        FileNotFoundError: If file doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Encrypted file not found: {filepath}")

    try:
        with open(filepath, 'rb') as f:
            encrypted = f.read()
        return decrypt_json(encrypted, key)
    except DecryptionError:
        raise
    except Exception as e:
        raise DecryptionError(f"JSON file decryption failed: {e}") from e
