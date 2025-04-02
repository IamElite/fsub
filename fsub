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

# Parse force sub channels/groups (max 4 allowed)
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
        if event.text and event.text.startswith('/'):
            missing_owner_subs = await check_owner_fsub(user_id)
            if missing_owner_subs is not True:
                # Create join buttons in 2x2 grid; text is only "Join"
                btns = []
                temp = []
                for channel in missing_owner_subs:
                    # Use inline callback button with data "fsub_join_<channel_id>"
                    temp.append(Button.inline("Join", data=f"fsub_join_{channel.id}"))
                    if len(temp) == 2:
                        btns.append(temp)
                        temp = []
                if temp:
                    btns.append(temp)
                await event.reply(
                    "**⚠️ Access Restricted ⚠️**\n\n"
                    "**You must join our channel(s) to use the bot!**\n"
                    "**Click the Join buttons below and then try again.**",
                    buttons=btns
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

# When bot is added to a group, send an intro message with required permissions
@app.on(events.ChatAction)
async def handle_added_to_chat(event):
    # Debug: print available attributes if needed
    # print(dir(event))
    if hasattr(event, 'user_left') and event.user_left:
        me = await app.get_me()
        if event.user_id == me.id:
            await remove_group(event.chat_id)
    if event.user_added:
        me = await app.get_me()
        if event.user_id == me.id:
            chat = await event.get_chat()
            await add_group(chat.id)
            # Send introduction message in group
            intro_text = (
                f"**Hello! I'm {me.first_name}.**\n\n"
                "Thank you for adding me to this group.\n\n"
                "**I require the following permissions:**\n"
                "• Send Messages\n"
                "• Delete Messages\n"
                "• Pin Messages\n"
                "• Read Message History\n\n"
                "Please ensure I have admin rights for proper functionality.\n"
                "Feel free to contact support for any help!"
            )
            await app.send_message(chat.id, intro_text)

# /start command with user-friendly interface (1,2,1 button layout)
@app.on(events.NewMessage(pattern=r"^/start(?:@\w+)?$"))
@check_fsub
async def start(event):
    if not await is_command_for_me(event):
        return
    user_id = event.sender_id
    await add_user(user_id)
    user = await event.get_sender()
    # Updated welcome message with 4 buttons arranged as 1,2,1 layout
    welcome_text = (
        "**Welcome to the Force Subscription Bot!**\n\n"
        "Use the buttons below to navigate through the bot options."
    )
    buttons = [
        [Button.inline("Add Team", b"add_team")],
        [Button.inline("Update", b"update"), Button.inline("Support", b"support")],
        [Button.inline("Owner", b"owner")]
    ]
    await event.reply(welcome_text, buttons=buttons)

# Updated /help command with user-friendly instructions
@app.on(events.NewMessage(pattern=r"^/help(?:@\w+)?$"))
@check_fsub
async def help(event):
    if not await is_command_for_me(event):
        return
    help_text = (
        "**Help Menu**\n\n"
        "• **/start** - Display the welcome message and main menu.\n"
        "• **/set <channel username/id/link>** - Set force subscription channels (up to 4).\n"
        "• **/fsub** - Manage force subscription settings (toggle on/off).\n"
        "• **/reset** - Reset force subscription settings and remove all channels.\n"
        "• **/stats** - View bot statistics (owner only).\n"
        "• **/broadcast <message>** - Broadcast a message to all users (owner only).\n"
        "• **/ban <user id>** / **/unban <user id>** - Ban or unban a user (owner only).\n\n"
        "For any queries, feel free to contact support."
    )
    await event.reply(help_text)

# Utility function for checking admin/owner status
async def is_admin_or_owner(chat_id, user_id):
    try:
        member = await app.get_permissions(chat_id, user_id)
        return member.is_admin or member.is_creator or user_id == OWNER_ID
    except ChatAdminRequiredError:
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

# /set command to set force subscription channels
@app.on(events.NewMessage(pattern=r"^/set(?:@\w+)?( .+)?$", func=lambda e: e.is_group))
@check_fsub
async def set_forcesub(event):
    if not await is_command_for_me(event):
        return
    chat_id = event.chat_id
    user_id = event.sender_id

    async def is_admin_or_owner(chat_id, user_id):
        try:
            member = await app.get_permissions(chat_id, user_id)
            return member.is_admin or member.is_creator or user_id == OWNER_ID
        except ChatAdminRequiredError:
            return False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    if not await is_admin_or_owner(chat_id, user_id):
        return await event.reply("**Only group owners, admins or the bot owner can use this command.**")

    await add_group(chat_id)
    command = event.pattern_match.group(1)
    if not command:
        return await event.reply("**Usage: /set <channel username/id/link> (up to 4)**")

    channels = command.strip().split()
    if len(channels) > 4:
        return await event.reply("**You can add up to 4 force subscriptions only.**")

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
            return await event.reply(f"**Failed to fetch data for {channel_input}.**")

    await forcesub_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"channels": fsub_data, "enabled": True}},
        upsert=True
    )

    set_by_user = f"@{event.sender.username}" if event.sender.username else event.sender.first_name
    channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in fsub_data])

    if len(fsub_data) == 1:
        channel_info = fsub_data[0]
        await event.reply(
            f"**Force subscription set to [{channel_info['title']}]({channel_info['username']}) for this group.**\n\n"
            f"**Channel ID:** `{channel_info['id']}`\n"
            f"**Channel Link:** [Get Link]({channel_info['link']})\n"
            f"**Set by:** {set_by_user}"
        )
    else:
        await event.reply(f"**Force subscription set for this group:**\n\n{channel_list}")

