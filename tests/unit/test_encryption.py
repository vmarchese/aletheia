"""Unit tests for encryption module.

Tests cover:
- Key derivation consistency
- Encryption/decryption round-trip
- File encryption/decryption
- JSON encryption/decryption
- Tamper detection
- Wrong password handling
- Salt uniqueness
- Security validations
"""

import json
import secrets
from pathlib import Path

import pytest

from aletheia.encryption import (
    DecryptionError,
    EncryptionError,
    create_session_encryption,
    decrypt_data,
    decrypt_file,
    decrypt_json,
    decrypt_json_file,
    derive_session_key,
    encrypt_data,
    encrypt_file,
    encrypt_json,
    encrypt_json_file,
)


class TestKeyDerivation:
    """Tests for PBKDF2 key derivation."""

    def test_derive_session_key_consistency(self):
        """Test that same password+salt produces same key."""
        password = "test-password-123"
        salt = secrets.token_bytes(32)

        key1 = derive_session_key(password, salt)
        key2 = derive_session_key(password, salt)

        assert key1 == key2
        assert len(key1) == 32  # 256-bit key

    def test_derive_session_key_different_salts(self):
        """Test that different salts produce different keys."""
        password = "test-password-123"
        salt1 = secrets.token_bytes(32)
        salt2 = secrets.token_bytes(32)

        key1 = derive_session_key(password, salt1)
        key2 = derive_session_key(password, salt2)

        assert key1 != key2

    def test_derive_session_key_different_passwords(self):
        """Test that different passwords produce different keys."""
        salt = secrets.token_bytes(32)

        key1 = derive_session_key("password1", salt)
        key2 = derive_session_key("password2", salt)

        assert key1 != key2

    def test_derive_session_key_minimum_iterations(self):
        """Test that minimum iteration count is enforced."""
        password = "test-password"
        salt = secrets.token_bytes(32)

        # Should work with minimum (10000)
        key = derive_session_key(password, salt, iterations=10000)
        assert len(key) == 32

        # Should fail with too few iterations
        with pytest.raises(ValueError, match="iterations must be at least 10000"):
            derive_session_key(password, salt, iterations=9999)

    def test_derive_session_key_invalid_salt(self):
        """Test that invalid salts are rejected."""
        password = "test-password"

        # Empty salt
        with pytest.raises(ValueError, match="salt must be at least 16 bytes"):
            derive_session_key(password, b"")

        # Too short salt
        with pytest.raises(ValueError, match="salt must be at least 16 bytes"):
            derive_session_key(password, b"short")

        # Minimum valid salt (16 bytes)
        key = derive_session_key(password, secrets.token_bytes(16))
        assert len(key) == 32

    def test_derive_session_key_custom_iterations(self):
        """Test that custom iteration counts work."""
        password = "test-password"
        salt = secrets.token_bytes(32)

        key1 = derive_session_key(password, salt, iterations=50000)
        key2 = derive_session_key(password, salt, iterations=100000)

        # Different iteration counts should produce different keys
        assert key1 != key2


class TestSessionEncryptionCreation:
    """Tests for create_session_encryption function."""

    def test_create_session_encryption_basic(self):
        """Test basic session encryption creation."""
        password = "test-password-123"

        key, salt = create_session_encryption(password)

        assert len(key) == 32
        assert len(salt) == 32
        assert isinstance(key, bytes)
        assert isinstance(salt, bytes)

    def test_create_session_encryption_salt_uniqueness(self):
        """Test that each session gets unique salt."""
        password = "same-password"

        key1, salt1 = create_session_encryption(password)
        key2, salt2 = create_session_encryption(password)

        # Different salts should be generated
        assert salt1 != salt2
        # Therefore different keys
        assert key1 != key2

    def test_create_session_encryption_custom_salt_size(self):
        """Test custom salt sizes."""
        password = "test-password"

        # Custom salt size
        key, salt = create_session_encryption(password, salt_size=64)
        assert len(salt) == 64
        assert len(key) == 32  # Key is always 32 bytes

        # Minimum salt size
        key, salt = create_session_encryption(password, salt_size=16)
        assert len(salt) == 16

        # Too small salt size
        with pytest.raises(ValueError, match="salt_size must be at least 16 bytes"):
            create_session_encryption(password, salt_size=15)

    def test_create_session_encryption_custom_iterations(self):
        """Test custom iteration counts."""
        password = "test-password"

        key1, salt1 = create_session_encryption(password, iterations=50000)
        key2, salt2 = create_session_encryption(password, iterations=100000)

        # Keys should be different due to different iteration counts
        # (even if salts were same, which they're not)
        assert len(key1) == 32
        assert len(key2) == 32


