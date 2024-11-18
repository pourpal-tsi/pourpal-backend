import pytest
from httpx import AsyncClient
import mongomock_motor
from datetime import datetime, timezone

from main import app

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
async def mock_mongodb():
    """Create a mock MongoDB client and database"""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client['pourpal']
    
    # Add test countries
    await db['countries'].insert_many([
        {
            "code": "FR",
            "unicode": "U+1F1EB U+1F1F7",
            "name": "France",
            "emoji": "🇫🇷",
            "added_at": datetime.now(timezone.utc)
        },
        {
            "code": "IT",
            "unicode": "U+1F1EE U+1F1F9",
            "name": "Italy",
            "emoji": "🇮🇹",
            "added_at": datetime.now(timezone.utc)
        },
        {
            "code": "ES",
            "unicode": "U+1F1EA U+1F1F8",
            "name": "Spain",
            "emoji": "🇪🇸",
            "added_at": datetime.now(timezone.utc)
        }
    ])

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
async def test_get_item_countries(async_client):
    """Test getting the list of countries"""
    response = await async_client.get("/item-countries")
    
    # Check response status code
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "countries" in data
    countries = data["countries"]
    
    # Check number of countries
    assert len(countries) == 3
    
    # Check countries are sorted by name
    assert countries[0]["name"] == "France"
    assert countries[1]["name"] == "Italy"
    assert countries[2]["name"] == "Spain"
    
    # Check country structure
    for country in countries:
        assert "code" in country
        assert "unicode" in country
        assert "name" in country
        assert "emoji" in country
        assert "added_at" not in country  # Should be excluded from response
