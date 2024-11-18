import pytest
from fastapi.testclient import TestClient
import mongomock_motor
from datetime import datetime, timezone
from uuid import uuid4
import asyncio
from httpx import AsyncClient

from main import app
from service_funcs import encode_token, password_is_correct
from models import UserAdmin, UserCustomer

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Test data
MOCK_ADMIN_TOKEN = encode_token({
    "user_id": "4d1a219f-b589-4040-be27-df94ee5731c5",
    "scope": "tier_1"
})

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test admin user
    admin = UserAdmin(
        user_id="4d1a219f-b589-4040-be27-df94ee5731c5",
        email="admin@test.com",
        password="admin123"
    )
    await db['users'].insert_one(admin.model_dump())
    
    # Add test customer user
    customer = UserCustomer(
        user_id="5e2a330f-c698-4151-cf85-eg7455551c6",
        email="customer@test.com",
        password="customer123"
    )
    await db['users'].insert_one(customer.model_dump())

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
async def test_login(async_client):
    """Test user login endpoint"""
    response = await async_client.post(
        "/auth/login",
        json={
            "email": "customer@test.com",
            "password": "customer123"
        }
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_register_admin(async_client):
    """Test admin registration endpoint"""
    response = await async_client.post(
        "/auth/register/admin",
        json={
            "email": "newadmin@test.com"
        },
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )
    assert response.status_code == 201
    assert "user_id" in response.json()
    assert response.json()["message"] == "Admin registered successfully"

@pytest.mark.asyncio
async def test_register_customer(async_client):
    """Test customer registration endpoint"""
    response = await async_client.post(
        "/auth/register/customer",
        json={
            "email": "newcustomer@test.com",
            "password": "newpass123"
        }
    )
    assert response.status_code == 201
    assert "user_id" in response.json()
    assert response.json()["message"] == "Customer registered successfully"

@pytest.mark.asyncio
async def test_get_profile(async_client):
    """Test get user profile endpoint"""
    response = await async_client.get(
        "/auth/profile",
        headers={"Authorization": f"Bearer {MOCK_ADMIN_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert data["role"] == "admin"
    assert "full_name" in data
    assert "is_active" in data
    assert "updated_at" in data
    assert "created_at" in data
