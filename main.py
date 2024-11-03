import pathlib
import passlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from motor.motor_asyncio import AsyncIOMotorClient
from bson import Decimal128
from contextlib import asynccontextmanager
from config import MONGO_DB

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form, HTTPException, Query, Path, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from server_items import get_items, get_item, create_item, update_item, delete_item
from server_countries import get_item_countries
from server_brands import get_item_brands, create_item_brand, update_item_brand, delete_item_brand
from server_types import get_item_types, create_item_type, update_item_type, delete_item_type
from server_registration_authentication import login, register_admin, register_customer, get_profile
from server_cart import get_cart, increment_cart_item, decrement_cart_item, update_cart_item, delete_cart_item


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

# @app.get("/", response_class=JSONResponse)
# async def root(request: Request):
#     """
#     Root endpoint.

#     Args:
#         request (Request): The incoming request object.

#     Returns:
#         JSONResponse: A JSON response containing a warning message.
#     """
#     return JSONResponse(status_code=status.HTTP_200_OK, content={"WARNING": f"We know who you are. Your IP address is {get_client_ip(request)}. Your name is Daniils. We will find you and you will be sorry for visiting this webpage!"})

@app.get("/", response_class=JSONResponse)
async def root(request: Request):
    """
    Redirect to the API documentation.

    Args:
        request (Request): The incoming request object.

    Returns:
        RedirectResponse: A redirect response to the API documentation.
    """
    return RedirectResponse(url="/docs")

