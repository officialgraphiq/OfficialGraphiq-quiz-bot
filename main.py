# import os
# import certifi
# import json
# import random
# import time
# from typing import Final
# from collections import defaultdict
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (
#     Application, CommandHandler, CallbackQueryHandler,
#     MessageHandler, ConversationHandler, ContextTypes, filters
# )
# from pymongo import MongoClient


# # ---------------------------
# # MongoDB Setup
# # ---------------------------
# MONGO_URI = os.getenv("MONGO_URI")
# client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
# db = client["quiz_bot"]
# users_col = db["users"]


# # ---------------------------
# # Environment
# # ---------------------------
# TOKEN: Final = os.getenv("BOT_TOKEN")
# BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
# WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")


# # ---------------------------
# # Category files (place these JSON files next to this script)
# # ---------------------------
# CATEGORIES = {
#     "General": "questions.json",
#     "Math": "questions_math.json",
#     "Chemistry": "questions_chemistry.json",
#     "Biology": "questions_biology.json",
#     "Geography": "questions_geography.json",
# }

# # Optional: preload general questions so the bot still works if you don't choose categories
# try:
#     with open(CATEGORIES["General"], "r") as f:
#         _ = json.load(f)
# except Exception:
#     # ignore if not available yet
#     pass

# # with open("questions.json", "r") as f:
# # #     QUIZ = json.load(f)


# # ---------------------------
# # Conversation states
# # ---------------------------
# REGISTER_USERNAME, REGISTER_EMAIL, REGISTER_CONFIRM = range(3)


# # ---------------------------
# # Helpers: DB Functions
# # ---------------------------
# def get_user(tg_id):
#     user = users_col.find_one({"telegram_id": tg_id})
#     if user and "balance" not in user:
#         users_col.update_one({"telegram_id": tg_id}, {"$set": {"balance": 0}})
#         user["balance"] = 0
#     return user

# def create_or_update_user(tg_id, username=None, email=None):
#     update = {}
#     if username: update["username"] = username
#     if email: update["email"] = email
#     users_col.update_one(
#         {"telegram_id": tg_id},
#         {"$setOnInsert": {"score": 0}, "$set": update},
#         upsert=True
#     )
#     return get_user(tg_id)

# def update_score(tg_id, points):
#     # increment the stored score by points (float allowed)
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"score": points}}, upsert=True)
#     return get_user(tg_id)

# def update_balance(tg_id, amount):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"balance": amount}}, upsert=True)
#     return get_user(tg_id)

# def increment_sessions(tg_id):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"sessions": 1}}, upsert=True)
#     return get_user(tg_id)


# def safe_remove_job(job):
#     if job:
#         try:
#             job.schedule_removal()
#         except Exception:
#             pass


# # ---------------------------
# # Speed Bonus Scoring
# # ---------------------------
# def apply_speed_bonus(all_answers):
#     grouped = defaultdict(list)
#     for ans in all_answers:
#         grouped[ans["question_id"]].append(ans)

#     final_scores = defaultdict(float)
#     for qid, answers in grouped.items():
#         # add base scores
#         for ans in answers:
#             final_scores[ans["user_id"]] += ans["base_score"]

#         # sort by elapsed time (fastest first)
#         sorted_answers = sorted(answers, key=lambda x: x["elapsed_time"])
#         for i, faster in enumerate(sorted_answers):
#             for slower in sorted_answers[i+1:]:
#                 diff = slower["elapsed_time"] - faster["elapsed_time"]
#                 if diff > 0:
#                     final_scores[faster["user_id"]] += diff * 0.1
#     return dict(final_scores)


# # ---------------------------
# # Commands
# # ---------------------------
# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     menu = (
#         "👋 Welcome to ORG Quiz Bot!\n\n"
#         "Here are the available commands:\n"
#         "/play - Start the quiz (must be registered + have ≥ 500 balance)\n"
#         "/register - Register yourself\n"
#         "/leaderboard - Show leaderboard\n"
#         "/fund - Add funds to your balance\n"
#         "/balance - Check your balance\n"
#         "/end - End your current quiz\n"
#     )
#     await update.message.reply_text(menu)

# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await start_command(update, context)


# # ---------------------------
# # Register
# # ---------------------------
# async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Please enter your username:")
#     return REGISTER_USERNAME

# async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["username"] = update.message.text
#     await update.message.reply_text("Now enter your email:")
#     return REGISTER_EMAIL

