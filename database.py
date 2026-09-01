import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient, ReturnDocument

class Database:
    def __init__(self, uri, db_name):
        if not uri:
            raise RuntimeError("MONGODB_URI is missing.")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        self.db = self.client[db_name]
        self.watch = self.db["watchlist"]
        self.results = self.db["results"]
        self.settings = self.db["settings"]
        self.watch.create_index([("guild_id", 1), ("roll_number", 1)], unique=True)
        self.results.create_index([("guild_id", 1), ("roll_number", 1)])

    async def add_watch(self, guild_id, roll_number, class_name, year):
        doc = {
            "guild_id": guild_id, "roll_number": roll_number,
            "class_name": class_name, "year": int(year),
            "announced": False, "updated_at": datetime.now(timezone.utc)
        }
        await asyncio.to_thread(self.watch.update_one,
            {"guild_id": guild_id, "roll_number": roll_number},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True)

    async def remove_watch(self, guild_id, roll_number):
        res = await asyncio.to_thread(self.watch.delete_one, {"guild_id": guild_id, "roll_number": roll_number})
        return res.deleted_count > 0

    async def list_watches(self, guild_id, announced=None):
        query = {"guild_id": guild_id}
        if announced is not None:
            query["announced"] = announced
        return await asyncio.to_thread(lambda: list(self.watch.find(query).sort("created_at", 1)))

    async def save_result(self, guild_id, roll_number, class_name, year, result, announced):
        await asyncio.to_thread(
            self.results.update_one,
            {"guild_id": guild_id, "roll_number": roll_number},
            {"$set": {
                "guild_id": guild_id, "roll_number": roll_number,
                "class_name": class_name, "year": year, "result": result,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        if announced:
            await asyncio.to_thread(
                self.watch.update_one,
                {"guild_id": guild_id, "roll_number": roll_number},
                {"$set": {"announced": True, "announced_at": datetime.now(timezone.utc)}}
            )

    async def get_result(self, guild_id, roll_number):
        doc = await asyncio.to_thread(self.results.find_one, {"guild_id": guild_id, "roll_number": roll_number})
        return doc.get("result") if doc else None

    async def set_setting(self, guild_id, key, value):
        await asyncio.to_thread(self.settings.update_one,
            {"guild_id": guild_id}, {"$set": {key: value}}, upsert=True)

    async def get_setting(self, guild_id, key):
        doc = await asyncio.to_thread(self.settings.find_one, {"guild_id": guild_id})
        return doc.get(key) if doc else None
