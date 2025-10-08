import os
import certifi
import json
import random
import time
from typing import Final
from datetime import datetime, timedelta
from telegram.ext import JobQueue
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from pymongo import MongoClient, ReturnDocument

#officialgraphiq25(GITIHUB PASS, MONGODB)
#cluster pass (Wd4qWrB30QGprjMa)

#mongodb+srv://tokumasamuel03_db_user:5QNgIFXxlLzyBGJv@graphiz-quizet.os3eb7u.mongodb.net/?retryWrites=true&w=majority&appName=graphiz-quizet



# ---------------------------
# MongoDB Setup
# ---------------------------
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["quiz_bot"]
users_col = db["users"]
winners_col = db["daily_winners"]   # NEW: store historical winners


# ---------------------------
# Environment
# ---------------------------
TOKEN: Final = os.getenv("BOT_TOKEN")
BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
ANNOUNCE_CHAT_ID = os.getenv("ANNOUNCE_CHAT_ID")  # set to integer string, e.g. -1001234567890


# ---------------------------
# Category files (place these JSON files next to this script)
# ---------------------------
CATEGORIES = {
    "General": "questions.json",
    "Math": "questions_math.json",
    "Chemistry": "questions_chemistry.json",
    "Biology": "questions_biology.json",
    "Geography": "questions_geography.json",
}

# Optional: preload a file so missing files don't break startup
try:
    with open(CATEGORIES["General"], "r") as f:
        _ = json.load(f)
except Exception:
    pass


# ---------------------------
# Conversation states
# ---------------------------
# REGISTER_USERNAME, REGISTER_EMAIL, REGISTER_CONFIRM = range(3)
USERNAME, EMAIL, PHONE, BANK, ACCOUNT = range(5)

# ---------------------------
# In-memory active quizzes
# ---------------------------
# NOTE: this is a process-memory dict. It works for jobs & handlers.
# If you need persistence across restarts, we can store this in MongoDB.
ACTIVE_QUIZZES: dict[int, dict] = {}


# ---------------------------
# Helpers: DB Functions
# ---------------------------
def get_user(tg_id):
    user = users_col.find_one({"telegram_id": tg_id})
    if user and "balance" not in user:
        users_col.update_one({"telegram_id": tg_id}, {"$set": {"balance": 0}})
        user["balance"] = 0
    return user

def create_or_update_user(tg_id, username=None, email=None):
    update = {}
    if username: update["username"] = username
    if email: update["email"] = email
    users_col.update_one(
        {"telegram_id": tg_id},
        {"$setOnInsert": {"score": 0, "balance": 0, "sessions": 0}, "$set": update},
        upsert=True
    )
    return get_user(tg_id)

def update_score(tg_id, points):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"score": points}}, upsert=True)
    return get_user(tg_id)

def update_balance(tg_id, amount):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"balance": amount}}, upsert=True)
    return get_user(tg_id)

def increment_sessions(tg_id):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"sessions": 1}}, upsert=True)
    return get_user(tg_id)


def safe_remove_job(job):
    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass


# ---------------------------
# Utility: check if user is currently in quiz
# ---------------------------
def user_in_quiz(user_id: int) -> bool:
    return user_id in ACTIVE_QUIZZES and ACTIVE_QUIZZES[user_id].get("active", False)


# ---------------------------
# Speed Bonus Scoring
# ---------------------------
def apply_speed_bonus(all_answers):
    """
    Finalize scores by summing the stored total_score values.
    """
    final_scores = defaultdict(float)
    for ans in all_answers:
        final_scores[ans["user_id"]] += ans.get("total_score", 0)
    return dict(final_scores)








#RESTRICT BOT--------------

ALLOWED_START_HOUR = 8   # 8 AM
ALLOWED_END_HOUR = 21    # 9 PM


async def restrict_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if not (ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR):
        await update.message.reply_text(
            "⛔ The bot is only active from 8:00 AM to 9:00 PM.\n"
            "Please come back during active hours."
        )
        return True  # Block further handlers
    return False

