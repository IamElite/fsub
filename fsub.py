import os, logging, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors.rpcerrorlist import UserNotParticipantError
from telethon.errors import ChatAdminRequiredError

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

# Global set to track users already greeted for joining fsub channels
greeted_users = set()

# Helper function to convert text to small caps
def to_small_caps(text):
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ',
        'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ',
        'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ',
        'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ',
        'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ',
        'z': 'ᴢ'
    }
    result = ""
    for char in text:
        if char.lower() in mapping:
            result += mapping[char.lower()]
        else:
            result += char
    return result

# Helper function to send reply messages in small caps
async def reply_small(event, text, **kwargs):
    return await event.reply(to_small_caps(text), **kwargs)

# Telegram client
app = TelegramClient('bot', api_id=API_ID, api_hash=API_HASH)

# MongoDB connection
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client.fsub
users_collection = db["users"]
groups_collection = db["groups"]
forcesub_collection = db["forcesubs"]
banned_users_collection = db["banned_users"]

# Database functions
async def add_user(user_id):
    if not await users_collection.find_one({"user_id": user_id}):
        await users_collection.insert_one({"user_id": user_id})

async def add_group(group_id):
    if not await groups_collection.find_one({"group_id": group_id}):
        await groups_collection.insert_one({"group_id": group_id})

async def remove_group(group_id):
    if await groups_collection.find_one({"group_id": group_id}):
        await groups_collection.delete_one({"group_id": group_id})

async def get_all_users():
    users = []
    cursor = users_collection.find()
    async for user in cursor:
        try:
            users.append(user["user_id"])
        except Exception:
            pass
    return users

async def get_all_groups():
    groups = []
    cursor = groups_collection.find()
    async for chat in cursor:
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
        if event.text and event.text.startswith('/'):
            missing_owner_subs = await check_owner_fsub(user_id)
            if missing_owner_subs is not True:
                # Arrange join buttons in 2x2 grid
                buttons_list = []
                for channel in missing_owner_subs:
                    if hasattr(channel, 'username') and channel.username:
                        buttons_list.append(Button.url("๏ ᴊᴏɪⁿ ๏", f"https://t.me/{channel.username}"))
                    else:
                        try:
                            invite = await app(ExportChatInviteRequest(channel))
                            buttons_list.append(Button.url("๏ ᴊᴏɪⁿ ๏", invite.link))
                        except Exception as e:
                            logger.error(f"Error creating invite for {channel.id}: {e}")
                            continue
                # Create 2x2 grid
                rows = [buttons_list[i:i+2] for i in range(0, len(buttons_list), 2)]
                await event.reply(
                    to_small_caps(
                        "**⚠️ ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ ⚠️**\n\n"
                        "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪⁿ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ!**\n"
                        "**ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪⁿ**\n"
                        "**ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ!**"
                    ),
                    buttons=rows
                )
                return
        return await func(event)
    return wrapper

# Utility function to check if command is meant for this bot
async def is_command_for_me(event):
    try:
        me = await app.get_me()
        bot_username = me.username
        parts = event.text.split('@', 1)
        if len(parts) > 1:
            target_bot = parts[1].strip().lower()
            return target_bot == bot_username.lower()
        return True
    except Exception as e:
        logger.error(f"Error checking command target: {e}")
        return True

# Global admin check function
async def is_admin_or_owner(chat_id, user_id):
    try:
        member = await app.get_permissions(chat_id, user_id)
        return member.is_admin or member.is_creator or user_id == OWNER_ID
    except ChatAdminRequiredError:
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