class TestDataEncryption:
    """Tests for encrypt_data and decrypt_data."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption/decryption preserves data."""
        password = "test-password-123"
        key, salt = create_session_encryption(password)

        original_data = b"This is secret data that needs encryption!"

        encrypted = encrypt_data(original_data, key)
        decrypted = decrypt_data(encrypted, key)

        assert decrypted == original_data
        assert encrypted != original_data  # Data is actually encrypted

    def test_encrypt_data_produces_different_output(self):
        """Test that encrypting same data twice produces different ciphertext.

        Fernet includes timestamp and IV, so output should differ.
        """
        password = "test-password"
        key, _ = create_session_encryption(password)
        data = b"same data"

        encrypted1 = encrypt_data(data, key)
        encrypted2 = encrypt_data(data, key)

        # Ciphertext should differ (Fernet includes timestamp)
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert decrypt_data(encrypted1, key) == data
        assert decrypt_data(encrypted2, key) == data

    def test_decrypt_with_wrong_key(self):
        """Test that wrong key fails decryption."""
        key1, _ = create_session_encryption("password1")
        key2, _ = create_session_encryption("password2")

        data = b"secret data"
        encrypted = encrypt_data(data, key1)

        # Decryption with wrong key should fail
        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_data(encrypted, key2)

    def test_decrypt_tampered_data(self):
        """Test that tampered data is detected (HMAC protection)."""
        password = "test-password"
        key, _ = create_session_encryption(password)

        data = b"important data"
        encrypted = encrypt_data(data, key)

        # Tamper with encrypted data
        tampered = bytearray(encrypted)
        tampered[10] ^= 0xFF  # Flip some bits
        tampered = bytes(tampered)

        # Decryption should fail due to HMAC check
        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_data(tampered, key)

    def test_encrypt_empty_data(self):
        """Test encryption of empty data."""
        key, _ = create_session_encryption("password")

        encrypted = encrypt_data(b"", key)
        decrypted = decrypt_data(encrypted, key)

        assert decrypted == b""

    def test_encrypt_large_data(self):
        """Test encryption of large data."""
        key, _ = create_session_encryption("password")

        # 1 MB of data
        large_data = secrets.token_bytes(1024 * 1024)

        encrypted = encrypt_data(large_data, key)
        decrypted = decrypt_data(encrypted, key)

        assert decrypted == large_data


