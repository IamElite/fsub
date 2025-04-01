import os
import logging
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors.rpcerrorlist import UserNotParticipantError
from pymongo import MongoClient
import asyncio

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DURGESH")

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", None)
MONGO_URI = os.getenv("MONGO_URL", None)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOGGER_ID = int(os.getenv("LOGGER_ID", "0"))
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", None)
FSUB = os.getenv("FSUB", "").strip()

# Telegram client
app = TelegramClient('bot', api_id=API_ID, api_hash=API_HASH)

# MongoDB connection
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.fsub
users_collection = db["users"]
groups_collection = db["groups"]
forcesub_collection = db["forcesubs"]
banned_users_collection = db["banned_users"]

# Database functions
async def add_user(user_id):
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id})

async def add_group(group_id):
    if not groups_collection.find_one({"group_id": group_id}):
        groups_collection.insert_one({"group_id": group_id})

async def remove_group(group_id):
    if groups_collection.find_one({"group_id": group_id}):
        groups_collection.delete_one({"group_id": group_id})

async def get_all_users():
    users = []
    for user in users_collection.find():
        try:
            users.append(user["user_id"])
        except Exception:
            pass
    return users

async def get_all_groups():
    groups = []
    for chat in groups_collection.find():
        try:
            groups.append(chat["group_id"])
        except Exception:
            pass
    return groups

# Parse force sub channels/groups
FSUB_IDS = []
if FSUB:
    try:
        fsub_list = FSUB.split()
        if len(fsub_list) > 4:
            logger.warning("Maximum 4 force subscription channels allowed. Using first 4.")
            fsub_list = fsub_list[:4]
        FSUB_IDS = [int(x) if x.isdigit() or (x.startswith('-') and x[1:].isdigit()) else x for x in fsub_list]
    except Exception as e:
        logger.error("Invalid FSUB format. Should be space-separated channel IDs or usernames.")

# Function to check owner's force subscription
async def check_owner_fsub(user_id):
    if not FSUB_IDS or user_id == OWNER_ID:
        return True

    missing_subs = []
    for channel_id in FSUB_IDS:
        try:
            if isinstance(channel_id, int):
                await app(GetParticipantRequest(channel=channel_id, participant=user_id))
            else:
                channel_entity = await app.get_entity(channel_id)
                await app(GetParticipantRequest(channel=channel_entity, participant=user_id))
        except UserNotParticipantError:
            try:
                if isinstance(channel_id, int):
                    channel = await app.get_entity(channel_id)
                else:
                    channel = await app.get_entity(channel_id)
                missing_subs.append(channel)
            except Exception as e:
                logger.error(f"Error getting channel {channel_id}: {e}")
                continue
        except Exception as e:
            logger.error(f"Error checking user in channel {channel_id}: {e}")
    return True if not missing_subs else missing_subs

# Decorator to check force subscription compliance
def check_fsub(func):
    async def wrapper(event):
        user_id = event.sender_id
        
        # Check for bot commands starting with '/'
        if event.text and event.text.startswith('/'):
            missing_owner_subs = await check_owner_fsub(user_id)
            if missing_owner_subs is not True:
                buttons = []
                for channel in missing_owner_subs:
                    if hasattr(channel, 'username') and channel.username:
                        buttons.append([Button.url(f"Join {channel.title}", f"https://t.me/{channel.username}")])
                    else:
                        try:
                            invite = await app(ExportChatInviteRequest(channel))
                            buttons.append([Button.url(f"Join {channel.title}", invite.link)])
                        except Exception as e:
                            logger.error(f"Error creating invite for {channel.id}: {e}")
                            continue
                await event.reply(
                    "**⚠️ ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
                    "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
                    "**ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ**\n"
                    "**ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ!**",
                    buttons=buttons
                )
                return
        return await func(event)
    return wrapper

# Sample command handler using the check_fsub decorator
@app.on(events.NewMessage(pattern='/start'))
@check_fsub
async def start_handler(event):
    await event.reply("Hello! Bot chal raha hai.")

# Main function to start the bot
def main():
    app.start(bot_token=BOT_TOKEN)
    logger.info("Bot started!")
    app.run_until_disconnected()

if __name__ == '__main__':
    main()