# Items
@app.get("/items", response_class=JSONResponse)
async def api_get_items(
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
        types (str, optional): Filter by beverage types (comma-separated) using type_id.
        countries (str, optional): Filter by countries of origin (comma-separated) using country_code.
        brands (str, optional): Filter by brands (comma-separated) using brand_id.
        min_price (float, optional): Minimum price for filtering.
        max_price (float, optional): Maximum price for filtering.
        sort_by (str, optional): Field to sort by (sku, title, type, brand, country, quantity, price).
        sort_order (str, optional): Sort order (asc or desc). Defaults to "asc".
        page_size (int, optional): Number of items per page. Defaults to 25.
        page_number (int, optional): Page number. Defaults to 1.

    Returns:
        JSONResponse: A JSON response containing the list of items and pagination metadata.

    Example:
        ```
        GET /items?search=wine&types=[uuid of type]&countries=FR,IT&brands=[uuid of brand]&min_price=10&max_price=50&sort_by=price&sort_order=desc&page_size=10&page_number=1

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

    Sort fields:
        - sku
        - title
        - type_name
        - brand_name
        - origin_country_name
        - quantity
        - price

    Sort order:
        - asc
        - desc
    """
    return await get_items(request, search, types, countries, brands, min_price, max_price, sort_by, sort_order, page_size, page_number)

@app.get("/items/{item_id}", response_class=JSONResponse)
async def api_get_item(request: Request, item_id: str = Path(..., title="The ID of the item to retrieve")):
    """
    Retrieve a specific item by its ID.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to retrieve.

    Returns:
        JSONResponse: A JSON response containing the item details.

    Example:
        ```
        GET /items/550e8400-e29b-41d4-a716-446655440000

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
    return await get_item(request, item_id)

@app.post("/items", response_class=JSONResponse)
async def api_create_item(request: Request, item: dict, authorization: str = Header(None)):
    """
    Create a new item. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        item (dict): The item data to create.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /items
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "title": "Chateau Lafite",
            "image_url": "https://example.com/chateau-lafite.jpg",
            "description": "A prestigious Bordeaux wine",
            "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
            "price": {
                "amount": "55.99",
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
    return await create_item(request, item, authorization)

@app.put("/items/{item_id}", response_class=JSONResponse)
async def api_update_item(request: Request, item: dict, item_id: str = Path(..., title="The ID of the item to update"), authorization: str = Header(None)):
    """
    Update an existing item. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        item (dict): The updated item data.
        item_id (str): The ID of the item to update.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        PUT /items/550e8400-e29b-41d4-a716-446655440000
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "title": "Chateau Lafite",
            "image_url": "https://example.com/chateau-lafite.jpg",
            "description": "A prestigious Bordeaux wine",
            "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
            "price": {
                "amount": "55.99",
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
            "quantity": 5,
            "origin_country_code": "FR",
            "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7"
        }

        Response:
        {
            "message": "Item updated successfully"
        }
        ```
    """
    return await update_item(request, item, item_id, authorization)

@app.delete("/items/{item_id}", response_class=JSONResponse)
async def api_delete_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete"), authorization: str = Header(None)):
    """
    Delete an item by its ID. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to delete.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        DELETE /items/550e8400-e29b-41d4-a716-446655440000
        Authorization: Bearer <access_token>

        Response:
        {
            "message": "Item deleted successfully"
        }
        ```
    """
    return await delete_item(request, item_id, authorization)

# Item Countries
@app.get("/item-countries", response_class=JSONResponse)
async def api_get_item_countries(request: Request):
    """
    Retrieve all available item countries, sorted alphabetically by country name.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the sorted list of item countries.

    Example:
        ```
        GET /item-countries

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
                    "code": "DE",
                    "unicode": "U+1F1E9 U+1F1EA",
                    "name": "Germany",
                    "emoji": "🇩🇪"
                },
                {
                    "code": "IT",
                    "unicode": "U+1F1EE U+1F1F9",
                    "name": "Italy",
                    "emoji": "🇮🇹"
                }
            ]
        }
        ```
    """
    return await get_item_countries(request)

# Item Brands
@app.get("/item-brands", response_class=JSONResponse)
async def api_get_item_brands(request: Request):
    """
    Retrieve all available item brands, sorted alphabetically by brand name.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the sorted list of item brands.

    Example:
        ```
        GET /item-brands

        Response:
        {
            "brands": [
                {
                    "brand_id": "8q9w0e1r-2t3y-4u5i-6o7p-8a9s0d1f2g3h",
                    "brand": "Chateau Margaux"
                },
                {
                    "brand_id": "7p8o9i0u-1y2t3r4e-5w6q7",
                    "brand": "Dom Perignon"
                },
                {
                    "brand_id": "9r0t1y2u-3i4o-5p6a-7s8d-9f0g1h2j3k4l",
                    "brand": "Heineken"
                }
            ]
        }
        ```
    """
    return await get_item_brands(request)

@app.post("/item-brands", response_class=JSONResponse)
async def api_create_item_brand(request: Request, brand: dict, authorization: str = Header(None)):
    """
    Create a new item brand. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        brand (dict): The brand data to create.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /item-brands
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "brand": "Chateau Margaux"
        }

        Response:
        {
            "message": "Brand created successfully",
            "brand_id": "550e8400-e29b-41d4-a716-446655440000"
        }
        ```
    """
    return await create_item_brand(request, brand, authorization)

@app.put("/item-brands/{brand_id}", response_class=JSONResponse)
async def api_update_item_brand(request: Request, brand: dict, brand_id: str = Path(..., title="The ID of the brand to update"), authorization: str = Header(None)):
    """
    Update an existing item brand. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        brand (dict): The updated brand data.
        brand_id (str): The ID of the brand to update.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        PUT /item-brands/550e8400-e29b-41d4-a716-446655440000
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "brand": "Chateau Lafite Rothschild"
        }

        Response:
        {
            "message": "Brand updated successfully"
        }
        ```
    """
    return await update_item_brand(request, brand, brand_id, authorization)

@app.delete("/item-brands/{brand_id}", response_class=JSONResponse)
async def api_delete_item_brand(request: Request, brand_id: str = Path(..., title="The ID of the brand to delete"), authorization: str = Header(None)):
    """
    Delete an item brand by its ID. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        brand_id (str): The ID of the brand to delete.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        DELETE /item-brands/550e8400-e29b-41d4-a716-446655440000
        Authorization: Bearer <access_token>

        Response:
        {
            "message": "Brand deleted successfully"
        }
        ```
    """
    return await delete_item_brand(request, brand_id, authorization)

# Item Types
@app.get("/item-types", response_class=JSONResponse)
async def api_get_item_types(request: Request):
    """
    Retrieve all available item types, sorted alphabetically by type name.

    Args:
        request (Request): The incoming request object.

    Returns:
        JSONResponse: A JSON response containing the sorted list of item types.

    Example:
        ```
        GET /item-types

        Response:
        {
            "types": [
                {
                    "type_id": "2b3c4d5e-6f7g-8h9i-0j1k-2l3m4n5o6p7q",
                    "type": "beer"
                },
                {
                    "type_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
                    "type": "red wine"
                },
                {
                    "type_id": "3c4d5e6f-7g8h-9i0j-1k2l-3m4n5o6p7q8r",
                    "type": "white wine"
                }
            ]
        }
        ```
    """
    return await get_item_types(request)

@app.post("/item-types", response_class=JSONResponse)
async def api_create_item_type(request: Request, type: dict, authorization: str = Header(None)):
    """
    Create a new item type. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        type (dict): The type data to create.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /item-types
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "type": "Red Wine"
        }

        Response:
        {
            "message": "Type created successfully",
            "type_id": "660e8400-e29b-41d4-a716-446655440001"
        }
        ```
    """
    return await create_item_type(request, type, authorization)

@app.put("/item-types/{type_id}", response_class=JSONResponse)
async def api_update_item_type(request: Request, type: dict, type_id: str = Path(..., title="The ID of the type to update"), authorization: str = Header(None)):
    """
    Update an existing item type. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        type (dict): The updated type data.
        type_id (str): The ID of the type to update.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        PUT /item-types/660e8400-e29b-41d4-a716-446655440001
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "type": "Bordeaux Red Wine"
        }

        Response:
        {
            "message": "Type updated successfully"
        }
        ```
    """
    return await update_item_type(request, type, type_id, authorization)

@app.delete("/item-types/{type_id}", response_class=JSONResponse)
async def api_delete_item_type(request: Request, type_id: str = Path(..., title="The ID of the type to delete"), authorization: str = Header(None)):
    """
    Delete an item type by its ID. Only accessible by authenticated admin users.

    Args:
        request (Request): The incoming request object.
        type_id (str): The ID of the type to delete.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        DELETE /item-types/660e8400-e29b-41d4-a716-446655440001
        Authorization: Bearer <access_token>

        Response:
        {
            "message": "Type deleted successfully"
        }
        ```
    """
    return await delete_item_type(request, type_id, authorization)

# Registration and Authentication
@app.post("/auth/login", response_class=JSONResponse)  # Returns two tokens: access and refresh
async def api_login(request: Request, user_data: dict):
    """
    Login a user.

    Args:
        request (Request): The incoming request object.
        user_data (dict): The user data to login. Must contain email and password.

    Returns:
        JSONResponse: A JSON response containing the access and refresh tokens.

    Example:
        ```
        POST /auth/login
        Content-Type: application/json

        {
            "email": "user@example.com",
            "password": "password123"
        }

        Response:
        {
            "access_token": "new_access_token"
        }
        ```
    """
    return await login(request, user_data)
    
@app.post("/auth/register/admin", response_class=JSONResponse)
async def api_register_admin(request: Request, user_data: dict, authorization: str = Header(None)):
    """
    Register a new admin user.

    Args:
        request (Request): The incoming request object.
        user_data (dict): The user data to register. Must contain new admin email.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /auth/register/admin
        Content-Type: application/json
        Authorization: Bearer <access_token>

        {
            "email": "admin@example.com"
        }

        Response:
        {
            "message": "Admin registered successfully",
            "user_id": "770e8400-e29b-41d4-a716-446655440001"
        }
        ```
    """
    return await register_admin(request, user_data, authorization)

@app.post("/auth/register/customer", response_class=JSONResponse)
async def api_register_customer(request: Request, user_data: dict):
    """
    Register a new customer user.

    Args:
        request (Request): The incoming request object.
        user_data (dict): The user data to register. Must contain new customer email and password.

    Returns:
        JSONResponse: A JSON response indicating the success or failure of the operation.

    Example:
        ```
        POST /auth/register/customer
        Content-Type: application/json

        {
            "email": "customer@example.com",
            "password": "password123"
        }

        Response:
        {
            "message": "Customer registered successfully",
            "user_id": "770e8400-e29b-41d4-a716-446655440002"
        }
        ```
    """
    return await register_customer(request, user_data)

@app.get("/auth/profile", response_class=JSONResponse)
async def api_get_profile(request: Request, authorization: str = Header(None)):
    """
    Get the profile details of the logged-in user.

    Args:
        request (Request): The incoming request object.
        authorization (str): The Authorization header containing the access token.

    Returns:
        JSONResponse: A JSON response containing the user's profile details.

    Example:
        ```
        GET /auth/profile
        Authorization: Bearer <access_token>

        Response:
        {
            "email": "user@example.com",
            "role": "admin",
            "full_name": "John Doe",
            "is_active": true,
            "updated_at": "2024-02-14T12:00:00Z",
            "created_at": "2024-02-14T12:00:00Z"
        }
        ```
    """
    return await get_profile(request, authorization)

# Cart
@app.get("/cart", response_class=JSONResponse)
async def api_get_cart(request: Request, authorization: str = Header(None)):
    """
    Retrieve the current user's cart.

    Args:
        request (Request): The incoming request object.
        authorization (str): The cart ID in the Authorization header.

    Returns:
        JSONResponse: A JSON response containing the cart details.

    Example:
        ```
        GET /cart
        Authorization: Bearer <access_token?> <cart_id>

        Response:
        {
            "new_cart": false,
            "cart_id": "550e8400-e29b-41d4-a716-446655440000",
            "cart_items": [
                {
                    "item_id": "660e8400-e29b-41d4-a716-446655440001",
                    "quantity": 2,
                    "unit_price": {
                        "amount": "45.99",
                        "currency": "€"
                    },
                    "total_price": {
                        "amount": "91.98",
                        "currency": "€"
                    }
                }
            ],
            "total_cart_price": 91.98
        }
        ```
    """
    return await get_cart(request, authorization)

@app.post("/cart/{item_id}/increment", response_class=JSONResponse)
async def api_increment_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to increment"), authorization: str = Header(None)):
    """
    Increment the quantity of an item in the cart by 1. If the item is not in the cart, it will be added from the catalogue.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to increment.
        authorization (str): The cart ID in the Authorization header.

    Returns:
        JSONResponse: A JSON response containing the updated cart details.

    Example:
        ```
        POST /cart/660e8400-e29b-41d4-a716-446655440001/increment
        Authorization: Bearer <access_token?> <cart_id>

        Response:
        {
            "new_cart": false,
            "cart_id": "550e8400-e29b-41d4-a716-446655440000",
            "cart_items": [...],
            "total_cart_price": 137.97
        }
        ```
    """
    return await increment_cart_item(request, item_id, authorization)

@app.post("/cart/{item_id}/decrement", response_class=JSONResponse)
async def api_decrement_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to decrement"), authorization: str = Header(None)):
    """
    Decrement the quantity of an item in the cart by 1. If the quantity is 0, the item will be removed from the cart.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to decrement.
        authorization (str): The cart ID in the Authorization header.

    Returns:
        JSONResponse: A JSON response containing the updated cart details.

    Example:
        ```
        POST /cart/660e8400-e29b-41d4-a716-446655440001/decrement
        Authorization: Bearer <access_token?> <cart_id>

        Response:
        {
            "new_cart": false,
            "cart_id": "550e8400-e29b-41d4-a716-446655440000",
            "cart_items": [...],
            "total_cart_price": 45.99
        }
        ```
    """
    return await decrement_cart_item(request, item_id, authorization)

@app.put("/cart/{item_id}", response_class=JSONResponse)
async def api_update_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to update"), quantity: int = Query(..., title="The new quantity of the item"), authorization: str = Header(None)):
    """
    Update the quantity of an item in the cart.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to update.
        quantity (int): The new quantity to set.
        authorization (str): The cart ID in the Authorization header.

    Returns:
        JSONResponse: A JSON response containing the updated cart details.

    Example:
        ```
        PUT /cart/660e8400-e29b-41d4-a716-446655440001?quantity=5
        Authorization: Bearer <access_token?> <cart_id>

        Response:
        {
            "new_cart": false,
            "cart_id": "550e8400-e29b-41d4-a716-446655440000",
            "cart_items": [
                {
                    "item_id": "660e8400-e29b-41d4-a716-446655440001",
                    "quantity": 5,
                    "unit_price": {
                        "amount": "45.99",
                        "currency": "€"
                    },
                    "total_price": {
                        "amount": "229.95",
                        "currency": "€"
                    }
                }
            ],
            "total_cart_price": 229.95
        }
        ```
    """
    return await update_cart_item(request, item_id, quantity, authorization)

@app.delete("/cart/{item_id}", response_class=JSONResponse)
async def api_delete_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete"), authorization: str = Header(None)):
    """
    Remove an item from the cart completely.

    Args:
        request (Request): The incoming request object.
        item_id (str): The ID of the item to delete.
        authorization (str): The cart ID in the Authorization header.

    Returns:
        JSONResponse: A JSON response containing the updated cart details.

    Example:
        ```
        DELETE /cart/660e8400-e29b-41d4-a716-446655440001
        Authorization: Bearer <access_token?> <cart_id>

        Response:
        {
            "new_cart": false,
            "cart_id": "550e8400-e29b-41d4-a716-446655440000",
            "cart_items": [],
            "total_cart_price": 0
        }
        ```
    """
    return await delete_cart_item(request, item_id, authorization)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
