import pytest
from datetime import datetime, timezone
from uuid import uuid4
from httpx import AsyncClient
import mongomock_motor

from main import app
from service_funcs import encode_token


# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_ADMIN_TOKEN = encode_token({
    "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
    "scope": "tier_1"
})
MOCK_BRAND_ID = str(uuid4())

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test brand
    await db['beverage_brands'].insert_one({
        "brand_id": MOCK_BRAND_ID,
        "brand": "Test Brand",
        "added_at": datetime.now(timezone.utc)
    })

    # Add test admin user
    await db['users'].insert_one({
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "role": "admin"
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
async def test_get_brands(async_client):
    """Test getting all brands"""
    response = await async_client.get("/item-brands")
    assert response.status_code == 200
    data = response.json()
    
    assert "brands" in data
    assert len(data["brands"]) == 1
    assert data["brands"][0]["brand_id"] == MOCK_BRAND_ID
    assert data["brands"][0]["brand"] == "Test Brand"

@pytest.mark.asyncio
async def test_create_brand(async_client):
    """Test creating a new brand"""
    new_brand = {
        "brand": "New Test Brand"
    }

    response = await async_client.post(
        "/item-brands",
        json=new_brand,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 201
    assert "brand_id" in response.json()
    assert response.json()["message"] == "Brand created successfully"

@pytest.mark.asyncio
async def test_update_brand(async_client):
    """Test updating an existing brand"""
    updated_brand = {
        "brand": "Updated Test Brand"
    }

    response = await async_client.put(
        f"/item-brands/{MOCK_BRAND_ID}",
        json=updated_brand,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Brand updated successfully"

@pytest.mark.asyncio
async def test_delete_brand(async_client):
    """Test deleting a brand"""
    response = await async_client.delete(
        f"/item-brands/{MOCK_BRAND_ID}",
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Brand deleted successfully"