# When bot is added to a chat (group)
@app.on(events.ChatAction)
async def handle_added_to_chat(event):
    me = await app.get_me()
    if hasattr(event, 'user_left') and event.user_left:
        if event.user_id == me.id:
            await remove_group(event.chat_id)
    if event.user_added:
        if event.user_id == me.id:
            chat = await event.get_chat()
            await add_group(chat.id)
            chat_link = f"https://t.me/{chat.username}" if chat.username else "Private Group"
            # Log message to LOGGER_ID
            await app.send_message(
                LOGGER_ID,
                to_small_caps(
                    f"**🔔 ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɴᴇᴡ ᴄʜᴀᴛ**\n\n"
                    f"**ᴄʜᴀᴛ ɴᴀᴍᴇ:** {chat.title}\n"
                    f"**ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`\n"
                    f"**ʟɪɴᴋ:** {chat_link}"
                )
            )
            # Send introduction message to group about bot and required permissions
            intro_text = (
                "ʜᴇʟʟᴏ, ɪ ᴀᴍ ᴛʜᴇ ʙᴏᴛ.\n"
                "ᴛʜᴀɴᴋs ᴛᴏ ʏᴏᴜ ғᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ.\n"
                "ᴘʟᴇᴀsᴇ ᴇɴɢᴀɢᴇ ᴍᴇ ᴡɪᴛʜ ᴍʏ ғᴇᴀᴛᴜʀᴇs.\n"
                "ɪ ʀᴇǫᴜɪʀᴇ ᴘᴇʀᴍɪssɪᴏɴs: ᴍᴇssᴀɢᴇ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ, ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇs, ᴘɪɴ ᴍᴇssᴀɢᴇs."
            )
            await app.send_message(chat.id, to_small_caps(intro_text))

@app.on(events.NewMessage(pattern=r"^/start(?:@\w+)?$"))
@check_fsub
async def start(event):
    if not await is_command_for_me(event):
        return
    user_id = event.sender_id
    await add_user(user_id)
    user = await event.get_sender()
    # Log new user start
    await app.send_message(
        LOGGER_ID,
        to_small_caps(
            f"**🆕 ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ**\n\n"
            f"**ɴᴀᴍᴇ:** {user.first_name}\n"
            f"**ᴜsᴇʀɴᴀᴍᴇ:** @{user.username}\n"
            f"**ᴜsᴇʀ ɪᴅ:** `{user.id}`"
        )
    )
    # Updated start message with 4 buttons in 1,2,1 layout
    start_text = (
        "ʜᴇʟʟᴏ! ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ.\n"
        "ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ."
    )
    start_buttons = [
        [Button.inline("ᴀᴅᴅ ᴛᴇᴀᴍ", b"add_team")],
        [Button.inline("ᴜᴘᴅᴀᴛᴇ", b"update"), Button.inline("ꜱᴜᴘᴘᴏʀᴛ", b"support")],
        [Button.url("ᴏᴡɴᴇʀ", "https://t.me/owner")]
    ]
    await event.reply(to_small_caps(start_text), buttons=start_buttons)

@app.on(events.NewMessage(pattern=r"^/help(?:@\w+)?$"))
@check_fsub
async def help(event):
    if not await is_command_for_me(event):
        return
    help_text = (
        "📖 ʜᴇʟᴘ ᴍᴇɴᴜ:\n\n"
        "/set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ/ɪᴅ/ʟɪɴᴋ> (ᴜᴘ ᴛᴏ 4) - sᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ.\n"
        "/fsub - ᴍᴀɴᴀɢᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ (ᴏɴ/ᴏғғ).\n"
        "/reset - ʀᴇsᴇᴛ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴀɴᴅ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟs.\n"
        "/stats - ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs.\n"
        "/broadcast <ᴍᴇssᴀɢᴇ> - ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴜsᴇʀs.\n"
        "/ban <ᴜsᴇʀ ɪᴅ> /unban <ᴜsᴇʀ ɪᴅ> - ʙᴀɴ/ᴜɴʙᴀɴ ᴜsᴇʀs."
    )
    await reply_small(event, help_text)

