from fastapi import Request, Path, Header, Query
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone

from models import Item, Money, Volume
from service_funcs import bson_to_json, validate_item_attrs, generate_sku, is_user_admin


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
    query = {}

    if search:
        query["title"] = {"$regex": search, "$options": "i"}

    if types:
        type_list = [t.strip() for t in types.split(',')]
        query["type_id"] = {"$in": type_list}
        print(type_list)
        print(query["type_id"])

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
        "quantity": "quantity",
        "price": "price.amount"
    }

    sort_query = []
    if sort_by and sort_by in sort_fields:
        sort_field = sort_fields[sort_by]
        sort_direction = 1 if sort_order.lower() == "asc" else -1 if sort_order.lower() == "desc" else None
        if sort_direction is not None:
            sort_query = [(sort_field, sort_direction)]

    # Count total matching items
    total_count = await request.app.mongodb['items'].count_documents(query)

    # Calculate pagination metadata
    total_pages = ceil(total_count / page_size)
    skip = (page_number - 1) * page_size

    # Fetch paginated items with sorting
    cursor = request.app.mongodb['items'].find(query, {'_id': 0})
    if sort_query:
        cursor = cursor.sort(sort_query)
    items = await cursor.skip(skip).limit(page_size).to_list(length=None)

    items = bson_to_json(items)
    
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

async def get_item(request: Request, item_id: str = Path(..., title="The ID of the item to retrieve")):
    item = await request.app.mongodb['items'].find_one({"item_id": item_id}, {'_id': 0})
    item = bson_to_json(item) if item else None
    return JSONResponse(status_code=status.HTTP_200_OK, content={"item": item})

async def create_item(request: Request, item: dict, authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})
    
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
            price=Money(amount=Decimal128(item['price']['amount']), currency=item['price']['currency']),
            volume=Volume(amount=Decimal128(item['volume']['amount']), unit=item['volume']['unit']),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']['amount']), unit=item['alcohol_volume']['unit']),
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

async def update_item(request: Request, item: dict, item_id: str = Path(..., title="The ID of the item to update"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

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
            price=Money(amount=Decimal128(item['price']['amount']), currency=item['price']['currency']),
            volume=Volume(amount=Decimal128(item['volume']['amount']), unit=item['volume']['unit']),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']['amount']), unit=item['alcohol_volume']['unit']),
            quantity=item['quantity'],
            origin_country_code=valid_country['code'],
            origin_country_name=valid_country['name'],
            brand_id=valid_brand['brand_id'],
            brand_name=valid_brand['brand'],
            updated_at=datetime.now(timezone.utc),
            added_at=db_item['added_at']
        )            
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

    result = await request.app.mongodb['items'].update_one(
        {"item_id": item_id},
        {"$set": updated_item.model_dump(exclude={"item_id"})}
    )
    if result.modified_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item updated successfully"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})

async def delete_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete"), authorization: str = Header(None)):
    # Authentication and authorization check
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    is_admin = await is_user_admin(request, access_token)
    if not is_admin:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Access denied"})

    result = await request.app.mongodb['items'].delete_one({"item_id": item_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item deleted successfully"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})
