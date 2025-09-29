import os
import certifi
import json
import requests
from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from pymongo import MongoClient


# MongoDB Setup MONGO PASS= 1alYeJpUg8UpmvjE
# MongoDB username= isrealkevin929_org-quiz_db_user
# MongoDB connection string= mongodb+srv://isrealkevin929_org-quiz_db_user:<db_password>@org-quiz-bot.1tycfmm.mongodb.net/?retryWrites=true&w=majority&appName=org-quiz-bot

# ---------------------------
MONGO_URI = os.getenv("MONGO_URI")  # stored in Railway environment variables

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["quiz_bot"]
users_col = db["users"]


# ---------------------------
# Environment
# ---------------------------
TOKEN: Final = os.getenv("BOT_TOKEN")
BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # set in Railway as WEBHOOK_URL

# ---------------------------
# Quiz Questions
# ---------------------------
# Load quiz questions
with open("questions.json", "r") as f:
    QUIZ = json.load(f)

# ---------------------------
# Helpers: User Management
# ---------------------------


# ---------------------------
# Conversation states
# ---------------------------
REGISTER_USERNAME, REGISTER_EMAIL, REGISTER_CONFIRM = range(3)

# ---------------------------
# Helpers
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
        {"$setOnInsert": {"score": 0}, "$set": update},
        upsert=True
    )
    return get_user(tg_id)


def update_score(tg_id, points):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"score": points}})
    return get_user(tg_id)


def update_balance(tg_id, amount):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"balance": amount}})
    return get_user(tg_id)


# Start Command
# ---------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = (
        "👋 Welcome to ORG Quiz Bot!\n\n"
        "Here are the available commands:\n"
        "/play - Start the quiz (must be registered + have ≥ 500 balance)\n"
        "/register - Register yourself\n"
        "/leaderboard - Show leaderboard\n"
        "/fund - Add funds to your balance\n"
        "/balance - Check your balance\n"
        "/end - End your current quiz\n"
    )
    await update.message.reply_text(menu)

# ---------------------------
# Command Handlers
# ---------------------------
# ---------------------------
# Register Command
# ---------------------------
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter your username:")
    return REGISTER_USERNAME


async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["username"] = update.message.text
    await update.message.reply_text("Now enter your email:")
    return REGISTER_EMAIL


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = update.message.text
    await update.message.reply_text(
        f"Confirm registration:\n\nUsername: {context.user_data['username']}\nEmail: {context.user_data['email']}\n\nType 'yes' to confirm or 'no' to cancel."
    )
    return REGISTER_CONFIRM


async def register_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() == "yes":
        tg_id = update.message.from_user.id
        create_or_update_user(
            tg_id,
            username=context.user_data["username"],
            email=context.user_data["email"]
        )
        await update.message.reply_text("✅ Registration successful!")
    else:
        await update.message.reply_text("❌ Registration cancelled.")
    return ConversationHandler.END


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = update.message.text
    keyboard = [[InlineKeyboardButton("Confirm ✅", callback_data="confirm_register")]]
    await update.message.reply_text(
        f"Name: {context.user_data['first_name']}\n"
        f"Account: {context.user_data['account_number']}\n"
        f"Email: {context.user_data['email']}\n\n"
        "Confirm registration?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return REGISTER_CONFIRM


async def register_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    username = query.from_user.username
    first_name = context.user_data.get("first_name")
    account_number = context.user_data.get("account_number")
    email = context.user_data.get("email")

    await create_or_update_user(tg_id, username, account_number, first_name, email)
    await query.edit_message_text("✅ Registered successfully!")
    return ConversationHandler.END


# ---------------------------
# Start Quiz
# ---------------------------


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    user = get_user(tg_id)

    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return
    if user.get("balance", 0) < 500:
        await update.message.reply_text("⚠️ You need at least 500 balance to play. Use /fund to add funds.")
        return

    # Deduct 500 for playing
    update_balance(tg_id, -500)

    context.user_data["quiz"] = {"score": 0, "current": 0, "active": True}
    await update.message.reply_text("🎉 Quiz starting... Good luck!")
    await send_question(update, context, tg_id)


# End quiz
async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    quiz = context.user_data.get("quiz")
    if not quiz or not quiz["active"]:
        await update.message.reply_text("❌ You are not currently in a quiz session.")
        return
    score = quiz["score"]
    total_answered = quiz["current"]
    update_score(tg_id, score)
    await update.message.reply_text(f"✅ Quiz ended!\nYou answered {total_answered} questions.\nScore gained: {score}")
    quiz["active"] = False



# Fund & Balance
# ---------------------------
async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    user = get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /fund <amount>\nExample: /fund 1000")
        return

    update_balance(tg_id, amount)
    user = get_user(tg_id)
    await update.message.reply_text(f"💰 {amount} added! Your new balance: {user['balance']}")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    user = get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return
    await update.message.reply_text(f"💳 Your balance: {user.get('balance',0)}")


# Send question
async def send_question(update, context, user_id):
    quiz = context.user_data["quiz"]
    current = quiz["current"]

    if current < len(QUIZ) and quiz["active"]:
        q = QUIZ[current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current+1}: {q['question']}",
            reply_markup=reply_markup
        )
    else:
        score = quiz["score"]
        update_score(user_id, score)
        await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/{len(QUIZ)}")
        quiz["active"] = False

    # Handle answers
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    quiz = context.user_data.get("quiz")

    if not quiz or not quiz["active"]:
        await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
        return

    current = quiz["current"]
    correct = QUIZ[current]["answer"]

    if query.data == correct:
        quiz["score"] += 1
        await query.edit_message_text(f"✅ Correct! The answer is {correct}")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

    quiz["current"] += 1
    await send_question(update, context, user_id)



# ---------------------------
# Leaderboard
# ---------------------------
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        msg_lines.append(f"{i}. {name} — {score} pts")

    # Add requester rank if not in top 10
    if requester:
        rank = users_col.count_documents({"score": {"$gt": requester.get("score", 0)}}) + 1
        if rank > 10:
            msg_lines.append(f"\n... {rank}. {requester.get('username','You')} — {requester.get('score',0)} pts")

    await update.message.reply_text("\n".join(msg_lines))


    # ---------------------------
# Main
# ---------------------------
def main():
    print("🤖 Bot starting...")
    app = Application.builder().token(TOKEN).build()

    # Register flow
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_command)],
        states={
            REGISTER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_username)],
            REGISTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
            REGISTER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_confirm)],
        },
        fallbacks=[],
    )

    app.add_handler(reg_conv)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CallbackQueryHandler(handle_answer))


     # Start webhook server
    print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path="webhook",
webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()
