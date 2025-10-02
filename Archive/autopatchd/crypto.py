"""
Simple XOR-based credential encryption using system keys
"""

import base64
import hashlib
from pathlib import Path
import socket
import logging


class SimpleCredentialManager:
    """Simple XOR-based credential encryption"""
    
    def __init__(self):
        self.key = self._generate_system_key()
    
    def _generate_system_key(self) -> bytes:
        """Generate a system-specific encryption key"""
        # Combine multiple system identifiers for the key
        identifiers = []
        
        # Try machine-id first (most stable)
        machine_id_file = Path("/etc/machine-id")
        if machine_id_file.exists():
            try:
                identifiers.append(machine_id_file.read_text().strip())
            except Exception:
                pass
        
        # Fallback to hostname
        identifiers.append(socket.gethostname())
        
        # Add some filesystem info as salt
        try:
            stat = Path("/").stat()
            identifiers.append(str(stat.st_dev))
        except Exception:
            pass
        
        # Combine all identifiers
        combined = "|".join(identifiers)
        
        # Hash to get consistent key
        key_hash = hashlib.sha256(combined.encode()).digest()
        
        logging.debug(f"Generated encryption key from: {len(identifiers)} system identifiers")
        return key_hash
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using XOR"""
        if not plaintext:
            return ""
        
        plaintext_bytes = plaintext.encode('utf-8')
        key = self.key
        
        # XOR each byte with corresponding key byte (cycle key if needed)
        encrypted = bytearray()
        for i, byte in enumerate(plaintext_bytes):
            key_byte = key[i % len(key)]
            encrypted.append(byte ^ key_byte)
        
        # Base64 encode for safe storage
        return base64.b64encode(encrypted).decode('ascii')
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt encrypted string using XOR"""
        if not encrypted:
            return ""
        
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted.encode('ascii'))
            key = self.key
            
            # XOR to decrypt (XOR is its own inverse)
            decrypted = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                key_byte = key[i % len(key)]
                decrypted.append(byte ^ key_byte)
            
            return decrypted.decode('utf-8')
            
        except Exception as e:
            logging.error(f"Failed to decrypt credential: {e}")
            return ""
    
    def store_credentials(self, creds_file: Path, smtp_user: str, smtp_pass: str):
        """Store encrypted credentials to file"""
        creds_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Encrypt credentials
        encrypted_user = self.encrypt(smtp_user) if smtp_user else ""
        encrypted_pass = self.encrypt(smtp_pass) if smtp_pass else ""
        
        # Store in simple format
        content = f"SMTP_USER_ENC={encrypted_user}\nSMTP_PASS_ENC={encrypted_pass}\n"
        
        with open(creds_file, 'w') as f:
            f.write(content)
        
        # Secure file permissions
        creds_file.chmod(0o600)
        logging.info(f"Encrypted credentials stored: {creds_file}")
    
    def load_credentials(self, creds_file: Path) -> tuple[str, str]:
        """Load and decrypt credentials from file"""
        if not creds_file.exists():
            return None, None
        
        try:
            with open(creds_file, 'r') as f:
                content = f.read()
            
            encrypted_user = ""
            encrypted_pass = ""
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('SMTP_USER_ENC='):
                    encrypted_user = line.split('=', 1)[1]
                elif line.startswith('SMTP_PASS_ENC='):
                    encrypted_pass = line.split('=', 1)[1]
            
            # Decrypt
            smtp_user = self.decrypt(encrypted_user) if encrypted_user else None
            smtp_pass = self.decrypt(encrypted_pass) if encrypted_pass else None
            
            return smtp_user, smtp_pass
            
        except Exception as e:
            logging.error(f"Failed to load credentials: {e}")
            return None, None


def test_encryption():
    """Test the encryption/decryption"""
    manager = SimpleCredentialManager()
    
    test_user = "testuser@example.com"
    test_pass = "super_secret_password_123!"
    
    print("🔐 Testing credential encryption...")
    
    # Test encryption
    enc_user = manager.encrypt(test_user)
    enc_pass = manager.encrypt(test_pass)
    
    print(f"Original user: {test_user}")
    print(f"Encrypted user: {enc_user}")
    
    # Test decryption
    dec_user = manager.decrypt(enc_user)
    dec_pass = manager.decrypt(enc_pass)
    
    print(f"Decrypted user: {dec_user}")
    
    # Verify
    if dec_user == test_user and dec_pass == test_pass:
        print("✅ Encryption test passed!")
        return True
    else:
        print("❌ Encryption test failed!")
        return False


if __name__ == "__main__":
    test_encryption()