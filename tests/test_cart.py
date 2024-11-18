import pytest
from fastapi.testclient import TestClient
import mongomock_motor
from datetime import datetime, timezone, timedelta
from bson import Decimal128
from uuid import uuid4
import asyncio
from httpx import AsyncClient

from main import app
from models import Cart, CartItem, Money
from service_funcs import encode_token

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_CART_ID = str(uuid4())
MOCK_ITEM_ID = str(uuid4())

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test cart with future expiration time
    await db['carts'].insert_one({
        "cart_id": MOCK_CART_ID,
        "cart_items": [
            {
                "item_id": MOCK_ITEM_ID,
                "quantity": 2,
                "unit_price": {"amount": Decimal128("29.99"), "currency": "€"},
                "total_price": {"amount": Decimal128("59.98"), "currency": "€"}
            }
        ],
        "updated_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "expiration_time": datetime.now(timezone.utc) + timedelta(days=7)  # Set expiration 7 days in the future
    })

    # Add test item to catalogue
    await db['items'].insert_one({
        "item_id": MOCK_ITEM_ID,
        "price": {"amount": Decimal128("29.99"), "currency": "€"}
    })

    yield db
    client.close()

@pytest.fixture(scope="function")
def test_app(mock_mongodb):
    """Create a test FastAPI application with mocked MongoDB"""
    app.mongodb = mock_mongodb
    return app

@pytest.fixture(scope="function")
async def async_client(test_app):
    """Create an async client for testing"""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_get_cart(async_client):
    response = await async_client.get(
        "/cart",
        headers={"Authorization": f"Bearer {MOCK_CART_ID}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert "cart_id" in data
    assert "cart_items" in data
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["item_id"] == MOCK_ITEM_ID
    assert float(data["total_cart_price"]) == 59.98

@pytest.mark.asyncio
async def test_increment_cart_item(async_client):
    response = await async_client.post(
        f"/cart/{MOCK_ITEM_ID}/increment",
        headers={"Authorization": f"Bearer {MOCK_CART_ID}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 3
    assert float(data["total_cart_price"]) == 89.97

@pytest.mark.asyncio
async def test_decrement_cart_item(async_client):
    response = await async_client.post(
        f"/cart/{MOCK_ITEM_ID}/decrement",
        headers={"Authorization": f"Bearer {MOCK_CART_ID}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 1
    assert float(data["total_cart_price"]) == 29.99

@pytest.mark.asyncio
async def test_update_cart_item(async_client):
    response = await async_client.put(
        f"/cart/{MOCK_ITEM_ID}?quantity=5",
        headers={"Authorization": f"Bearer {MOCK_CART_ID}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 5
    assert float(data["total_cart_price"]) == 149.95

@pytest.mark.asyncio
async def test_delete_cart_item(async_client):
    response = await async_client.delete(
        f"/cart/{MOCK_ITEM_ID}",
        headers={"Authorization": f"Bearer {MOCK_CART_ID}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["cart_items"]) == 0
    assert float(data["total_cart_price"]) == 0
