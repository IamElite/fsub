import os
import logging
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChannelParticipantCreator, ChannelParticipantAdmin, ChannelParticipantsSearch
from telethon.errors import UserIsBlockedError
from telethon.errors.rpcerrorlist import UserNotParticipantError, ButtonUrlInvalidError
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

# MongoDB connection
fsubdb = MongoClient(MONGO_URI)
forcesub_collection = fsubdb.status_db.status
banned_users_collection = fsubdb.status_db.banned_users

# Telegram client
app = TelegramClient('bot', api_id=API_ID, api_hash=API_HASH)

# Parse force sub channels/groups
FSUB_IDS = []
if FSUB:
    try:
        fsub_list = FSUB.split()
        if len(fsub_list) > 4:
            logger.warning("Maximum 4 force subscription channels allowed. Using first 4.")
            fsub_list = fsub_list[:4]
        FSUB_IDS = [int(x) for x in fsub_list]
    except:
        logger.error("Invalid FSUB format. Should be space-separated channel IDs.")

# Add new function to check owner's force sub
async def check_owner_fsub(user_id):
    if not FSUB_IDS or user_id == OWNER_ID:
        return True
        
    missing_subs = []
    for channel_id in FSUB_IDS:
        try:
            await app(GetParticipantRequest(channel=channel_id, participant=user_id))
        except UserNotParticipantError:
            try:
                channel = await app.get_entity(channel_id)
                missing_subs.append(channel)
            except:
                continue
    return missing_subs

@app.on(events.ChatAction)
async def handle_added_to_chat(event):
    if event.user_added and event.user_id == app.uid:
        chat = await event.get_chat()
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

@app.on(events.NewMessage(pattern=r"^/start$", func=lambda e: e.is_private))
async def start(event):
    user = await event.get_sender()
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

@app.on(events.NewMessage(pattern=r"^/help$", func=lambda e: e.is_private))
async def help(event):
    await event.reply(
        "**📖 ʜᴇʟᴘ ᴍᴇɴᴜ:**\n\n"
        "**/set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ> (ᴜᴘ ᴛᴏ 4)** - ᴛᴏ sᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴀ ɢʀᴏᴜᴘ.\n"
        "**/fsub** - ᴛᴏ ᴍᴀɴᴀɢᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ (ᴏɴ/ᴏғғ).\n"
        "**/start** - ᴛᴏ ᴅɪsᴘʟᴀʏ ᴛʜᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ.\n"
        "**/help** - ᴛᴏ ᴅɪsᴘʟᴀʏ ᴛʜᴇ ʜᴇʟᴘ ᴍᴇɴᴜ.\n"
        "**/stats** - ᴛᴏ ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs.\n"
        "**/broadcast <ᴍᴇssᴀɢᴇ>** - ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs.\n"
        "**/ban <ᴜsᴇʀ ɪᴅ>** - ᴛᴏ ʙᴀɴ ᴀ ᴜsᴇʀ.\n"
        "**/unban <ᴜsᴇʀ ɪᴅ>** - ᴛᴏ ᴜɴʙᴀɴ ᴀ ᴜsᴇʀ.\n\n"
        "**➲ ᴛʜᴇsᴇ ᴄᴏᴍᴍᴀɴᴅs ᴏɴʟʏ ᴡᴏʀᴋ ɪɴ ɢʀᴏᴜᴘs:**\n"
        "**/set** - ᴛᴏ sᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n"
        "**/fsub** - ᴛᴏ ᴍᴀɴᴀɢᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n\n"
        "**➲ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜᴇsᴇ ᴄᴏᴍᴍᴀɴᴅs.**"
    )

@app.on(events.NewMessage(pattern=r"^/set( .+)?$", func=lambda e: e.is_group))
async def set_forcesub(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    member = await app(GetParticipantRequest(chat_id, user_id))
    if not (isinstance(member.participant, (ChannelParticipantCreator, ChannelParticipantAdmin)) or user_id == OWNER_ID):
        return await event.reply("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    command = event.pattern_match.group(1)
    if not command:
        return await event.reply("**ᴜsᴀɢᴇ: /set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ> (ᴜᴘ ᴛᴏ 4)**")

    channels = command.strip().split()
    if len(channels) > 4:
        return await event.reply("**🚫 ʏᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴀᴅᴅ ᴜᴘ ᴛᴏ 4 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴs.**")

    fsub_data = []
    for channel_input in channels:
        try:
            channel_info = await app(GetFullChannelRequest(channel_input))
            channel_id = channel_info.full_chat.id
            channel_title = channel_info.chats[0].title
            if channel_info.chats[0].username:
                channel_username = f"@{channel_info.chats[0].username}"
                channel_link = f"https://t.me/{channel_info.chats[0].username}"
            else:
                invite = await app(ExportChatInviteRequest(channel_id))
                channel_username = invite.link
                channel_link = invite.link
            
            channel_members = await app(GetParticipantsRequest(
                channel=channel_id,
                filter=ChannelParticipantsSearch(''),
                offset=0,
                limit=1
            ))
            channel_members_count = channel_members.count
            
            fsub_data.append({"id": channel_id, "username": channel_username, "title": channel_title, "link": channel_link})
        except Exception as e:
            logger.error(f"Error fetching channel info for {channel_input}: {e}")
            return await event.reply(f"**🚫 ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴅᴀᴛᴀ ғᴏʀ {channel_input}.**")

    forcesub_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"channels": fsub_data}},
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
async def manage_forcesub(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    member = await app(GetParticipantRequest(chat_id, user_id))
    if not (isinstance(member.participant, (ChannelParticipantCreator, ChannelParticipantAdmin)) or user_id == OWNER_ID):
        return await event.reply("**ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")

    forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})
    if not forcesub_data or not forcesub_data.get("channels"):
        return await event.reply("**🚫 ɴᴏ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ɪs sᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.**")

    channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
    await event.reply(
        f"**📊 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n{channel_list}",
        buttons=[
            [Button.inline("ON", data=f"fsub_on_{chat_id}"), Button.inline("OFF", data=f"fsub_off_{chat_id}")]
        ]
    )

