from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return value.lower()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        return value.strip()


class CategoryUpsert(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    icon: str = Field(min_length=1, max_length=10)
    slug: str = Field(min_length=2, max_length=50, pattern=SLUG_PATTERN)
    is_active: bool = True

    @field_validator("name", "icon", "slug")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProductUpsert(BaseModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0)
    image: str | None = Field(default=None, max_length=255)
    slug: str = Field(min_length=2, max_length=50, pattern=SLUG_PATTERN)
    is_active: bool = True

    @field_validator("name", "slug")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "image")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
