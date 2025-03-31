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
                missing_subs.append(channel)
            except:
                continue
        except Exception as e:
            logger.error(f"Error checking user in channel {channel_id}: {e}")
    return missing_subs

# Decorator to check force subscription compliance
def check_fsub(func):
    async def wrapper(event):
        user_id = event.sender_id
        
        # Skip check for non-private chats or specific handlers
        if not event.is_private or isinstance(event, events.CallbackQuery):
            return await func(event)
            
        # Set a custom attribute to prevent duplicate checks
        if hasattr(event, '_fsub_checked'):
            return await func(event)
        event._fsub_checked = True
        
        missing_subs = await check_owner_fsub(user_id)
        if missing_subs is True:
            return await func(event)
            
        if missing_subs:
            buttons = []
            for channel in missing_subs:
                if hasattr(channel, 'username') and channel.username:
                    buttons.append([Button.url(f"Join {channel.title}", f"https://t.me/{channel.username}")])
                else:
                    try:
                        invite = await app(ExportChatInviteRequest(channel.id))
                        buttons.append([Button.url(f"Join {channel.title}", invite.link)])
                    except:
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

@app.on(events.ChatAction)
async def handle_added_to_chat(event):
    # Debugging: Print available attributes of the event object
    print(dir(event))  # This will help identify the correct attribute

    # Replace 'user_removed' with the correct attribute
    # Example: if the correct attribute is 'user_left', update the code as follows:
    if hasattr(event, 'user_left') and event.user_left:
        me = await app.get_me()
        if event.user_id == me.id:
            await remove_group(event.chat_id)  # Remove group when bot is removed

    if event.user_added:
        me = await app.get_me()
        if event.user_id == me.id:
            chat = await event.get_chat()
            await add_group(chat.id)  # Add group to the database
            if chat.username:
                chat_link = f"https://t.me/{chat.username}"
            else:
                chat_link = "Private Group"
            await app.send_message(
                LOGGER_ID,
                f"**🔔 ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɴᴇᴡ ᴄʜᴀᴛ**\n\n"
                f"**ᴄʜᴀᴛ ɴᴀᴍᴇ:** {chat.title}\n"
                f"**ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`\n"
                f"**ʟɪɴᴋ:** {chat_link}"
            )

# Update start command pattern to include optional bot username
@app.on(events.NewMessage(pattern=r"^/start(?:@\w+)?$"))
@check_fsub
async def start(event):
    user_id = event.sender_id
    await add_user(user_id)  # Add user to the database
    user = await event.get_sender()
    user_id = user.id

    await app.send_message(
        LOGGER_ID,
        f"**🆕 ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ**\n\n"
        f"**ɴᴀᴍᴇ:** {user.first_name}\n"
        f"**ᴜsᴇʀɴᴀᴍᴇ:** @{user.username}\n"
        f"**ᴜsᴇʀ ɪᴅ:** `{user.id}`"
    )
    await event.reply(
        "**👋 ʜᴇʟʟᴏ! ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʙᴏᴛ.**\n\n"
        "**➲ ᴜsᴇ ᴛʜɪs ʙᴏᴛ ᴛᴏ ᴇɴғᴏʀᴄᴇ ᴜsᴇʀs ᴛᴏ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟs ᴏʀ ɢʀᴏᴜᴘs ʙᴇғᴏʀᴇ ᴛʜᴇʏ ᴄᴀɴ sᴇɴᴅ ᴍᴇssᴀɢᴇs ɪɴ ᴀ ɢʀᴏᴜᴘ.**\n\n"
        "**➲ ᴛʏᴘᴇ /help ғᴏʀ ᴍᴏʀᴇ ɪɴғᴏʀᴍᴀᴛɪᴏɴ.**"
    )

