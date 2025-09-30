# import os
# import certifi
# import json
# import requests
# import random
# from typing import Final
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (
#     Application, CommandHandler, CallbackQueryHandler,
#     MessageHandler, ConversationHandler, JobQueue, ContextTypes, filters
# )
# from pymongo import MongoClient


# # MongoDB Setup MONGO PASS= 1alYeJpUg8UpmvjE
# # MongoDB username= isrealkevin929_org-quiz_db_user
# # MongoDB connection string= mongodb+srv://isrealkevin929_org-quiz_db_user:<db_password>@org-quiz-bot.1tycfmm.mongodb.net/?retryWrites=true&w=majority&appName=org-quiz-bot

# # ---------------------------
# MONGO_URI = os.getenv("MONGO_URI")  # stored in Railway environment variables

# client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
# db = client["quiz_bot"]
# users_col = db["users"]


# # ---------------------------
# # Environment
# # ---------------------------
# TOKEN: Final = os.getenv("BOT_TOKEN")
# BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
# WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # set in Railway as WEBHOOK_URL

# # ---------------------------
# # Quiz Questions
# # ---------------------------
# # Load quiz questions
# with open("questions.json", "r") as f:
#     QUIZ = json.load(f)

# # ---------------------------
# # Helpers: User Management
# # ---------------------------


# # ---------------------------
# # Conversation states
# # ---------------------------
# REGISTER_USERNAME, REGISTER_EMAIL, REGISTER_CONFIRM = range(3)

# # ---------------------------
# # Helpers
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
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"score": points}})
#     return get_user(tg_id)


# def update_balance(tg_id, amount):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"balance": amount}})
#     return get_user(tg_id)

# def increment_sessions(tg_id):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"sessions": 1}})
#     return get_user(tg_id)

# def safe_remove_job(job):
#     if job:
#         try:
#             job.schedule_removal()
#         except Exception:
#             # Job already removed or expired
#             pass

# # Start Command
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

#     # Help Command (reuse start)
# # ---------------------------
# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     # Just call start_command so both are identical
#     await start_command(update, context)

# # ---------------------------
# # Command Handlers
# # ---------------------------
# # ---------------------------
# # Register Command
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
# # Start Quiz
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

#     # Deduct 500 for playing
#     update_balance(tg_id, -500)
#     increment_sessions(tg_id)

#     # Pick 5 random questions
#     questions = random.sample(QUIZ, 5)

#     context.user_data["quiz"] = {
#         "score": 0,
#         "current": 0,
#         "questions": questions,
#         "active": True,
#         "timeout_job": None,
#     }

#     await update.message.reply_text("🎉 Quiz starting... Good luck!")
#     await send_question(update, context, tg_id)



# # End quiz
# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     tg_id = update.message.from_user.id
#     quiz = context.user_data.get("quiz")
#     if not quiz or not quiz["active"]:
#         await update.message.reply_text("❌ You are not currently in a quiz session.")
#         return
#     score = quiz["score"]
#     total_answered = quiz["current"]
#     update_score(tg_id, score)
#     await update.message.reply_text(f"✅ Quiz ended!\nYou answered {total_answered} questions.\nScore gained: {score}")
#     quiz["active"] = False



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


# # Send question
# async def send_question(update, context, user_id):
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")

#     if not quiz:
#         return  # nothing to do

#     current = quiz["current"]
#     # quiz = context.user_data["quiz"]
#     # current = quiz["current"]

#     if current < len(quiz["questions"]) and quiz["active"]:
#         q = quiz["questions"][current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         msg = await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current+1}/5:\n{q['question']}\n\n⏳ You have 60 seconds!",
#             reply_markup=reply_markup
#         )

#         # Cancel old timeout if any
#         # if quiz.get("timeout_job"):
#         #     quiz["timeout_job"].schedule_removal()
#         safe_remove_job(quiz.get("timeout_job"))

#         # Schedule timeout for THIS question
#         job = context.job_queue.run_once(
#             timeout_question, 
#             60,
#             data={"user_id": user_id, "msg_id": msg.message_id}
#         )
#         quiz["timeout_job"] = job

#     else:
#         # Quiz finished
#         score = quiz["score"]
#         answered = quiz.get("answered", quiz["current"])
#         update_score(user_id, score)
#         await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/5")
#         quiz["active"] = False




# # Timeout Handler
# # ---------------------------
# async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
#     data = context.job.data
#     user_id = data["user_id"]
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")