# async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["email"] = update.message.text
#     await update.message.reply_text(
#         f"Confirm registration:\n\nUsername: {context.user_data['username']}\nEmail: {context.user_data['email']}\n\nType 'yes' to confirm or 'no' to cancel."
#     )
#     return REGISTER_CONFIRM

# async def register_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.message.text.lower() == "yes":
#         tg_id = update.message.from_user.id
#         create_or_update_user(
#             tg_id,
#             username=context.user_data["username"],
#             email=context.user_data["email"]
#         )
#         await update.message.reply_text("✅ Registration successful!")
#     else:
#         await update.message.reply_text("❌ Registration cancelled.")
#     return ConversationHandler.END


# # ---------------------------
# #Quiz: category selection --> start
# # ---------------------------


# async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     user = get_user(tg_id)

#     if not user:
#         await update.message.reply_text("⚠️ You must register first using /register")
#         return
#     if user.get("balance", 0) < 500:
#         await update.message.reply_text("⚠️ You need at least 500 balance to play. Use /fund to add funds.")
#         return

#     # Build category keyboard
#     keyboard = [
#         [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")]
#         for cat in CATEGORIES.keys()
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)

#     await update.message.reply_text(
#         "🎮 Choose a category to start your quiz:",
#         reply_markup=reply_markup
#     )


# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     quiz = context.user_data.get("quiz")
#     if not quiz or not quiz["active"]:
#         await update.message.reply_text("❌ You are not currently in a quiz session.")
#         return
#     quiz["active"] = False
#     await finalize_quiz(context, tg_id, quiz)


# # ---------------------------
# # Fund & Balance
# # ---------------------------
# async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     user = get_user(tg_id)
#     if not user:
#         await update.message.reply_text("⚠️ You must register first using /register")
#         return
#     try:
#         amount = int(context.args[0])
#         if amount <= 0:
#             raise ValueError
#     except (IndexError, ValueError):
#         await update.message.reply_text("Usage: /fund <amount>\nExample: /fund 1000")
#         return

#     update_balance(tg_id, amount)
#     user = get_user(tg_id)
#     await update.message.reply_text(f"💰 {amount} added! Your new balance: {user['balance']}")

# async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     user = get_user(tg_id)
#     if not user:
#         await update.message.reply_text("⚠️ You must register first using /register")
#         return
#     await update.message.reply_text(f"💳 Your balance: {user.get('balance',0)}")




# async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id

#     cat = query.data.split("_", 1)[1]
#     filepath = CATEGORIES.get(cat)
#     if not filepath:
#         await query.edit_message_text("⚠️ Unknown category selected.")
#         return

#     try:
#         with open(filepath, "r") as f:
#             all_questions = json.load(f)
#     except Exception as e:
#         await query.edit_message_text(f"⚠️ Failed to load {cat} questions: {e}")
#         return

#     if len(all_questions) < 5:
#         await query.edit_message_text(f"⚠️ Not enough questions in {cat}.")
#         return

#     selected = random.sample(all_questions, 5)

#     context.user_data["quiz"] = {
#     "score": 0,
#     "current": 0,
#     "questions": selected,
#     "active": True,
#     "timeout_job": None,
#     "answers": [],
#     "category": cat,
#     "sent_at": None
# }


#     await query.edit_message_text(f"✅ You chose {cat}. Quiz starting…")
#     await send_question(update, context, user_id)  # pass update instead of None



# # ---------------------------
# # Send Question
# # ---------------------------

# async def send_question(update, context, user_id):
#     quiz = context.application.user_data.get(user_id, {}).get("quiz")
#     if not quiz or not quiz.get("active", True):
#         return

#     current = quiz["current"]
#     if current < len(quiz["questions"]):
#         q = quiz["questions"][current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         msg = await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current+1}/{len(quiz['questions'])}:\n{q['question']}\n\n⏳ You have 60 seconds!",
#             reply_markup=reply_markup
#         )

#         # 🔹 Cancel old timeout job safely
#         safe_remove_job(quiz.get("timeout_job"))

#         # 🔹 Schedule new timeout job
#         job = context.job_queue.run_once(
#             timeout_question,
#             60,
#             data={"user_id": user_id, "msg_id": msg.message_id},
#         )
#         quiz["timeout_job"] = job
#         quiz["sent_at"] = time.time()
#     else:
#         await finalize_quiz(context, user_id, quiz)

# # ---------------------------
# # Timeout Handler
# # ---------------------------


