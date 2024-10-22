from fastapi import Request, Path, Header, Query
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from bson import Decimal128
from math import ceil
from datetime import datetime, timezone

from models import Cart, CartItem
from service_funcs import bson_to_json, is_user_admin


async def get_cart(request: Request, authorization: str = Header(None)):
  return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Not implemented yet"})

async def increment_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to increment"), authorization: str = Header(None)):
  return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Not implemented yet"})

async def decrement_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to decrement"), authorization: str = Header(None)):
  return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Not implemented yet"})

async def update_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to update"), quantity: int = Query(..., title="The new quantity of the item"), authorization: str = Header(None)):
  return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Not implemented yet"})

async def delete_cart_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete"), authorization: str = Header(None)):
  return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Not implemented yet"})