#     if not quiz or not quiz["active"]:
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     # Tell user time’s up
#     await context.bot.send_message(
#         chat_id=user_id,
#         text=f"⌛ Time’s up! The correct answer was {correct}."
#     )

#     quiz["answered"] = quiz.get("answered", 0) + 1

#     # Move to next question
#     quiz["current"] += 1
#     await send_question(None, context, user_id)


# # Handle Answer (cancel timeout if answered)
# # ---------------------------
# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id
#     # quiz = context.user_data.get("quiz")
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")

#     if not quiz or not quiz["active"]:
#         await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
#         return

#     current = quiz["current"]
    
#     correct = quiz["questions"][current]["answer"]

#     # Cancel timeout
#     # if quiz.get("timeout_job"):
#     #     quiz["timeout_job"].schedule_removal()
#     #     quiz["timeout_job"] = None

#     safe_remove_job(quiz.get("timeout_job"))

#     if query.data == correct:
#         quiz["score"] += 1
#         await query.edit_message_text(f"✅ Correct! The answer is {correct}")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

#         quiz["answered"] = quiz.get("answered", 0) + 1

#     quiz["current"] += 1
#     await send_question(update, context, user_id)



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
#         msg_lines.append(f"{i}. {name} — {score} pts")

#     # Add requester rank if not in top 10
#     if requester:
#         rank = users_col.count_documents({"score": {"$gt": requester.get("score", 0)}}) + 1
#         if rank > 10:
#             msg_lines.append(f"\n... {rank}. {requester.get('username','You')} — {requester.get('score',0)} pts")

#     await update.message.reply_text("\n".join(msg_lines))


#     # ---------------------------
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
#     app.add_handler(CallbackQueryHandler(handle_answer))


#      # Start webhook server
#     print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
#     app.run_webhook(
#         listen="0.0.0.0",
#         port=int(os.environ.get("PORT", 8080)),
#         url_path="webhook",
# webhook_url=f"{WEBHOOK_URL}/webhook"
#     )

# if __name__ == "__main__":
#     main()
























# import os
# import certifi
# import json
# import requests
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
# # Load Questions
# # ---------------------------
# with open("questions.json", "r") as f:
#     QUIZ = json.load(f)


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
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"score": points}})
#     return get_user(tg_id)

# def update_balance(tg_id, amount):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"balance": amount}})
#     return get_user(tg_id)

# def increment_sessions(tg_id):
#     users_col.update_one({"telegram_id": tg_id}, {"$inc": {"sessions": 1}})
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
#         for ans in answers:
#             final_scores[ans["user_id"]] += ans["base_score"]

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
# # Quiz
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

#     update_balance(tg_id, -500)
#     increment_sessions(tg_id)

#     questions = random.sample(QUIZ, 5)

#     context.user_data["quiz"] = {
#         "score": 0,
#         "current": 0,
#         "questions": questions,
#         "active": True,
#         "timeout_job": None,
#         "answers": []
#     }

#     await update.message.reply_text("🎉 Quiz starting... Good luck!")
#     await send_question(update, context, tg_id)

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


# # ---------------------------
# # Send Question
# # ---------------------------
# async def send_question(update, context, user_id):
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")
#     if not quiz: return

#     current = quiz["current"]
#     if current < len(quiz["questions"]) and quiz["active"]:
#         q = quiz["questions"][current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         msg = await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current+1}/5:\n{q['question']}\n\n⏳ You have 60 seconds!",
#             reply_markup=reply_markup
#         )

#         if quiz.get("timeout_job"):
#             safe_remove_job(quiz.get("timeout_job"))

#         job = context.job_queue.run_once(
#             timeout_question,
#             60,
#             data={"user_id": user_id, "msg_id": msg.message_id}
#         )
#         quiz["timeout_job"] = job
#         quiz["sent_at"] = time.time()
#     else:
#         await finalize_quiz(context, user_id, quiz)


# # ---------------------------
# # Timeout Handler
# # ---------------------------
# async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
#     data = context.job.data
#     user_id = data["user_id"]
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")
#     if not quiz or not quiz["active"]:
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     await context.bot.send_message(chat_id=user_id, text=f"⌛ Time’s up! The correct answer was {correct}.")

#     quiz["answers"].append({
#         "user_id": user_id,
#         "question_id": current,
#         "base_score": 0,
#         "elapsed_time": 60
#     })

#     quiz["current"] += 1
#     await send_question(None, context, user_id)