# /fsub command to manage force subscription settings
@app.on(events.NewMessage(pattern=r"^/fsub(?:@\w+)?$", func=lambda e: e.is_group))
@check_fsub
async def manage_forcesub(event):
    if not await is_command_for_me(event):
        return
    try:
        chat_id = event.chat_id
        user_id = event.sender_id

        async def is_admin_or_owner(chat_id, user_id):
            try:
                member = await app.get_permissions(chat_id, user_id)
                return member.is_admin or member.is_creator or user_id == OWNER_ID
            except ChatAdminRequiredError:
                return False
            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                return False

        if not await is_admin_or_owner(chat_id, user_id):
            return await event.reply("**Only group owners, admins or the bot owner can use this command.**")

        forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
        if not forcesub_data or not forcesub_data.get("channels") or not forcesub_data.get("enabled", True):
            return await event.reply("**No force subscription is set for this group.**")

        channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
        is_enabled = forcesub_data.get("enabled", True)
        
        # Toggle button callback data
        callback_data = f"fsub_toggle_{chat_id}_{1 if not is_enabled else 0}"
        
        buttons = [[Button.inline("🔴 Turn Off" if is_enabled else "🟢 Turn On", callback_data)]]
        await event.reply(
            f"**Force Subscription for this group:**\n\n"
            f"{channel_list}\n\n"
            f"**Current Status:** {'🟢 On' if is_enabled else '🔴 Off'}",
            buttons=buttons
        )
    except Exception as e:
        logger.error(f"Error in manage_forcesub: {str(e)}")
        await event.reply("**An error occurred while processing the command.**")

# Callback query for toggling force subscription status (unchanged)
@app.on(events.CallbackQuery(pattern=r"fsub_toggle_(\-?\d+)_([01])"))
async def toggle_forcesub(event):
    try:
        chat_id = int(event.pattern_match.group(1))
        new_state = bool(int(event.pattern_match.group(2)))
        user_id = event.sender_id
        
        logger.info(f"Toggle callback received: chat_id={chat_id}, new_state={new_state}, user_id={user_id}")

        async def is_admin_or_owner(chat_id, user_id):
            try:
                member = await app.get_permissions(chat_id, user_id)
                return member.is_admin or member.is_creator or user_id == OWNER_ID
            except ChatAdminRequiredError:
                return False
            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                return False

        if not await is_admin_or_owner(chat_id, user_id):
            return await event.answer("**Only group owners, admins or the bot owner can use this.**", alert=True)

        forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
        if not forcesub_data:
            return await event.answer("**No force subscription is set.**", alert=True)

        await forcesub_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"enabled": new_state}}
        )
        logger.info(f"Database updated for chat {chat_id}, new state: {new_state}")

        channel_list = "\n".join([f"**{c['title']}** ({c['username']})" for c in forcesub_data["channels"]])
        next_state = not new_state
        new_buttons = [[Button.inline("🔴 Turn Off" if new_state else "🟢 Turn On", f"fsub_toggle_{chat_id}_{1 if next_state else 0}")]]
        await event.edit(
            f"**Force Subscription for this group:**\n\n"
            f"{channel_list}\n\n"
            f"**Current Status:** {'🟢 On' if new_state else '🔴 Off'}",
            buttons=new_buttons
        )
        await event.answer(
            f"**Force subscription {'enabled' if new_state else 'disabled'} successfully!**",
            alert=True
        )
        logger.info(f"Toggle complete for chat {chat_id}, new state: {new_state}")
        
    except Exception as e:
        logger.error(f"Error in toggle_forcesub: {str(e)}")
        await event.answer("**An error occurred while processing your request.**", alert=True)

# /reset command to remove force subscription from a group
@app.on(events.NewMessage(pattern=r"^/reset(?:@\w+)?$", func=lambda e: e.is_group))
@check_fsub
async def reset_forcesub(event):
    if not await is_command_for_me(event):
        return
    chat_id = event.chat_id
    user_id = event.sender_id

    async def is_admin_or_owner(chat_id, user_id):
        try:
            member = await app.get_permissions(chat_id, user_id)
            return member.is_admin or member.is_creator or user_id == OWNER_ID
        except ChatAdminRequiredError:
            return False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    if not await is_admin_or_owner(chat_id, user_id):
        return await event.reply("**Only group owners, admins or the bot owner can use this command.**")

    await remove_group(chat_id)
    await forcesub_collection.delete_one({"chat_id": chat_id})
    await event.reply("**Force subscription has been reset for this group.**")

