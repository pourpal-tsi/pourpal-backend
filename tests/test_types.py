import pytest
from httpx import AsyncClient
import mongomock_motor
from datetime import datetime, timezone
from uuid import uuid4

from main import app
from service_funcs import encode_token

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_ADMIN_TOKEN = encode_token({
    "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
    "scope": "tier_1"
})
MOCK_TYPE_ID = str(uuid4())

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test type
    await db['beverage_types'].insert_one({
        "type_id": MOCK_TYPE_ID,
        "type": "Test Wine",
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
async def test_get_item_types(async_client):
    """Test getting all beverage types"""
    response = await async_client.get("/item-types")
    assert response.status_code == 200
    data = response.json()
    
    assert "types" in data
    assert len(data["types"]) == 1
    assert data["types"][0]["type_id"] == MOCK_TYPE_ID
    assert data["types"][0]["type"] == "Test Wine"

@pytest.mark.asyncio
async def test_create_item_type(async_client):
    """Test creating a new beverage type"""
    new_type = {
        "type": "New Wine Type"
    }

    response = await async_client.post(
        "/item-types",
        json=new_type,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert "type_id" in data
    assert data["message"] == "Type created successfully"

@pytest.mark.asyncio
async def test_update_item_type(async_client):
    """Test updating an existing beverage type"""
    updated_type = {
        "type": "Updated Wine Type"
    }

    response = await async_client.put(
        f"/item-types/{MOCK_TYPE_ID}",
        json=updated_type,
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Type updated successfully"

@pytest.mark.asyncio
async def test_delete_item_type(async_client):
    """Test deleting a beverage type"""
    response = await async_client.delete(
        f"/item-types/{MOCK_TYPE_ID}",
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Type deleted successfully"
