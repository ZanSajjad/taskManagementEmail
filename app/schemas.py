from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: Optional[int] = 1
    deadline: Optional[datetime] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: int
    deadline: Optional[datetime]
    is_completed: bool
    owner_id: Optional[int] = None

    class Config:
        from_attributes = True