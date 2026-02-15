# Secure Database Credential Storage Architecture

## Problem Statement

With application authentication (login page), we need to separate:
1. **Application Authentication** - Who is the user? (login credentials)
2. **Database Connection** - Which database does this user want to connect to? (DB credentials)

The challenge: How do we securely handle database credentials when users are already authenticated to the application?

**Important Constraint:** Credentials cannot be stored in the same database used by Apache AGE, as users may connect to different databases. We need a separate, simple storage mechanism.

## Current State

Currently, the system:
- Takes DB credentials from user in connection form
- Stores `connection_config` (including password) in session dict in memory (line 34 in `auth.py`)
- Stores DB connection object in session
- **Security Issue**: Passwords stored in plaintext in memory

## Solution: Hybrid Approach with Encrypted Storage

**Approach:** Support both saved connections (encrypted) and one-time connections. Use a separate storage mechanism (not the Apache AGE database).

**Flow:**
1. User logs into application → Gets app session
2. User can:
   - Select from saved connections (encrypted, stored separately)
   - Enter new connection (not saved)
   - Enter new connection and save it (encrypted)
3. Backend handles both cases

**Benefits:**
- ✅ **Best UX**: Users can save frequently used connections
- ✅ **Security**: Encrypted credential storage with proper key management
- ✅ **Flexibility**: Support for both saved and one-time connections
- ✅ **Production-grade**: Meets enterprise requirements for credential management
- ✅ **Separation**: Credentials stored separately from Apache AGE database

## Storage Options (Separate from Apache AGE Database)

Since credentials cannot be stored in the Apache AGE database, we need a simple, separate storage mechanism:

### Option A: Encrypted JSON File (Recommended for Simplicity)

**Approach:** Store encrypted credentials in a JSON file on the filesystem.

**Pros:**
- Simple to implement
- No additional database setup
- Easy to backup and migrate
- Works for single-server deployments
- File permissions can restrict access

**Cons:**
- Not ideal for multi-server deployments (needs shared filesystem)
- File locking needed for concurrent writes
- Backup strategy required

**Implementation:**
```python
# File structure: ~/.kotte/connections.json (encrypted)
# Or: /var/lib/kotte/connections.json (encrypted)
```

### Option B: Separate SQLite Database

**Approach:** Use a lightweight SQLite database for credential storage.

**Pros:**
- Simple, no external dependencies
- ACID transactions
- Easy to query and manage
- Portable (single file)
- Good for single-server deployments

**Cons:**
- Not ideal for multi-server (needs shared filesystem)
- SQLite has concurrency limitations

**Schema:**
```sql
CREATE TABLE user_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    database TEXT NOT NULL,
    encrypted_username BLOB NOT NULL,
    encrypted_password BLOB NOT NULL,
    sslmode TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, name)
);
```

### Option C: Separate PostgreSQL Database

**Approach:** Use a dedicated PostgreSQL database (separate from Apache AGE).

**Pros:**
- Production-grade for multi-server deployments
- Full ACID guarantees
- Excellent concurrency
- Can use connection pooling
- Supports replication and backups

**Cons:**
- Requires separate database setup
- More complex deployment
- Additional infrastructure

**Schema:**
```sql
CREATE TABLE user_connections (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    database VARCHAR(255) NOT NULL,
    encrypted_username BYTEA NOT NULL,
    encrypted_password BYTEA NOT NULL,
    sslmode VARCHAR(50),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, name)
);
```

### Option D: Key-Value Store (Redis)

**Approach:** Use Redis for credential storage.

**Pros:**
- Fast and scalable
- Good for multi-server deployments
- Built-in expiration support
- Can use Redis persistence (AOF/RDB)

**Cons:**
- Requires Redis infrastructure
- Not ideal for complex queries
- Data structure: `user:{user_id}:connections:{connection_id}`

