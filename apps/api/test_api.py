import asyncio
from app.api.endpoints.user_assets import list_user_assets
from app.core.database import connect_to_mongo

async def main():
    await connect_to_mongo()
    try:
        res = await list_user_assets(current_user={"_id": "dummy"})
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
