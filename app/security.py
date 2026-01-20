import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Union, Generator
from contextlib import contextmanager
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

def get_encryption_key() -> bytes:
    """
    Get encryption key from environment or generate a temporary one.
    Warning: If a temporary key is used, encrypted files will be unreadable after restart.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Check if we have a key file (alternative persistence)
        key_file = Path(".encryption_key")
        if key_file.exists():
            return key_file.read_bytes().strip()
            
        logger.warning("ENCRYPTION_KEY not set! Generating temporary key. Encrypted files will be lost on restart.")
        new_key = Fernet.generate_key()
        # Try to save it to avoid data loss during dev
        try:
            key_file.write_bytes(new_key)
            logger.info(f"Generated new encryption key and saved to {key_file.absolute()}")
        except Exception as e:
            logger.warning(f"Could not save generated key: {e}")
            logger.warning(f"Key: {new_key.decode()}")
        return new_key
    return key.encode() if isinstance(key, str) else key

_FERNET: Optional[Fernet] = None

def get_fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        key = get_encryption_key()
        _FERNET = Fernet(key)
    return _FERNET

def encrypt_file(file_path: Union[str, Path]) -> None:
    """Encrypt a file in place."""
    path = Path(file_path)
    if not path.exists():
        return
        
    try:
        data = path.read_bytes()
        fernet = get_fernet()
        encrypted_data = fernet.encrypt(data)
        path.write_bytes(encrypted_data)
        logger.info(f"Encrypted file: {path}")
    except Exception as e:
        logger.error(f"Failed to encrypt file {path}: {e}")
        raise

def decrypt_file_content(file_path: Union[str, Path]) -> bytes:
    """Read and decrypt file content."""
    path = Path(file_path)
    data = path.read_bytes()
    try:
        fernet = get_fernet()
        return fernet.decrypt(data)
    except Exception:
        # Fallback: maybe it's not encrypted?
        logger.warning(f"Decryption failed for {path}, assuming plain text.")
        return data

@contextmanager
def decrypted_file_context(file_path: Union[str, Path]) -> Generator[str, None, None]:
    """
    Context manager that provides a path to a decrypted temporary file.
    Cleans up the temp file on exit.
    
    Usage:
        with decrypted_file_context(encrypted_path) as temp_path:
            process(temp_path)
    """
    path = Path(file_path)
    if not path.exists():
        yield str(path) # Return original if not exists (will fail later but safe)
        return

    decrypted_data = decrypt_file_content(path)
    
    # Create temp file with same extension
    suffix = path.suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(decrypted_data)
        tmp_path = tmp.name
    
    try:
        yield tmp_path
    finally:
        # Cleanup
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file {tmp_path}: {e}")
