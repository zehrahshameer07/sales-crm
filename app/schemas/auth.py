from typing import Optional

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class DemoAccount(BaseModel):
    role: str
    email: str
    password: str


class AuthConfig(BaseModel):
    demo_accounts: list[DemoAccount] = []
    password_min_length: int = 10
    app_timezone: str
    version: str
    demo_note: Optional[str] = None
