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
from models import Item, Money, Volume
from fastapi import Path

from service_funcs import decimal128_to_str


BASE_DIR = pathlib.Path(__file__).resolve().parent  # app
TEMPLATES_DIR = BASE_DIR / "templates"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Atlas at application startup
    app.mongodb_client = AsyncIOMotorClient(MONGO_DB)
    app.mongodb = app.mongodb_client['pourpal']
    yield
    # Disconnect from Atlas at application shutdown
    app.mongodb_client.close()

app = FastAPI(lifespan=lifespan) 


# Endpoints

@app.get("/", response_class=JSONResponse)
async def root(request: Request):
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

@app.get("/items", response_class=JSONResponse)
async def get_items(request: Request):
    items = await request.app.mongodb['items'].find().to_list(length=None)
    serializable_items = []
    for item in items:
        item_dict = Item(**item).model_dump()
        item_dict['price']['amount'] = decimal128_to_str(item_dict['price']['amount'])
        item_dict['volume']['amount'] = decimal128_to_str(item_dict['volume']['amount'])
        item_dict['alcohol_volume']['amount'] = decimal128_to_str(item_dict['alcohol_volume']['amount'])
        serializable_items.append(item_dict)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": serializable_items})

@app.get("/items/{item_id}", response_class=JSONResponse)
async def get_item(request: Request, item_id: str = Path(..., title="The ID of the item to retrieve")):
    item = await request.app.mongodb['items'].find_one({"item_id": item_id})
    if item:
        item_dict = Item(**item).model_dump()
        item_dict['price']['amount'] = decimal128_to_str(item_dict['price']['amount'])
        item_dict['volume']['amount'] = decimal128_to_str(item_dict['volume']['amount'])
        item_dict['alcohol_volume']['amount'] = decimal128_to_str(item_dict['alcohol_volume']['amount'])
        return JSONResponse(status_code=status.HTTP_200_OK, content=item_dict)
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/items", response_class=JSONResponse)
async def create_item(request: Request, item: dict):
    try:
        new_item = Item(
            title=item['title'],
            image_url=item['image_url'],
            description=item['description'],
            type=item['type'],
            price=Money(amount=Decimal128(item['price'])),
            volume=Volume(amount=Decimal128(item['volume']), unit='l'),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']), unit='%'),
            quantity=item['quantity'],
            origin_country=item['origin_country'],
            brand=item['brand']
        )       
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = await request.app.mongodb['items'].insert_one(new_item.model_dump())
    if result.inserted_id:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Item created successfully", "item_id": new_item.item_id})
    raise HTTPException(status_code=500, detail="Failed to create item")

@app.put("/items/{item_id}", response_class=JSONResponse)
async def update_item(request: Request, item: dict, item_id: str = Path(..., title="The ID of the item to update")):
    try:    
        updated_item = Item(
            title=item['title'],
            image_url=item['image_url'],
            description=item['description'],
            type=item['type'],
            price=Money(amount=Decimal128(item['price'])),
            volume=Volume(amount=Decimal128(item['volume']), unit='l'),
            alcohol_volume=Volume(amount=Decimal128(item['alcohol_volume']), unit='%'),
            quantity=item['quantity'],
            origin_country=item['origin_country'],
            brand=item['brand']
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = await request.app.mongodb['items'].update_one(
        {"item_id": item_id},
        {"$set": updated_item.model_dump(exclude={"item_id"})}
    )
    if result.modified_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item updated successfully"})
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{item_id}", response_class=JSONResponse)
async def delete_item(request: Request, item_id: str = Path(..., title="The ID of the item to delete")):
    result = await request.app.mongodb['items'].delete_one({"item_id": item_id})
    if result.deleted_count:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Item deleted successfully"})
    raise HTTPException(status_code=404, detail="Item not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
