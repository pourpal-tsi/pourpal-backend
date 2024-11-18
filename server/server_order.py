from fastapi import Request, Path, Header, Query, Body, HTTPException
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone, timedelta
import json

from models import Order, DeliveryInformation
from service_funcs import bson_to_json, is_user_admin, decode_token


async def create_order(request: Request, 
                      delivery_info: DeliveryInformation = Body(...),
                      authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None
    if not cart_id:
        raise HTTPException(status_code=400, detail="No cart ID provided")
    
    # Get the cart
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id})
    if not cart or not cart['cart_items']:
        raise HTTPException(status_code=400, detail="Cart is empty or not found")

    # Check inventory quantities
    for cart_item in cart['cart_items']:
        item = await request.app.mongodb['items'].find_one({"item_id": cart_item['item_id']})
        if not item or item['quantity'] < cart_item['quantity']:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock for item: {item['title'] if item else cart_item['item_id']}"
            )

    # Calculate total price
    total_price = sum(item['total_price']['amount'].to_decimal() for item in cart['cart_items'])
    
    # Generate order number (9 digits)
    last_order = await request.app.mongodb['orders'].find_one(
        sort=[("order_number", -1)]
    )
    next_number = "000000001" if not last_order else str(int(last_order['order_number']) + 1).zfill(9)

    # Get user_id from authorization header
    access_token = authorization.replace("Bearer ", "").split(" ")[0]
    access_token_data = decode_token(access_token) if access_token else None
    user_id = access_token_data.get('user_id') if access_token_data else None

    # Create order
    order = Order(
        order_number=next_number,
        user_id=user_id,
        delivery_information=delivery_info,
        order_items=cart['cart_items'],
        total_price={"amount": str(total_price), "currency": "€"}
    ).model_dump()

    # Update inventory quantities
    for item in cart['cart_items']:
        await request.app.mongodb['items'].update_one(
            {"item_id": item['item_id']},
            {"$inc": {"quantity": -item['quantity']}}
        )

    # Save order
    await request.app.mongodb['orders'].insert_one(order)

    # Clear cart
    await request.app.mongodb['carts'].delete_one({"cart_id": cart_id})

    return JSONResponse(
        status_code=status.HTTP_201_CREATED, 
        content=bson_to_json(order)
    )

async def get_all_orders(
    request: Request,
    page_size: int = Query(25, ge=1, le=100, description="Number of items per page"),
    page_number: int = Query(1, ge=1, description="Page number"),
    authorization: str = Header(None)
):
    # Check admin rights
    access_token = authorization.replace("Bearer ", "").split(" ")[0]
    if not await is_user_admin(request, access_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator rights required"
        )
    
    # Get total count for pagination
    total_count = await request.app.mongodb['orders'].count_documents({})
    total_pages = ceil(total_count / page_size)
    skip = (page_number - 1) * page_size

    # Get paginated orders
    orders = await request.app.mongodb['orders'].find(
        {}, 
        {"_id": 0}
    ) \
        .sort("created_at", -1) \
        .skip(skip) \
        .limit(page_size) \
        .to_list(length=None)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=bson_to_json({
            "orders": orders,
            "paging": {
                "count": len(orders),
                "page_size": page_size,
                "page_number": page_number,
                "total_count": total_count,
                "total_pages": total_pages,
                "first_page": page_number == 1,
                "last_page": page_number == total_pages
            }
        })
    )

async def get_user_orders(
    request: Request,
    page_size: int = Query(25, ge=1, le=100, description="Number of items per page"),
    page_number: int = Query(1, ge=1, description="Page number"),
    authorization: str = Header(None)
):
    # Get user_id from session
    access_token = authorization.replace("Bearer ", "").split(" ")[0]
    access_token_data = decode_token(access_token) if access_token else None
    user_id = access_token_data.get('user_id') if access_token_data else None
    user = await request.app.mongodb['users'].find_one({"user_id": user_id}) if user_id else None
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Get total count for pagination
    total_count = await request.app.mongodb['orders'].count_documents({"user_id": user_id})
    total_pages = ceil(total_count / page_size)
    skip = (page_number - 1) * page_size

    # Get paginated orders
    orders = await request.app.mongodb['orders'].find(
        {"user_id": user_id},  # Filter by user_id
        {"_id": 0}
    ) \
        .sort("created_at", -1) \
        .skip(skip) \
        .limit(page_size) \
        .to_list(length=None)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=bson_to_json({
            "orders": orders,
            "paging": {
                "count": len(orders),
                "page_size": page_size,
                "page_number": page_number,
                "total_count": total_count,
                "total_pages": total_pages,
                "first_page": page_number == 1,
                "last_page": page_number == total_pages
            }
        })
    )