class TestFileEncryption:
    """Tests for file encryption/decryption."""

    def test_encrypt_decrypt_file_roundtrip(self, tmp_path):
        """Test file encryption/decryption preserves content."""
        key, _ = create_session_encryption("password")

        # Create test file
        original_file = tmp_path / "test.txt"
        original_data = b"This is test file content!\nMultiple lines.\n"
        original_file.write_bytes(original_data)

        # Encrypt file
        encrypted_file = encrypt_file(original_file, key)
        assert encrypted_file.exists()
        assert encrypted_file.name == "test.txt.encrypted"

        # Verify encrypted content is different
        encrypted_data = encrypted_file.read_bytes()
        assert encrypted_data != original_data

        # Decrypt file
        decrypted_file = decrypt_file(encrypted_file, key)
        assert decrypted_file.exists()
        assert decrypted_file.name == "test.txt"

        # Verify content matches
        decrypted_data = decrypted_file.read_bytes()
        assert decrypted_data == original_data

    def test_encrypt_file_custom_output_path(self, tmp_path):
        """Test file encryption with custom output path."""
        key, _ = create_session_encryption("password")

        original_file = tmp_path / "input.txt"
        original_file.write_bytes(b"test data")

        custom_output = tmp_path / "custom_encrypted.bin"
        encrypted_file = encrypt_file(original_file, key, output_path=custom_output)

        assert encrypted_file == custom_output
        assert encrypted_file.exists()

    def test_decrypt_file_custom_output_path(self, tmp_path):
        """Test file decryption with custom output path."""
        key, _ = create_session_encryption("password")

        original_file = tmp_path / "test.txt"
        original_data = b"test data"
        original_file.write_bytes(original_data)

        encrypted_file = encrypt_file(original_file, key)

        custom_output = tmp_path / "decrypted_custom.txt"
        decrypted_file = decrypt_file(encrypted_file, key, output_path=custom_output)

        assert decrypted_file == custom_output
        assert decrypted_file.read_bytes() == original_data

    def test_encrypt_nonexistent_file(self, tmp_path):
        """Test encrypting non-existent file raises error."""
        key, _ = create_session_encryption("password")
        nonexistent = tmp_path / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            encrypt_file(nonexistent, key)

    def test_decrypt_nonexistent_file(self, tmp_path):
        """Test decrypting non-existent file raises error."""
        key, _ = create_session_encryption("password")
        nonexistent = tmp_path / "does_not_exist.encrypted"

        with pytest.raises(FileNotFoundError):
            decrypt_file(nonexistent, key)

    def test_decrypt_file_with_wrong_key(self, tmp_path):
        """Test file decryption with wrong key fails."""
        key1, _ = create_session_encryption("password1")
        key2, _ = create_session_encryption("password2")

        original_file = tmp_path / "test.txt"
        original_file.write_bytes(b"secret content")

        encrypted_file = encrypt_file(original_file, key1)

        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_file(encrypted_file, key2)


class TestJsonEncryption:
    """Tests for JSON encryption/decryption."""

    def test_encrypt_decrypt_json_roundtrip(self):
        """Test JSON encryption/decryption preserves structure."""
        key, _ = create_session_encryption("password")

        original_data = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"key": "value"},
            "unicode": "Hello 世界",
        }

        encrypted = encrypt_json(original_data, key)
        decrypted = decrypt_json(encrypted, key)

        assert decrypted == original_data
        assert isinstance(encrypted, bytes)

    def test_encrypt_json_various_types(self):
        """Test JSON encryption with various data types."""
        key, _ = create_session_encryption("password")

        test_cases = [
            {"string": "hello"},
            {"number": 42},
            {"float": 3.14},
            {"boolean": True},
            {"null": None},
            {"list": [1, 2, 3]},
            {"nested": {"a": {"b": {"c": "deep"}}}},
        ]

        for data in test_cases:
            encrypted = encrypt_json(data, key)
            decrypted = decrypt_json(encrypted, key)
            assert decrypted == data

    def test_decrypt_json_with_wrong_key(self):
        """Test JSON decryption with wrong key fails."""
        key1, _ = create_session_encryption("password1")
        key2, _ = create_session_encryption("password2")

        data = {"secret": "information"}
        encrypted = encrypt_json(data, key1)

        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_json(encrypted, key2)

    def test_encrypt_json_invalid_data(self):
        """Test that non-JSON-serializable data raises error."""
        key, _ = create_session_encryption("password")

        # Functions are not JSON serializable
        with pytest.raises(EncryptionError, match="JSON encryption failed"):
            encrypt_json({"func": lambda x: x}, key)


class TestJsonFileEncryption:
    """Tests for JSON file encryption/decryption."""

    def test_encrypt_decrypt_json_file_roundtrip(self, tmp_path):
        """Test JSON file encryption/decryption preserves data."""
        key, _ = create_session_encryption("password")

        original_data = {
            "session_id": "INC-123",
            "metadata": {"created": "2025-10-13", "status": "active"},
            "data": [1, 2, 3],
        }

        # Encrypt JSON to file
        encrypted_file = tmp_path / "data.json.encrypted"
        result_path = encrypt_json_file(original_data, encrypted_file, key)
        assert result_path == encrypted_file
        assert encrypted_file.exists()

        # Decrypt JSON from file
        decrypted_data = decrypt_json_file(encrypted_file, key)
        assert decrypted_data == original_data

    def test_decrypt_json_file_nonexistent(self, tmp_path):
        """Test decrypting non-existent JSON file raises error."""
        key, _ = create_session_encryption("password")
        nonexistent = tmp_path / "does_not_exist.json.encrypted"

        with pytest.raises(FileNotFoundError):
            decrypt_json_file(nonexistent, key)

    def test_decrypt_json_file_with_wrong_key(self, tmp_path):
        """Test JSON file decryption with wrong key fails."""
        key1, _ = create_session_encryption("password1")
        key2, _ = create_session_encryption("password2")

        data = {"secret": "data"}
        encrypted_file = tmp_path / "secret.json.encrypted"
        encrypt_json_file(data, encrypted_file, key1)

        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_json_file(encrypted_file, key2)


