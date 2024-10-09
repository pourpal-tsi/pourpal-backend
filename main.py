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
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form, HTTPException, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from math import ceil

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
    """
    Root endpoint.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing a warning message.
    """
    return JSONResponse(status_code=status.HTTP_200_OK, content={"WARNING": f"We know who you are. Your IP address is {get_client_ip(request)}. Your name is Daniils. We will find you and you will be sorry for visiting this webpage!"})

@app.get("/items", response_class=JSONResponse)
async def get_items(
    request: Request,
    search: Optional[str] = Query(None, description="Search items by title (case-insensitive, substring match)"),
    types: Optional[str] = Query(None, description="Filter by beverage types (comma-separated)"),
    countries: Optional[str] = Query(None, description="Filter by countries of origin (comma-separated)"),
    brands: Optional[str] = Query(None, description="Filter by brands (comma-separated)"),
    min_price: Optional[float] = Query(None, description="Minimum price for filtering"),
    max_price: Optional[float] = Query(None, description="Maximum price for filtering"),
    sort_by: Optional[str] = Query(None, description="Field to sort by (sku, title, type, brand, country, quantity)"),
    sort_order: Optional[str] = Query("asc", description="Sort order (asc or desc)"),
    page_size: int = Query(25, ge=1, le=100, description="Number of items per page"),
    page_number: int = Query(1, ge=1, description="Page number"),
):
    """
    Retrieve a paginated list of items with optional filtering and sorting.

    Args:
        request (Request): The incoming request object.
        search (str, optional): Search items by title (case-insensitive, substring match).
        types (str, optional): Filter by beverage types (comma-separated).
        countries (str, optional): Filter by countries of origin (comma-separated).
        brands (str, optional): Filter by brands (comma-separated).
        min_price (float, optional): Minimum price for filtering.
        max_price (float, optional): Maximum price for filtering.
        sort_by (str, optional): Field to sort by (sku, title, type, brand, country, quantity).
        sort_order (str, optional): Sort order (asc or desc). Defaults to "asc".
        page_size (int, optional): Number of items per page. Defaults to 25.
        page_number (int, optional): Page number. Defaults to 1.

    Returns:
        JSONResponse: A JSON response containing the list of items and pagination metadata.

    Example:
        ```
        GET /items?search=wine&types=red,white&countries=FR,IT&brands=Chateau&min_price=10&max_price=50&sort_by=price&sort_order=desc&page_size=10&page_number=1

        Response:
        {
            "items": [
                {
                    "item_id": "550e8400-e29b-41d4-a716-446655440000",
                    "sku": "W123",
                    "title": "Chateau Margaux",
                    "image_url": "https://example.com/chateau-margaux.jpg",
                    "description": "A fine red wine from Bordeaux",
                    "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
                    "type_name": "red",
                    "price": {
                        "amount": "45.99",
                        "currency": "€"
                    },
                    "volume": {
                        "amount": "750",
                        "unit": "ml"
                    },
                    "alcohol_volume": {
                        "amount": "13.5",
                        "unit": "%"
                    },
                    "quantity": 10,
                    "origin_country_code": "FR",
                    "origin_country_name": "France",
                    "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7",
                    "brand_name": "Chateau",
                    "updated_at": "2023-04-01T12:00:00Z",
                    "added_at": "2023-03-15T09:30:00Z"
                },
                // ... more items ...
            ],
            "paging": {
                "count": 10,
                "page_size": 10,
                "page_number": 1,
                "total_count": 50,
                "total_pages": 5,
                "first_page": true,
                "last_page": false
            }
        }
        ```
    """
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

    # Sorting logic
    sort_fields = {
        "sku": "sku",
        "title": "title",
        "type": "type_name",
        "brand": "brand_name",
        "country": "origin_country_name",
        "quantity": "quantity"
    }

    if sort_by and sort_by in sort_fields:
        sort_field = sort_fields[sort_by]
        sort_direction = 1 if sort_order.lower() == "asc" else -1
        sort_query = [(sort_field, sort_direction)]
    else:
        sort_query = None

    # Count total matching items
    total_count = await request.app.mongodb['items'].count_documents(query)

    # Calculate pagination metadata
    total_pages = ceil(total_count / page_size)
    skip = (page_number - 1) * page_size

    # Fetch paginated items with sorting
    items = await request.app.mongodb['items'].find(query, {'_id': 0}).sort(sort_query).skip(skip).limit(page_size).to_list(length=None)

    items = jsonable_encoder(bson_to_json(items))
    
    # Prepare pagination metadata
    paging = {
        "count": len(items),
        "page_size": page_size,
        "page_number": page_number,
        "total_count": total_count,
        "total_pages": total_pages,
        "first_page": page_number == 1,
        "last_page": page_number == total_pages
    }

    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items, "paging": paging})

