import os
import logging
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors import UserIsBlockedError, UserNotParticipantError, ChatAdminRequiredError
from pymongo import MongoClient
import asyncio

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DURGESH")

# Environment variables with validation
def get_env_var(name, default=None, cast=str):
    value = os.getenv(name, default)
    if value is None or (cast == int and not value.isdigit()):
        raise ValueError(f"{name} must be set in environment variables")
    return cast(value)

BOT_TOKEN = get_env_var("BOT_TOKEN", None, str)
MONGO_URI = get_env_var("MONGO_URL", None, str)
OWNER_ID = get_env_var("OWNER_ID", None, int)
LOGGER_ID = get_env_var("LOGGER_ID", None, int)
API_ID = get_env_var("API_ID", None, int)
API_HASH = get_env_var("API_HASH", None, str)
FSUB = get_env_var("FSUB", "").strip()

# Telegram client
app = TelegramClient('bot', api_id=API_ID, api_hash=API_HASH)

# MongoDB connection
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client.fsub
    users_collection = db["users"]
    groups_collection = db["groups"]
    forcesub_collection = db["forcesubs"]
    banned_users_collection = db["banned_users"]
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Database functions
async def add_user(user_id):
    try:
        if not users_collection.find_one({"user_id": user_id}):
            users_collection.insert_one({"user_id": user_id})
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")

async def add_group(group_id):
    try:
        if not groups_collection.find_one({"group_id": group_id}):
            groups_collection.insert_one({"group_id": group_id})
    except Exception as e:
        logger.error(f"Error adding group {group_id}: {e}")

async def remove_group(group_id):
    try:
        if groups_collection.find_one({"group_id": group_id}):
            groups_collection.delete_one({"group_id": group_id})
    except Exception as e:
        logger.error(f"Error removing group {group_id}: {e}")

async def get_all_users():
    users = []
    try:
        for user in users_collection.find():
            users.append(user["user_id"])
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
    return users

async def get_all_groups():
    groups = []
    try:
        for chat in groups_collection.find():
            groups.append(chat["group_id"])
    except Exception as e:
        logger.error(f"Error fetching groups: {e}")
    return groups

# Parse force sub channels/groups
FSUB_IDS = []
if FSUB:
    try:
        fsub_list = FSUB.split()
        if len(fsub_list) > 4:
            logger.warning("Maximum 4 force subscription channels allowed. Using first 4.")
            fsub_list = fsub_list[:4]
        for item in fsub_list:
            try:
                FSUB_IDS.append(int(item))
            except ValueError:
                FSUB_IDS.append(item)  # Keep as string if not an integer
    except Exception as e:
        logger.error(f"Invalid FSUB format: {e}. Should be space-separated channel IDs or usernames.")

# Check owner's force subscription
async def check_owner_fsub(user_id):
    if not FSUB_IDS or user_id == OWNER_ID:
        return True

    missing_subs = []
    for channel_id in FSUB_IDS:
        try:
            channel_entity = await app.get_entity(channel_id)
            await app(GetParticipantRequest(channel=channel_entity, participant=user_id))
        except UserNotParticipantError:
            missing_subs.append(channel_entity)
        except (ValueError, ChatAdminRequiredError) as e:
            logger.error(f"Cannot access channel {channel_id}: {e}")
            missing_subs.append(channel_id)  # Treat as missing if inaccessible
        except Exception as e:
            logger.error(f"Unexpected error checking channel {channel_id}: {e}")
            continue
    return missing_subs if missing_subs else True

# Decorator to check force subscription compliance
def check_fsub(func):
    async def wrapper(event):
        user_id = event.sender_id
        
        # Check force sub only for bot commands
        if event.text and event.text.startswith('/'):
            missing_owner_subs = await check_owner_fsub(user_id)
            if missing_owner_subs is not True:
                buttons = []
                for channel in missing_owner_subs:
                    if isinstance(channel, str):  # If channel_id was a string and failed to resolve
                        logger.warning(f"Channel {channel} could not be resolved")
                        continue
                    if hasattr(channel, 'username') and channel.username:
                        buttons.append([Button.url(f"Join {channel.title}", f"https://t.me/{channel.username}")])
                    else:
                        try:
                            invite = await app(ExportChatInviteRequest(channel.id))
                            buttons.append([Button.url(f"Join {channel.title}", invite.link)])
                        except ChatAdminRequiredError:
                            logger.error(f"Bot lacks permission to generate invite for {channel.title}")
                            continue
                        except Exception as e:
                            logger.error(f"Error generating invite for {channel.title}: {e}")
                            continue
                if buttons:  # Only reply if there are valid buttons
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

# Example command to test the bot
@app.on(events.NewMessage(pattern='/start'))
@check_fsub
async def start(event):
    await event.reply("Welcome to the bot! You've passed the force subscription check.")
    await add_user(event.sender_id)

# Start the bot
async def main():
    await app.start(bot_token=BOT_TOKEN)
    logger.info("Bot started successfully")
    await app.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
