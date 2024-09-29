from pydantic import BaseModel, Field, conlist, conset
from enum import Enum
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from decimal import Decimal
from typing import Literal
from bson import Decimal128


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
