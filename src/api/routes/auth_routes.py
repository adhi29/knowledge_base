"""Authentication endpoints: login, register, me."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from src.api.auth import authenticate_user, register_user, create_access_token, get_current_user, TokenData
from src.api.models import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_access_token({
        "sub":      user["user_id"],
        "username": user["username"],
        "role":     user["role"],
    })
    return TokenResponse(
        access_token=token,
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
    )


@router.post("/register", status_code=201)
def register(req: RegisterRequest):
    return register_user(req.username, req.password, req.role, req.department)


@router.get("/me")
def me(current_user: TokenData = Depends(get_current_user)):
    return {
        "user_id":  current_user.user_id,
        "username": current_user.username,
        "role":     current_user.role,
    }