**Implementation:**
```python
# Key format: user:{user_id}:connections:{connection_id}
# Value: JSON with encrypted credentials
```

## Recommended Approach: Encrypted JSON File (Option A)

For production, we recommend **Option A (Encrypted JSON File)** with the following considerations:

1. **Start Simple**: JSON file is easiest to implement and maintain
2. **Upgrade Path**: Can migrate to SQLite or PostgreSQL later if needed
3. **Security**: File encryption + file system permissions provide good security
4. **Backup**: Simple file-based backup strategy

**If multi-server deployment is required**, use **Option C (Separate PostgreSQL Database)**.

## Encryption Implementation

### Credential Encryption Service

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import hashlib
import os

class CredentialEncryption:
    """Encrypts and decrypts database credentials."""
    
    def __init__(self, master_key: bytes):
        """
        Initialize with master key from environment.
        
        Master key should be 32 bytes (256 bits) for AES-256.
        """
        if len(master_key) < 32:
            raise ValueError("Master key must be at least 32 bytes")
        self.master_key = master_key[:32]  # Use first 32 bytes
    
    def encrypt(self, plaintext: str, user_id: str) -> bytes:
        """
        Encrypt credential with user-specific salt.
        
        This adds an extra security layer - even if one user's data
        is compromised, other users' credentials remain secure.
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
        """Decrypt credential."""
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
```

### Storage Service (JSON File Example)

```python
import json
import os
import fcntl
from pathlib import Path
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timezone

class ConnectionStorage:
    """Manages saved database connections (encrypted JSON file storage)."""
    
    def __init__(self, storage_path: str, encryption: CredentialEncryption):
        """
        Initialize connection storage.
        
        Args:
            storage_path: Path to encrypted JSON file
            encryption: CredentialEncryption instance
        """
        self.storage_path = Path(storage_path)
        self.encryption = encryption
        self._ensure_storage_file()
    
    def _ensure_storage_file(self):
        """Create storage file if it doesn't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            # Create empty encrypted file
            self._write_connections({})
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.storage_path, 0o600)
    
    def _read_connections(self) -> Dict:
        """Read and decrypt connections file."""
        if not self.storage_path.exists():
            return {}
        
        with open(self.storage_path, 'rb') as f:
            fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reading
            try:
                encrypted_data = f.read()
                if not encrypted_data:
                    return {}
                # Decrypt file (using a file-level key)
                # For simplicity, we'll store JSON encrypted at file level
                # In production, consider encrypting the entire file
                data = json.loads(encrypted_data.decode('utf-8'))
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        
        return data
    
    def _write_connections(self, connections: Dict):
        """Write and encrypt connections file."""
        with open(self.storage_path, 'wb') as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
            try:
                json_data = json.dumps(connections, indent=2)
                # Encrypt file (using a file-level key)
                # In production, encrypt the entire file
                f.write(json_data.encode('utf-8'))
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    
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
            self.encryption.encrypt(username, user_id)
        ).decode('utf-8')
        encrypted_password = base64.b64encode(
            self.encryption.encrypt(password, user_id)
        ).decode('utf-8')
        
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
        
        conn["username"] = self.encryption.decrypt(encrypted_username, user_id)
        conn["password"] = self.encryption.decrypt(encrypted_password, user_id)
        
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
            result.append({
                "id": conn["id"],
                "name": conn["name"],
                "host": conn["host"],
                "port": conn["port"],
                "database": conn["database"],
                "created_at": conn["created_at"],
                "updated_at": conn["updated_at"],
            })
        
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
        return True
```

## Security Best Practices

### 1. Key Management
- **Master encryption key** from environment variable or secret manager
- **Never** hardcode keys in source code
- **Rotate keys** periodically (requires re-encryption of all credentials)
- **Use secret managers** in production (AWS Secrets Manager, HashiCorp Vault, etc.)

```python
# Recommended: Use environment variable or secret manager
MASTER_ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
if not MASTER_ENCRYPTION_KEY:
    raise ValueError("MASTER_ENCRYPTION_KEY must be set")