# Update help command pattern to include optional bot username
@app.on(events.NewMessage(pattern=r"^/help(?:@\w+)?$"))
@check_fsub
async def help(event):
    user_id = event.sender_id
    await event.reply(
        "**📖 ʜᴇʟᴘ ᴍᴇɴᴜ:**\n\n"
        "**/set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ ᴏʀ ʟɪɴᴋ> (ᴜᴘ ᴛᴏ 4)** - ᴛᴏ sᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴀ ɢʀᴏᴜᴘ.\n"
        "**/fsub** - ᴛᴏ ᴍᴀɴᴀɢᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ (ᴏɴ/ᴏғғ).\n"
        "**/reset** - ᴛᴏ ʀᴇsᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴀɴᴅ ʀᴇᴍᴏᴠᴇ ᴀʟʟ ᴄʜᴀɴɴᴇʟs.\n"
        "**/start** - ᴛᴏ ᴅɪsᴘʟᴀʏ ᴛʜᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ.\n"
        "**/help** - ᴛᴏ ᴅɪsᴘʟᴀʏ ᴛʜᴇ ʜᴇʟᴘ ᴍᴇɴᴜ.\n"
        "**/stats** - ᴛᴏ ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs.\n"
        "**/broadcast <ᴍᴇssᴀɢᴇ>** - ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs.\n"
        "**/ban <ᴜsᴇʀ ɪᴅ>** - ᴛᴏ ʙᴀɴ ᴀ ᴜsᴇʀ.\n"
        "**/unban <ᴜsᴇʀ ɪᴅ>** - ᴛᴏ ᴜɴʙᴀɴ ᴀ ᴜsᴇʀ.\n\n"
        "**➲ ᴛʜᴇsᴇ ᴄᴏᴍᴍᴀɴᴅs ᴏɴʟʏ ᴡᴏʀᴋ ɪɴ ɢʀᴏᴜᴘs:**\n"
        "**/set** - ᴛᴏ sᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n"
        "**/fsub** - ᴛᴏ ᴍᴀɴᴀɢᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n"
        "**/reset** - ᴛᴏ ʀᴇsᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n\n"
        "**➲ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs, ᴀᴅᴍɪɴs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜᴇsᴇ ᴄᴏᴍᴍᴀɴᴅs.**"
     )
    
async def is_admin_or_owner(chat_id, user_id):
    try:
        member = await app.get_permissions(chat_id, user_id)
        return member.is_admin or member.is_creator or user_id == OWNER_ID
    except ChatAdminRequiredError:
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

@app.on(events.NewMessage(pattern=r"^/set( .+)?$", func=lambda e: e.is_group))
@check_fsub
async def set_forcesub(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    if not await is_admin_or_owner(chat_id, user_id):
        return await event.reply("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs, ᴀᴅᴍɪɴs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    await add_group(chat_id)  # Add group to database when setting force sub

    command = event.pattern_match.group(1)
    if not command:
        return await event.reply("**ᴜsᴀɢᴇ: /set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ ᴏʀ ʟɪɴᴋ> (ᴜᴘ ᴛᴏ 4)**")

    channels = command.strip().split()
    if len(channels) > 4:
        return await event.reply("**🚫 ʏᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴀᴅᴅ ᴜᴘ ᴛᴏ 4 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴs.**")

    fsub_data = []
    for channel_input in channels:
        try:
            if channel_input.startswith("https://t.me/"):
                channel_input = channel_input.replace("https://t.me/", "")

            # Attempt to get entity as integer ID first
            try:
                channel_id = int(channel_input)
                channel_entity = await app.get_entity(channel_id)
            except ValueError:
                # If not an integer, try as username
                channel_entity = await app.get_entity(channel_input)
                channel_id = channel_entity.id
            
            channel_info = await app(GetFullChannelRequest(channel_entity))
            channel_title = channel_info.chats[0].title

            if channel_info.chats[0].username:
                channel_username = f"@{channel_info.chats[0].username}"
                channel_link = f"https://t.me/{channel_info.chats[0].username}"
            else:
                invite = await app(ExportChatInviteRequest(channel_id))
                channel_username = invite.link
                channel_link = invite.link

            fsub_data.append({"id": channel_id, "username": channel_username, "title": channel_title, "link": channel_link})
        except Exception as e:
            logger.error(f"Error fetching channel info for {channel_input}: {e}")
            return await event.reply(f"**🚫 ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴅᴀᴛᴀ ғᴏʀ {channel_input}.**")

    forcesub_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"channels": fsub_data, "enabled": True}},
        upsert=True
    )

    set_by_user = f"@{event.sender.username}" if event.sender.username else event.sender.first_name

    channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in fsub_data])

    if len(fsub_data) == 1:
        channel_info = fsub_data[0]
        await event.reply(
            f"**🎉 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ sᴇᴛ ᴛᴏ** [{channel_info['title']}]({channel_info['username']}) **ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.**\n\n"
            f"**🆔 ᴄʜᴀɴɴᴇʟ ɪᴅ:** `{channel_info['id']}`\n"
            f"**🖇️ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ:** [ɢᴇᴛ ʟɪɴᴋ]({channel_info['link']})\n"
            f"**👤 sᴇᴛ ʙʏ:** {set_by_user}"
        )
    else:
        await event.reply(f"**🎉 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ sᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n{channel_list}")