@app.on(events.NewMessage(pattern=r"^/set(?:@\w+)?( .+)?$", func=lambda e: e.is_group))
@check_fsub
async def set_forcesub(event):
    if not await is_command_for_me(event):
        return
    chat_id = event.chat_id
    user_id = event.sender_id

    if not await is_admin_or_owner(chat_id, user_id):
        return await reply_small(event, "ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs/ᴀᴅᴍɪɴs ᴏʀ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")

    await add_group(chat_id)
    command = event.pattern_match.group(1)
    if not command:
        return await reply_small(event, "ᴜsᴀɢᴇ: /set <ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ/ɪᴅ/ʟɪɴᴋ> (ᴜᴘ ᴛᴏ 4)")

    channels = command.strip().split()
    if len(channels) > 4:
        return await reply_small(event, "🚫 ʏᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴀᴅᴅ ᴜᴘ ᴛᴏ 4 ғᴏʀ ᴄʜᴀɴɴᴇʟs.")

    fsub_data = []
    for channel_input in channels:
        try:
            if channel_input.startswith("https://t.me/"):
                channel_input = channel_input.replace("https://t.me/", "")
            try:
                channel_id = int(channel_input)
                channel_entity = await app.get_entity(channel_id)
            except ValueError:
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
            fsub_data.append({
                "id": channel_id,
                "username": channel_username,
                "title": channel_title,
                "link": channel_link
            })
        except Exception as e:
            logger.error(f"Error fetching channel info for {channel_input}: {e}")
            return await reply_small(event, f"🚫 ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴅᴀᴛᴀ ғᴏʀ {channel_input}.")

    await forcesub_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"channels": fsub_data, "enabled": True}},
        upsert=True
    )

    set_by_user = f"@{event.sender.username}" if event.sender.username else event.sender.first_name
    channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in fsub_data])

    if len(fsub_data) == 1:
        channel_info = fsub_data[0]
        await reply_small(
            event,
            f"🎉 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ sᴇᴛ ᴛᴏ [{channel_info['title']}]({channel_info['username']}) ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.\n\n"
            f"🆔 ᴄʜᴀɴɴᴇʟ ɪᴅ: `{channel_info['id']}`\n"
            f"🖇️ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ: [ɢᴇᴛ ʟɪɴᴋ]({channel_info['link']})\n"
            f"👤 sᴇᴛ ʙʏ: {set_by_user}"
        )
    else:
        await reply_small(event, f"🎉 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ sᴇᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ:\n\n{channel_list}")

@app.on(events.NewMessage(pattern=r"^/fsub(?:@\w+)?$", func=lambda e: e.is_group))
@check_fsub
async def manage_forcesub(event):
    if not await is_command_for_me(event):
        return
    chat_id = event.chat_id
    user_id = event.sender_id

    if not await is_admin_or_owner(chat_id, user_id):
        return await reply_small(event, "ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs/ᴀᴅᴍɪɴs ᴏʀ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")

    forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
    if not forcesub_data or not forcesub_data.get("channels") or not forcesub_data.get("enabled", True):
        return await reply_small(event, "🚫 ɴᴏ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ɪs sᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.")

    channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
    is_enabled = forcesub_data.get("enabled", True)
    
    callback_data = f"fsub_toggle_{chat_id}_{1 if not is_enabled else 0}"
    await reply_small(
        event,
        f"📊 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:\n\n"
        f"{channel_list}\n\n"
        f"ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs: {'🟢 ᴏɴ' if is_enabled else '🔴 ᴏғғ'}",
        buttons=[[Button.inline("🔴 ᴛᴜʀɴ ᴏғғ" if is_enabled else "🟢 ᴛᴜʀɴ ᴏɴ", callback_data)]]
    )