class TestSecurityValidation:
    """Security-focused tests."""

    def test_salt_uniqueness_statistical(self):
        """Test that salts are statistically unique."""
        password = "test-password"
        salts = set()

        # Generate 100 sessions
        for _ in range(100):
            _, salt = create_session_encryption(password)
            salts.add(salt)

        # All salts should be unique
        assert len(salts) == 100

    def test_key_uniqueness_with_same_password(self):
        """Test that keys are unique even with same password."""
        password = "same-password"
        keys = set()

        # Generate 100 sessions
        for _ in range(100):
            key, _ = create_session_encryption(password)
            keys.add(key)

        # All keys should be unique (due to unique salts)
        assert len(keys) == 100

    def test_hmac_prevents_tampering(self):
        """Test that HMAC authentication prevents tampering."""
        key, _ = create_session_encryption("password")
        data = b"important data that should not be tampered with"

        encrypted = encrypt_data(data, key)

        # Try various tampering attacks
        tamper_attempts = [
            # Flip single bit
            lambda e: bytes([e[0] ^ 1]) + e[1:],
            # Flip multiple bits
            lambda e: bytes([b ^ 0xFF for b in e[:10]]) + e[10:],
            # Truncate
            lambda e: e[:-10],
            # Append garbage
            lambda e: e + b"garbage",
        ]

        for tamper in tamper_attempts:
            tampered = tamper(encrypted)
            with pytest.raises(DecryptionError, match="Decryption failed"):
                decrypt_data(tampered, key)

    def test_wrong_password_fails_consistently(self):
        """Test that wrong password consistently fails decryption."""
        password = "correct-password"
        key, salt = create_session_encryption(password)

        data = b"secret data"
        encrypted = encrypt_data(data, key)

        # Try decrypting with wrong passwords
        wrong_passwords = ["wrong1", "wrong2", "almost-correct-password"]

        for wrong_pwd in wrong_passwords:
            wrong_key = derive_session_key(wrong_pwd, salt)
            with pytest.raises(DecryptionError, match="Decryption failed"):
                decrypt_data(encrypted, wrong_key)

    def test_no_credential_leaks_in_errors(self):
        """Test that error messages don't leak sensitive info."""
        password = "super-secret-password-123"
        key, salt = create_session_encryption(password)

        data = b"secret"
        encrypted = encrypt_data(data, key)

        # Wrong key
        wrong_key, _ = create_session_encryption("wrong")

        try:
            decrypt_data(encrypted, wrong_key)
        except DecryptionError as e:
            error_msg = str(e).lower()
            # Error should not contain password or key material
            assert "super-secret" not in error_msg
            assert password not in error_msg
            assert key.hex() not in error_msg
            assert salt.hex() not in error_msg

    def test_timing_resistance_basic(self):
        """Basic test that decryption failures don't reveal timing info.

        Note: This is a basic test. Real timing attack resistance
        requires specialized testing and hardware.
        """
        import time

        key, salt = create_session_encryption("password")
        data = b"test data"
        encrypted = encrypt_data(data, key)

        # Test multiple wrong keys
        timing_samples = []
        for _ in range(10):
            wrong_key, _ = create_session_encryption("wrong")
            start = time.perf_counter()
            try:
                decrypt_data(encrypted, wrong_key)
            except DecryptionError:
                pass
            end = time.perf_counter()
            timing_samples.append(end - start)

        # All failures should take roughly similar time
        # (Within 10x factor - very permissive for basic test)
        min_time = min(timing_samples)
        max_time = max(timing_samples)
        assert max_time < min_time * 10


