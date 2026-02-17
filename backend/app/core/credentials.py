"""Credential encryption service."""

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)


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
                # Generate a key for development (warn in production)
                if settings.environment == "production":
                    raise ValueError(
                        "MASTER_ENCRYPTION_KEY must be set in production environment"
                    )
                key_str = Fernet.generate_key().decode()
                import warnings

                warnings.warn(
                    "MASTER_ENCRYPTION_KEY not set, using generated key. "
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


