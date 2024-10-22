from fastapi import Request, Path, Header, Query
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone

from models import Brand
from service_funcs import bson_to_json, is_user_admin


async def get_item_brands(request: Request):
    brands = await request.app.mongodb['beverage_brands'].find({}, {'_id': 0, 'added_at': 0}).sort("brand", 1).to_list(length=None)
    brands = bson_to_json(brands)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"brands": brands})

async def create_item_brand(request: Request, brand: dict, authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    if 'brand' not in brand or not brand['brand']:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Brand name is required"})

    existing_brand = await request.app.mongodb['beverage_brands'].find_one({"brand": brand['brand']})
    if existing_brand:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Brand already exists"})

    new_brand = Brand(brand=brand['brand'])
    result = await request.app.mongodb['beverage_brands'].insert_one(new_brand.model_dump())
    if result.inserted_id:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Brand created successfully", "brand_id": new_brand.brand_id})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Failed to create brand"})

async def update_item_brand(request: Request, brand: dict, brand_id: str = Path(..., title="The ID of the brand to update"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    if 'brand' not in brand or not brand['brand']:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Brand name is required"})

    existing_brand = await request.app.mongodb['beverage_brands'].find_one({"brand": brand['brand'], "brand_id": {"$ne": brand_id}})
    if existing_brand:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Brand name already exists"})

    result = await request.app.mongodb['beverage_brands'].update_one(
        {"brand_id": brand_id},
        {"$set": {"brand": brand['brand']}}
    )
    if result.modified_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Brand updated successfully"})
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Brand not found"})

async def delete_item_brand(request: Request, brand_id: str = Path(..., title="The ID of the brand to delete"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    result = await request.app.mongodb['beverage_brands'].delete_one({"brand_id": brand_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Brand deleted successfully"})
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Brand not found"})
