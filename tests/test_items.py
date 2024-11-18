import pytest
from fastapi.testclient import TestClient
import mongomock_motor
from datetime import datetime, timezone
from bson import Decimal128
from uuid import uuid4
import asyncio
from httpx import AsyncClient

from main import app
from models import Item, Money, Volume
from service_funcs import encode_token, decode_token


# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_ADMIN_TOKEN = encode_token({
    "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
    "scope": "tier_1"
})
MOCK_ITEM_ID = str(uuid4())
MOCK_TYPE_ID = "c36dfd53-7a31-410b-b0f5-c3f52a55c206"
MOCK_BRAND_ID = "e0888397-6970-4fef-9b3e-fff6c53ffae5"

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test data
    await db['items'].insert_one({
        "item_id": MOCK_ITEM_ID,
        "sku": "TEST123",
        "title": "Test Wine",
        "image_url": "https://example.com/test.jpg",
        "description": "A test wine",
        "type_id": MOCK_TYPE_ID,
        "type_name": "red wine",
        "price": {"amount": Decimal128("29.99"), "currency": "€"},
        "volume": {"amount": Decimal128("750"), "unit": "ml"},
        "alcohol_volume": {"amount": Decimal128("13.5"), "unit": "%"},
        "quantity": 10,
        "origin_country_code": "FR",
        "origin_country_name": "France",
        "brand_id": MOCK_BRAND_ID,
        "brand_name": "Test Brand",
        "updated_at": datetime.now(timezone.utc),
        "added_at": datetime.now(timezone.utc)
    })

    # Add test type
    await db['beverage_types'].insert_one({
        "type_id": MOCK_TYPE_ID,
        "type": "Test wine"
    })

    # Add test brand
    await db['beverage_brands'].insert_one({
        "brand_id": MOCK_BRAND_ID,
        "brand": "Test Brand"
    })

    # Add test country
    await db['countries'].insert_one({
        "code": "FR",
        "unicode": "U+1F1EB U+1F1F7",
        "name": "France",
        "emoji": "🇫🇷"
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
async def test_get_items(async_client):
    response = await async_client.get("/items")
    assert response.status_code == 200
    data = response.json()
    
    assert "items" in data
    assert "paging" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["item_id"] == MOCK_ITEM_ID

@pytest.mark.asyncio
async def test_get_item(async_client):
    response = await async_client.get(f"/items/{MOCK_ITEM_ID}")
    assert response.status_code == 200
    assert response.json()["item"]["item_id"] == MOCK_ITEM_ID

@pytest.mark.asyncio
async def test_create_item(async_client, mock_mongodb):
    # Add a test admin user to the database
    await mock_mongodb['users'].insert_one({
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "role": "admin"
    })

    new_item = {
        "title": "New Wine",
        "image_url": "https://example.com/new.jpg",
        "description": "A new test wine",
        "type_id": MOCK_TYPE_ID,
        "price": {"amount": "39.99", "currency": "€"},
        "volume": {"amount": "750", "unit": "ml"},
        "alcohol_volume": {"amount": "14.5", "unit": "%"},
        "quantity": 5,
        "origin_country_code": "FR",
        "brand_id": MOCK_BRAND_ID
    }

    response = await async_client.post(
        "/items",
        json=new_item,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 201
    assert "item_id" in response.json()
    
@pytest.mark.asyncio
async def test_update_item(async_client, mock_mongodb):
    # Add a test admin user to the database
    await mock_mongodb['users'].insert_one({
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "role": "admin"
    })

    updated_item = {
        "title": "Updated Wine",
        "image_url": "https://example.com/updated.jpg",
        "description": "An updated test wine",
        "type_id": MOCK_TYPE_ID,
        "price": {"amount": "49.99", "currency": "€"},
        "volume": {"amount": "750", "unit": "ml"},
        "alcohol_volume": {"amount": "14.0", "unit": "%"},
        "quantity": 15,
        "origin_country_code": "FR",
        "brand_id": MOCK_BRAND_ID
    }

    response = await async_client.put(
        f"/items/{MOCK_ITEM_ID}",
        json=updated_item,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Item updated successfully"

    # Verify the item was actually updated
    updated = await mock_mongodb['items'].find_one({"item_id": MOCK_ITEM_ID}, {'_id': 0})
    assert updated["title"] == "Updated Wine"
    assert updated["price"]["amount"] == Decimal128("49.99")
    assert updated["quantity"] == 15

@pytest.mark.asyncio
async def test_delete_item(async_client, mock_mongodb):
    # Add a test admin user to the database
    await mock_mongodb['users'].insert_one({
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "role": "admin"
    })

    response = await async_client.delete(
        f"/items/{MOCK_ITEM_ID}",
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Item deleted successfully"

    # Verify the item was actually deleted
    deleted = await mock_mongodb['items'].find_one({"item_id": MOCK_ITEM_ID})
    assert deleted is None
