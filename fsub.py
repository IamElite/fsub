import os
import logging
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors import UserIsBlockedError
from telethon.errors.rpcerrorlist import UserNotParticipantError, ButtonUrlInvalidError, ChatAdminRequiredError
from pymongo import MongoClient
import asyncio

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DURGESH")

# Environment variables with default values
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
        # Ensure FSUB_IDS are integers
        FSUB_IDS = [int(x) if x.isdigit() or (x.startswith('-') and x[1:].isdigit()) else x for x in fsub_list]
    except:
        logger.error("Invalid FSUB format. Should be space-separated channel IDs or usernames.")

# Add new function to check owner's force sub
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
                
                # Get more channel info for better button display
                try:
                    channel_info = await app(GetFullChannelRequest(channel))
                    channel_title = channel_info.chats[0].title
                    channel.title = channel_title  # Add title attribute
                except Exception as e:
                    logger.error(f"Error getting channel info: {e}")
                    channel.title = "Channel"  # Fallback title
                
                missing_subs.append(channel)
            except Exception as e:
                logger.error(f"Error getting channel entity: {e}")
                continue
        except Exception as e:
            logger.error(f"Error checking user in channel {channel_id}: {e}")
    return missing_subs

# Decorator to check force subscription compliance
def check_fsub(func):
    async def wrapper(event):
        user_id = event.sender_id
        
        # Check owner's force sub only for bot commands
        if event.text and event.text.startswith('/'):
            missing_owner_subs = await check_owner_fsub(user_id)
            if missing_owner_subs is not True:
                buttons = []
                for channel in missing_owner_subs:
                    try:
                        if hasattr(channel, 'username') and channel.username:
                            channel_title = getattr(channel, 'title', 'Channel')
                            buttons.append([Button.url(f"🔗 Join {channel_title}", f"https://t.me/{channel.username}")])
                        else:
                            try:
                                invite = await app(ExportChatInviteRequest(channel.id))
                                if invite and invite.link:
                                    channel_title = getattr(channel, 'title', 'Channel')
                                    buttons.append([Button.url(f"🔗 Join {channel_title}", invite.link)])
                            except Exception as e:
                                logger.error(f"Error creating invite link: {e}")
                                continue
                    except Exception as e:
                        logger.error(f"Error creating button for channel {getattr(channel, 'id', 'unknown')}: {e}")
                        continue
                
                # Only send message with buttons if we have valid buttons
                if buttons:
                    await event.reply(
                        "**⚠️ ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
                        "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
                        "**ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ**\n"
                        "**ᴛʜᴇɴ ᴄʟɪᴄᴋ 🔄 ᴛʀʏ ᴀɢᴀɪɴ**",
                        buttons=buttons + [[Button.inline("🔄 ᴛʀʏ ᴀɢᴀɪɴ", "check_fsub")]]
                    )
                else:
                    # Fallback message if no valid buttons could be created
                    await event.reply(
                        "**⚠️ ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
                        "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
                        "**ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴄᴏɴᴛʀᴏʟ ᴏғ ᴛʜᴇ ʙᴏᴛ!**\n"
                        "**ᴛʀʏ ᴀɢᴀɪɴ**",
                        buttons=[[Button.inline("🔄 ᴛʀʏ ᴀɢᴀɪɴ", "check_fsub")]]
                    )
                return
        return await func(event)
    return wrapper

# Add this after the other callback handlers
@app.on(events.CallbackQuery(pattern=r"check_fsub"))
async def check_fsub_callback(event):
    user_id = event.sender_id
    
    # Check if user has joined all required channels
    missing_owner_subs = await check_owner_fsub(user_id)
    
    if missing_owner_subs is True:
        # User has joined all channels
        await event.answer("✅ Thank you for joining! You can now use the bot.", alert=True)
        # Edit the message to show success
        await event.edit(
            "**✅ ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ!**\n\n"
            "**ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴊᴏɪɴɪɴɢ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs.**\n"
            "**ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ.**\n\n"
            "**ᴛʏᴘᴇ /start ᴛᴏ sᴛᴀʀᴛ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ.**"
        )
    else:
        # User still needs to join some channels
        buttons = []
        for channel in missing_owner_subs:
            try:
                if hasattr(channel, 'username') and channel.username:
                    channel_title = getattr(channel, 'title', 'Channel')
                    buttons.append([Button.url(f"🔗 Join {channel_title}", f"https://t.me/{channel.username}")])
                else:
                    try:
                        invite = await app(ExportChatInviteRequest(channel.id))
                        if invite and invite.link:
                            channel_title = getattr(channel, 'title', 'Channel')
                            buttons.append([Button.url(f"🔗 Join {channel_title}", invite.link)])
                    except Exception as e:
                        logger.error(f"Error creating invite link: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error creating button for channel {getattr(channel, 'id', 'unknown')}: {e}")
                continue
        
        await event.answer("❌ You need to join all channels to use the bot.", alert=True)
        
        if buttons:
            await event.edit(
                "**⚠️ ᴀᴄᴄᴇss sᴛɪʟʟ ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
                "**ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
                "**ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ**\n"
                "**ᴛʜᴇɴ ᴄʟɪᴄᴋ 🔄 ᴛʀʏ ᴀɢᴀɪɴ!**",
                buttons=buttons + [[Button.inline("🔄 ᴛʀʏ ᴀɢᴀɪɴ", "check_fsub")]]
            )

async def startup_notification():
    try:
        # Initialize database counts
        total_users = len(await get_all_users())
        total_groups = len(await get_all_groups())
        
        await app.send_message(
            LOGGER_ID,
            "**✅ ʙᴏᴛ ʜᴀs sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʀʀʏ!**\n\n"
            f"**ʙᴏᴛ ɪɴғᴏ:**\n"
            f"**➲ ᴏᴡɴᴇʀ ɪᴅ:** `{OWNER_ID}`\n"
            f"**➲ ʟᴏɢɢᴇʀ ɪᴅ:** `{LOGGER_ID}`\n"
            f"**➲ ᴛᴏᴛᴀʟ ᴜsᴇʀs:** `{total_users}`\n"
            f"**➲ ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs:** `{total_groups}`"
        )
    except Exception as e:
        logger.error(f"Error sending startup notification: {e}")

async def main():
    await app.start(bot_token=BOT_TOKEN)
    await startup_notification()
    logger.info("Bot is running.")
    await app.run_until_disconnected()

if __name__ == "__main__":
    logger.info("Starting the bot...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