# async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
#     job = context.job
#     data = job.data
#     user_id = data["user_id"]

#     quiz = context.application.user_data.get(user_id, {}).get("quiz")
#     if not quiz or not quiz.get("active", True):
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     # 🔹 Record timeout (no points)
#     quiz["answers"].append({
#         "user_id": user_id,
#         "question_id": current,
#         "base_score": 0,
#         "elapsed_time": 60
#     })

#     await context.bot.send_message(chat_id=user_id, text=f"⌛ Time’s up! The correct answer was {correct}.")

#     quiz["current"] += 1
#     # 🔹 Immediately send next question
#     await send_question(None, context, user_id)


# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id

#     quiz = context.application.user_data.get(user_id, {}).get("quiz")
#     if not quiz or not quiz.get("active", True):
#         await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     # 🔹 Cancel timeout immediately
#     safe_remove_job(quiz.get("timeout_job"))

#     elapsed = time.time() - quiz.get("sent_at", time.time())
#     base_score = 0
#     if query.data == correct:
#         if elapsed <= 30:
#             base_score = 10
#         elif elapsed <= 60:
#             base_score = 5

#     # Record answer
#     quiz["answers"].append({
#         "user_id": user_id,
#         "question_id": current,
#         "base_score": base_score if query.data == correct else 0,
#         "elapsed_time": elapsed
#     })

#     if query.data == correct:
#         await query.edit_message_text(f"✅ Correct! You earned {base_score} points.")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer was {correct}.")

#     quiz["current"] += 1
#     # 🔹 Immediately send next question
#     await send_question(update, context, user_id)




# # ---------------------------
# # Finalize Quiz
# # ---------------------------
# async def finalize_quiz(context, user_id, quiz):
#     # if quiz already finalized, do nothing
#     if not quiz or not quiz.get("active", True):
#         return
#     quiz["active"] = False

#     # compute final scores for this quiz (may only include one user in single-player mode)
#     final_results = apply_speed_bonus(quiz.get("answers", []))

#     # update DB for every participant found in final_results
#     for uid, pts in final_results.items():
#         update_score(uid, pts)

#     # report to the user who finished
#     user_final_score = final_results.get(user_id, 0)
#     await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {user_final_score:.1f}")


# # ---------------------------
# # Leaderboard
# # ---------------------------
# async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     top_users = list(users_col.find().sort("score", -1).limit(10))
#     requester = get_user(tg_id)
#     if not top_users:
#         await update.message.reply_text("⚠️ No players yet.")
#         return

#     msg_lines = ["🏆 Top 10 Leaderboard 🏆\n"]
#     for i, user in enumerate(top_users, start=1):
#         name = user.get("username", "Anonymous")
#         score = user.get("score", 0)
#         msg_lines.append(f"{i}. {name} — {score:.1f} pts")

#     if requester:
#         rank = users_col.count_documents({"score": {"$gt": requester.get("score", 0)}}) + 1
#         if rank > 10:
#             msg_lines.append(f"\n... {rank}. {requester.get('username','You')} — {requester.get('score',0):.1f} pts")

#     await update.message.reply_text("\n".join(msg_lines))


# # ---------------------------
# # Main
# # ---------------------------
# def main():
#     print("🤖 Bot starting...")
#     app = Application.builder().token(TOKEN).build()

#     # Register flow
#     reg_conv = ConversationHandler(
#         entry_points=[CommandHandler("register", register_command)],
#         states={
#             REGISTER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_username)],
#             REGISTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
#             REGISTER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_confirm)],
#         },
#         fallbacks=[],
#     )

#     app.add_handler(reg_conv)
#     app.add_handler(CommandHandler("start", start_command))
#     app.add_handler(CommandHandler("play", play_command))
#     app.add_handler(CommandHandler("end", end_command))
#     app.add_handler(CommandHandler("fund", fund_command))
#     app.add_handler(CommandHandler("balance", balance_command))
#     app.add_handler(CommandHandler("leaderboard", leaderboard_command))
#     app.add_handler(CommandHandler("help", help_command))

#     # category chooser must be registered *before* the generic answer handler
#     app.add_handler(CallbackQueryHandler(choose_category, pattern=r"^cat_"))
#     app.add_handler(CallbackQueryHandler(handle_answer))

#     print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
#     app.run_webhook(
#         listen="0.0.0.0",
#         port=int(os.environ.get("PORT", 8080)),
#         url_path="webhook",
#         webhook_url=f"{WEBHOOK_URL}/webhook"
#     )