async def reset_daily(context: ContextTypes.DEFAULT_TYPE):
    # Reset only scores and sessions (leave balance untouched)
    users_col.update_many({}, {"$set": {"score": 0, "sessions": 0}})
    
    # Clear in-memory active quizzes
    ACTIVE_QUIZZES.clear()

    print("✅ Daily reset completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))



def schedule_daily_reset(job_queue: JobQueue):
    now = datetime.now()
    next_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    delay = (next_midnight - now).total_seconds()

    job_queue.run_repeating(
        reset_daily,
        interval=86400,  # every 24 hours
        first=delay      # first run at next midnight
    )



# ---------------------------
# Winner announcement feature (NEW)
async def winner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When a user calls /winner, we simply acknowledge that the winner will
    be announced by 9:10 PM today.
    """
    # enforce active hours if you want: (optional)
    now = datetime.now()
    if now.hour >= ALLOWED_END_HOUR:
        await update.message.reply_text("⛔ The bot is already closed for the day. Winner will be announced at 9:10 PM.")
        return

    await update.message.reply_text("🏆 Winner will be announced by 9:10 PM today. Stay tuned!")

async def announce_winner(context: ContextTypes.DEFAULT_TYPE):
    """
    Job scheduled to run daily at 21:10.
    Picks top scorer, stores in winners_col, announces to ANNOUNCE_CHAT_ID (if set) or DMs the winner.
    """
    try:
        # get top user by score
        top_user = users_col.find_one({}, sort=[("score", -1)])
        today_str = datetime.now().strftime("%Y-%m-%d")
        announce_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not top_user or top_user.get("score", 0) <= 0:
            # No winner today
            message = f"🏆 Winner announcement for {today_str}:\nNo winner today (no players or scores)."
            # If ANNOUNCE_CHAT_ID is set, announce there; otherwise no action
            if ANNOUNCE_CHAT_ID:
                try:
                    chat_id = int(ANNOUNCE_CHAT_ID)
                    await context.bot.send_message(chat_id=chat_id, text=message)
                except Exception as e:
                    print("Failed to send no-winner announcement to ANNOUNCE_CHAT_ID:", e)
            else:
                print(message)
            return

        winner_record = {
            "date": today_str,
            "username": top_user.get("username", "Anonymous"),
            "telegram_id": top_user.get("telegram_id"),
            "score": float(top_user.get("score", 0)),
            "announced_at": announce_time
        }

        # Persist winner to winners collection
        winners_col.insert_one(winner_record)

        # Prepare announcement text
        announcement = (
            f"🏆 *Daily Winner — {today_str}* 🏆\n\n"
            f"🥇 Username: {winner_record['username']}\n"
            f"🔢 Score: {winner_record['score']:.1f}\n\n"
            f"Congratulations! 🎉"
        )

        # Send to announce chat if provided; else DM the winner
        if ANNOUNCE_CHAT_ID:
            try:
                chat_id = int(ANNOUNCE_CHAT_ID)
                await context.bot.send_message(chat_id=chat_id, text=announcement, parse_mode="Markdown")
            except Exception as e:
                print("Failed to send winner announcement to ANNOUNCE_CHAT_ID:", e)
                # fallback: DM the winner
                try:
                    await context.bot.send_message(chat_id=winner_record["telegram_id"], text=announcement, parse_mode="Markdown")
                except Exception as e2:
                    print("Failed to DM winner as a fallback:", e2)
        else:
            # No announce chat set — DM the winner
            try:
                await context.bot.send_message(chat_id=winner_record["telegram_id"], text=announcement, parse_mode="Markdown")
            except Exception as e:
                print("Failed to DM winner:", e)

        print(f"✅ Announced winner for {today_str}: {winner_record['username']} ({winner_record['telegram_id']})")
    except Exception as ex:
        print("Error in announce_winner job:", ex)

def schedule_winner_announcement(job_queue: JobQueue):
    """
    Schedule the announce_winner job for 21:10 daily.
    """
    now = datetime.now()
    target_time = now.replace(hour=21, minute=10, second=0, microsecond=0)
    if now >= target_time:
        # schedule for tomorrow
        target_time = target_time + timedelta(days=1)
    delay = (target_time - now).total_seconds()
    job_queue.run_repeating(announce_winner, interval=86400, first=delay)
    print(f"🕘 Winner announcement scheduled for {target_time}")




# ---------------------------
# Commands
# ---------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⏰ Global pre-check: allow only between 8AM - 9PM
    now = datetime.now()
    if not (ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR):
        await update.message.reply_text(
            "⛔ The bot is only active from 8:00 AM to 9:00 PM.\n"
            "Please come back during active hours."
        )
        return

    user_id = update.effective_user.id
    # Block if in quiz (only /end allowed)
    if user_in_quiz(user_id):
        await update.message.reply_text(
            "⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit."
        )
        return

    menu = (
        "👋 Welcome to ORG Quiz Bot!\n\n"
        "Here are the available commands:\n"
        "/play - Start the quiz (must be registered + have ≥ ₦200 balance)\n"
        "/register - Register yourself\n"
        "/leaderboard - Show leaderboard\n"
        "/fund - Add funds to your balance\n"
        "/update - Update your profile details\n"
        "/profile - View your profile\n"
        "/balance - Check your balance\n"
        "/end - End your current quiz\n"
    )
    await update.message.reply_text(menu)



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit.")
        return
    await start_command(update, context)


# ---------------------------
# Register
# ---------------------------
ACTIVE_REGISTRATIONS = set()
ACTIVE_UPDATES = set()

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 Complete it or use /end before registering.")
        return ConversationHandler.END

    user = users_col.find_one({"telegram_id": user_id})

    if user:
        await update.message.reply_text("✅ You are already registered. Use /update to change your details.")
        return ConversationHandler.END

    await update.message.reply_text("📋 Welcome to registration!\nPlease enter a username:")
    return USERNAME



async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()

    # Check uniqueness
    if users_col.find_one({"username": username, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Username already taken, try another one.")
        return USERNAME

    context.user_data["username"] = username
    await update.message.reply_text("✅ Username saved.\nNow enter your email:")
    return EMAIL




async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()

    if users_col.find_one({"email": email, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Email already registered, try another one.")
        return EMAIL

    context.user_data["email"] = email
    await update.message.reply_text("✅ Email saved.\nNow enter your phone number:")
    return PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    if users_col.find_one({"phone": phone, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Phone already used, enter a different number.")
        return PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text("✅ Phone saved.\nEnter your bank name:")
    return BANK

async def register_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bank"] = update.message.text.strip()
    await update.message.reply_text("✅ Bank name saved.\nEnter your account number:")
    return ACCOUNT

async def register_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text.strip()

    if users_col.find_one({"account_number": account_number, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Account number already registered, try again.")
        return ACCOUNT

    context.user_data["account_number"] = account_number

    # ✅ Save everything to MongoDB
    users_col.update_one(
        {"telegram_id": update.effective_user.id},
        {"$set": {
            "username": context.user_data["username"],
            "email": context.user_data["email"],
            "phone": context.user_data["phone"],
            "bank": context.user_data["bank"],
            "account_number": account_number,
            "telegram_id": update.effective_user.id
        }},
        upsert=True
    )

    await update.message.reply_text("🎉 Registration complete! You may now use the bot.")
    return ConversationHandler.END


# async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("❌ Registration cancelled.")
#     return ConversationHandler.END
async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled. You can start again anytime with /register.")
    return ConversationHandler.END


# Profile Update states (reuse same order)

UPD_USERNAME, UPD_EMAIL, UPD_PHONE, UPD_BANK, UPD_ACCOUNT = range(5, 10)

async def start_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 Complete it or use /end before updating your profile.")
        return ConversationHandler.END

    user = users_col.find_one({"telegram_id": user_id})

    if not user:
        await update.message.reply_text("⚠️ You are not registered yet. Use /register first.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"📝 Updating your profile.\n"
        f"📝 To cancel update, use /cancel.\n"
        f"Current details:\n"
        f"- Username: {user.get('username', 'Not set')}\n"
        f"- Email: {user.get('email', 'Not set')}\n"
        f"- Phone: {user.get('phone', 'Not set')}\n"
        f"- Bank: {user.get('bank', 'Not set')}\n"
        f"- Account: {user.get('account_number', 'Not set')}\n\n"
        f"Please enter a new username:"
    )
    return UPD_USERNAME


async def update_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()

    if users_col.find_one({"username": username, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Username already taken, try another one.")
        return UPD_USERNAME

    context.user_data["username"] = username
    await update.message.reply_text("✅ Username saved.\nNow enter your new email:")
    return UPD_EMAIL


async def update_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()

    if users_col.find_one({"email": email, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Email already registered, try another one.")
        return UPD_EMAIL

    context.user_data["email"] = email
    await update.message.reply_text("✅ Email saved.\nNow enter your new phone number:")
    return UPD_PHONE


async def update_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    if users_col.find_one({"phone": phone, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Phone already used, enter a different one.")
        return UPD_PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text("✅ Phone saved.\nEnter your new bank name:")
    return UPD_BANK


async def update_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bank"] = update.message.text.strip()
    await update.message.reply_text("✅ Bank name saved.\nEnter your new account number:")
    return UPD_ACCOUNT


async def update_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text.strip()

    if users_col.find_one({"account_number": account_number, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Account number already registered, try again.")
        return UPD_ACCOUNT

    context.user_data["account_number"] = account_number

    # ✅ Update in DB
    users_col.update_one(
        {"telegram_id": update.effective_user.id},
        {"$set": {
            "username": context.user_data["username"],
            "email": context.user_data["email"],
            "phone": context.user_data["phone"],
            "bank": context.user_data["bank"],
            "account_number": account_number
        }},
    )

    await update.message.reply_text("🎉 Profile updated successfully!")
    return ConversationHandler.END


# async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("❌ Update cancelled.")
#     return ConversationHandler.END
async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Update cancelled. You can start again anytime with /update.")
    return ConversationHandler.END


# Fallback for blocking other commands during registration/update
async def block_other_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Allow /end if in quiz
    if user_id in ACTIVE_QUIZZES and update.message and update.message.text.strip().startswith("/end"):
        return  # don't block, let /end handler run

    # Otherwise block everything
    await update.message.reply_text(
        "⚠️ You cannot use other commands right now.\n"
        "👉 Finish your profile update first, or type /cancel to stop updating."
    )


# ---------------------------
# Profile Command
# ---------------------------
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit.")
        return

    tg_id = update.message.from_user.id
    user = get_user(tg_id)

    if not user:
        await update.message.reply_text("⚠️ You are not registered yet. Use /register first.")
        return

    profile_text = (
        "👤 Your Profile:\n\n"
        f"Username: {user.get('username', '—')}\n"
        f"Email: {user.get('email', '—')}\n"
        f"Phone: {user.get('phone', '—')}\n"
        f"Bank: {user.get('bank', '—')}\n"
        f"Account No: {user.get('account_number', '—')}\n"
        f"Score: {user.get('score', 0):.1f}\n"
        f"Balance: ₦{user.get('balance', 0):,}\n"
        f"Sessions: {user.get('sessions', 0)}"
    )

    await update.message.reply_text(profile_text)






# ---------------------------
# Quiz: show categories (balance check)
# ---------------------------


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⏰ Global pre-check: only active between 8AM - 9PM
    now = datetime.now()
    if not (ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR):
        await update.message.reply_text(
            "⛔ The bot is only active from 8:00 AM to 9:00 PM.\n"
            "Please come back during active hours."
        )
        return

    user_id = update.message.from_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text(
            "⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit."
        )
        return

    tg_id = user_id
    user = get_user(tg_id)

    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return

    if user.get("balance", 0) < 200:
        await update.message.reply_text(
            "⚠️ You need at least ₦200 to play. Use /fund to add funds."
        )
        return

    if tg_id in ACTIVE_QUIZZES:
        await update.message.reply_text(
            "⚠️ You are already in an active quiz session!\n"
            "👉 Use /end first if you want to quit and start again."
        )
        return

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")]
        for cat in CATEGORIES.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💳 Balance: ₦{user.get('balance',0):,}\n\n🎮 Choose a category to start your quiz:",
        reply_markup=reply_markup
    )






async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /end should always be allowed
    user_id = update.effective_user.id

    quiz = ACTIVE_QUIZZES.get(user_id)
    if not quiz or not quiz.get("active", False):
        await update.message.reply_text("⚠️ You are not currently in an active quiz session.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, end now", callback_data="confirm_end"),
            InlineKeyboardButton("❌ No, continue", callback_data="cancel_end"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_msg = await update.message.reply_text(
        "⚠️ Are you sure you want to *end your quiz session*?\n\n"
        "👉 Ending early means you *forfeit the session* and *will not be refunded*.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    # Schedule expiration after 30s
    context.job_queue.run_once(
        expire_end_confirmation,
        30,
        data={
            "chat_id": sent_msg.chat.id,
            "message_id": sent_msg.message_id,
            "user_id": user_id,
        },
    )




async def expire_end_confirmation(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    user_id = data["user_id"]

    # Only expire if quiz is still active
    if user_id in ACTIVE_QUIZZES:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⌛ The end request *expired*. Your quiz continues! 🎉",
                parse_mode="Markdown"
            )
        except:
            pass


async def block_during_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    This is a global handler that replies immediately when a command (except /end) is used
    while the user is in a quiz. It is registered early so users get an immediate block message.
    We still keep defensive checks at the top of each command handler to ensure commands
    do not perform their logic if user is in a quiz.
    """
    # defensively handle both message and callback (we expect commands here)
    if update.message is None:
        return

    user_id = update.effective_user.id

    # Allow /end
    if update.message.text and update.message.text.startswith("/end"):
        return  # let /end proceed

    if user_in_quiz(user_id):
        await update.message.reply_text(
            "⛔ You are currently in a quiz session.\n"
            "👉 The only command available is /end to quit."
        )
        return



async def confirm_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    quiz = ACTIVE_QUIZZES.pop(user_id, None)
    if quiz:
        # Cancel any timeout jobs
        safe_remove_job(quiz.get("timeout_job"))

        # ✅ Record the points earned so far
        final_results = apply_speed_bonus(quiz.get("answers", []))
        user_score_so_far = final_results.get(user_id, 0)

        # Update DB with current points
        update_score(user_id, user_score_so_far)

        await query.edit_message_text(
            f"❌ Your quiz session has been *ended*.\n\n"
            f"⚠️ You forfeited the remaining questions, but your current points ({user_score_so_far:.1f}) have been recorded.\n"
            "👉 You can start again anytime with /play.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("⚠️ You have no active session.")



async def cancel_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Tell user we're continuing; do not let this callback be treated as an answer
    await query.edit_message_text("✅ You chose to continue your quiz. Good luck! 🎉")




# ---------------------------
# Fund & Balance
# ---------------------------

async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⏰ Global pre-check: only active between 8AM - 9PM
    now = datetime.now()
    if not (ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR):
        await update.message.reply_text(
            "⛔ The bot is only active from 8:00 AM to 9:00 PM.\n"
            "Please come back during active hours."
        )
        return

    user_id = update.message.from_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text(
            "⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit."
        )
        return

    tg_id = user_id
    user = get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Usage: /fund <amount>\nExample: /fund 1000"
        )
        return

    update_balance(tg_id, amount)
    user = get_user(tg_id)
    await update.message.reply_text(
        f"💰 {amount} added! Your new balance: ₦{user.get('balance',0):,}"
    )



async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit.")
        return

    tg_id = update.message.from_user.id
    user = get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return
    await update.message.reply_text(f"💳 Your balance: ₦{user.get('balance',0):,}")


# ---------------------------
# Choose category -> deduct fee, increment sessions, start quiz
# ---------------------------
async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # check user & balance again (safety)
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("❌ You must register first using /register.")
        return
    if user.get("balance", 0) < 200:
        await query.edit_message_text(f"💳 Your balance is ₦{user.get('balance',0):,}.\n❌ You need at least ₦200 to play. Please top up.")
        return

    cat = query.data.split("_", 1)[1]
    filepath = CATEGORIES.get(cat)
    if not filepath:
        await query.edit_message_text("⚠️ Unknown category selected.")
        return

    try:
        with open(filepath, "r") as f:
            all_questions = json.load(f)
    except Exception as e:
        await query.edit_message_text(f"⚠️ Failed to load {cat} questions: {e}")
        return

    if len(all_questions) < 5:
        await query.edit_message_text(f"⚠️ Not enough questions in {cat}.")
        return

    # Deduct ₦200 and increment sessions atomically, return updated user
    updated_user = users_col.find_one_and_update(
        {"telegram_id": user_id},
        {"$inc": {"balance": -200, "sessions": 1}},
        return_document=ReturnDocument.AFTER,
        upsert=True
    )

    new_balance = updated_user.get("balance", 0)

    selected = random.sample(all_questions, 5)

    # store quiz state in module-level ACTIVE_QUIZZES for job access
    quiz_state = {
        "score": 0,
        "current": 0,
        "questions": selected,
        "active": True,
        "timeout_job": None,
        "answers": [],
        "category": cat,
        "sent_at": None
    }
    ACTIVE_QUIZZES[user_id] = quiz_state

    await query.edit_message_text(f"✅ ₦200 deducted. Remaining balance: ₦{new_balance:,}\n✅ You chose {cat}. Quiz starting…")
    # start the first question
    await send_question(update, context, user_id)


# ---------------------------
# Send Question
# ---------------------------
async def send_question(update, context, user_id):
    quiz = ACTIVE_QUIZZES.get(user_id)
    if not quiz or not quiz.get("active", True):
        return

    current = quiz["current"]
    if current < len(quiz["questions"]):
        q = quiz["questions"][current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current+1}/{len(quiz['questions'])}:\n{q['question']}\n\n⏳ You have 60 seconds!",
            reply_markup=reply_markup
        )

        # Cancel old timeout job safely
        safe_remove_job(quiz.get("timeout_job"))

        # Schedule new timeout job
        job = context.job_queue.run_once(
            timeout_question,
            60,
            data={"user_id": user_id, "msg_id": msg.message_id},
        )
        quiz["timeout_job"] = job
        quiz["sent_at"] = time.time()
    else:
        await finalize_quiz(context, user_id, quiz)


