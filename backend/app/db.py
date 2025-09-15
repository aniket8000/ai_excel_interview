import os
import pathlib
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# load backend/.env
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "examinerDB")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI not set in backend/.env")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[MONGO_DB_NAME]

transcripts_collection = db["transcripts"]
reports_collection = db["reports"]
