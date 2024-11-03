
from datetime import datetime, timedelta, timezone
from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

from fastapi import Request, status, Header
from fastapi.responses import JSONResponse
from models import UserAdmin, UserCustomer, UserAuthorization

from service_funcs import bson_to_json, generate_random_password, encode_token, decode_token, send_emails, password_is_correct, is_user_admin

from service_rules import DEV_MODE_ENABLED


async def login(request: Request, user_data: dict):
    # Check if email and password are provided
    if 'email' not in user_data or 'password' not in user_data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Email and password are required"})

    # Check if user exists and password is correct
    user = await request.app.mongodb['users'].find_one({"email": user_data['email']})
    if not user or not password_is_correct(user_password=user_data['password'], encoded_password=user['encoded_password']):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid email or password"})

    # Generate tokens
    access_token = encode_token(data={'user_id': user['user_id']}, expires_delta_minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    # Update user's authorization timestamps
    await request.app.mongodb['users'].update_one(
        {"user_id": user['user_id']},
        {"$push": {"authorizations": UserAuthorization(headers=dict(request.headers), timestamp=datetime.now(timezone.utc)).model_dump()}}
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content={"access_token": access_token})
    
async def register_admin(request: Request, user_data: dict, authorization: str = Header(None)):
    # Check if the caller is an admin
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    token_data = decode_token(access_token)
    caller_user_id = token_data.get('user_id') if token_data else None
    if caller_user_id:
        caller_user = await request.app.mongodb['users'].find_one({"user_id": caller_user_id})
        if caller_user['role'] != 'admin':
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": "Caller user is not an admin"})
    else:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid access token"})

    # Check if request body has email
    if 'email' not in user_data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Email is required"})
    
    # Check if email is already in use
    existing_user = await request.app.mongodb['users'].find_one({"email": user_data['email']})
    if existing_user:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Email already in use"})
        
    # Create new admin user
    password = generate_random_password(length=8)
    user = UserAdmin(email=user_data['email'], password=password)
    result = await request.app.mongodb['users'].insert_one(user.model_dump())
    if result.inserted_id:
        if not DEV_MODE_ENABLED:
            # Send email to the new admin user
            subject = "Admin Registration Successful"
            message = f'''Dear <i>{user.email}</i>,<br><br>You have been registered as an administrator of the PourPal platform.
                        <br>Your password is: <b>{password}</b><br><small style="color: gray;">Please change your password after logging in.</small><br><br>Best regards,<br>The PourPal Team<br><a href="https://pourpal.site/">www.pourpal.site</a>'''
            try:
                await send_emails([user.email], subject, html=message)
            except Exception as e:
                return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": f"Failed to send email: {e}"})
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Admin registered successfully", "user_id": user.user_id})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Failed to register admin"})

async def register_customer(request: Request, user_data: dict):
    # Check if request body has email and password
    if 'email' not in user_data or 'password' not in user_data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Email and password are required"})
    
    # Check if email is already in use
    existing_user = await request.app.mongodb['users'].find_one({"email": user_data['email']})
    if existing_user:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Email already in use"})
    
    # Create new customer user
    user = UserCustomer(email=user_data['email'], password=user_data['password'])
    result = await request.app.mongodb['users'].insert_one(user.model_dump())
    if result.inserted_id:
        if not DEV_MODE_ENABLED:
            # Send email to the new customer user
            subject = "Customer Registration Successful"
            message = f'''Dear <i>{user.email}</i>,<br><br>You have been registered as a customer of the PourPal platform.
                        <br><br>Best regards,<br>The PourPal Team<br><a href="https://pourpal.site/">www.pourpal.site</a>'''
            try:
                await send_emails([user.email], subject, html=message)
            except Exception as e:
                return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": f"Failed to send email: {e}"})
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Customer registered successfully", "user_id": user.user_id})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Failed to register customer"})

async def get_profile(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid authorization header"})

    access_token = authorization.split(" ")[1]
    
    # Decode the access token
    try:
        decoded_token = decode_token(access_token)
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": f"Invalid access token: {str(e)}"})

    # Get the user ID from the access token
    user_id = decoded_token.get('user_id')
    if not user_id:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Invalid access token"})

    # Get the user details from the database
    user = await request.app.mongodb['users'].find_one({"user_id": user_id})
    if not user:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "User not found"})

    bson_user_data = {
        "email": user['email'],
        "role": user['role'],
        "full_name": user['full_name'],
        "is_active": user['is_active'],
        "updated_at": user['updated_at'],
        "created_at": user['created_at']
    }
    
    return JSONResponse(status_code=status.HTTP_200_OK, content=bson_to_json(bson_user_data))
