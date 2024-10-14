import pathlib
from datetime import datetime, timedelta, timezone
import passlib
from uuid import uuid4
from motor.motor_asyncio import AsyncIOMotorClient
from bson import Decimal128, json_util
from contextlib import asynccontextmanager
from config import MONGO_DB

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from models import Item, Money, Volume

import json
from random import randint


def generate_sku(type_name: str) -> str:
    type_code = type_name[:3].upper()
    random_number = randint(1000000, 9999999)
    return f"{type_code}{random_number}"    

def get_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(':')[0]
        port = x_forwarded_for.split(':')[1]
        return ip_address
    return None

def decimal128_to_str(obj):
    if isinstance(obj, Decimal128):
        return str(obj.to_decimal())
    return obj

async def validate_item_attrs(request, item):
    # Validate type_id, brand_id, and origin_country_code
    type_id = item.get('type_id')
    brand_id = item.get('brand_id')
    origin_country_code = item.get('origin_country_code')

    # Check if type_name is valid
    valid_type = await request.app.mongodb['beverage_types'].find_one({"type_id": type_id})
    if not valid_type:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid type_id"}), None, None, None)

    # Check if brand_name is valid
    valid_brand = await request.app.mongodb['beverage_brands'].find_one({"brand_id": brand_id})
    if not valid_brand:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid brand_id"}), None, None, None)

    # Check if origin_country_name is valid
    valid_country = await request.app.mongodb['countries'].find_one({"code": origin_country_code})
    if not valid_country:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid origin_country_code"}), None, None, None)
    
    return (True, JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Validation successful"}), valid_type, valid_brand, valid_country)

def bson_to_json(data):
    if isinstance(data, dict):
        return {key: bson_to_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [bson_to_json(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, Decimal128):
        return str(data.to_decimal())
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict) and '$date' in data:
        return data['$date']
    elif isinstance(data, dict) and '$numberDecimal' in data:
        return str(data['$numberDecimal'])
    else:
        return data