# # ---------------------------
# # Handle Answer
# # ---------------------------
# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id
#     user_data = context.application.user_data.get(user_id, {})
#     quiz = user_data.get("quiz")
#     if not quiz or not quiz["active"]:
#         await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     safe_remove_job(quiz.get("timeout_job"))

#     elapsed = time.time() - quiz.get("sent_at", time.time())
#     base_score = 0
#     if query.data == correct:
#         if elapsed <= 30:
#             base_score = 10
#         elif elapsed <= 60:
#             base_score = 5
#         await query.edit_message_text(f"✅ Correct! The answer is {correct}")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

#     quiz["answers"].append({
#         "user_id": user_id,
#         "question_id": current,
#         "base_score": base_score if query.data == correct else 0,
#         "elapsed_time": elapsed
#     })

#     quiz["current"] += 1
#     await send_question(update, context, user_id)


# # ---------------------------
# # Finalize Quiz
# # ---------------------------
# async def finalize_quiz(context, user_id, quiz):
#     if not quiz["active"]:
#         return
#     quiz["active"] = False

#     final_results = apply_speed_bonus(quiz["answers"])
#     user_final_score = final_results.get(user_id, 0)

#     update_score(user_id, user_final_score)
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
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from pymongo import MongoClient


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

# Optional: preload general questions so the bot still works if you don't choose categories
try:
    with open(CATEGORIES["General"], "r") as f:
        _ = json.load(f)
except Exception:
    # ignore if not available yet
    pass

# with open("questions.json", "r") as f:
# #     QUIZ = json.load(f)


# ---------------------------
# Conversation states
# ---------------------------
REGISTER_USERNAME, REGISTER_EMAIL, REGISTER_CONFIRM = range(3)


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
        {"$setOnInsert": {"score": 0}, "$set": update},
        upsert=True
    )
    return get_user(tg_id)

def update_score(tg_id, points):
    # increment the stored score by points (float allowed)
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
    grouped = defaultdict(list)
    for ans in all_answers:
        grouped[ans["question_id"]].append(ans)

    final_scores = defaultdict(float)
    for qid, answers in grouped.items():
        # add base scores
        for ans in answers:
            final_scores[ans["user_id"]] += ans["base_score"]

        # sort by elapsed time (fastest first)
        sorted_answers = sorted(answers, key=lambda x: x["elapsed_time"])
        for i, faster in enumerate(sorted_answers):
            for slower in sorted_answers[i+1:]:
                diff = slower["elapsed_time"] - faster["elapsed_time"]
                if diff > 0:
                    final_scores[faster["user_id"]] += diff * 0.1
    return dict(final_scores)


# ---------------------------
# Commands
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)


# ---------------------------
# Register
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
#Quiz: category selection --> start
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

    # Build category keyboard
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")]
        for cat in CATEGORIES.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎮 Choose a category to start your quiz:",
        reply_markup=reply_markup
    )