@app.on(events.CallbackQuery(pattern=r"fsub_toggle_(\-?\d+)_([01])"))
async def toggle_forcesub(event):
    try:
        chat_id = int(event.pattern_match.group(1))
        new_state = bool(int(event.pattern_match.group(2)))
        user_id = event.sender_id
        
        logger.info(f"Toggle callback received: chat_id={chat_id}, new_state={new_state}, user_id={user_id}")

        if not await is_admin_or_owner(chat_id, user_id):
            return await event.answer(to_small_caps("ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs/ᴀᴅᴍɪɴs ᴏʀ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs."), alert=True)

        forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
        if not forcesub_data:
            return await event.answer(to_small_caps("ɴᴏ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ɪs sᴇᴛ."), alert=True)

        await forcesub_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"enabled": new_state}}
        )
        logger.info(f"Database updated for chat {chat_id}, new state: {new_state}")

        channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
        next_state = not new_state
        new_buttons = [[Button.inline("🔴 ᴛᴜʀɴ ᴏғғ" if new_state else "🟢 ᴛᴜʀɴ ᴏɴ",
                            f"fsub_toggle_{chat_id}_{1 if next_state else 0}")]]
    
        await event.edit(
            to_small_caps(
                f"📊 ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ:\n\n"
                f"{channel_list}\n\n"
                f"ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs: {'🟢 ᴏɴ' if new_state else '🔴 ᴏғғ'}"
            ),
            buttons=new_buttons
        )
        
        await event.answer(to_small_caps(f"✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ {'enabled' if new_state else 'disabled'} sᴜᴄᴄᴇssғᴜʟʟʏ!"), alert=True)
        logger.info(f"Toggle complete for chat {chat_id}, new state: {new_state}")
        
    except Exception as e:
        logger.error(f"Error in toggle_forcesub: {str(e)}")
        await event.answer(to_small_caps("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀᴇᴅ."), alert=True)

