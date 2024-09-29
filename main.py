import pathlib
from datetime import datetime, timedelta, timezone
import passlib
from uuid import uuid4
from motor.motor_asyncio import AsyncIOMotorClient
from bson import Decimal128
from contextlib import asynccontextmanager
from config import MONGO_DB

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from fastapi import Path
from fastapi.encoders import jsonable_encoder
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from models import Item, Money, Volume

from service_funcs import bson_to_json, get_client_ip, validate_item_attrs, generate_sku


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Atlas at application startup
    app.mongodb_client = AsyncIOMotorClient(MONGO_DB)
    app.mongodb = app.mongodb_client['pourpal']
    yield
    # Disconnect from Atlas at application shutdown
    app.mongodb_client.close()

# TODO: disable docs, redoc, openapi in production
app = FastAPI(
    lifespan=lifespan,
    # docs_url=None,     # Disable /docs
    # redoc_url=None,    # Disable /redoc
    # openapi_url=None   # Disable /openapi.json
) 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Endpoints

@app.get("/", response_class=JSONResponse)
async def root(request: Request):
    return JSONResponse(status_code=status.HTTP_200_OK, content={"WARNING": f"We know who you are. Your IP address is {get_client_ip(request)}. Your name is Daniils. We will find you and you will be sorry for visiting this webpage!"})

@app.get("/items", response_class=JSONResponse)  # Example: /items?search=X&types=X,X&countries=X,X&brands=X,X&min_price=X&max_price=X
async def get_items(
    request: Request,
    search: Optional[str] = Query(None, description="Search items by title (case-insensitive, substring match)"), 
    types: Optional[str] = Query(None, description="Filter by beverage types (comma-separated)"),
    countries: Optional[str] = Query(None, description="Filter by countries of origin (comma-separated)"), 
    brands: Optional[str] = Query(None, description="Filter by brands (comma-separated)"),
    min_price: Optional[float] = Query(None, description="Minimum price for filtering"),  
    max_price: Optional[float] = Query(None, description="Maximum price for filtering"),
):
    query = {}

    if search:
        query["title"] = {"$regex": search, "$options": "i"}

    if types:
        type_list = [t.strip() for t in types.split(',')]
        query["type_id"] = {"$in": type_list}

    if countries:
        country_list = [c.strip() for c in countries.split(',')]
        query["origin_country_code"] = {"$in": country_list}

    if brands:
        brand_list = [b.strip() for b in brands.split(',')]
        query["brand_id"] = {"$in": brand_list}

    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            price_query["$gte"] = Decimal128(str(min_price))
        if max_price is not None:
            price_query["$lte"] = Decimal128(str(max_price))
        query["price.amount"] = price_query

    items = await request.app.mongodb['items'].find(query, {'_id': 0}).to_list(length=None)

    items = jsonable_encoder(bson_to_json(items))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items})

@app.get("/item/{item_id}", response_class=JSONResponse)
async def get_item(request: Request, item_id: str = Path(..., title="The ID of the item to retrieve")):
    item = await request.app.mongodb['items'].find_one({"item_id": item_id}, {'_id': 0})
    item = jsonable_encoder(bson_to_json(item)) if item else None
    return JSONResponse(status_code=status.HTTP_200_OK, content={"item": item})

@app.post("/items", response_class=JSONResponse)
async def create_item(request: Request, item: dict):
    is_valid, validation_response, valid_type, valid_brand, valid_country = await validate_item_attrs(request, item)
    if not is_valid:
        return validation_response
    
    try:
        new_item = Item(
            title=item['title'],
            sku=generate_sku(type_name=valid_type['type']),
            image_url=item['image_url'],
            description=item['description'],
            type_id=valid_type['type_id'],
            type_name=valid_type['type'],
            price=Money(amount=Decimal128(item['price'])),
            volume=Volume(amount=Decimal128(item['volume']), unit=item['volume_unit']),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']), unit='%'),
            quantity=item['quantity'],
            origin_country_code=valid_country['code'],
            origin_country_name=valid_country['name'],
            brand_id=valid_brand['brand_id'],
            brand_name=valid_brand['brand']
        )       
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": str(e)})

    result = await request.app.mongodb['items'].insert_one(new_item.model_dump())
    if result.inserted_id:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Item created successfully", "item_id": new_item.item_id})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Failed to create item"})

@app.put("/item/{item_id}", response_class=JSONResponse)
async def update_item(request: Request, item: dict, item_id: str = Path(..., title="The ID of the item to update")):
    is_valid, validation_response, valid_type, valid_brand, valid_country = await validate_item_attrs(request, item)
    if not is_valid:
        return validation_response

    try:    
        updated_item = Item(
            title=item['title'],
            sku=item['sku'],
            image_url=item['image_url'],
            description=item['description'],
            type_id=valid_type['type_id'],
            type_name=valid_type['type'],
            price=Money(amount=Decimal128(item['price'])),
            volume=Volume(amount=Decimal128(item['volume']), unit=item['volume_unit']),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']), unit='%'),
            quantity=item['quantity'],
            origin_country_code=valid_country['code'],
            origin_country_name=valid_country['name'],
            brand_id=valid_brand['brand_id'],
            brand_name=valid_brand['brand']
        )            
    except Exception as e:
        return JSONResponse(status_code=400, detail=str(e))

    result = await request.app.mongodb['items'].update_one(
        {"item_id": item_id},
        {"$set": updated_item.model_dump(exclude={"item_id"})}
    )
    if result.modified_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item updated successfully"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})

@app.delete("/item/{item_id}", response_class=JSONResponse)
async def delete_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete")):
    result = await request.app.mongodb['items'].delete_one({"item_id": item_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item deleted successfully"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})

@app.get("/items/types", response_class=JSONResponse)
async def get_item_types(request: Request):
    types = await request.app.mongodb['beverage_types'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    types = jsonable_encoder(bson_to_json(types))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"types": types})

@app.get("/items/brands", response_class=JSONResponse)
async def get_item_brands(request: Request):
    brands = await request.app.mongodb['beverage_brands'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    brands = jsonable_encoder(bson_to_json(brands))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"brands": brands})

@app.get("/items/countries", response_class=JSONResponse)
async def get_item_countries(request: Request):
    countries = await request.app.mongodb['countries'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    countries = jsonable_encoder(bson_to_json(countries))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"countries": countries})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