async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    quiz = context.user_data.get("quiz")
    if not quiz or not quiz["active"]:
        await update.message.reply_text("❌ You are not currently in a quiz session.")
        return
    quiz["active"] = False
    await finalize_quiz(context, tg_id, quiz)


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
    await update.message.reply_text(f"💰 {amount} added! Your new balance: {user['balance']}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.message.from_user.id
    user = get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ You must register first using /register")
        return
    await update.message.reply_text(f"💳 Your balance: {user.get('balance',0)}")




async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

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

    selected = random.sample(all_questions, 5)

    context.user_data["quiz"] = {
    "score": 0,
    "current": 0,
    "questions": selected,
    "active": True,
    "timeout_job": None,
    "answers": [],
    "category": cat,
    "sent_at": None
}


    await query.edit_message_text(f"✅ You chose {cat}. Quiz starting…")
    await send_question(update, context, user_id)  # pass update instead of None



# ---------------------------
# Send Question
# ---------------------------
# async def send_question(update, context, user_id):
#     quiz = context.application.user_data.get(user_id, {}).get("quiz")


#     if not quiz:
#         return

#     current = quiz["current"]
#     if current < len(quiz["questions"]) and quiz["active"]:
#         q = quiz["questions"][current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         msg = await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current+1}/5:\n{q['question']}\n\n⏳ You have 60 seconds!",
#             reply_markup=reply_markup
#         )

#         # remove old timeout job safely
#         safe_remove_job(quiz.get("timeout_job"))


#         job = context.job_queue.run_once(
#     timeout_question,
#     60,
#     data={"user_id": user_id, "msg_id": msg.message_id},
# )
#         quiz["timeout_job"] = job
#         quiz["sent_at"] = time.time()

#     else:
#         await finalize_quiz(context, user_id, quiz)




async def send_question(update, context, user_id):
    quiz = context.application.user_data.get(user_id, {}).get("quiz")
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

        # 🔹 Cancel old timeout job safely
        safe_remove_job(quiz.get("timeout_job"))

        # 🔹 Schedule new timeout job
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


# async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
#     job = context.job
#     data = job.data
#     user_id = data["user_id"]

#     quiz = context.application.user_data.get(user_id, {}).get("quiz")
#     if not quiz or not quiz.get("active", True):
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     # Record timeout (no points)
#     quiz["answers"].append({
#         "user_id": user_id,
#         "question_id": current,
#         "base_score": 0,
#         "elapsed_time": 60
#     })

#     await context.bot.send_message(chat_id=user_id, text=f"⌛ Time’s up! The correct answer was {correct}.")

#     quiz["current"] += 1
#     await send_question(None, context, user_id)





async def timeout_question(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    user_id = data["user_id"]

    quiz = context.application.user_data.get(user_id, {}).get("quiz")
    if not quiz or not quiz.get("active", True):
        return

    current = quiz["current"]
    correct = quiz["questions"][current]["answer"]

    # 🔹 Record timeout (no points)
    quiz["answers"].append({
        "user_id": user_id,
        "question_id": current,
        "base_score": 0,
        "elapsed_time": 60
    })

    await context.bot.send_message(chat_id=user_id, text=f"⌛ Time’s up! The correct answer was {correct}.")

    quiz["current"] += 1
    # 🔹 Immediately send next question
    await send_question(None, context, user_id)







# ---------------------------
# Handle Answer
# ---------------------------
# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id

#     # user_data = context.application.user_data.get(user_id, {})
#     # quiz = user_data.get("quiz")
#     quiz = context.application.user_data.get(user_id, {}).get("quiz")


#     if not quiz or not quiz["active"]:
#         await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
#         return

#     current = quiz["current"]
#     correct = quiz["questions"][current]["answer"]

#     # cancel timeout safely
#     safe_remove_job(quiz.get("timeout_job"))

#     elapsed = time.time() - quiz.get("sent_at", time.time())
#     base_score = 0
#     if query.data == correct:
#         if elapsed <= 30:
#             base_score = 10
#         elif elapsed <= 60:
#             base_score = 5

#     # record answer
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
#     await send_question(update, context, user_id)




async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    quiz = context.application.user_data.get(user_id, {}).get("quiz")
    if not quiz or not quiz.get("active", True):
        await query.edit_message_text("❌ You are not in an active quiz. Type /play to begin.")
        return

    current = quiz["current"]
    correct = quiz["questions"][current]["answer"]

    # 🔹 Cancel timeout immediately
    safe_remove_job(quiz.get("timeout_job"))

    elapsed = time.time() - quiz.get("sent_at", time.time())
    base_score = 0
    if query.data == correct:
        if elapsed <= 30:
            base_score = 10
        elif elapsed <= 60:
            base_score = 5

    # Record answer
    quiz["answers"].append({
        "user_id": user_id,
        "question_id": current,
        "base_score": base_score if query.data == correct else 0,
        "elapsed_time": elapsed
    })

    if query.data == correct:
        await query.edit_message_text(f"✅ Correct! You earned {base_score} points.")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer was {correct}.")

    quiz["current"] += 1
    # 🔹 Immediately send next question
    await send_question(update, context, user_id)




# ---------------------------
# Finalize Quiz
# ---------------------------
async def finalize_quiz(context, user_id, quiz):
    # if quiz already finalized, do nothing
    if not quiz or not quiz.get("active", True):
        return
    quiz["active"] = False

    # compute final scores for this quiz (may only include one user in single-player mode)
    final_results = apply_speed_bonus(quiz.get("answers", []))

    # update DB for every participant found in final_results
    for uid, pts in final_results.items():
        update_score(uid, pts)

    # report to the user who finished
    user_final_score = final_results.get(user_id, 0)
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
    app.add_handler(CommandHandler("help", help_command))

    # category chooser must be registered *before* the generic answer handler
    app.add_handler(CallbackQueryHandler(choose_category, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(handle_answer))

    print(f"🚀 Starting webhook at {WEBHOOK_URL}/webhook")
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )


if __name__ == "__main__":
    main()
