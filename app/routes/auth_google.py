# auth_google.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.auth import (
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    hash_password, get_current_user
)
from datetime import timedelta
import httpx
from urllib.parse import urlencode
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

router = APIRouter()

# Google OAuth settings (should be in environment variables)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

print((GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

@router.get("/login")
async def google_login():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_callback(
        request: Request,
        code: str,
        db: Session = Depends(get_db)
):
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )

    tokens = token_response.json()
    if token_response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail="Failed to get access token from Google"
        )

    # Get user info
    async with httpx.AsyncClient() as client:
        user_info_response = await client.get(
            GOOGLE_USER_INFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

    user_info = user_info_response.json()

    # Check if user exists
    user = db.query(User).filter(
        (User.email == user_info["email"]) |
        (User.google_id == user_info["sub"])
    ).first()

    if not user:
        # Create new user
        user = User(
            username=user_info["email"].split("@")[0],
            email=user_info["email"],
            google_id=user_info["sub"],
             is_active=True,
            email_verified=True
        )
        db.add(user)
        db.commit()
    elif not user.google_id:
        # Update existing user with Google ID
        user.google_id = user_info["sub"]
        user.profile_picture = user_info.get("picture")
        user.email_verified = True
        user.is_active = True
        db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return response