# if __name__ == "__main__":
#     main()






























import os
import certifi
import json
import random
import time
from typing import Final
from telegram.ext import JobQueue
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from pymongo import MongoClient, ReturnDocument


# ---------------------------
# MongoDB Setup
# ---------------------------
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["quiz_bot"]
users_col = db["users"]


# ---------------------------
# Environment
# ---------------------------
TOKEN: Final = os.getenv("BOT_TOKEN")
BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")


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
# Speed Bonus Scoring
# ---------------------------

def apply_speed_bonus(all_answers):
    """
    Finalize scores by summing the stored base_score (which already includes time bonuses).
    """
    final_scores = defaultdict(float)
    for ans in all_answers:
        final_scores[ans["user_id"]] += ans.get("total_score", 0)
    return dict(final_scores)




# ---------------------------
# Commands
# ---------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = (
        "👋 Welcome to ORG Quiz Bot!\n\n"
        "Here are the available commands:\n"
        "/play - Start the quiz (must be registered + have ≥ ₦300 balance)\n"
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
    await start_command(update, context)


# ---------------------------
# Register
# ---------------------------
# async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Please enter your username:")
#     return USERNAME
# async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("📋 Welcome to registration!\nPlease enter a username:")
#     return USERNAME

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users_col.find_one({"telegram_id": update.effective_user.id})

    if user:
        await update.message.reply_text("✅ You are already registered. Use /update to change your details.")
        return ConversationHandler.END

    await update.message.reply_text("📋 Welcome to registration!\nPlease enter a username:")
    return USERNAME



# async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["username"] = update.message.text
#     await update.message.reply_text("Now enter your email:")
#     return EMAIL
async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()

    # Check uniqueness
    if users_col.find_one({"username": username, "telegram_id": {"$ne": update.effective_user.id}}):
        await update.message.reply_text("❌ Username already taken, try another one.")
        return USERNAME

    context.user_data["username"] = username
    await update.message.reply_text("✅ Username saved.\nNow enter your email:")
    return EMAIL




# async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["email"] = update.message.text
#     await update.message.reply_text(
#         f"Confirm registration:\n\nUsername: {context.user_data['username']}\nEmail: {context.user_data['email']}\n\nType 'yes' to confirm or 'no' to cancel."
#     )
#     return CONFIRM

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


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled.")
    return ConversationHandler.END


# Profile Update states (reuse same order)

UPD_USERNAME, UPD_EMAIL, UPD_PHONE, UPD_BANK, UPD_ACCOUNT = range(5, 10)

async def start_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users_col.find_one({"telegram_id": update.effective_user.id})

    if not user:
        await update.message.reply_text("⚠️ You are not registered yet. Use /register first.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"📝 Updating your profile.\n"
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


async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Update cancelled.")
    return ConversationHandler.END


# Fallback for blocking other commands
# async def block_other_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "⚠️ You’re currently in the middle of registration/update. "
#         "Please finish or /cancel before using other commands."
#     )
async def block_other_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Allow /end if in quiz
    if user_id in ACTIVE_QUIZZES and update.message.text.strip().startswith("/end"):
        return  # don't block, let /end handler run

    # Otherwise block everything
    await update.message.reply_text(
        "⚠️ You cannot use other commands right now.\n"
        "👉 Finish your ongoing quiz or registration/update first."
    )



# ---------------------------
# Profile Command
# ---------------------------
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    tg_id = update.message.from_user.id
    user = get_user(tg_id)

    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return
    # Require at least 300 to start a session
    if user.get("balance", 0) < 300:
        await update.message.reply_text("⚠️ You need at least ₦300 to play. Use /fund to add funds.")
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


# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     quiz = ACTIVE_QUIZZES.get(tg_id)
#     if not quiz or not quiz.get("active", False):
#         await update.message.reply_text("❌ You are not currently in a quiz session.")
#         return
#     quiz["active"] = False
#     await finalize_quiz(context, tg_id, quiz)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id

#     if user_id not in ACTIVE_QUIZZES:
#         await update.message.reply_text("⚠️ You are not in an active quiz session.")
#         return

#     keyboard = [
#         [
#             InlineKeyboardButton("✅ Yes, end now", callback_data="confirm_end"),
#             InlineKeyboardButton("❌ No, continue", callback_data="cancel_end"),
#         ]
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)