@app.on(events.NewMessage(pattern=r"^/fsub$", func=lambda e: e.is_group))
@check_fsub
async def manage_forcesub(event):
    try:
        chat_id = event.chat_id
        user_id = event.sender_id

        if not await is_admin_or_owner(chat_id, user_id):
            return await event.reply("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs, ᴀᴅᴍɪɴs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

        forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})
        if not forcesub_data or not forcesub_data.get("channels"):
            return await event.reply("**🚫 ɴᴏ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ɪs sᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.**")

        channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
        is_enabled = forcesub_data.get("enabled", True)
        
        # Create unique callback data
        callback_data = f"fsub_toggle_{chat_id}_{1 if not is_enabled else 0}"
        
        buttons = [[Button.inline(
            "🔴 ᴛᴜʀɴ ᴏғғ" if is_enabled else "🟢 ᴛᴜʀɴ ᴏɴ", 
            callback_data
        )]]

        await event.reply(
            f"**📊 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n"
            f"{channel_list}\n\n"
            f"**ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs:** {'🟢 ᴏɴ' if is_enabled else '🔴 ᴏғғ'}",
            buttons=buttons
        )
    except Exception as e:
        logger.error(f"Error in manage_forcesub: {str(e)}")
        await event.reply("**❌ An error occurred while processing the command.**")

@app.on(events.CallbackQuery(pattern=r"fsub_toggle_(\-?\d+)_([01])"))
async def toggle_forcesub(event):
    try:
        chat_id = int(event.pattern_match.group(1))
        new_state = bool(int(event.pattern_match.group(2)))
        user_id = event.sender_id
        
        logger.info(f"Toggle callback received: chat_id={chat_id}, new_state={new_state}, user_id={user_id}")

        if not await is_admin_or_owner(chat_id, user_id):
            return await event.answer("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs, ᴀᴅᴍɪɴs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs.**", alert=True)

        forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})
        if not forcesub_data:
            return await event.answer("**ɴᴏ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ɪs sᴇᴛ.**", alert=True)

        # Update database
        forcesub_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"enabled": new_state}}
        )
        logger.info(f"Database updated for chat {chat_id}, new state: {new_state}")

        # Update message
        channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
        next_state = not new_state
        new_buttons = [[Button.inline(
            "🔴 ᴛᴜʀɴ ᴏғғ" if new_state else "🟢 ᴛᴜʀɴ ᴏɴ",
            f"fsub_toggle_{chat_id}_{1 if next_state else 0}"
        )]]

        await event.edit(
            f"**📊 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n"
            f"{channel_list}\n\n"
            f"**ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs:** {'🟢 ᴏɴ' if new_state else '🔴 ᴏғғ'}",
            buttons=new_buttons
        )
        
        await event.answer(
            f"**✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ {new_state and 'enabled' or 'disabled'} sᴜᴄᴄᴇssғᴜʟʟʏ!**",
            alert=True
        )
        logger.info(f"Toggle complete for chat {chat_id}, new state: {new_state}")
        
    except Exception as e:
        logger.error(f"Error in toggle_forcesub: {str(e)}")
        await event.answer("**❌ An error occurred while processing your request.**", alert=True)