# ---------------------------
# Timeout Handler
# ---------------------------
async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    user_id = data["user_id"]
    msg_id = data["msg_id"]

    quiz = ACTIVE_QUIZZES.get(user_id)
    if not quiz or not quiz.get("active", True):
        return

    current = quiz["current"]
    # guard: if current index out of range, finalize
    if current >= len(quiz["questions"]):
        await finalize_quiz(context, user_id, quiz)
        return

    correct = quiz["questions"][current]["answer"]

    # Record timeout (no points)
    quiz["answers"].append({
        "user_id": user_id,
        "question_id": current,
        "base_score": 0,
        "elapsed_time": 60,
        "total_score": 0
    })

     # ❌ Disable old buttons
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=msg_id,
            reply_markup=None
        )
    except Exception:
        pass  # Ignore if already answered/edited

    await context.bot.send_message(chat_id=user_id, text=f"⌛ Time’s up! The correct answer was {correct}.")

    quiz["current"] += 1
    # Immediately send next question
    await send_question(None, context, user_id)


# ---------------------------
# Handle Answer
# ---------------------------

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Defensive: ignore confirm/cancel callbacks here
    if query.data in ("confirm_end", "cancel_end"):
        # Let the specific handlers (confirm_end/cancel_end) handle this callback.
        return

    user_id = query.from_user.id

    quiz = ACTIVE_QUIZZES.get(user_id)
    if not quiz or not quiz.get("active", True):
        try:
            await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
        except Exception:
            pass
        return

    current = quiz["current"]
    if current >= len(quiz["questions"]):
        try:
            await query.edit_message_text("✅ Quiz already finished.")
        except Exception:
            pass
        return

    correct = quiz["questions"][current]["answer"]

    # Cancel timeout immediately
    safe_remove_job(quiz.get("timeout_job"))
    quiz["timeout_job"] = None

    elapsed = time.time() - quiz.get("sent_at", time.time())
    base_score = 0
    bonus = 0.0
    total_score = 0.0

    if query.data == correct:
        if elapsed <= 30:
            base_score = 10
        elif elapsed <= 60:
            base_score = 5

        # bonus scoring
        if elapsed <= 10:
            bonus = 0.3
        elif elapsed <= 20:
            bonus = 0.2
        elif elapsed <= 30:
            bonus = 0.1

        total_score = base_score + bonus

    # Record answer
    quiz["answers"].append({
        "user_id": user_id,
        "question_id": current,
        "total_score": total_score if query.data == correct else 0,
        "elapsed_time": elapsed
    })

    # Disable buttons & show result
    try:
        if query.data == correct:
            await query.edit_message_text(f"✅ Correct! You earned {base_score} points + {bonus:.1f} bonus = {total_score:.1f} pts.")
        else:
            await query.edit_message_text(f"❌ Wrong! The correct answer was {correct}.")
    except Exception:
        pass

    quiz["current"] += 1
    # Immediately send next question
    await send_question(update, context, user_id)


