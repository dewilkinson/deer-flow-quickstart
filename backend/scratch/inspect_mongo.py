import sys
import os
from pymongo import MongoClient
import json

def inspect_mongodb():
    conn_string = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = MongoClient(conn_string)
    db = client["checkpointing_db"]
    collection = db["checkpoints"]
    
    print("### MONGO DB CHECKPOINT INSPECTION")
    
    # 1. Total docs
    total = collection.count_documents({})
    print(f"Total Checkpoints: {total}")
    
    # 2. Latest thread
    latest = collection.find_one(sort=[("checkpoint_id", -1)])
    if latest:
        thread_id = latest.get("thread_id")
        print(f"Latest Thread ID: {thread_id}")
        
        # 3. Checkpoint size for latest thread
        # 'checkpoint' field is bytes
        size_bytes = len(latest.get("checkpoint", b""))
        print(f"Latest Checkpoint Size: {size_bytes / 1024:.2f} KB")
        
        # 4. Count messages in that checkpoint if possible
        # We'd need to de-serialize using LangGraph's serde
        print("Checkpoint Type:", latest.get("type"))
    
    # 5. List high-volume threads
    pipeline = [
        {"$group": {"_id": "$thread_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    print("\nTop 5 Threads by Checkpoint Count:")
    for res in collection.aggregate(pipeline):
        print(f"- {res['_id']}: {res['count']} checkpoints")

if __name__ == "__main__":
    inspect_mongodb()