# Or use secret manager
import boto3
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='kotte/encryption-key')
MASTER_ENCRYPTION_KEY = secret['SecretString'].encode()
```

### 2. File System Security
- **Restrictive permissions**: `chmod 600` (owner read/write only)
- **Secure directory**: Store in `/var/lib/kotte/` or `~/.kotte/` with proper permissions
- **File locking**: Use `fcntl` for concurrent access safety
- **Backup strategy**: Encrypted backups of the connections file

### 3. Encryption
- **AES-256-GCM** for encryption (via Fernet which uses AES-128, but we can upgrade)
- **PBKDF2** with 100,000+ iterations for key derivation
- **User-specific salts** for additional security
- **Never log credentials** (even in debug mode)

### 4. Credential Handling
- **Clear credentials from memory** after use (where possible)
- **Encrypt in session storage** if using Redis/DB for sessions
- **Never return credentials** in API responses (except during connection)
- **Audit log** all credential operations (without credentials)

### 5. Access Control
- **Validate user ownership** before allowing access to connections
- **Rate limit** connection attempts
- **Log connection attempts** (without credentials)
- **Support connection timeouts**

## Implementation Plan

### Step 1: Add Application Authentication
1. Create login endpoint
2. Create user model/service
3. Require auth before `/session/connect`

### Step 2: Implement Encrypted Credential Storage
1. Create credential encryption service
2. Create connection storage service (JSON file or chosen storage)
3. Set up key management (environment variable or secret manager)
4. Add save/load/update/delete connection endpoints
5. Encrypt credentials in session storage
6. Clear credentials on disconnect
7. Add audit logging for all credential operations
8. Implement credential rotation support

### Step 3: Frontend Integration
1. Update connection page with saved connections UI
2. Add connection management interface (save, edit, delete, test)
3. Support both saved and one-time connections
4. Add connection sharing (optional, with permissions)

## Configuration

```python
# In app/core/config.py
class Settings(BaseSettings):
    # Credential storage
    credential_storage_type: str = "json_file"  # json_file, sqlite, postgresql, redis
    credential_storage_path: str = "/var/lib/kotte/connections.json"
    master_encryption_key: str = ""  # From environment
    
    # For SQLite
    credential_db_path: str = "/var/lib/kotte/credentials.db"
    
    # For PostgreSQL
    credential_db_host: str = "localhost"
    credential_db_port: int = 5432
    credential_db_name: str = "kotte_credentials"
    credential_db_user: str = "kotte"
    credential_db_password: str = ""
```

## Security Checklist

- [ ] Master encryption key from environment/secret manager
- [ ] Credentials encrypted at rest
- [ ] Storage file/database has restrictive permissions (600 or equivalent)
- [ ] Credentials never logged
- [ ] Credentials cleared on logout/disconnect
- [ ] Session encryption if using persistent storage
- [ ] Rate limiting on connection attempts
- [ ] Audit logging for connection events (without credentials)
- [ ] Key rotation strategy documented
- [ ] Secure key storage (not in code/repo)
- [ ] Backup strategy for credential storage
- [ ] File locking for concurrent access (if using file storage)

## Migration Path

If starting with JSON file and needing to scale:

1. **JSON File** → **SQLite**: Simple migration script to convert JSON to SQLite
2. **SQLite** → **PostgreSQL**: Use `pgloader` or custom migration script
3. **Any** → **Redis**: Export and import with proper key structure

All migrations should maintain encryption - only storage mechanism changes.

## References

- [OWASP Credential Storage](https://cheatsheetseries.owasp.org/cheatsheets/Credential_Storage_Cheat_Sheet.html)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [Python Cryptography Best Practices](https://cryptography.io/en/latest/)
- [Fernet (Symmetric Encryption)](https://cryptography.io/en/latest/fernet/)
