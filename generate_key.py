"""
Generate a Fernet encryption key for cookie encryption
Run this and copy the output to your .env file
"""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print("Generated encryption key:")
    print(key.decode())
    print("\nCopy this key to your .env file as ENCRYPTION_KEY")
