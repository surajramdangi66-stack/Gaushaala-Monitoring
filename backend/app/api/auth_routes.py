from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from backend.app.auth import authenticate_user, create_access_token, get_current_user
from backend.app.config import DEFAULT_USERS

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: Optional[str] = "operator"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password. Default is admin / gaushala2026",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    }

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    uname = req.username.strip().lower()
    if not uname or len(uname) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if uname in DEFAULT_USERS:
        raise HTTPException(status_code=400, detail="Username is already registered")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    new_user = {
        "username": uname,
        "full_name": req.full_name.strip() or uname.title(),
        "password_hash": req.password,
        "role": req.role if req.role in ["admin", "operator", "veterinarian"] else "operator"
    }
    DEFAULT_USERS[uname] = new_user

    token = create_access_token(data={"sub": uname, "role": new_user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": uname,
            "full_name": new_user["full_name"],
            "role": new_user["role"]
        }
    }

@router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"]
    }
