from fastapi import Request, Path, Header, Query
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone, timedelta

from models import Cart, CartItem, Money
from service_funcs import bson_to_json, is_user_admin
from service_rules import CART_EXPIRATION_TIME_DAYS


async def get_cart(request: Request, authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None

    # Get the cart from database
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id}) if cart_id else None
    
    # Create a new cart if it doesn't exist or if it has expired
    is_new_cart = False
    if not cart or (cart and cart.get('expiration_time') and cart['expiration_time'].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)):
        is_new_cart = True
        cart = Cart().model_dump()
        await request.app.mongodb['carts'].insert_one(cart)
    else:
        # Update expiration time
        await request.app.mongodb['carts'].update_one(
            {"cart_id": cart['cart_id']},
            {"$set": {"expiration_time": datetime.now(timezone.utc) + timedelta(days=CART_EXPIRATION_TIME_DAYS)}}
        )

    return_content = bson_to_json(
        dict( 
            new_cart=is_new_cart,
            cart_id=cart['cart_id'],
            cart_items=cart['cart_items'],
            total_cart_price=f"{float(sum(item['total_price']['amount'].to_decimal() for item in cart['cart_items'])):.2f}"
        )
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=return_content)

async def increment_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to increment"), authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None
    if not cart_id:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "No cart ID provided"})
    
    # Get the cart from database
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id})
    if not cart:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Cart not found"})
    
    # Find the item in cart_items
    item_found = False
    for item in cart['cart_items']:
        if item['item_id'] == item_id:
            item_found = True
            break
        
    if not item_found:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Item not found"})
    
    # Increment quantity
    item['quantity'] += 1
    item['total_price']['amount'] = Decimal128(f"{item['quantity'] * item['unit_price']['amount'].to_decimal():.2f}")

    # Update the cart in database
    await request.app.mongodb['carts'].update_one(
        {"cart_id": cart_id},
        {"$set": {"cart_items": cart['cart_items']}}
    )

    return await get_cart(request, authorization)

async def decrement_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to decrement"), authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None
    if not cart_id:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "No cart ID provided"})
    
    # Get the cart from database
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id})
    if not cart:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Cart not found"})
    
    # Find the item in cart_items
    item_found = False
    for item in cart['cart_items']:
        if item['item_id'] == item_id:
            item_found = True
            break
        
    if not item_found:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Item not found"})
    
    # Decrement quantity if it's greater than 1
    if item['quantity'] > 1:
        item['quantity'] -= 1
        item['total_price']['amount'] = Decimal128(f"{item['quantity'] * item['unit_price']['amount'].to_decimal():.2f}")
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Quantity cannot be less than 1"})

    # Update the cart in database
    await request.app.mongodb['carts'].update_one(
        {"cart_id": cart_id},
        {"$set": {"cart_items": cart['cart_items']}}
    )

    return await get_cart(request, authorization)

async def update_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to update"), quantity: int = Query(..., title="The new quantity of the item"), authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None
    if not cart_id:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "No cart ID provided"})

    # Get the cart from database
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id})
    if not cart:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Cart not found"})

    # Find the item in cart_items
    item_found = False
    for item in cart['cart_items']:
        if item['item_id'] == item_id:
            item_found = True
            # Update quantity and total price
            item['quantity'] = quantity
            unit_price_decimal = float(item['unit_price']['amount'].to_decimal())
            item['total_price']['amount'] = Decimal128(f"{quantity * unit_price_decimal:.2f}")
            break

    if not item_found:
        catalogue_item = await request.app.mongodb['items'].find_one({"item_id": item_id})
        if not catalogue_item:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Item not found"})
        cart['cart_items'].append(CartItem(
            item_id=catalogue_item['item_id'],
            quantity=quantity,
            unit_price=catalogue_item['price'],
            total_price=Money(amount=Decimal128(f"{quantity * float(catalogue_item['price']['amount'].to_decimal()):.2f}"))
        ).model_dump())

    # Update the cart in database
    await request.app.mongodb['carts'].update_one(
        {"cart_id": cart_id},
        {"$set": {"cart_items": cart['cart_items']}}
    )

    return await get_cart(request, authorization)

async def delete_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete"), authorization: str = Header(None)):
    # Get cart_id from authorization header
    cart_id = authorization.split(" ")[-1] if authorization else None
    if not cart_id:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "No cart ID provided"})
    
    # Get the cart from database
    cart = await request.app.mongodb['carts'].find_one({"cart_id": cart_id})
    if not cart:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Cart not found"})
    
    # Find the item in cart_items
    item_found = False
    for item in cart['cart_items']:
        if item['item_id'] == item_id:
            item_found = True
            break
        
    if not item_found:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Item not found"})
    
    # Delete the item from cart_items
    cart['cart_items'] = [item for item in cart['cart_items'] if item['item_id'] != item_id]

    # Update the cart in database
    await request.app.mongodb['carts'].update_one(
        {"cart_id": cart_id},
        {"$set": {"cart_items": cart['cart_items']}}
    )

    return await get_cart(request, authorization)
