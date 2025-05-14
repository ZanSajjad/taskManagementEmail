from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task, User
from app.auth import get_authenticated_user
from fastapi.responses import RedirectResponse
from datetime import datetime

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/add")
def add_task(
        request: Request,
        title: str = Form(...),
        description: str = Form(...),
        deadline: str = Form(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_authenticated_user)
):
    if deadline:
        deadline = datetime.strptime(deadline, "%Y-%m-%d")
    new_task = Task(title=title, description=description, deadline=deadline, owner_id=current_user.id)
    db.add(new_task)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/edit/{task_id}")
def edit_task(
        task_id: int,
        title: str = Form(...),
        description: str = Form(...),
        deadline: str = Form(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_authenticated_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.title = title
    task.description = description
    if deadline:
        task.deadline = datetime.strptime(deadline, "%Y-%m-%d")

    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/complete/{task_id}")
def complete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_authenticated_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.is_completed = True
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/delete/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_authenticated_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)