@app.get("/item/{item_id}", response_class=JSONResponse)
async def get_item(request: Request, item_id: str = Path(..., title="The ID of the item to retrieve")):
    """
    Retrieve a specific item by its ID.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to retrieve.

    Returns:
        JSONResponse: A JSON response containing the item details.

    Example:
        ```
        GET /item/550e8400-e29b-41d4-a716-446655440000

        Response:
        {
            "item": {
                "item_id": "550e8400-e29b-41d4-a716-446655440000",
                "sku": "W123",
                "title": "Chateau Margaux",
                "image_url": "https://example.com/chateau-margaux.jpg",
                "description": "A fine red wine from Bordeaux",
                "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
                "type_name": "red",
                "price": {
                    "amount": "45.99",
                    "currency": "€"
                },
                "volume": {
                    "amount": "750",
                    "unit": "ml"
                },
                "alcohol_volume": {
                    "amount": "13.5",
                    "unit": "%"
                },
                "quantity": 10,
                "origin_country_code": "FR",
                "origin_country_name": "France",
                "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7",
                "brand_name": "Chateau",
                "updated_at": "2023-04-01T12:00:00Z",
                "added_at": "2023-03-15T09:30:00Z"
            }
        }
        ```
    """
    item = await request.app.mongodb['items'].find_one({"item_id": item_id}, {'_id': 0})
    item = jsonable_encoder(bson_to_json(item)) if item else None
    return JSONResponse(status_code=status.HTTP_200_OK, content={"item": item})

@app.post("/items", response_class=JSONResponse)
async def create_item(request: Request, item: dict):
    """
    Create a new item.

    Args:
        request (Request): The incoming request object.
        item (dict): The item data to create.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /items
        Content-Type: application/json

        {
            "title": "Chateau Lafite",
            "image_url": "https://example.com/chateau-lafite.jpg",
            "description": "A prestigious Bordeaux wine",
            "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
            "price": "55.99",
            "volume": "750",
            "volume_unit": "ml",
            "alcohol_volume": "13.5",
            "quantity": 5,
            "origin_country_code": "FR",
            "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7"
        }

        Response:
        {
            "message": "Item created successfully",
            "item_id": "660e8400-e29b-41d4-a716-446655440001"
        }
        ```
    """
    is_valid, validation_response, valid_type, valid_brand, valid_country = await validate_item_attrs(request, item)
    if not is_valid:
        return validation_response
    
    try:
        new_item = Item(
            sku=generate_sku(type_name=valid_type['type']),
            title=item['title'],
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
    """
    Update an existing item.

    Args:
        request (Request): The incoming request object.
        item (dict): The updated item data.
        item_id (str): The ID of the item to update.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        PUT /item/550e8400-e29b-41d4-a716-446655440000
        Content-Type: application/json

        {
            "price": "47.99",
            "quantity": 8
        }

        Response:
        {
            "message": "Item updated successfully",
            "item_id": "550e8400-e29b-41d4-a716-446655440000"
        }
        ```
    """
    is_valid, validation_response, valid_type, valid_brand, valid_country = await validate_item_attrs(request, item)
    if not is_valid:
        return validation_response

    try:    
        db_item = await request.app.mongodb['items'].find_one({"item_id": item_id}, {'_id': 0})

        updated_item = Item(
            sku=db_item['sku'],
            title=item['title'],
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
            brand_name=valid_brand['brand'],
            updated_at=datetime.now(timezone.utc),
            added_at=db_item['added_at']
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
    """
    Delete an item by its ID.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to delete.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        DELETE /item/{uuid}

        Response:
        {
            "message": "Item deleted successfully",
            "item_id": "{uuid}"
        }
        ```
    """
    result = await request.app.mongodb['items'].delete_one({"item_id": item_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item deleted successfully"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})

@app.get("/items/types", response_class=JSONResponse)
async def get_item_types(request: Request):
    """
    Retrieve all available item types.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the list of item types.

    Example:
        ```
        GET /items/types

        Response:
        {
            "types": [
                {
                    "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
                    "type": "red"
                },
                {
                    "type_id": "2b3c4d5e-6f7g-8h9i-0j1k-2l3m4n5o6p7q",
                    "type": "white"
                },
                // ... more types ...
            ]
        }
        ```
    """
    types = await request.app.mongodb['beverage_types'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    types = jsonable_encoder(bson_to_json(types))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"types": types})

@app.get("/items/brands", response_class=JSONResponse)
async def get_item_brands(request: Request):
    """
    Retrieve all available item brands.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the list of item brands.

    Example:
        ```
        GET /items/brands

        Response:
        {
            "brands": [
                {
                    "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7",
                    "brand": "Chateau"
                },
                {
                    "brand_id": "8q9w0e1r-2t3y-4u5i-6o7p-8a9s0d1f2g3h",
                    "brand": "Domaine"
                },
                // ... more brands ...
            ]
        }
        ```
    """
    brands = await request.app.mongodb['beverage_brands'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    brands = jsonable_encoder(bson_to_json(brands))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"brands": brands})

@app.get("/items/countries", response_class=JSONResponse)
async def get_item_countries(request: Request):
    """
    Retrieve all available item countries.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the list of item countries.

    Example:
        ```
        GET /items/countries

        Response:
        {
            "countries": [
                {
                    "code": "FR",
                    "unicode": "U+1F1EB U+1F1F7",
                    "name": "France",
                    "emoji": "🇫🇷"
                },
                {
                    "code": "IT",
                    "unicode": "U+1F1EE U+1F1F9",
                    "name": "Italy",
                    "emoji": "🇮🇹"
                },
                // ... more countries ...
            ]
        }
        ```
    """
    countries = await request.app.mongodb['countries'].find({}, {'_id': 0, 'added_at': 0}).to_list(length=None)
    countries = jsonable_encoder(bson_to_json(countries))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"countries": countries})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
