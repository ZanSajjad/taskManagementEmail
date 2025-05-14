from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from app.database import get_db
from app.models import User
from app.auth import (
    hash_password, verify_password, get_authenticated_user,
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    send_verification_email, send_password_reset_email,
    create_verification_token, create_reset_token
)

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
def register_user(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...),
        db: Session = Depends(get_db)
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"}
        )

    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email or username already registered"}
        )

    hashed_password = hash_password(password)
    verification_token = create_verification_token()

    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        verification_token=verification_token,
        is_active=False
    )
    db.add(new_user)
    db.commit()

    send_verification_email(email, verification_token)

    return templates.TemplateResponse(
        "register_success.html",
        {"request": request, "email": email}
    )


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(
        request: Request,
        token: str,
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        return templates.TemplateResponse(
            "verification_failed.html",
            {"request": request}
        )

    user.email_verified = True
    user.is_active = True
    user.verification_token = None
    db.commit()

    return templates.TemplateResponse(
        "verification_success.html",
        {"request": request}
    )


@router.get("/resend-verification", response_class=HTMLResponse)
def resend_verification_page(request: Request):
    return templates.TemplateResponse("resend_verification.html", {"request": request})


@router.post("/resend-verification", response_class=HTMLResponse)
def resend_verification(
        request: Request,
        email: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified:
        if not user.verification_token:
            user.verification_token = create_verification_token()
            db.commit()

        send_verification_email(email, user.verification_token)

    # Always return success to prevent email enumeration
    return templates.TemplateResponse(
        "resend_verification_success.html",
        {"request": request, "email": email}
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    flash_message = request.cookies.get("flash_message")
    response = templates.TemplateResponse(
        "login.html",
        {"request": request, "flash_message": flash_message}
    )
    if flash_message:
        response.delete_cookie("flash_message")
    return response


@router.post("/login", response_class=HTMLResponse)
def login_user(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )

    if not user.email_verified:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Email not verified. Please check your email for the verification link."
            }
        )

    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account is not active. Please contact support."}
        )

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


@router.get("/logout", response_class=HTMLResponse)
def logout():
    response = RedirectResponse(url="/users/login")
    response.delete_cookie("access_token")
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(
        request: Request,
        email: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if user:
        reset_token = create_reset_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=15)
        db.commit()

        send_password_reset_email(email, reset_token)

    # Always return success to prevent email enumeration
    return templates.TemplateResponse(
        "forgot_password_success.html",
        {"request": request, "email": email}
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(
        request: Request,
        token: str,
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expires > datetime.utcnow()
    ).first()

    if not user:
        return templates.TemplateResponse(
            "reset_password_invalid.html",
            {"request": request}
        )

    return templates.TemplateResponse(
        "reset_password.html",
        {"request": request, "token": token}
    )


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(
        request: Request,
        token: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...),
        db: Session = Depends(get_db)
):
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error": "Passwords don't match"}
        )

    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expires > datetime.utcnow()
    ).first()

    if not user:
        return templates.TemplateResponse(
            "reset_password_invalid.html",
            {"request": request}
        )

    user.hashed_password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return templates.TemplateResponse(
        "reset_password_success.html",
        {"request": request}
    )


# @router.get("/profile", response_class=HTMLResponse)
# def profile_page(
#         request: Request,
#         current_user: User = Depends(get_authenticated_user),
#         db: Session = Depends(get_db)
# ):
#     if isinstance(current_user, RedirectResponse):
#         return current_user
#
#     return templates.TemplateResponse(
#         "profile.html",
#         {"request": request, "user": current_user}
#     )