from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DEFAULT_USERS
from backend.app.db.database import SessionLocal
from backend.app.db.models import UserModel

security = HTTPBearer(auto_error=False)

def verify_password(plain_password: str, stored_password: str) -> bool:
    return plain_password == stored_password

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    # First, query database
    try:
        db = SessionLocal()
        try:
            db_user = db.query(UserModel).filter(UserModel.username == username).first()
            if db_user:
                if verify_password(password, db_user.password_hash):
                    return {
                        "username": db_user.username,
                        "full_name": db_user.full_name,
                        "role": db_user.role
                    }
                return None
        finally:
            db.close()
    except Exception:
        pass

    # Fallback to configured defaults
    user = DEFAULT_USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"]
    }

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    payload = decode_token(token)
    if payload is None:
        return None
    username = payload.get("sub")
    if not username:
        return None

    try:
        db = SessionLocal()
        try:
            db_user = db.query(UserModel).filter(UserModel.username == username).first()
            if db_user:
                return {
                    "username": db_user.username,
                    "full_name": db_user.full_name,
                    "role": db_user.role
                }
        finally:
            db.close()
    except Exception:
        pass

    if username in DEFAULT_USERS:
        return DEFAULT_USERS[username]
    return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    user = get_user_from_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
