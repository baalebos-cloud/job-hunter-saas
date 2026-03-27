from pydantic import BaseModel, EmailStr, Field

# -----------------------------
# Request models
# -----------------------------
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

    model_config = {
        "from_attributes": True  # Pydantic v2 replacement for orm_mode
    }

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    model_config = {
        "from_attributes": True
    }

# -----------------------------
# Response models
# -----------------------------
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str

    model_config = {
        "from_attributes": True
    }

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token for authenticated user")
    token_type: str = Field(default="bearer", description="Token type, usually 'bearer'")

    model_config = {
        "from_attributes": True
    }
