import pytest
from httpx import AsyncClient
import mongomock_motor
from datetime import datetime, timezone
from bson import Decimal128
from uuid import uuid4

from main import app
from service_funcs import encode_token
from models import DeliveryInformation

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_USER_TOKEN = encode_token({
    "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
    "scope": "tier_0"
})
MOCK_ADMIN_TOKEN = encode_token({
    "user_id": "5e2a319f-c689-4040-be27-df94ee5731d6",
    "scope": "tier_1"
})
MOCK_CART_ID = str(uuid4())
MOCK_ORDER_ID = str(uuid4())

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test user
    await db['users'].insert_one({
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "role": "customer"
    })

    # Add test admin
    await db['users'].insert_one({
        "user_id": "5e2a319f-c689-4040-be27-df94ee5731d6",
        "role": "admin"
    })

    # Add test cart
    await db['carts'].insert_one({
        "cart_id": MOCK_CART_ID,
        "cart_items": [
            {
                "item_id": "123",
                "quantity": 2,
                "unit_price": {"amount": Decimal128("29.99"), "currency": "€"},
                "total_price": {"amount": Decimal128("59.98"), "currency": "€"}
            }
        ]
    })

    # Add test item
    await db['items'].insert_one({
        "item_id": "123",
        "title": "Test Wine",
        "quantity": 5
    })

    # Add test order
    await db['orders'].insert_one({
        "order_id": MOCK_ORDER_ID,
        "order_number": "000000001",
        "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
        "status": "pending",
        "delivery_information": {
            "recipient_name": "John Doe",
            "recipient_phone": "+1234567890",
            "recipient_city": "Test City",
            "recipient_street_address": "123 Test St"
        },
        "order_items": [
            {
                "item_id": "123",
                "quantity": 2,
                "unit_price": {"amount": Decimal128("29.99"), "currency": "€"},
                "total_price": {"amount": Decimal128("59.98"), "currency": "€"}
            }
        ],
        "total_price": {"amount": Decimal128("59.98"), "currency": "€"},
        "created_at": datetime.now(timezone.utc)
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
async def test_create_order(async_client):
    """Test creating a new order"""
    delivery_info = {
        "recipient_name": "John Doe",
        "recipient_phone": "+1234567890",
        "recipient_city": "New York",
        "recipient_street_address": "123 Main St",
        "comment": "Please deliver in the evening"
    }

    response = await async_client.post(
        "/orders",
        json=delivery_info,
        headers={"Authorization": f"Bearer {MOCK_USER_TOKEN} {MOCK_CART_ID}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "order_id" in data
    assert data["order_number"] == "000000002"  # Since we already have order 000000001
    assert data["status"] == "pending"
    assert data["delivery_information"] == delivery_info

@pytest.mark.asyncio
async def test_get_all_orders(async_client):
    """Test getting all orders (admin only)"""
    response = await async_client.get(
        "/orders",
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "orders" in data
    assert "paging" in data
    assert len(data["orders"]) == 1
    assert data["orders"][0]["order_id"] == MOCK_ORDER_ID

@pytest.mark.asyncio
async def test_get_user_orders(async_client):
    """Test getting user's orders"""
    response = await async_client.get(
        "/auth/profile/orders",
        headers={"Authorization": f"Bearer {MOCK_USER_TOKEN}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "orders" in data
    assert "paging" in data
    assert len(data["orders"]) == 1
    assert data["orders"][0]["order_id"] == MOCK_ORDER_ID
    assert data["orders"][0]["user_id"] == "4d1a219f-b589-4040-be27-df94ee5731c5"