@app.on(events.NewMessage(pattern=r"^/reset(?:@\w+)?$", func=lambda e: e.is_group))
@check_fsub
async def reset_forcesub(event):
    if not await is_command_for_me(event):
        return
    chat_id = event.chat_id
    user_id = event.sender_id

    if not await is_admin_or_owner(chat_id, user_id):
        return await reply_small(event, "ᴏɴʟʏ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀs/ᴀᴅᴍɪɴs ᴏʀ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
    await remove_group(chat_id)
    await forcesub_collection.delete_one({"chat_id": chat_id})
    await reply_small(event, "✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ʀᴇsᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.")

@app.on(events.NewMessage(pattern=r"^/stats(?:@\w+)?$"))
@check_fsub
async def stats(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await reply_small(event, "🚫 ᴏɴʟʏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
    total_users = len(await get_all_users())
    total_groups = len(await get_all_groups())
    banned_users = await banned_users_collection.count_documents({})
    stats_text = (
        "📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs:\n\n"
        f"➲ ᴛᴏᴛᴀʟ ᴜsᴇʀs: {total_users}\n"
        f"➲ ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs: {total_groups}\n"
        f"➲ ʙᴀɴɴᴇᴅ ᴜsᴇʀs: {banned_users}"
    )
    await reply_small(event, stats_text)

@app.on(events.NewMessage(pattern=r"^/ban(?:@\w+)? (\d+)$"))
@check_fsub
async def ban_user(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await reply_small(event, "🚫 ᴏɴʟʏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
    user_id = int(event.pattern_match.group(1))
    await banned_users_collection.insert_one({"user_id": user_id})
    await reply_small(event, f"✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.")

@app.on(events.NewMessage(pattern=r"^/unban(?:@\w+)? (\d+)$"))
@check_fsub
async def unban_user(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await reply_small(event, "🚫 ᴏɴʟʏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
    user_id = int(event.pattern_match.group(1))
    await banned_users_collection.delete_one({"user_id": user_id})
    await reply_small(event, f"✅ ᴜsᴇʀ {user_id} ʜᴀs ʙᴇᴇɴ ᴜɴᴀʙɴᴇᴅ.")

@app.on(events.NewMessage(pattern=r"^/(broadcast|gcast)(?:@\w+)?( .*)?$"))
@check_fsub
async def broadcast(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await reply_small(event, "🚫 ᴏɴʟʏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
    reply = event.reply_to_message if hasattr(event, 'reply_to_message') else None
    text = event.pattern_match.group(2)
    if not reply and not text:
        return await reply_small(event, "❖ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴛᴇxᴛ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ.")
    progress_msg = await event.reply(to_small_caps("❖ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴍᴇssᴀɢᴇ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ..."))
    sent_groups, sent_users, failed, pinned = 0, 0, 0, 0
    users = await get_all_users()
    groups = await get_all_groups()
    recipients = groups + users
    for chat_id in recipients:
        try:
            if reply:
                msg = await event.reply_to_message.forward(chat_id)
            else:
                msg = await app.send_message(chat_id, text.strip())
            if isinstance(chat_id, int) and chat_id < 0:
                try:
                    await app.pin_message(chat_id, msg.id, notify=False)
                    pinned += 1
                except Exception:
                    pass
                sent_groups += 1
            else:
                sent_users += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to send broadcast to {chat_id}: {e}")
            failed += 1
    await progress_msg.edit(
        to_small_caps(
            f"✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴍʀᴇᴛᴇᴅ.\n\n"
            f"👥 ɢʀᴏᴜᴘs sᴇɴᴛ: {sent_groups}\n"
            f"🧑‍💻 ᴜsᴇʀs sᴇɴᴛ: {sent_users}\n"
            f"📌 ᴘɪɴɴᴇᴅ: {pinned}\n"
            f"❌ ғᴀɪʟᴇᴅ: {failed}"
        )
    )

@app.on(events.NewMessage(func=lambda e: e.is_private))
async def check_ban(event):
    if await banned_users_collection.find_one({"user_id": event.sender_id}):
        return await reply_small(event, "🚫 ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.")

@app.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_private:
        await add_user(event.sender_id)
    elif event.is_group:
        await add_group(event.chat_id)

# Force subscription check handler with DM greeting upon successful join
@app.on(events.NewMessage)
async def check_fsub_handler(event):
    if hasattr(event, '_fsub_checked'):
        return

    user_id = event.sender_id
    if event.is_group:
        chat_id = event.chat_id
        forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
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
            except Exception as e:
                logger.error(f"Could not delete message: {e}")
            try:
                buttons_list = [Button.url("๏ ᴊᴏɪⁿ ๏", c['link']) for c in forcesub_data['channels'] if c.get("link") and c.get("title")]
                rows = [buttons_list[i:i+2] for i in range(0, len(buttons_list), 2)]
                channel_lines = ["๏ [{}]({})".format(c["title"], c["link"]) for c in forcesub_data["channels"] if c.get("title") and c.get("link")]
                if rows:
                    await event.reply(
                        to_small_caps(
                            f"👋 ʜᴇʟʟᴏ {event.sender.first_name},\n\n"
                            f"ʏᴏᴜ ɴᴇᴇᴅ ᴊᴏɪɴ ᴛʜᴇ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇs ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ:\n\n"
                            + "\n".join(channel_lines)
                        ),
                        buttons=rows
                    )
            except Exception as e:
                logger.error(f"An error occurred while sending the force sub message: {e}")
            return
        else:
            # If user is a member and not greeted before, send DM thanking for join
            if user_id not in greeted_users:
                try:
                    await app.send_message(user_id, to_small_caps("ʟɪᴋᴇ ᴛx ғᴏʀ ᴊᴏɪɴ"))
                    greeted_users.add(user_id)
                except Exception as e:
                    logger.error(f"Error sending DM for join: {e}")
    setattr(event, '_fsub_checked', True)

async def startup_notification():
    try:
        total_users = len(await get_all_users())
        total_groups = len(await get_all_groups())
        await app.send_message(
            LOGGER_ID,
            to_small_caps(
                f"✅ ʙᴏᴛ ʜᴀs sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʀʀʏ!\n\n"
                f"ʙᴏᴛ ɪɴғᴏ:\n"
                f"➲ ᴏᴡɴᴇʀ ɪᴅ: `{OWNER_ID}`\n"
                f"➲ ʟᴏɢɢᴇʀ ɪᴅ: `{LOGGER_ID}`\n"
                f"➲ ᴛᴏᴛᴀʟ ᴜsᴇʀs: `{total_users}`\n"
                f"➲ ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs: `{total_groups}`"
            )
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