@app.on(events.CallbackQuery(pattern=r"fsub_(on|off)_(\d+)"))
async def toggle_forcesub(event):
    action, chat_id = event.pattern_match.group(1), int(event.pattern_match.group(2))

    if action == "on":
        await event.edit("**✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.**")
    elif action == "off":
        forcesub_collection.delete_one({"chat_id": chat_id})
        await event.edit("**❌ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.**")

@app.on(events.NewMessage(func=lambda e: e.is_group))
async def enforce_forcesub(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})
    if not forcesub_data or not forcesub_data.get("channels"):
        return

    is_member = True
    for channel in forcesub_data["channels"]:
        try:
            await app(GetParticipantRequest(channel["id"], user_id))
        except UserNotParticipantError:
            is_member = False
            break
        except Exception as e:
            if "Could not find the input entity" in str(e):
                logger.warning(f"Could not check user {user_id} in channel {channel['id']}: {e}")
                # We can't check this user, so we'll assume they are not a member.
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
                f"**ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ғᴏʟʟᴏᴡɪɴɢ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇs ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ:**\n\n"
                f"{chr(10).join([f'๏ [{c['title']}]({c['username']})' for c in forcesub_data['channels']])}",
                buttons=[[Button.url(f"๏ ᴊᴏɪɴ {c['title']} ๏", url=c['username']) for c in forcesub_data['channels']]]
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

@app.on(events.NewMessage(pattern=r"^/stats$", func=lambda e: e.is_private))
async def stats(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")
    
    total_users = len(await app.get_dialogs())
    banned_users = banned_users_collection.count_documents({})
    await event.reply(f"**📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs:**\n\n**➲ ᴛᴏᴛᴀʟ ᴜsᴇʀs:** {total_users}\n**➲ ʙᴀɴɴᴇᴅ ᴜsᴇʀs:** {banned_users}")

@app.on(events.NewMessage(pattern=r"^/broadcast (.+)$", func=lambda e: e.is_private))
async def broadcast(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")
    
    message = event.pattern_match.group(1)
    async for dialog in app.iter_dialogs():
        try:
            await app.send_message(dialog.id, message)
        except UserIsBlockedError:
            logger.warning(f"User {dialog.id} has blocked the bot.")
        except Exception as e:
            logger.error(f"Failed to send message to {dialog.id}: {e}")
    await event.reply("**✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ.**")

@app.on(events.NewMessage(pattern=r"^/ban (\d+)$", func=lambda e: e.is_private))
async def ban_user(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")
    
    user_id = int(event.pattern_match.group(1))
    banned_users_collection.insert_one({"user_id": user_id})
    await event.reply(f"**✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.**")

@app.on(events.NewMessage(pattern=r"^/unban (\d+)$", func=lambda e: e.is_private))
async def unban_user(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("**🚫 ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.**")
    
    user_id = int(event.pattern_match.group(1))
    banned_users_collection.delete_one({"user_id": user_id})
    await event.reply(f"**✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ᴜɴʙᴀɴɴᴇᴅ.**")

@app.on(events.NewMessage(func=lambda e: e.is_private))
async def check_ban(event):
    if banned_users_collection.find_one({"user_id": event.sender_id}):
        return await event.reply("**🚫 ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.**")

@app.on(events.NewMessage)
async def check_fsub_handler(event):
    if event.is_private:
        user_id = event.sender_id
        missing_subs = await check_owner_fsub(user_id)

        if missing_subs is True:
            return

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
            return True
    return False

async def startup_notification():
    try:
        await app.send_message(
            LOGGER_ID,
            "**✅ ʙᴏᴛ ʜᴀs sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
            f"**ʙᴏᴛ ɪɴғᴏ:**\n"
            f"**➲ ᴏᴡɴᴇʀ ɪᴅ:** `{OWNER_ID}`\n"
            f"**➲ ʟᴏɢɢᴇʀ ɪᴅ:** `{LOGGER_ID}`"
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
