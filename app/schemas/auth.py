from pydantic import BaseModel, EmailStr, Field


class ResetPassword(BaseModel):
    token: str = Field(..., min_length=30)
    new_password: str = Field(..., min_length=8)