class TestErrorHandling:
    """Tests for error handling and exception paths."""

    def test_encrypt_data_invalid_key(self):
        """Test encryption with invalid key."""
        # Key must be properly formatted for Fernet
        with pytest.raises(EncryptionError, match="Encryption failed"):
            encrypt_data(b"test", b"invalid-key")

    def test_decrypt_data_invalid_key(self):
        """Test decryption with invalid key."""
        password = "test-password"
        key, _ = create_session_encryption(password)
        encrypted = encrypt_data(b"test", key)

        # Invalid key format
        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_data(encrypted, b"invalid-key")

    def test_encrypt_file_permission_error(self, tmp_path):
        """Test file encryption with permission errors."""
        key, _ = create_session_encryption("password")

        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test data")

        # Try to write to a read-only directory
        import os
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, 0o444)

        output_path = readonly_dir / "encrypted.bin"

        try:
            with pytest.raises(EncryptionError, match="File encryption failed"):
                encrypt_file(test_file, key, output_path=output_path)
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    def test_decrypt_file_corrupted(self, tmp_path):
        """Test file decryption with corrupted file."""
        key, _ = create_session_encryption("password")

        # Create corrupted encrypted file
        corrupted_file = tmp_path / "corrupted.encrypted"
        corrupted_file.write_bytes(b"not valid encrypted data")

        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_file(corrupted_file, key)

    def test_encrypt_json_with_circular_reference(self):
        """Test JSON encryption with circular reference."""
        key, _ = create_session_encryption("password")

        # Create circular reference
        data = {"key": "value"}
        data["self"] = data

        with pytest.raises(EncryptionError, match="JSON encryption failed"):
            encrypt_json(data, key)

    def test_decrypt_json_invalid_format(self):
        """Test JSON decryption with non-JSON data."""
        key, _ = create_session_encryption("password")

        # Encrypt non-JSON data
        encrypted = encrypt_data(b"not json data", key)

        with pytest.raises(DecryptionError, match="JSON decryption failed"):
            decrypt_json(encrypted, key)

    def test_encrypt_json_file_invalid_path(self):
        """Test JSON file encryption with invalid path."""
        key, _ = create_session_encryption("password")
        data = {"test": "data"}

        # Invalid path (directory doesn't exist)
        invalid_path = Path("/nonexistent/directory/file.json")

        with pytest.raises(EncryptionError, match="JSON file encryption failed"):
            encrypt_json_file(data, invalid_path, key)

    def test_decrypt_json_file_corrupted(self, tmp_path):
        """Test JSON file decryption with corrupted file."""
        key, _ = create_session_encryption("password")

        # Create corrupted file
        corrupted_file = tmp_path / "corrupted.json.encrypted"
        corrupted_file.write_bytes(b"corrupted data")

        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt_json_file(corrupted_file, key)


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_encrypt_decrypt_unicode_data(self):
        """Test encryption with unicode data in JSON."""
        key, _ = create_session_encryption("password")

        data = {
            "english": "Hello",
            "chinese": "你好",
            "arabic": "مرحبا",
            "emoji": "🔐🔑",
        }

        encrypted = encrypt_json(data, key)
        decrypted = decrypt_json(encrypted, key)

        assert decrypted == data

    def test_encrypt_decrypt_binary_safe(self):
        """Test that encryption handles binary data correctly."""
        key, _ = create_session_encryption("password")

        # Random binary data including null bytes
        binary_data = bytes(range(256))

        encrypted = encrypt_data(binary_data, key)
        decrypted = decrypt_data(encrypted, key)

        assert decrypted == binary_data

    def test_key_derivation_with_special_chars_password(self):
        """Test key derivation with special characters in password."""
        special_passwords = [
            "pass@word!123",
            "pásswörd",
            "密码123",
            "password\n\t\r",
            "🔑🔐",
        ]

        salt = secrets.token_bytes(32)

        for password in special_passwords:
            key = derive_session_key(password, salt)
            assert len(key) == 32

            # Verify consistency
            key2 = derive_session_key(password, salt)
            assert key == key2
