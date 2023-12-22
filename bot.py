import os
import yaml
import time
from datetime import datetime, timedelta
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message

# Load configuration from config.yaml
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

API_ID = config['api']['id']
API_HASH = config['api']['hash']
BOT_TOKEN = config['api']['token']

MONGO_URI = config['mongo']['uri']

ADMIN_USER_IDS = config['admin']['user_ids']

LOG_CHANNEL_ID = config['channels']['log_channel_id']
DB_CHANNEL_ID = config['channels']['db_channel_id']

app = Client(
    "your_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["file_records"]

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text('Send me a file.')

@app.on_message(filters.document & filters.user(ADMIN_USER_IDS))
async def handle_file(client, message):
    file_id = message.document.file_id
    user_id = message.from_user.id

    file_record = {
        "user_id": user_id,
        "file_id": file_id,
        "file_link": None,
        "timestamp": datetime.now(),
    }

    db.files.insert_one(file_record)

    file_link = f'https://yourdomain.com/get_file/{file_record["_id"]}'
    file_record["file_link"] = file_link

    db.files.update_one({"_id": file_record["_id"]}, {"$set": {"file_link": file_link}})

    # Send a message to the database channel
    await app.send_message(DB_CHANNEL_ID, f'New file link: {file_link}')

    await message.reply_text(f'File link: {file_link}')

@app.on_message(filters.command("batch") & filters.user(ADMIN_USER_IDS))
async def batch_command(client, message):
    await message.reply_text('Send the start link of the batch.')

    # Handle the start link
    start_link = (await app.get_messages(message.chat.id, message.reply_to_message.message_id)).text

    await message.reply_text('Send the stop link of the batch.')

    # Handle the stop link
    stop_link = (await app.get_messages(message.chat.id, message.reply_to_message.message_id)).text

    # Generate and send the one-link of the batch
    start_time = datetime.strptime(start_link, "%Y-%m-%d %H:%M:%S")
    stop_time = datetime.strptime(stop_link, "%Y-%m-%d %H:%M:%S")

    file_links = db.files.find(
        {"timestamp": {"$gte": start_time, "$lte": stop_time}},
        {"file_link": 1, "_id": 0},
    )

    one_link = '\n'.join(link["file_link"] for link in file_links)

    # Send a message to the database channel
    await app.send_message(DB_CHANNEL_ID, f'One link for the batch:\n{one_link}')

    await message.reply_text(f'One link for the batch:\n{one_link}')

@app.on_message(filters.text & ~filters.user(ADMIN_USER_IDS))
async def non_admin_message(client, message):
    await message.reply_text('Admin will reply soon.')

    # Log the message to the log channel
    await app.send_message(
        LOG_CHANNEL_ID,
        f"User {message.from_user.id} ({message.from_user.username}) sent a message:\n\n{message.text}"
    )

async def delete_old_files():
    one_hour_ago = datetime.now() - timedelta(hours=1)
    db.files.delete_many({"timestamp": {"$lt": one_hour_ago}})

if __name__ == '__main__':
    # Start a job to delete old files every 15 seconds
    app.scheduler.add_job(delete_old_files, trigger="interval", seconds=15)

    # Start the bot
    app.run()