@app.on(events.NewMessage(pattern=r"^/reset$", func=lambda e: e.is_group))
@check_fsub
async def reset_forcesub(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    if not await is_admin_or_owner(chat_id, user_id):
        return await event.reply("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs, ᴀᴅᴍɪɴs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    await remove_group(chat_id)  # Remove group from the database
    forcesub_collection.delete_one({"chat_id": chat_id})
    await event.reply("**✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ʀᴇsᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.**")

@app.on(events.NewMessage(pattern=r"^/stats$", func=lambda e: e.is_private))
@check_fsub
async def stats(event):
    user_id = event.sender_id
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    total_users = len(await get_all_users())  # Get all users from the database
    total_groups = len(await get_all_groups())  # Get all groups from the database
    banned_users = banned_users_collection.count_documents({})
    await event.reply(
        f"**📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs:**\n\n"
        f"**➲ ᴛᴏᴛᴀʟ ᴜsᴇʀs:** {total_users}\n"
        f"**➲ ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs:** {total_groups}\n"
        f"**➲ ʙᴀɴɴᴇᴅ ᴜsᴇʀs:** {banned_users}"
    )

@app.on(events.NewMessage(pattern=r"^/(broadcast|gcast)( .*)?$", func=lambda e: e.is_private))
@check_fsub
async def broadcast(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    # Check if there's a replied message or text content
    reply = event.reply_to_message if hasattr(event, 'reply_to_message') else None
    text = event.pattern_match.group(2)

    if not reply and not text:
        return await event.reply("**❖ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴛᴇxᴛ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ.**")

    progress_msg = await event.reply("**❖ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴍᴇssᴀɢᴇ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...**")

    sent_groups, sent_users, failed, pinned = 0, 0, 0, 0
    
    # Get all users and groups
    users = await get_all_users()
    groups = await get_all_groups()
    
    # Combine recipients
    recipients = groups + users

    for chat_id in recipients:
        try:
            if reply:
                msg = await event.reply_to_message.forward(chat_id)
            else:
                msg = await app.send_message(chat_id, text.strip())
            
            # Check if it's a group and try to pin
            if isinstance(chat_id, int) and chat_id < 0:
                try:
                    await app.pin_message(chat_id, msg.id, notify=False)
                    pinned += 1
                except:
                    pass
                sent_groups += 1
            else:
                sent_users += 1

            await asyncio.sleep(0.2)  # Prevent rate limits

        except Exception as e:
            logger.error(f"Failed to send broadcast to {chat_id}: {e}")
            failed += 1

    await progress_msg.edit(
        f"**✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ.**\n\n"
        f"**👥 ɢʀᴏᴜᴘs sᴇɴᴛ:** {sent_groups}\n"
        f"**🧑‍💻 ᴜsᴇʀs sᴇɴᴛ:** {sent_users}\n"
        f"**📌 ᴘɪɴɴᴇᴅ:** {pinned}\n"
        f"**❌ ғᴀɪʟᴇᴅ:** {failed}"
    )

@app.on(events.NewMessage(pattern=r"^/ban (\d+)$", func=lambda e: e.is_private))
@check_fsub
async def ban_user(event):
    user_id = event.sender_id
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    user_id = int(event.pattern_match.group(1))
    banned_users_collection.insert_one({"user_id": user_id})
    await event.reply(f"**✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.**")

@app.on(events.NewMessage(pattern=r"^/unban (\d+)$", func=lambda e: e.is_private))
@check_fsub
async def unban_user(event):
    user_id = event.sender_id
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    user_id = int(event.pattern_match.group(1))
    banned_users_collection.delete_one({"user_id": user_id})
    await event.reply(f"**✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ᴜɴᴀʙɴᴇᴅ.**")

@app.on(events.NewMessage(func=lambda e: e.is_private))
async def check_ban(event):
    user_id = event.sender_id
    if banned_users_collection.find_one({"user_id": event.sender_id}):
        return await event.reply("**🚫 ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.**")

@app.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_private:
        await add_user(event.sender_id)  # Add user to database on any private message
    elif event.is_group:
        await add_group(event.chat_id)

# Update check_fsub_handler to include owner fsub check for groups
@app.on(events.NewMessage)
async def check_fsub_handler(event):
    if hasattr(event, '_fsub_checked'):
        return
        
    user_id = event.sender_id
    
    # First check owner's force sub for both private and group chats
    missing_owner_subs = await check_owner_fsub(user_id)
    if missing_owner_subs is not True:
        buttons = []
        for channel in missing_owner_subs:
            if hasattr(channel, 'username') and channel.username:
                buttons.append([Button.url(f"Join {channel.title}", f"https://t.me/{channel.username}")])
            else:
                try:
                    invite = await app(ExportChatInviteRequest(channel.id))
                    buttons.append([Button.url(f"Join {channel.title}", invite.link)])
                except:
                    continue

        await event.reply(
            "**⚠️ ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
            "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
            "**ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ**\n"
            "**ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ!**",
            buttons=buttons
        )
        try:
            await event.delete()
        except:
            pass
        return

    # Handle group chats force sub check
    if event.is_group:
        chat_id = event.chat_id
        forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})

        if not forcesub_data or not forcesub_data.get("channels") or not forcesub_data.get("enabled", True):
            return

        is_member = True
        for channel in forcesub_data["channels"]:
            try:
                if isinstance(channel["id"], int):
                    await app(GetParticipantRequest(channel=channel["id"], participant=user_id))
                else:
                    channel_entity = await app.get_entity(channel["id"])
                    await app(GetParticipantRequest(channel=channel_entity, participant=user_id))
            except UserNotParticipantError:
                is_member = False
                break
            except Exception as e:
                if "Could not find the input entity" in str(e):
                    logger.warning(f"Could not check user {user_id} in channel {channel['id']}: {e}")
                    is_member = False
                    break
                else:
                    logger.error(f"An error occurred while checking user participation: {e}")
                    return

        if not is_member:
            try:
                await event.delete()
            except:
                pass

            try:
                await event.reply(
                    f"**👋 ʜᴇʟʟᴏ {event.sender.first_name},**\n\n"
                    f"**ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇs ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n"
                    f"{chr(10).join([f'๏ [{c['title']}]({c['username']})' for c in forcesub_data['channels']])}",
                    buttons=[[Button.url(f"๏ ᴊᴏɪɴ {c['title']} ๏", url=c['link']) for c in forcesub_data['channels']]]
                )
            except ButtonUrlInvalidError:
                logger.error(f"Button URL invalid for channel: {channel['username']}")
                await event.reply(
                    f"**👋 ʜᴇʟʟᴏ {event.sender.first_name},**\n\n"
                    f"**ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ channel to send messages in this group.**\n"
                    f"**Channel title:** {channel['title']}\n"
                    f"**Channel username or link:** {channel['username']}"
                )
            except Exception as e:
                logger.error(f"An error occurred while sending the force sub message: {e}")
            return

async def startup_notification():
    try:
        # Initialize database counts
        total_users = len(await get_all_users())
        total_groups = len(await get_all_groups())
        
        await app.send_message(
            LOGGER_ID,
            "**✅ ʙᴏᴛ ʜᴀs sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
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