#     await update.message.reply_text(
#         "⚠️ Are you sure you want to *end your quiz session*?\n\n"
#         "👉 Ending early means you *forfeit the session* and *will not be refunded*.",
#         reply_markup=reply_markup,
#         parse_mode="Markdown"
#     )

async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        expire_end_confirmation, 30, 
        data={"chat_id": sent_msg.chat.id, "message_id": sent_msg.message_id, "user_id": user_id}
    )

async def expire_end_confirmation(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    user_id = data["user_id"]

    # If the quiz still exists, it means the user didn’t confirm or cancel
    if user_id in ACTIVE_QUIZZES:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⌛ The end request *expired*. Your quiz continues! 🎉",
                parse_mode="Markdown"
            )
        except:
            pass  # ignore if message already changed


def is_in_quiz(update: Update) -> bool:
    user_id = update.effective_user.id
    return user_id in ACTIVE_QUIZZES


async def block_during_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ You are currently in a quiz session.\n"
        "👉 The only command available is /end to quit."
    )

async def confirm_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    quiz = ACTIVE_QUIZZES.pop(user_id, None)
    if quiz:
        # Cancel any scheduled timeout job
        safe_remove_job(quiz.get("timeout_job"))

        await query.edit_message_text(
            "❌ Your quiz session has been *ended*.\n\n"
            "⚠️ No refund is given for ending early.\n"
            "👉 You can start again anytime with /play.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("⚠️ You have no active session.")

        

async def cancel_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ You chose to continue your quiz. Good luck! 🎉")




# ---------------------------
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
    await update.message.reply_text(f"💰 {amount} added! Your new balance: ₦{user.get('balance',0):,}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if user.get("balance", 0) < 300:
        await query.edit_message_text(f"💳 Your balance is ₦{user.get('balance',0):,}.\n❌ You need at least ₦300 to play. Please top up.")
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

    # Deduct ₦300 and increment sessions atomically, return updated user
    updated_user = users_col.find_one_and_update(
        {"telegram_id": user_id},
        {"$inc": {"balance": -300, "sessions": 1}},
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

    await query.edit_message_text(f"✅ ₦300 deducted. Remaining balance: ₦{new_balance:,}\n✅ You chose {cat}. Quiz starting…")
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
        "elapsed_time": 60
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
    user_id = query.from_user.id

    quiz = ACTIVE_QUIZZES.get(user_id)
    if not quiz or not quiz.get("active", True):
        await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
        return

    current = quiz["current"]
    if current >= len(quiz["questions"]):
        await query.edit_message_text("✅ Quiz already finished.")
        return

    correct = quiz["questions"][current]["answer"]

    # Cancel timeout immediately
    safe_remove_job(quiz.get("timeout_job"))
    quiz["timeout_job"] = None

    elapsed = time.time() - quiz.get("sent_at", time.time())
    base_score = 0
    bonus = 0.0
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
        # "base_score": base_score if query.data == correct else 0,
        "total_score": total_score if query.data == correct else 0,
        "elapsed_time": elapsed
    })

    if query.data == correct:
        await query.edit_message_text(f"✅ Correct! You earned {base_score} points + {bonus:.1f} bonus = {total_score:.1f} pts.")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer was {correct}.")

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

    # clear stored quiz state
    ACTIVE_QUIZZES.pop(user_id, None)

    await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {user_final_score:.1f}")


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
    fallbacks=[
        CommandHandler("cancel", cancel_update),
        MessageHandler(filters.COMMAND, block_other_commands),  # 👈 deny other commands
    ],
    allow_reentry=True,
)

def main():
    print("🤖 Bot starting...")
    app = Application.builder().token(TOKEN).build()
    

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
        fallbacks=[CommandHandler("cancel", cancel_registration),
        MessageHandler(filters.COMMAND, block_other_commands),  # 👈 deny other commands
    ],
    allow_reentry=True,
    )

    app.add_handler(reg_conv)
    app.add_handler(update_conv_handler)
    app.add_handler(MessageHandler(filters.COMMAND & ~filters.Regex("^/end$"),
        block_during_quiz
    ))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))

    # category chooser must be registered *before* the generic answer handler
    app.add_handler(CallbackQueryHandler(choose_category, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(confirm_end, pattern="^confirm_end$"))
    app.add_handler(CallbackQueryHandler(cancel_end, pattern="^cancel_end$"))


    print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )


if __name__ == "__main__":
    main()
