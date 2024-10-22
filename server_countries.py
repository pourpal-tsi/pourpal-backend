from fastapi import Request, Path, Header
from fastapi.responses import JSONResponse
from fastapi import status

from service_funcs import bson_to_json, is_user_admin


async def get_item_countries(request: Request):
    countries = await request.app.mongodb['countries'].find({}, {'_id': 0, 'added_at': 0}).sort("name", 1).to_list(length=None)
    countries = bson_to_json(countries)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"countries": countries})
