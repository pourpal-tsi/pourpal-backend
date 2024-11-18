from fastapi import Request, Path, Header, Query
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone

from models import BeverageType
from service_funcs import bson_to_json, is_user_admin


async def get_item_types(request: Request):
    types = await request.app.mongodb['beverage_types'].find({}, {'_id': 0, 'added_at': 0}).sort("type", 1).to_list(length=None)
    types = bson_to_json(types)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"types": types})

async def create_item_type(request: Request, type: dict, authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    if 'type' not in type or not type['type']:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Type name is required"})

    existing_type = await request.app.mongodb['beverage_types'].find_one({"type": type['type']})
    if existing_type:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Type already exists"})

    new_type = BeverageType(type=type['type'])
    result = await request.app.mongodb['beverage_types'].insert_one(new_type.model_dump())
    if result.inserted_id:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Type created successfully", "type_id": new_type.type_id})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Failed to create type"})

async def update_item_type(request: Request, type: dict, type_id: str = Path(..., title="The ID of the type to update"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    if 'type' not in type or not type['type']:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Type name is required"})

    existing_type = await request.app.mongodb['beverage_types'].find_one({"type": type['type'], "type_id": {"$ne": type_id}})
    if existing_type:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Type name already exists"})

    result = await request.app.mongodb['beverage_types'].update_one(
        {"type_id": type_id},
        {"$set": {"type": type['type']}}
    )
    if result.modified_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Type updated successfully"})
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Type not found"})

async def delete_item_type(request: Request, type_id: str = Path(..., title="The ID of the type to delete"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    result = await request.app.mongodb['beverage_types'].delete_one({"type_id": type_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Type deleted successfully"})
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Type not found"})