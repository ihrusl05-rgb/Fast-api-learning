from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool = True
    image: str | None = None
    model_config = ConfigDict(from_attributes=True)


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    icon: str = "📦"
    slug: str
    model_config = ConfigDict(from_attributes=True)

class ProductOut(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None = None
    price: Decimal
    is_active: bool = True
    image: str | None = None
    slug: str
    model_config = ConfigDict(from_attributes=True)