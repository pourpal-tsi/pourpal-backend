import pathlib
from datetime import datetime, timedelta, timezone, UTC
import passlib
from uuid import uuid4
from motor.motor_asyncio import AsyncIOMotorClient
from bson import Decimal128, json_util
from contextlib import asynccontextmanager
from config import MONGO_DB

from smtplib import SMTP, SMTPException
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from jose import JWTError, jwt
import bcrypt

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, Request, Depends, status, Response, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from models import Item, Money, Volume

import json
import random
import string

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_DEFAULT_EXPIRE_MINUTES, GOOGLE_MAIL_APP_EMAIL, GOOGLE_MAIL_APP_PASSWORD


JWT_SECURITY: bool = False  # TODO: JWT_SECURITY=False for local development
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587


def generate_sku(type_name: str) -> str:
    type_code = type_name[:3].upper()
    random_number = random.randint(1000000, 9999999)
    return f"{type_code}{random_number}"    

def get_client_ip_and_agent(request: Request) -> tuple[str, str] | None:
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    user_agent = request.headers.get("User-Agent")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(':')[0]
        port = x_forwarded_for.split(':')[1]
        return ip_address, user_agent
    return None, None

def decimal128_to_str(obj):
    if isinstance(obj, Decimal128):
        return str(obj.to_decimal())
    return obj

async def validate_item_attrs(request, item):
    # Validate type_id, brand_id, and origin_country_code
    type_id = item.get('type_id')
    brand_id = item.get('brand_id')
    origin_country_code = item.get('origin_country_code')

    # Check if type_name is valid
    valid_type = await request.app.mongodb['beverage_types'].find_one({"type_id": type_id})
    if not valid_type:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid type_id"}), None, None, None)

    # Check if brand_name is valid
    valid_brand = await request.app.mongodb['beverage_brands'].find_one({"brand_id": brand_id})
    if not valid_brand:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid brand_id"}), None, None, None)

    # Check if origin_country_name is valid
    valid_country = await request.app.mongodb['countries'].find_one({"code": origin_country_code})
    if not valid_country:
        return (False, JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid origin_country_code"}), None, None, None)
    
    return (True, JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Validation successful"}), valid_type, valid_brand, valid_country)

def bson_to_json(data):
    if isinstance(data, dict):
        return {key: bson_to_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [bson_to_json(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, Decimal128):
        return str(data.to_decimal())
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict) and '$date' in data:
        return data['$date']
    elif isinstance(data, dict) and '$numberDecimal' in data:
        return str(data['$numberDecimal'])
    else:
        return data

# Token functions
def encode_token(data: dict, expires_delta_minutes: int = JWT_DEFAULT_EXPIRE_MINUTES, scope: str = "tier_1"):
    data['scope'] = scope
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expires_delta_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    
# Random Password Generator
## Password must contain at least one uppercase letter, one lowercase letter and one number
def generate_random_password(length: int = 8):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

# Send Email
async def send_emails(receivers_emails: list, subject: str, html: str | None = None, message: str | None = None):
    # Login to the server email
    try:
        smtp = SMTP(EMAIL_HOST, EMAIL_PORT)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(GOOGLE_MAIL_APP_EMAIL, GOOGLE_MAIL_APP_PASSWORD)
    except SMTPException as e:
        return
    
    # Send email to each email in the list
    for rec_email in receivers_emails:
        try:
            msg = MIMEMultipart()
            msg['From'] = GOOGLE_MAIL_APP_EMAIL
            msg['To'] = rec_email
            msg['Subject'] = subject
            if html:
                msg.attach(MIMEText(html, 'html'))
            else:
                msg.attach(MIMEText(message, 'plain'))
            smtp.sendmail(GOOGLE_MAIL_APP_EMAIL, rec_email, msg.as_string())
        except Exception as e:
            print(f"Error sending email to {rec_email}: {e}")

    smtp.quit()

# Check if user password is correct
def password_is_correct(user_password: str, encoded_password: str) -> bool:
    return bcrypt.checkpw(user_password.encode('utf-8'), encoded_password.encode('utf-8'))

# Check if user is admin
async def is_user_admin(request: Request, access_token: str) -> bool | None:
    try:
        token_data = decode_token(access_token)
        user_id = token_data.get('user_id')
        user = await request.app.mongodb['users'].find_one({"user_id": user_id})
        if user is None:
            return None
        return user['role'] == 'admin'
    except Exception as e:
        return None
