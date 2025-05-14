from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.staticfiles import StaticFiles
from app.database import get_db, Base, engine
from app.models import Task, User
from app.auth import get_authenticated_user
from app.routes import users, tasks,auth_google
from starlette.middleware.sessions import SessionMiddleware
import os
# Initialize FastAPI app
app = FastAPI()

# Create database tables
Base.metadata.create_all(bind=engine)

# Configure templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY"),
    session_cookie="session_token",
    max_age=3600
)

# Include routers
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(auth_google.router, prefix="/auth/google")
# Home route
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Dashboard route
@app.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user)
):
    # If user is not authenticated, redirect to login
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Fetch tasks for logged-in user
    tasks = db.query(Task).filter(Task.owner_id == current_user.id).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": current_user, "tasks": tasks})

