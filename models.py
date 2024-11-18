from pydantic import BaseModel, Field, conlist, conset
from enum import Enum
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from decimal import Decimal
from typing import Literal
from bson import Decimal128
import bcrypt
from service_rules import CART_EXPIRATION_TIME_DAYS


class Money(BaseModel):
    amount: Decimal128 | str
    currency: Literal['£', '€', '$'] = '€'

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_decimal128

    @classmethod
    def validate_decimal128(cls, v):
        if isinstance(v, Decimal128):
            return v
        return Decimal128(str(v))
    
    
class Volume(BaseModel):
    amount: Decimal128 | str
    unit: Literal['ml', 'cl', 'dl', 'l', '%']
    
    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_decimal128

    @classmethod
    def validate_decimal128(cls, v):
        if isinstance(v, Decimal128):
            return v
        return Decimal128(str(v))
    

class Country(BaseModel):
    code: str
    unicode: str
    name: str
    emoji: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BeverageType(BaseModel):
    type_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Brand(BaseModel):
    brand_id: str = Field(default_factory=lambda: str(uuid4()))
    brand: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Item(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    sku: str
    title: str
    image_url: str
    description: str
    type_id: str
    type_name: str
    price: Money
    volume: Volume
    alcohol_volume: Volume
    quantity: int
    origin_country_code: str
    origin_country_name: str
    brand_id: str
    brand_name: str
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserAuthorization(BaseModel):
    headers: dict | None = None
    timestamp: datetime


class User(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    password: str
    encoded_password: str = ""
    full_name: str | None = None
    gender: bool = True  # True = male, False = female
    sessions_ids: list[str] = []
    is_active: bool = True
    authorizations: list[UserAuthorization] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __init__(self, **data):
        super().__init__(**data)
        if self.password and not self.encoded_password:
            self.encoded_password = self.encode_password(self.password)
            self.password = ""  # Clear the plain text password

    @staticmethod
    def encode_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


class UserAdmin(User):
    role: Literal['admin'] = 'admin'


class CartItem(BaseModel):
    item_id: str
    quantity: int
    unit_price: Money
    total_price: Money


class Cart(BaseModel):
    cart_id: str = Field(default_factory=lambda: str(uuid4()))
    cart_items: list[CartItem] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expiration_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=CART_EXPIRATION_TIME_DAYS))


class DeliveryInformation(BaseModel):
    recipient_name: str
    recipient_phone: str
    recipient_city: str
    recipient_street_address: str
    comment: str | None = None


class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid4()))
    order_number: str  # Order number consisting of 9 digits like '000000001'
    user_id: str | None = None
    status: Literal['pending', 'completed', 'cancelled', 'returned'] = 'pending'
    delivery_information: DeliveryInformation | None = None
    order_items: list[CartItem] = []
    total_price: Money
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    

class UserCustomer(User):
    role: Literal['customer'] = 'customer'
    carts_ids: list[str] = []
