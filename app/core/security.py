import os
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from jose import jwt
from passlib.context import CryptContext

load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Encryption for API keys
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
# Initialize with a direct approach to avoid indentation issues
if isinstance(ENCRYPTION_KEY, str):
    fernet = Fernet(ENCRYPTION_KEY.encode())
else:
    fernet = Fernet(ENCRYPTION_KEY)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key"""
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt an API key"""
    return fernet.decrypt(encrypted_api_key.encode()).decode()


def generate_forge_api_key() -> str:
    """
    Generate a unique Forge API key.
    """
    import secrets

    return f"forge-{secrets.token_hex(18)}"
