from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=1,
        max_length=100,
    )

    password: str = Field(
        min_length=1,
        max_length=1024,
    )


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


class LoginResponse(BaseModel):
    message: str
    user: UserResponse


class LogoutResponse(BaseModel):
    message: str