# ---------------------------
# Finalize Quiz
# ---------------------------
async def finalize_quiz(context, user_id, quiz):
    if not quiz or not quiz.get("active", True):
        return
    quiz["active"] = False

    final_results = apply_speed_bonus(quiz.get("answers", []))

    # update DB for every participant found in final_results
    for uid, pts in final_results.items():
        update_score(uid, pts)

    user_final_score = final_results.get(user_id, 0)

    # Cancel any job
    safe_remove_job(quiz.get("timeout_job"))

    # clear stored quiz state
    ACTIVE_QUIZZES.pop(user_id, None)

    try:
        await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {user_final_score:.1f}")
    except Exception:
        pass


# ---------------------------
# Leaderboard
# ---------------------------
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_in_quiz(user_id):
        await update.message.reply_text("⛔ You are currently in a quiz session.\n👉 The only command available is /end to quit.")
        return

    tg_id = update.message.from_user.id
    top_users = list(users_col.find().sort("score", -1).limit(10))
    requester = get_user(tg_id)
    if not top_users:
        await update.message.reply_text("⚠️ No players yet.")
        return

    msg_lines = ["🏆 Top 10 Leaderboard 🏆\n"]
    for i, user in enumerate(top_users, start=1):
        name = user.get("username", "Anonymous")
        score = user.get("score", 0)
        msg_lines.append(f"{i}. {name} — {score:.1f} pts")

    if requester:
        rank = users_col.count_documents({"score": {"$gt": requester.get("score", 0)}}) + 1
        if rank > 10:
            msg_lines.append(f"\n... {rank}. {requester.get('username','You')} — {requester.get('score',0):.1f} pts")

    await update.message.reply_text("\n".join(msg_lines))


