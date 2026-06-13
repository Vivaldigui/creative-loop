#!/usr/bin/env python3
"""Generate SECRET_KEY and ENCRYPTION_KEY for .env.
Run: python scripts/gen_keys.py
"""
import secrets
from cryptography.fernet import Fernet

secret_key = secrets.token_hex(32)
encryption_key = Fernet.generate_key().decode()

print("Add to your .env:")
print(f"SECRET_KEY={secret_key}")
print(f"ENCRYPTION_KEY={encryption_key}")
