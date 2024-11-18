# PourPal Backend

The backend service for PourPal, a beverage e-commerce platform developed as a software engineering group project at TSI, 2024.

## Technologies

- **Framework**: FastAPI
- **Database**: MongoDB
- **Authentication**: JWT-based token authentication
- **Testing**: Pytest

## Features

- **Product Management**
  - CRUD operations for beverages
  - Filtering and sorting capabilities
  - Pagination support
  - Image handling
  - Categories and brands management

- **User Management**
  - Customer registration and authentication
  - Admin user management
  - Profile management
  - Role-based access control

- **Shopping Cart**
  - Cart creation and management
  - Item quantity updates
  - Price calculations
  - Cart expiration handling

- **Order Processing**
  - Order creation from cart
  - Order history
  - Delivery information handling
  - Order status tracking

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register/customer` - Customer registration
- `POST /auth/register/admin` - Admin registration (admin only)
- `GET /auth/profile` - Get user profile

### Products
- `GET /items` - List all items with filtering and sorting
- `GET /items/{item_id}` - Get specific item
- `POST /items` - Create new item (admin only)
- `PUT /items/{item_id}` - Update item (admin only)
- `DELETE /items/{item_id}` - Delete item (admin only)

### Categories
- `GET /item-types` - List all beverage types
- `POST /item-types` - Create new type (admin only)
- `PUT /item-types/{type_id}` - Update type (admin only)
- `DELETE /item-types/{type_id}` - Delete type (admin only)

### Brands
- `GET /item-brands` - List all brands
- `POST /item-brands` - Create new brand (admin only)
- `PUT /item-brands/{brand_id}` - Update brand (admin only)
- `DELETE /item-brands/{brand_id}` - Delete brand (admin only)

### Shopping Cart
- `GET /cart` - Get current cart
- `POST /cart/{item_id}/increment` - Add item to cart
- `POST /cart/{item_id}/decrement` - Remove item from cart
- `PUT /cart/{item_id}` - Update item quantity
- `DELETE /cart/{item_id}` - Remove item completely

### Orders
- `POST /orders` - Create new order
- `GET /orders` - List all orders (admin only)
- `GET /auth/profile/orders` - List user's orders

## Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/pourpal-backend.git
cd pourpal-backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the development server:
```bash
uvicorn main:app --reload
```

## Documentation

When running in development mode, API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`