# ---------------------------
# Main
# ---------------------------
update_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("update", start_update)],
    states={
        UPD_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_username)],
        UPD_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_email)],
        UPD_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_phone)],
        UPD_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_bank)],
        UPD_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_account)],
    },
    # fallbacks=[
    #     CommandHandler("cancel", cancel_update),
    #     MessageHandler(filters.COMMAND, block_other_commands),  # 👈 deny other commands
    # ],
fallbacks=[CommandHandler("cancel", cancel_update),
           MessageHandler(filters.COMMAND, block_other_commands),
           ],
           allow_reentry=True,   # so user can restart update after finishing/cancelling
    per_user=True,        # ensure blocking applies per user
)

    

def main():
    print("🤖 Bot starting...")
    app = Application.builder().token(TOKEN).build()
    schedule_daily_reset(app.job_queue)
    # Register flow
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", start_registration)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_username)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone)],
            BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_bank)],
            ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_account)],
        },
        # fallbacks=[],
    #     fallbacks=[CommandHandler("cancel", cancel_registration),
    #     MessageHandler(filters.COMMAND, block_other_commands),  # 👈 deny other commands
    # ],
    # allow_reentry=True,
        fallbacks=[CommandHandler("cancel", cancel_registration)],
    )

    app.add_handler(reg_conv)
    app.add_handler(update_conv_handler)

    # Global blocker for commands during quiz (except /end)
    # Register early so users get immediate block reply when they try commands mid-quiz.
    # Blocker (placed AFTER command handlers, so they get first chance)
    app.add_handler(
    MessageHandler(filters.COMMAND & ~filters.Regex("^/end$"), block_during_quiz),
    group=1,
)


    # Core command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("winner", winner_command))

    # CALLBACK QUERY HANDLERS: specific handlers first, then the generic answer handler
    app.add_handler(CallbackQueryHandler(choose_category, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(confirm_end, pattern="^confirm_end$"))
    app.add_handler(CallbackQueryHandler(cancel_end, pattern="^cancel_end$"))
    app.add_handler(CallbackQueryHandler(handle_answer))

    print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
    # Use webhook if WEBHOOK_URL is set, otherwise fallback to polling
    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook"
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()

