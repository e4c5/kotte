"""Credential encryption service."""

import base64
import hashlib
import logging
import os
import warnings
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)

# Key file for persisting auto-generated key (development only)
_DEV_KEY_FILENAME = ".master_encryption_key"


def _get_dev_key_path() -> Path:
    """Get path for dev master key file (next to connections file)."""
    storage_path = Path(settings.credential_storage_path)
    return storage_path.parent / _DEV_KEY_FILENAME


def _load_or_create_dev_key() -> str:
    """
    Load persisted dev key or create and persist a new one.
    Ensures encrypted connections survive server restarts in development.
    """
    key_path = _get_dev_key_path()
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            key_str = key_path.read_text().strip()
            if len(key_str.encode()) >= 32:
                return key_str
        # Generate new key and persist
        key_str = Fernet.generate_key().decode()
        key_path.write_text(key_str)
        try:
            os.chmod(key_path, 0o600)
        except OSError as e:
            logger.warning(f"Could not set restrictive permissions on key file: {e}")
        return key_str
    except OSError as e:
        logger.warning(f"Could not persist dev encryption key to {key_path}: {e}")
        return Fernet.generate_key().decode()


class CredentialEncryption:
    """Encrypts and decrypts database credentials."""

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize with master key from environment.

        Args:
            master_key: Optional master key (defaults to settings.master_encryption_key)
        """
        if master_key is None:
            key_str = settings.master_encryption_key
            if not key_str:
                # Generate or load persisted key for development
                if settings.environment == "production":
                    raise ValueError(
                        "MASTER_ENCRYPTION_KEY must be set in production environment"
                    )
                key_str = _load_or_create_dev_key()
                warnings.warn(
                    "MASTER_ENCRYPTION_KEY not set, using persisted dev key. "
                    "Set MASTER_ENCRYPTION_KEY in production!",
                    UserWarning,
                )
            master_key = key_str.encode() if isinstance(key_str, str) else key_str

        if len(master_key) < 32:
            raise ValueError("Master key must be at least 32 bytes")
        self.master_key = master_key[:32]  # Use first 32 bytes

    def encrypt(self, plaintext: str, user_id: str) -> bytes:
        """
        Encrypt credential with user-specific salt.

        This adds an extra security layer - even if one user's data
        is compromised, other users' credentials remain secure.

        Args:
            plaintext: Plain text credential to encrypt
            user_id: User ID for salt generation

        Returns:
            Encrypted bytes
        """
        # Derive key per user using PBKDF2
        salt = hashlib.sha256(user_id.encode()).digest()[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        f = Fernet(key)
        return f.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes, user_id: str) -> str:
        """
        Decrypt credential.

        Args:
            ciphertext: Encrypted bytes
            user_id: User ID for salt generation

        Returns:
            Decrypted plain text
        """
        salt = hashlib.sha256(user_id.encode()).digest()[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        f = Fernet(key)
        return f.decrypt(ciphertext).decode()


# Global instance
credential_encryption = CredentialEncryption()