# /stats command to show bot statistics (owner only)
@app.on(events.NewMessage(pattern=r"^/stats(?:@\w+)?$"))
@check_fsub
async def stats(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await event.reply("**Only the bot owner can use this command.**")

    total_users = len(await get_all_users())
    total_groups = len(await get_all_groups())
    banned_users = await banned_users_collection.count_documents({})
    await event.reply(
        f"**Bot Statistics:**\n\n"
        f"• Total Users: {total_users}\n"
        f"• Total Groups: {total_groups}\n"
        f"• Banned Users: {banned_users}"
    )

# /ban command (owner only)
@app.on(events.NewMessage(pattern=r"^/ban(?:@\w+)? (\d+)$"))
@check_fsub
async def ban_user(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await event.reply("**Only the bot owner can use this command.**")
    user_id = int(event.pattern_match.group(1))
    await banned_users_collection.insert_one({"user_id": user_id})
    await event.reply(f"**User {user_id} has been banned.**")

# /unban command (owner only)
@app.on(events.NewMessage(pattern=r"^/unban(?:@\w+)? (\d+)$"))
@check_fsub
async def unban_user(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await event.reply("**Only the bot owner can use this command.**")
    user_id = int(event.pattern_match.group(1))
    await banned_users_collection.delete_one({"user_id": user_id})
    await event.reply(f"**User {user_id} has been unbanned.**")

# /broadcast command to send a message to all users and groups (owner only)
@app.on(events.NewMessage(pattern=r"^/(broadcast|gcast)(?:@\w+)?( .*)?$"))
@check_fsub
async def broadcast(event):
    if not await is_command_for_me(event):
        return
    if event.sender_id != OWNER_ID:
        return await event.reply("**Only the bot owner can use this command.**")
    reply = event.reply_to_message if hasattr(event, 'reply_to_message') else None
    text = event.pattern_match.group(2)
    if not reply and not text:
        return await event.reply("**Reply to a message or provide text to broadcast.**")
    progress_msg = await event.reply("**Broadcasting message, please wait...**")
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
        f"**Broadcast Completed.**\n\n"
        f"• Groups Sent: {sent_groups}\n"
        f"• Users Sent: {sent_users}\n"
        f"• Pinned: {pinned}\n"
        f"• Failed: {failed}"
    )

# Handler for private messages to check if user is banned
@app.on(events.NewMessage(func=lambda e: e.is_private))
async def check_ban(event):
    if await banned_users_collection.find_one({"user_id": event.sender_id}):
        return await event.reply("**You are banned from using this bot.**")

# For every new message, add user or group to database
@app.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_private:
        await add_user(event.sender_id)
    elif event.is_group:
        await add_group(event.chat_id)

# Check force subscription in groups and send join buttons in 2x2 layout
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
                # Create 2x2 grid join buttons with text "Join"
                btns = []
                temp = []
                for c in forcesub_data['channels']:
                    temp.append(Button.inline("Join", data=f"fsub_join_{c['id']}"))
                    if len(temp) == 2:
                        btns.append(temp)
                        temp = []
                if temp:
                    btns.append(temp)
                channel_lines = ["๏ [{}]({})".format(c["title"], c["link"]) for c in forcesub_data["channels"] if c.get("title") and c.get("link")]
                await event.reply(
                    f"**Hello {event.sender.first_name},**\n\n"
                    f"You need to join the force subscription channel(s) to send messages in this group:\n\n"
                    f"{chr(10).join(channel_lines)}",
                    buttons=btns
                )
            except Exception as e:
                logger.error(f"An error occurred while sending the force sub message: {e}")
            return

# Callback handler for force subscription join buttons
@app.on(events.CallbackQuery(pattern=r"fsub_join_(\d+)"))
async def fsub_join_handler(event):
    try:
        channel_id = int(event.pattern_match.group(1))
        # Get group id from message context
        chat_id = event.message.chat_id
        forcesub_data = await forcesub_collection.find_one({"chat_id": chat_id})
        target_channel = None
        if forcesub_data:
            for c in forcesub_data.get("channels", []):
                if int(c["id"]) == channel_id:
                    target_channel = c
                    break
        if not target_channel:
            return await event.answer("Channel not found.", alert=True)
        # Answer callback with URL to open join link
        await event.answer(url=target_channel["link"])
        # Send DM to user thanking for joining
        try:
            await app.send_message(event.sender_id, "Thanks for joining!")
        except Exception as e:
            logger.error(f"Error sending DM to user {event.sender_id}: {e}")
    except Exception as e:
        logger.error(f"Error in fsub_join_handler: {e}")
        await event.answer("An error occurred.", alert=True)

async def startup_notification():
    try:
        total_users = len(await get_all_users())
        total_groups = len(await get_all_groups())
        await app.send_message(
            LOGGER_ID,
            "**Bot has started successfully!**\n\n"
            f"• Owner ID: `{OWNER_ID}`\n"
            f"• Logger ID: `{LOGGER_ID}`\n"
            f"• Total Users: `{total_users}`\n"
            f"• Total Groups: `{total_groups}`"
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
