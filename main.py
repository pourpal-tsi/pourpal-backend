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
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks


BASE_DIR = pathlib.Path(__file__).resolve().parent  # app
TEMPLATES_DIR = BASE_DIR / "templates"
# templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Atlas at application startup
    app.mongodb_client = AsyncIOMotorClient(MONGO_DB)
    app.mongodb = app.mongodb_client['pourpal']
    yield
    # Disconnect from Atlas at application shutdown
    app.mongodb_client.close()


app = FastAPI(lifespan=lifespan) 
# app.mount("/static", StaticFiles(directory="static"), name="static")


# Functions

def get_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(':')[0]
        port = x_forwarded_for.split(':')[1]
        return ip_address
    return None


# Endpoints

@app.get("/", response_class=JSONResponse)
async def root(request: Request):
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

@app.get("/new-item/{item_name}", response_class=JSONResponse)
async def new_item(request: Request, item_name: str):
    await request.app.mongodb['items'].insert_one({'name': item_name, 'ip_address': get_client_ip(request), 'added_at': datetime.now(timezone.utc)})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": f"Item {item_name} added successfully. Your IP address is {get_client_ip(request)}. Added at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
