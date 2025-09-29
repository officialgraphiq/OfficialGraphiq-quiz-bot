import os
import certifi
import json
import requests
import random
from datetime import datetime
from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, JobQueue, ContextTypes, filters
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

def increment_sessions(tg_id):
    users_col.update_one({"telegram_id": tg_id}, {"$inc": {"sessions": 1}})
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

    # Help Command (reuse start)
# ---------------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Just call start_command so both are identical
    await start_command(update, context)

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
    increment_sessions(tg_id)

    # Pick 5 random questions
    questions = random.sample(QUIZ, 5)

    context.user_data["quiz"] = {
        "score": 0,
        "current": 0,
        "questions": questions,
        "active": True,
        "timeout_job": None,
    }

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

    if current < len(quiz["questions"]) and quiz["active"]:
        q = quiz["questions"][current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current+1}/5:\n{q['question']}\n\n⏳ You have 60 seconds!",
            reply_markup=reply_markup
        )

        # Cancel old job if any
        if quiz.get("timeout_job"):
            quiz["timeout_job"].schedule_removal()

        # Schedule timeout in 60s
        job = context.job_queue.run_once(timeout_question, 60, data={"user_id": user_id, "msg_id": msg.message_id})
        quiz["timeout_job"] = job

    else:
        score = quiz["score"]
        update_score(user_id, score)
        await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/5")
        quiz["active"] = False


# Timeout Handler
# ---------------------------
async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    user_id = data["user_id"]
    user_data = context.application.user_data[user_id]
    quiz = user_data.get("quiz")

    if not quiz or not quiz["active"]:
        return

    current = quiz["current"]
    correct = quiz["questions"][current]["answer"]

    # Mark as failed due to timeout
    await context.bot.send_message(
        chat_id=user_id,
        text=f"⌛ Time’s up! The correct answer was {correct}."
    )

    quiz["current"] += 1
    await send_question(None, context, user_id)


# Handle Answer (cancel timeout if answered)
# ---------------------------
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    quiz = context.user_data.get("quiz")

    if not quiz or not quiz["active"]:
        await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
        return

    current = quiz["current"]
    correct = quiz["questions"][current]["answer"]

    # Cancel timeout
    if quiz.get("timeout_job"):
        quiz["timeout_job"].schedule_removal()
        quiz["timeout_job"] = None

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


def table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the leaderboard with decimal scores."""
    top_users = list(users_col.find().sort("score", -1).limit(10))

    if not top_users:
        update.message.reply_text("📊 No scores yet. Start playing with /play!")
        return

    leaderboard = "🏆 *Leaderboard* 🏆\n\n"
    for i, user in enumerate(top_users, start=1):
        username = user.get("username", f"User{user['telegram_id']}")
        score = user.get("score", 0)
        leaderboard += f"{i}. {username} — *{score:.1f}* pts\n"

    update.message.reply_text(leaderboard, parse_mode="Markdown")




    # ---------------------------
# Main
# ---------------------------
def main():
    print("🤖 Bot starting...")
    app = Application.builder().token(TOKEN).build()
    app.job_queue
    

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
    app.add_handler(CommandHandler("help", help_command))
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
