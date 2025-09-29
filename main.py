# #5ESyrJcJ4UCweJEN     SUPABASE DB PASSWORD
# from supabase import create_client, Client
# import os
# import re
# import json
# import io
# import csv
# import asyncio
# from decimal import Decimal
# from typing import Final
# from dotenv import load_dotenv

# import asyncpg
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (
#     Application,
#     CommandHandler,
#     CallbackQueryHandler,
#     MessageHandler,
#     ConversationHandler,
#     ContextTypes,
#     filters,
# )

# load_dotenv()

# # -----------------------
# # Config
# # -----------------------
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# TOKEN = os.getenv("TOKEN")
# # DATABASE_URL = os.getenv("DATABASE_URL")  # Railway-provided Postgres URL
# ADMIN_IDS = set(
#     int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
# )


# if not TOKEN:
#     raise RuntimeError("Environment variable TOKEN is required.")
# if not DATABASE_URL:
#     raise RuntimeError("Environment variable DATABASE_URL is required.")

# QUIZ_FEE: Final = Decimal("100")  # quiz entry fee

# # -----------------------
# # Load questions.json
# # -----------------------
# QUESTIONS_FILE = "questions.json"
# try:
#     with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
#         QUIZ = json.load(f)
# except FileNotFoundError:
#     print(f"ERROR: {QUESTIONS_FILE} not found. Place questions.json alongside main.py.")
#     QUIZ = []

# # -----------------------
# # In-memory user state
# # -----------------------
# user_data: dict = {}  # telegram_id -> {"score": int, "current": int, "active": bool}

# # db_pool: asyncpg.pool.Pool | None = None  # global pool


# USERNAME, ACCOUNT, EMAIL, CONFIRM = range(4)

# ASK_USERNAME, ASK_EMAIL = range(2)   # add a new state

# async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["username"] = update.message.text
#     await update.message.reply_text("Great! Now please enter your email:")
#     return ASK_EMAIL


# # Save email + username + telegram_id into DB
# async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     email = update.message.text
#     username = context.user_data["username"]
#     telegram_id = update.effective_user.id

#     pool = context.application.bot_data["db_pool"]
#     async with pool.acquire() as conn:
#         await conn.execute(
#             """
#             INSERT INTO users (telegram_id, username, email)
#             VALUES ($1, $2, $3)
#             ON CONFLICT (telegram_id) DO UPDATE
#             SET username = EXCLUDED.username,
#                 email = EXCLUDED.email
#             """,
#             telegram_id, username, email
#         )

#     await update.message.reply_text("✅ Registration complete!")
#     return ConversationHandler.END


# # -----------------------
# # Database
# # -----------------------
# async def init_db():
#     global db_pool
#     db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
#     print("✅ Connected to PostgreSQL")

#     async with db_pool.acquire() as conn:
#         await conn.execute(
#             """
#             CREATE TABLE IF NOT EXISTS users (
#                 id SERIAL PRIMARY KEY,
#                 telegram_id BIGINT UNIQUE NOT NULL,
#                 username TEXT,
#                 account_number TEXT,
#                 first_name TEXT,
#                 wallet NUMERIC DEFAULT 0,
#                 total_score INTEGER DEFAULT 0,
#                 created_at TIMESTAMP DEFAULT NOW()
#             );
#             """
#         )
#         await conn.execute(
#             """
#             CREATE TABLE IF NOT EXISTS scores (
#                 id SERIAL PRIMARY KEY,
#                 user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
#                 score INTEGER NOT NULL,
#                 created_at TIMESTAMP DEFAULT NOW()
#             );
#             """
#         )

#           # safely add email column if missing (migration step)
#         await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;")
#         # index to speed up email lookups if you search by it
#         await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

#     print("📦 DB tables ensured")


# async def get_user_record(telegram_id: int):
#     global db_pool
#     async with db_pool.acquire() as conn:
#         return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", telegram_id)


# # async def create_or_update_user(telegram_id, username, account_number, first_name, email=None):
# #     """
# #     Create or update a user. email is optional.
# #     """
# #     global db_pool
# #     async with db_pool.acquire() as conn:
# #         await conn.execute(
# #             """
# #             INSERT INTO users (telegram_id, username, account_number, first_name, email)
# #             VALUES ($1, $2, $3, $4, $5)
# #             ON CONFLICT (telegram_id) DO UPDATE
# #             SET username = EXCLUDED.username,
# #                 account_number = COALESCE(EXCLUDED.account_number, users.account_number),
# #                 first_name = COALESCE(EXCLUDED.first_name, users.first_name),
# #                 email = COALESCE(EXCLUDED.email, users.email)
# #             """,
# #             telegram_id, username, account_number, first_name, email,
# #         )

# def create_or_update_user(telegram_id, username, email=None):
#     supabase.table("users").upsert({
#         "telegram_id": telegram_id,
#         "username": username,
#         "email": email,
#     }).execute()





# async def add_funds(telegram_id: int, amount: Decimal):
#     global db_pool
#     async with db_pool.acquire() as conn:
#         await conn.execute("INSERT INTO users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", telegram_id)
#         await conn.execute(
#             "UPDATE users SET wallet = wallet + $1 WHERE telegram_id = $2",
#             str(amount), telegram_id,
#         )
#         row = await conn.fetchrow("SELECT wallet FROM users WHERE telegram_id=$1", telegram_id)
#         return Decimal(row["wallet"])


# async def deduct_fee(telegram_id: int, fee: Decimal):
#     global db_pool
#     async with db_pool.acquire() as conn:
#         row = await conn.fetchrow("SELECT wallet FROM users WHERE telegram_id=$1 FOR UPDATE", telegram_id)
#         if not row:
#             return None
#         balance = Decimal(row["wallet"])
#         if balance < fee:
#             return None
#         new_balance = balance - fee
#         await conn.execute("UPDATE users SET wallet = $1 WHERE telegram_id = $2", str(new_balance), telegram_id)
#         return new_balance


# # async def save_score_db(telegram_id: int, score: int):
# #     global db_pool
# #     async with db_pool.acquire() as conn:
# #         user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
# #         if not user:
# #             await conn.execute("INSERT INTO users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", telegram_id)
# #             user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
# #         if user:
# #             await conn.execute("INSERT INTO scores (user_id, score) VALUES ($1, $2)", user["id"], score)
# #             await conn.execute("UPDATE users SET total_score = total_score + $1 WHERE id = $2", score, user["id"])


# def save_score_db(telegram_id: int, score: int):
#     # fetch user
#     user = supabase.table("users").select("id", "total_score").eq("telegram_id", telegram_id).single().execute()
#     if not user.data:
#         return

#     user_id = user.data["id"]
#     new_total = user.data["total_score"] + score

#     # insert into scores table
#     supabase.table("scores").insert({
#         "user_id": user_id,
#         "score": score,
#     }).execute()

#     # update total score
#     supabase.table("users").update({"total_score": new_total}).eq("id", user_id).execute()






# def get_leaderboard(limit=10):
#     result = supabase.table("users") \
#         .select("username,total_score") \
#         .order("total_score", desc=True) \
#         .limit(limit) \
#         .execute()
#     return result.data


# # async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
# #     global db_pool
# #     async with db_pool.acquire() as conn:
# #         rows = await conn.fetch(
# #             "SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT 10"
# #         )

# #     if not rows:
# #         await update.message.reply_text("No scores yet.")
# #         return

# #     msg = "🏆 Leaderboard 🏆\n\n"
# #     for i, r in enumerate(rows, start=1):
# #         msg += f"{i}. {r['username'] or 'Anonymous'} — {r['total_score']} pts\n"
# #     await update.message.reply_text(msg)



# # -----------------------
# # Quiz logic
# # -----------------------
# async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
#     if user_id not in user_data:
#         return
#     state = user_data[user_id]
#     current = state["current"]
#     if state.get("active") and current < len(QUIZ):
#         q = QUIZ[current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current + 1}: {q['question']}",
#             reply_markup=InlineKeyboardMarkup(keyboard),
#         )
#     else:
#         score = state["score"]
#         total = len(QUIZ)
#         await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/{total}")
#         state["active"] = False
#         await save_score_db(user_id, score)


# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id

#     if user_id not in user_data or not user_data[user_id].get("active"):
#         await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
#         return

#     state = user_data[user_id]
#     current = state["current"]
#     if current >= len(QUIZ):
#         await query.edit_message_text("This quiz is already finished.")
#         return

#     correct = QUIZ[current]["answer"]
#     selected = query.data
#     if selected == correct:
#         state["score"] += 1
#         await query.edit_message_text(f"✅ Correct! The answer is {correct}")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

#     state["current"] += 1
#     await send_question(context, user_id)


# # -----------------------
# # Commands
# # -----------------------
# async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
#     args = context.args
#     username = args[0] if len(args) >= 1 else user.username
#     account_number = args[1] if len(args) >= 2 else None
#     await create_or_update_user(user.id, username, account_number, user.first_name)
#     await update.message.reply_text("✅ Registered successfully!")


# async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     row = await get_user_record(update.effective_user.id)
#     if not row:
#         await update.message.reply_text("⚠️ Not registered. Use /register.")
#         return
#     await update.message.reply_text(f"💰 Balance: {Decimal(row['wallet'])}")


# async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if len(context.args) < 1:
#         await update.message.reply_text("Usage: /fund <amount>")
#         return
#     try:
#         amount = Decimal(context.args[0])
#         if amount <= 0:
#             raise ValueError
#     except Exception:
#         await update.message.reply_text("Invalid amount.")
#         return
#     await create_or_update_user(update.effective_user.id, update.effective_user.username, None, update.effective_user.first_name)
#     new_balance = await add_funds(update.effective_user.id, amount)
#     await update.message.reply_text(f"✅ New balance: {new_balance}")


# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
#     row = await get_user_record(user.id)
#     if not row:
#         await update.message.reply_text("⚠️ Not registered. Use /register.")
#         return
#     balance = Decimal(row["wallet"])
#     if balance < QUIZ_FEE:
#         await update.message.reply_text(f"💰 Insufficient funds ({balance}). Need {QUIZ_FEE}. Use /fund <amount>.")
#         return
#     new_balance = await deduct_fee(user.id, QUIZ_FEE)
#     if new_balance is None:
#         await update.message.reply_text("⚠️ Could not deduct fee.")
#         return
#     user_data[user.id] = {"score": 0, "current": 0, "active": True}
#     await update.message.reply_text(f"✅ Fee deducted. Starting quiz. Balance: {new_balance}")
#     await send_question(context, user.id)


# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if user_id not in user_data or not user_data[user_id].get("active"):
#         await update.message.reply_text("Not in a quiz session.")
#         return
#     score = user_data[user_id]["score"]
#     await save_score_db(user_id, score)
#     user_data[user_id]["active"] = False
#     await update.message.reply_text(f"✅ Quiz ended. Score: {score}")


# async def table_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     rows = await get_leaderboard_db()
#     if not rows:
#         await update.message.reply_text("No scores yet.")
#         return
#     msg = "🏆 Leaderboard 🏆\n"
#     for i, r in enumerate(rows, start=1):
#         msg += f"{i}. {r['username'] or 'Anonymous'} — {r['total_score']} pts\n"
#     await update.message.reply_text(msg)


# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "/register [username] - Register\n"
#         "/fund <amount> - Add funds\n"
#         "/balance - Check balance\n"
#         f"/start - Pay {QUIZ_FEE} and play\n"
#         "/end - End quiz\n"
#         "/table - Leaderboard\n"
#     )


# async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Use /help for commands.")


# # -----------------------
# # Setup + run
# # ... your imports remain the same ...




# def _is_valid_email(email: str) -> bool:
#     return re.match(r"^[^@]+@[^@]+\.[^@]+$", email) is not None

# async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Entry point for /register conversation"""
#     user = update.effective_user
#     # if user already registered, ask if they want to update
#     existing = await get_user_record(user.id)
#     if existing:
#         await update.message.reply_text(
#             "You are already registered. Send /cancel to abort or reply 'yes' to update your details.\n"
#             "Reply 'yes' to update or /cancel to stop."
#         )
#         # store a flag to indicate update intent on confirm
#         context.user_data["reg"] = {"updating": True}
#         return USERNAME

#     context.user_data["reg"] = {"updating": False}
#     await update.message.reply_text(
#         "Welcome — let's register you!\n"
#         "Send your preferred username, or send /skip to use your Telegram username."
#     )
#     return USERNAME


# #REGISTER USER
# # def register_user(telegram_id, username):
# #     supabase.table("users").upsert({
# #         "telegram_id": telegram_id,
# #         "username": username
# #     }).execute()


# #UPDATE SCORES
# # def update_score(telegram_id, points):
# #     # Fetch current score
# #     current = supabase.table("users").select("score").eq("telegram_id", telegram_id).execute()
# #     if current.data:
# #         new_score = current.data[0]["score"] + points
# #         supabase.table("users").update({"score": new_score}).eq("telegram_id", telegram_id).execute()




# async def username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text.strip()
#     if text.lower() == "/skip" or text.lower() == "skip":
#         username = update.effective_user.username or None
#     else:
#         username = text
#     context.user_data["reg"]["username"] = username
#     await update.message.reply_text("Send your account number (or /skip to skip):")
#     return ACCOUNT

# async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text.strip()
#     if text.lower() == "/skip" or text.lower() == "skip":
#         account_number = None
#     else:
#         account_number = text
#     context.user_data["reg"]["account_number"] = account_number
#     await update.message.reply_text("Send your email address (this is required):")
#     return EMAIL

# async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     email = update.message.text.strip()
#     if not _is_valid_email(email):
#         await update.message.reply_text("That's not a valid email. Please send a valid email address.")
#         return EMAIL
#     context.user_data["reg"]["email"] = email

#     summary = context.user_data["reg"]
#     await update.message.reply_text(
#         "Please confirm your details:\n"
#         f"Username: {summary.get('username')}\n"
#         f"Account number: {summary.get('account_number') or '(none)'}\n"
#         f"Email: {summary.get('email')}\n\n"
#         "Send 'yes' to confirm and save, or 'no' to cancel."
#     )
#     return CONFIRM

# async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     answer = update.message.text.strip().lower()
#     if answer not in ("yes", "y"):
#         await update.message.reply_text("Registration cancelled. No changes were made.")
#         context.user_data.pop("reg", None)
#         return ConversationHandler.END

#     reg = context.user_data.get("reg", {})
#     username = reg.get("username")
#     account_number = reg.get("account_number")
#     email = reg.get("email")
#     user = update.effective_user

#     # Save to DB
#     await create_or_update_user(user.id, username, account_number, user.first_name, email)
#     context.user_data.pop("reg", None)
#     await update.message.reply_text("✅ Registered successfully! Thank you.")
#     return ConversationHandler.END

# async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data.pop("reg", None)
#     await update.message.reply_text("Registration cancelled.")
#     return ConversationHandler.END

# # -----------------------
# # Admin commands
# # -----------------------
# async def _is_admin(user_id: int) -> bool:
#     return user_id in ADMIN_IDS

# async def export_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     uid = update.effective_user.id
#     if not await _is_admin(uid):
#         await update.message.reply_text("Unauthorized.")
#         return

#     # fetch all users
#     global db_pool
#     async with db_pool.acquire() as conn:
#         rows = await conn.fetch(
#             "SELECT telegram_id, username, email, account_number, first_name, wallet, total_score, created_at FROM users ORDER BY id"
#         )

#     if not rows:
#         await update.message.reply_text("No users found.")
#         return

#     # build CSV in memory
#     sio = io.StringIO()
#     writer = csv.writer(sio)
#     writer.writerow(['telegram_id', 'username', 'email', 'account_number', 'first_name', 'wallet', 'total_score', 'created_at'])
#     for r in rows:
#         writer.writerow([
#             r['telegram_id'],
#             r['username'] or "",
#             r['email'] or "",
#             r['account_number'] or "",
#             r['first_name'] or "",
#             str(r['wallet']) if r['wallet'] is not None else "0",
#             r['total_score'] or 0,
#             r['created_at'].isoformat() if r['created_at'] else ""
#         ])

#     bio = io.BytesIO(sio.getvalue().encode())
#     bio.name = "users_export.csv"
#     bio.seek(0)
#     await update.message.reply_document(document=bio, filename="users_export.csv")

# async def users_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     uid = update.effective_user.id
#     if not await _is_admin(uid):
#         await update.message.reply_text("Unauthorized.")
#         return
#     limit = 20
#     if context.args and context.args[0].isdigit():
#         limit = min(100, int(context.args[0]))  # allow admin to request more up to 100
#     async with db_pool.acquire() as conn:
#         rows = await conn.fetch("SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT $1", limit)
#     if not rows:
#         await update.message.reply_text("No users yet.")
#         return
#     msg = "🏆 Leaderboard 🏆\n"
#     for i, r in enumerate(rows, start=1):
#         msg += f"{i}. {r['username'] or 'Anonymous'} — {r['total_score']} pts\n"
#     await update.message.reply_text(msg)


# # -----------------------
# # Setup + run
# # -----------------------
# # -----------------------
# # Setup + run
# # -----------------------
# # -----------------------
# # Setup + run
# # -----------------------






# async def on_startup(app: Application):
#     """Runs when the bot starts (inside PTB's loop)."""
#     await init_db()   # Now db_pool lives in the correct loop
#     print("🚀 Startup tasks done")


# def main():
#     # Create application
#     app = Application.builder().token(TOKEN).post_init(on_startup).build()

#      # Conversation for registration
#     reg_conv = ConversationHandler(
#         entry_points=[CommandHandler("register", register_start)],
#         states={
#             USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username_handler)],
#             ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_handler)],
#             EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_handler)],
#             CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)],
#         },
#         fallbacks=[CommandHandler("cancel", cancel_registration)],
#         allow_reentry=True,
#     )


#     # Handlers
#     app.add_handler(reg_conv)
#     app.add_handler(CommandHandler("fund", fund_command))
#     app.add_handler(CommandHandler("balance", balance_command))
#     app.add_handler(CommandHandler("start", start_command))
#     app.add_handler(CommandHandler("end", end_command))
#     app.add_handler(CommandHandler("table", table_command))
#     app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
#     app.add_handler(CommandHandler("help", help_command))
#     app.add_handler(CommandHandler("export_users", export_users_command))
#     app.add_handler(CommandHandler("users", users_admin_command))
#     app.add_handler(CallbackQueryHandler(handle_answer))
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

#     print("🤖 Bot is running...")
#     app.run_polling(close_loop=False)  # keep loop open


# if __name__ == "__main__":
#     main()

















# 5ESyrJcJ4UCweJEN     SUPABASE DB PASSWORD
# from supabase import create_client, Client
# import os
# import re
# import json
# import io
# import csv
# import asyncio
# from decimal import Decimal
# from typing import Final
# from dotenv import load_dotenv

# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (
#     Application,
#     CommandHandler,
#     CallbackQueryHandler,
#     MessageHandler,
#     ConversationHandler,
#     ContextTypes,
#     filters,
# )

# load_dotenv()

# # -----------------------
# # Config
# # -----------------------
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
# ADMIN_IDS = set(
#     int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
# )

# if not TOKEN:
#     raise RuntimeError("Environment variable TOKEN is required.")
# if not SUPABASE_URL or not SUPABASE_KEY:
#     raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are required.")

# QUIZ_FEE: Final = Decimal("100")  # quiz entry fee

# # -----------------------
# # Load questions.json
# # -----------------------
# QUESTIONS_FILE = "questions.json"
# try:
#     with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
#         QUIZ = json.load(f)
# except FileNotFoundError:
#     print(f"ERROR: {QUESTIONS_FILE} not found. Place questions.json alongside main.py.")
#     QUIZ = []

# # -----------------------
# # In-memory user state
# # -----------------------
# user_data: dict = {}  # telegram_id -> {"score": int, "current": int, "active": bool}


# USERNAME, ACCOUNT, EMAIL, CONFIRM = range(4)
# ASK_USERNAME, ASK_EMAIL = range(2)  # add a new state


# # -----------------------
# # Helpers (async wrappers around blocking supabase client)
# # We use asyncio.to_thread so PTB event loop isn't blocked.
# # -----------------------
# def _upsert_user_payload(telegram_id, username=None, account_number=None, first_name=None, email=None):
#     payload = {"telegram_id": telegram_id}
#     if username is not None:
#         payload["username"] = username
#     if account_number is not None:
#         payload["account_number"] = account_number
#     if first_name is not None:
#         payload["first_name"] = first_name
#     if email is not None:
#         payload["email"] = email
#     return payload

# # async def create_or_update_user(telegram_id, username=None, account_number=None, first_name=None, email=None):
# #     payload = _upsert_user_payload(telegram_id, username, account_number, first_name, email)
# #     # ensure defaults exist if creating
# #     # if "wallet" not in payload:
# #     #     payload.setdefault("wallet", 0)
# #     # if "total_score" not in payload:
# #     #     payload.setdefault("total_score", 0)

# #     payload.setdefault("wallet", 0)
# #     payload.setdefault("total_score", 0)
# #     def _do():
# #         return supabase.table("users").upsert(payload).execute()
# #     return await asyncio.to_thread(_do)



# async def create_or_update_user(telegram_id, username=None, account_number=None, first_name=None):
#     def _do():
#         # Try to find user
#         existing = (
#             supabase.table("users")
#             .select("*")
#             .eq("telegram_id", telegram_id)
#             .execute()
#         )
#         if existing.data and len(existing.data) > 0:
#             # Update username / first_name if provided
#             updates = {}
#             if username is not None:
#                 updates["username"] = username
#             if first_name is not None:
#                 updates["first_name"] = first_name

#             if updates:
#                 res = (
#                     supabase.table("users")
#                     .update(updates)
#                     .eq("telegram_id", telegram_id)
#                     .select("*")
#                     .execute()
#                 )
#                 return res.data[0] if res.data else existing.data[0]
#             return existing.data[0]

    
#         # If not found, create new
#         res = (
#             supabase.table("users")
#             .insert(
#                 {
#                     "telegram_id": telegram_id,
#                     "username": username or "",
#                     "first_name": first_name or "",
#                     "account_number": account_number or "",
#                     "wallet": 0.0,
#                 }
#             )
#             .select("*")
#             .execute()
#         )
#         return res.data[0] if res.data else None

#     return await asyncio.to_thread(_do)





# async def get_user_record(telegram_id: int):
#     def _do():
#         res = supabase.table("users").select("*").eq("telegram_id", telegram_id).single().execute()
#         return res.data if res.data else None
#     return await asyncio.to_thread(_do)

# async def add_funds(telegram_id: int, amount: Decimal):
#     # ensure user exists
#     user = await get_user_record(telegram_id)
#     if not user:
#         # create minimal user record if missing
#         await create_or_update_user(telegram_id, None, None, None, None)
#         user = await get_user_record(telegram_id)

#     old_balance = Decimal(str(user.get("wallet", 0) or 0))
#     new_balance = old_balance + amount

#     def _do():
#         # request select("*") so Supabase returns the updated row
#         res = (
#             supabase.table("users")
#             .update({"wallet": float(new_balance)})
#             .eq("telegram_id", telegram_id)
#             .select("*")
#             .execute()
#         )
#         if res.data and isinstance(res.data, list) and len(res.data) > 0:
#             return Decimal(str(res.data[0].get("wallet", float(new_balance))))
#         return Decimal(str(new_balance))

#     return await asyncio.to_thread(_do)



# async def deduct_fee(telegram_id: int, fee: Decimal):
#     user = await get_user_record(telegram_id)
#     if not user:
#         return None
#     balance = Decimal(str(user.get("wallet", 0)))
#     if balance < fee:
#         return None
#     new_balance = balance - fee

#     def _do():
#         res = supabase.table("users")\
#             .update({"wallet": float(new_balance)})\
#             .eq("telegram_id", telegram_id)\
#             .select("*")\
#             .execute()
#         if res.data and isinstance(res.data, list) and len(res.data) > 0:
#             return Decimal(str(res.data[0].get("wallet", float(new_balance))))
#         return Decimal(str(new_balance))
#     return await asyncio.to_thread(_do)


# async def save_score_db(telegram_id: int, score: int):
#     # Ensure user exists
#     user = await get_user_record(telegram_id)
#     if not user:
#         # create minimal user record
#         await create_or_update_user(telegram_id, None, None, None, None)
#         user = await get_user_record(telegram_id)

#     def _do():
#         user_id = user.get("id")
#         current_total = int(user.get("total_score", 0))
#         new_total = current_total + int(score)
#         # insert into scores table (if you created scores table in Supabase)
#         try:
#             supabase.table("scores").insert({"user_id": user_id, "score": int(score)}).execute()
#         except Exception:
#             # if scores table doesn't exist, ignore but still update total_score
#             pass
#         supabase.table("users").update({"total_score": new_total}).eq("id", user_id).execute()
#         return new_total
#     return await asyncio.to_thread(_do)


# async def get_leaderboard_db(limit=10):
#     def _do():
#         res = supabase.table("users").select("username,total_score").order("total_score", desc=True).limit(limit).execute()
#         return res.data if res.data else []
#     return await asyncio.to_thread(_do)


# # -----------------------
# # Quiz logic
# # -----------------------
# # async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
# #     if user_id not in user_data:
# #         return
# #     state = user_data[user_id]
# #     current = state["current"]
# #     if state.get("active") and current < len(QUIZ):
# #         q = QUIZ[current]
# #         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
# #         await context.bot.send_message(
# #             chat_id=user_id,
# #             text=f"❓ Question {current + 1}: {q['question']}",
# #             reply_markup=InlineKeyboardMarkup(keyboard),
# #         )
# #     else:
# #         score = state["score"]
# #         total = len(QUIZ)
# #         await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/{total}")
# #         state["active"] = False
# #         await save_score_db(user_id, score)


# # small helper for consistent money formatting
# def format_currency(d: Decimal) -> str:
#     try:
#         return f"{d:.2f}"
#     except Exception:
#         return str(d)


# async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
#     """Send the next question to user_id. Safe guards for empty quiz and bad question shape."""
#     # ensure user still has a session
#     if user_id not in user_data:
#         print(f"[send_question] no session for user {user_id}")
#         return

#     state = user_data[user_id]
#     current = state.get("current", 0)

#     # safety: ensure QUIZ is loaded
#     if not QUIZ:
#         await context.bot.send_message(
#             chat_id=user_id,
#             text="⚠️ Quiz questions are not available right now. Please contact the admin."
#         )
#         state["active"] = False
#         print("[send_question] QUIZ is empty or not loaded.")
#         return

#     # end condition
#     if not state.get("active") or current >= len(QUIZ):
#         score = state.get("score", 0)
#         total = len(QUIZ)
#         await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/{total}")
#         state["active"] = False
#         # persist score
#         try:
#             await save_score_db(user_id, score)
#         except Exception as e:
#             print(f"[send_question] save_score_db error for {user_id}: {e!r}")
#         return

#     # safe access to question
#     try:
#         q = QUIZ[current]
#         question_text = q.get("question", "No question text available.")
#         options = q.get("options", [])
#         if not options:
#             # fallback single-option so UI doesn't crash
#             options = ["(no options)"]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]
#     except Exception as e:
#         print(f"[send_question] failed to prepare question #{current} for {user_id}: {e!r}")
#         await context.bot.send_message(chat_id=user_id, text="⚠️ Error preparing the question. Contact admin.")
#         state["active"] = False
#         return

#     # send it
#     await context.bot.send_message(
#         chat_id=user_id,
#         text=f"❓ Question {current + 1}: {question_text}",
#         reply_markup=InlineKeyboardMarkup(keyboard),
#     )




# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id

#     if user_id not in user_data or not user_data[user_id].get("active"):
#         await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
#         return

#     state = user_data[user_id]
#     current = state["current"]
#     if current >= len(QUIZ):
#         await query.edit_message_text("This quiz is already finished.")
#         return

#     correct = QUIZ[current]["answer"]
#     selected = query.data
#     if selected == correct:
#         state["score"] += 1
#         await query.edit_message_text(f"✅ Correct! The answer is {correct}")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

#     state["current"] += 1
#     await send_question(context, user_id)


# # -----------------------
# # Commands
# # -----------------------


# async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     row = await get_user_record(update.effective_user.id)
#     if not row:
#         await update.message.reply_text("⚠️ Not registered. Use /register.")
#         return
#     # wallet = row.get("wallet", 0)
#     wallet = Decimal(str(row.get("wallet", 0)))
#     total_score = row.get("total_score", 0)
#     await update.message.reply_text(f"💰 Balance: {Decimal(str(wallet))}\n🏅 Total score: {total_score}")



# async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
#     args = context.args

#     if not args:
#         await update.message.reply_text("⚠️ Usage: /fund <amount>")
#         return

#     # Accept formats like "1,000", "₦1000", "$10.50"
#     amt_raw = args[0].strip().replace(",", "")
#     amt_raw = re.sub(r"[^\d.]", "", amt_raw)  # keep only digits and "."

#     try:
#         amount = Decimal(amt_raw)
#     except Exception:
#         await update.message.reply_text("⚠️ Amount must be a number.")
#         return

#     if amount <= 0:
#         await update.message.reply_text("⚠️ Amount must be positive.")
#         return

#     # Ensure user exists
#     await create_or_update_user(
#         telegram_id=user.id,
#         username=user.username,
#         account_number=None,
#         first_name=user.first_name
#     )

#     try:
#         # Add funds in Supabase
#         new_balance = await add_funds(user.id, amount)
#     except Exception as e:
#         print("fund_command error:", repr(e))  # log for debugging
#         await update.message.reply_text("⚠️ Could not add funds due to an internal error.")
#         return

#     # Show success message
#     await update.message.reply_text(
#         f"✅ You funded {amount}. Your new balance is {new_balance}."
#     )




#     # ensure user exists


# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "👋 Welcome to the Quiz Bot!\n\n"
#         "/register - Register your account\n"
#         "/fund <amount> - Add funds\n"
#         "/balance - Check your balance\n"
#         "/play - Pay fee & start the quiz\n"
#         "/table - View leaderboard\n"
#         "/end - End quiz\n"
#         "/help - Show all commands"
#     )



# async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Attempt to charge the quiz fee and start a quiz session. Includes diagnostics/logging."""
#     user = update.effective_user
#     uid = user.id

#     # Ensure user exists (create minimal record if missing)
#     try:
#         await create_or_update_user(uid, user.username, None, user.first_name)
#     except Exception as e:
#         print(f"[play_command] create_or_update_user failed for {uid}: {e!r}")
#         await update.message.reply_text("⚠️ Internal error when preparing your account. Try again later.")
#         return

#     # ensure there are quiz questions
#     if not QUIZ:
#         await update.message.reply_text("⚠️ No quiz questions are available right now. Please contact the admin.")
#         print("[play_command] QUIZ empty — cannot start quiz.")
#         return

#     # fetch latest wallet
#     row = await get_user_record(uid)
#     if not row:
#         await update.message.reply_text("⚠️ Not registered. Use /register.")
#         return

#     try:
#         balance = Decimal(str(row.get("wallet", 0)))
#     except Exception as e:
#         print(f"[play_command] invalid wallet for {uid}: {row.get('wallet')!r} ({e!r})")
#         await update.message.reply_text("⚠️ Your wallet balance is invalid. Contact admin.")
#         return

#     # check balance
#     if balance < QUIZ_FEE:
#         await update.message.reply_text(
#             f"💰 Insufficient funds ({format_currency(balance)}). Need {format_currency(QUIZ_FEE)}. Use /fund <amount>."
#         )
#         return

#     # attempt deduction with clear error handling
#     try:
#         new_balance = await deduct_fee(uid, QUIZ_FEE)
#     except Exception as e:
#         print(f"[play_command] deduct_fee exception for {uid}: {e!r}")
#         await update.message.reply_text("⚠️ Could not deduct fee due to an internal error. Try again later.")
#         return

#     if new_balance is None:
#         # deduct_fee returns None when balance is insufficient OR user not found
#         # re-check current balance and report
#         latest = await get_user_record(uid)
#         latest_bal = Decimal(str(latest.get("wallet", 0))) if latest else Decimal("0")
#         print(f"[play_command] deduct_fee returned None for {uid}; balance={latest_bal}")
#         await update.message.reply_text(
#             f"⚠️ Could not deduct fee. Your balance is {format_currency(latest_bal)}. Need {format_currency(QUIZ_FEE)}."
#         )
#         return

#     # initialize in-memory session and start
#     user_data[uid] = {"score": 0, "current": 0, "active": True}
#     await update.message.reply_text(f"✅ Fee {format_currency(QUIZ_FEE)} deducted. Starting quiz. Balance: {format_currency(new_balance)}")
#     # send first question
#     await send_question(context, uid)


# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if user_id not in user_data or not user_data[user_id].get("active"):
#         await update.message.reply_text("Not in a quiz session.")
#         return
#     score = user_data[user_id]["score"]
#     await save_score_db(user_id, score)
#     user_data[user_id]["active"] = False
#     await update.message.reply_text(f"✅ Quiz ended. Score: {score}")


# async def table_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     rows = await get_leaderboard_db(10)
#     if not rows:
#         await update.message.reply_text("No scores yet.")
#         return
#     msg = "🏆 Leaderboard 🏆\n"
#     for i, r in enumerate(rows, start=1):
#         msg += f"{i}. {r.get('username') or 'Anonymous'} — {r.get('total_score', 0)} pts\n"
#     await update.message.reply_text(msg)


# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "/register [username] - Register\n"
#         "/fund <amount> - Add funds\n"
#         "/balance - Check balance\n"
#         f"/start - Pay {QUIZ_FEE} and play\n"
#         "/end - End quiz\n"
#         "/table - Leaderboard\n"
#     )


# async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Use /help for commands.")


# # -----------------------
# # Registration conversation handlers
# # -----------------------
# def _is_valid_email(email: str) -> bool:
#     return re.match(r"^[^@]+@[^@]+\.[^@]+$", email) is not None

# async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Entry point for /register conversation"""
#     user = update.effective_user
#     existing = await get_user_record(user.id)
#     if existing:
#         await update.message.reply_text(
#             "You are already registered. Send /cancel to abort or reply 'yes' to update your details.\n"
#             "Reply 'yes' to update or /cancel to stop."
#         )
#         context.user_data["reg"] = {"updating": True}
#         return USERNAME

#     context.user_data["reg"] = {"updating": False}
#     await update.message.reply_text(
#         "Welcome — let's register you!\n"
#         "Send your preferred username, or send /skip to use your Telegram username."
#     )
#     return USERNAME


# async def username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text.strip()
#     if text.lower() in ("/skip", "skip"):
#         username = update.effective_user.username or None
#     else:
#         username = text
#     context.user_data["reg"]["username"] = username
#     await update.message.reply_text("Send your account number (or /skip to skip):")
#     return ACCOUNT


# async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text.strip()
#     if text.lower() in ("/skip", "skip"):
#         account_number = None
#     else:
#         account_number = text
#     context.user_data["reg"]["account_number"] = account_number
#     await update.message.reply_text("Send your email address (this is required):")
#     return EMAIL


# async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     email = update.message.text.strip()
#     if not _is_valid_email(email):
#         await update.message.reply_text("That's not a valid email. Please send a valid email address.")
#         return EMAIL
#     context.user_data["reg"]["email"] = email

#     summary = context.user_data["reg"]
#     await update.message.reply_text(
#         "Please confirm your details:\n"
#         f"Username: {summary.get('username')}\n"
#         f"Account number: {summary.get('account_number') or '(none)'}\n"
#         f"Email: {summary.get('email')}\n\n"
#         "Send 'yes' to confirm and save, or 'no' to cancel."
#     )
#     return CONFIRM


# async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     answer = update.message.text.strip().lower()
#     if answer not in ("yes", "y"):
#         await update.message.reply_text("Registration cancelled. No changes were made.")
#         context.user_data.pop("reg", None)
#         return ConversationHandler.END

#     reg = context.user_data.get("reg", {})
#     username = reg.get("username")
#     account_number = reg.get("account_number")
#     email = reg.get("email")
#     user = update.effective_user

#     # Save to Supabase
#     await create_or_update_user(user.id, username, account_number, user.first_name, email)
#     context.user_data.pop("reg", None)
#     await update.message.reply_text("✅ Registered successfully! Thank you.")
#     return ConversationHandler.END


# async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data.pop("reg", None)
#     await update.message.reply_text("Registration cancelled.")
#     return ConversationHandler.END


# # -----------------------
# # Admin commands (using Supabase)
# # -----------------------
# async def _is_admin(user_id: int) -> bool:
#     return user_id in ADMIN_IDS

# async def export_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     uid = update.effective_user.id
#     if not await _is_admin(uid):
#         await update.message.reply_text("Unauthorized.")
#         return

#     def _do():
#         res = supabase.table("users").select("telegram_id,username,email,account_number,first_name,wallet,total_score,created_at").order("id").execute()
#         return res.data if res.data else []
#     rows = await asyncio.to_thread(_do)

#     if not rows:
#         await update.message.reply_text("No users found.")
#         return

#     sio = io.StringIO()
#     writer = csv.writer(sio)
#     writer.writerow(['telegram_id', 'username', 'email', 'account_number', 'first_name', 'wallet', 'total_score', 'created_at'])
#     for r in rows:
#         writer.writerow([
#             r.get('telegram_id'),
#             r.get('username') or "",
#             r.get('email') or "",
#             r.get('account_number') or "",
#             r.get('first_name') or "",
#             str(r.get('wallet')) if r.get('wallet') is not None else "0",
#             r.get('total_score') or 0,
#             r.get('created_at') or ""
#         ])

#     bio = io.BytesIO(sio.getvalue().encode())
#     bio.name = "users_export.csv"
#     bio.seek(0)
#     await update.message.reply_document(document=bio, filename="users_export.csv")


# async def users_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     uid = update.effective_user.id
#     if not await _is_admin(uid):
#         await update.message.reply_text("Unauthorized.")
#         return
#     limit = 20
#     if context.args and context.args[0].isdigit():
#         limit = min(100, int(context.args[0]))  # allow admin to request more up to 100

#     def _do():
#         res = supabase.table("users").select("username,total_score").order("total_score", desc=True).limit(limit).execute()
#         return res.data if res.data else []
#     rows = await asyncio.to_thread(_do)

#     if not rows:
#         await update.message.reply_text("No users yet.")
#         return
#     msg = "🏆 Leaderboard 🏆\n"
#     for i, r in enumerate(rows, start=1):
#         msg += f"{i}. {r.get('username') or 'Anonymous'} — {r.get('total_score', 0)} pts\n"
#     await update.message.reply_text(msg)


# # -----------------------
# # Main setup + run
# # -----------------------
# async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     rows = await get_leaderboard_db(10)
#     if not rows:
#         await update.message.reply_text("🏆 No scores yet.")
#         return
#     board = "\n".join([f"{i+1}. {r.get('username') or 'Anonymous'} — {r.get('total_score', 0)} pts"
#                        for i, r in enumerate(rows)])
#     await update.message.reply_text("🏆 Leaderboard:\n" + board)


# def main():
#     app = Application.builder().token(TOKEN).build()

    
#     # Conversation for registration
#     reg_conv = ConversationHandler(
#         entry_points=[CommandHandler("register", register_start)],
#         states={
#             USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username_handler)],
#             ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_handler)],
#             EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_handler)],
#             CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)],
#         },
#         fallbacks=[CommandHandler("cancel", cancel_registration)],
#         allow_reentry=True,
#     )

#     # Handlers
#     app.add_handler(reg_conv)
#     app.add_handler(CommandHandler("start", start_command))       # welcome/help
#     app.add_handler(CommandHandler("play", play_command))
#     app.add_handler(CommandHandler("fund", fund_command))
#     app.add_handler(CommandHandler("balance", balance_command))
#     app.add_handler(CommandHandler("end", end_command))
#     app.add_handler(CommandHandler("table", table_command))
#     app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
#     app.add_handler(CommandHandler("help", help_command))
#     app.add_handler(CommandHandler("export_users", export_users_command))
#     app.add_handler(CommandHandler("users", users_admin_command))
#     app.add_handler(CallbackQueryHandler(handle_answer))
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

#     print("🤖 Bot is running...")
#     app.run_polling(close_loop=False)  # keep loop open


# if __name__ == "__main__":
#     main()












































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
