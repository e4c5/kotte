"""Connection storage service (encrypted JSON file)."""

import base64
import fcntl
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.credentials import credential_encryption

logger = logging.getLogger(__name__)


class ConnectionStorage:
    """Manages saved database connections (encrypted JSON file storage)."""

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize connection storage.

        Args:
            storage_path: Path to encrypted JSON file (defaults to settings)
        """
        self.storage_path = Path(storage_path or settings.credential_storage_path)
        self._ensure_storage_file()

    def _ensure_storage_file(self):
        """Create storage file if it doesn't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            # Create empty file
            self._write_connections({})
        # Set restrictive permissions (owner read/write only)
        try:
            os.chmod(self.storage_path, 0o600)
        except OSError as e:
            logger.warning(f"Could not set file permissions: {e}")

    def _read_connections(self) -> Dict:
        """Read connections file."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading connections file: {e}")
            return {}

    def _write_connections(self, connections: Dict):
        """Write connections file."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
                try:
                    json.dump(connections, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except IOError as e:
            logger.error(f"Error writing connections file: {e}")
            raise

    def save_connection(
        self,
        user_id: str,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        sslmode: Optional[str] = None,
    ) -> str:
        """Save a new connection (encrypted)."""
        connection_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Encrypt credentials
        encrypted_username = base64.b64encode(
            credential_encryption.encrypt(username, user_id)
        ).decode("utf-8")
        encrypted_password = base64.b64encode(
            credential_encryption.encrypt(password, user_id)
        ).decode("utf-8")

        connection = {
            "id": connection_id,
            "user_id": user_id,
            "name": name,
            "host": host,
            "port": port,
            "database": database,
            "encrypted_username": encrypted_username,
            "encrypted_password": encrypted_password,
            "sslmode": sslmode,
            "created_at": now,
            "updated_at": now,
        }

        # Read existing connections
        connections = self._read_connections()
        user_key = f"user:{user_id}"
        if user_key not in connections:
            connections[user_key] = {}

        # Check for duplicate name
        for conn_id, conn in connections[user_key].items():
            if conn["name"] == name:
                raise ValueError(f"Connection '{name}' already exists")

        # Save connection
        connections[user_key][connection_id] = connection
        self._write_connections(connections)

        logger.info(f"Saved connection '{name}' for user '{user_id}'")
        return connection_id

    def get_connection(self, user_id: str, connection_id: str) -> Optional[Dict]:
        """Get a connection and decrypt credentials."""
        connections = self._read_connections()
        user_key = f"user:{user_id}"

        if user_key not in connections:
            return None

        if connection_id not in connections[user_key]:
            return None

        conn = connections[user_key][connection_id].copy()

        # Decrypt credentials
        encrypted_username = base64.b64decode(conn["encrypted_username"])
        encrypted_password = base64.b64decode(conn["encrypted_password"])

        conn["username"] = credential_encryption.decrypt(encrypted_username, user_id)
        conn["password"] = credential_encryption.decrypt(encrypted_password, user_id)

        # Remove encrypted fields from response
        del conn["encrypted_username"]
        del conn["encrypted_password"]

        return conn

    def list_connections(self, user_id: str) -> List[Dict]:
        """List all connections for a user (without decrypting)."""
        connections = self._read_connections()
        user_key = f"user:{user_id}"

        if user_key not in connections:
            return []

        result = []
        for conn_id, conn in connections[user_key].items():
            # Return metadata only (no credentials)
            result.append(
                {
                    "id": conn["id"],
                    "name": conn["name"],
                    "host": conn["host"],
                    "port": conn["port"],
                    "database": conn["database"],
                    "created_at": conn["created_at"],
                    "updated_at": conn["updated_at"],
                }
            )

        return result

    def delete_connection(self, user_id: str, connection_id: str) -> bool:
        """Delete a connection."""
        connections = self._read_connections()
        user_key = f"user:{user_id}"

        if user_key not in connections:
            return False

        if connection_id not in connections[user_key]:
            return False

        del connections[user_key][connection_id]
        self._write_connections(connections)
        logger.info(f"Deleted connection '{connection_id}' for user '{user_id}'")
        return True


# Global instance
connection_storage = ConnectionStorage()

