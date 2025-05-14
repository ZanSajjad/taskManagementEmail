from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, Request, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from app.database import get_db
from app.models import User
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent/ '.env'
load_dotenv(env_path)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Email settings
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
print((SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD))
EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@example.com")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    return user

def get_authenticated_user(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        response = RedirectResponse(url="/users/login", status_code=303)
        response.set_cookie("flash_message", "Please log in to access this page.")
        return response
    return user

def send_verification_email(email: str, token: str):
    subject = "Verify your email address"
    verification_url = f"{BASE_URL}/users/verify-email?token={token}"

    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = email
    message["Subject"] = subject

    body = f"""
    <h1>Welcome to our Task Management System!</h1>
    <p>Please click the link below to verify your email address:</p>
    <a href="{verification_url}">Verify Email</a>
    <p>If you didn't create an account, you can safely ignore this email.</p>
    """

    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except Exception as e:
        print(f"Error sending verification email: {e}")

def send_password_reset_email(email: str, token: str):
    subject = "Password Reset Request"
    reset_url = f"{BASE_URL}/users/reset-password?token={token}"

    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = email
    message["Subject"] = subject

    body = f"""
    <h1>Password Reset Request</h1>
    <p>We received a request to reset your password. Click the link below to reset it:</p>
    <a href="{reset_url}">Reset Password</a>
    <p>This link will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
    """

    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except Exception as e:
        print(f"Error sending password reset email: {e}")

def create_verification_token() -> str:
    return secrets.token_urlsafe(32)

def create_reset_token() -> str:
    return secrets.token_urlsafe(32)