




#postgresql://postgres:[o7ssKZVE16PIKzZX]@db.duvzrsxrhjbqqlvdwkyg.supabase.co:5432/postgres


#DB PASSWORD = o7ssKZVE16PIKzZX
# import json
# import asyncpg
# import asyncio
# from datetime import datetime
# from typing import Final
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes



# DB_URL = "postgresql://postgres:o7ssKZVE16PIKzZX@db.duvzrsxrhjbqqlvdwkyg.supabase.co:5432/postgres"  # from Supabase




# from datetime import datetime

# def is_within_hours():
#     now = datetime.now().hour
#     return 8 <= now < 20  # between 8AM and 8PM

# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if not is_within_hours():
#         await update.message.reply_text("⏳ The bot is available between 8AM and 8PM daily. Please come back then.")
#         return
#     # normal behavior
#     await update.message.reply_text("🎉 Welcome to the Quiz! Let's begin...")







# async def init_db():
#     return await asyncpg.create_pool(DB_URL)

# async def register_user(pool, telegram_id, username, account_number):
#     async with pool.acquire() as conn:
#         await conn.execute("""
#             INSERT INTO users (telegram_id, username, account_number)
#             VALUES ($1, $2, $3)
#             ON CONFLICT (telegram_id) DO NOTHING
#         """, telegram_id, username, account_number)

# async def save_score(pool, telegram_id, score):
#     async with pool.acquire() as conn:
#         user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
#         if user:
#             await conn.execute("""
#                 INSERT INTO scores (user_id, score) VALUES ($1, $2)
#             """, user["id"], score)

# async def get_leaderboard(pool):
#     async with pool.acquire() as conn:
#         rows = await conn.fetch("""
#             SELECT u.username, SUM(s.score) as total_score
#             FROM users u
#             JOIN scores s ON u.id = s.user_id
#             GROUP BY u.username
#             ORDER BY total_score DESC
#             LIMIT 10
#         """)
#         return rows





# TOKEN: Final = "7998359586:AAFBFpjdvmZqBEvZxNmeaWiEhTnCBthG_Rc"  # use env variable in production
# BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"

# # Question Bank
# with open("questions.json", "r") as f:
#     QUIZ = json.load(f)

# # Store user progress
# user_data = {}

# # Start the quiz
# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     user_data[user_id] = {"score": 0, "current": 0, "active": True}
#     await update.message.reply_text("🎉 Welcome to the Quiz! Let's begin...")
#     await send_question(update, context, user_id)

# # End the quiz anytime
# async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.message.chat_id

#     if user_id not in user_data or not user_data[user_id].get("active", False):
#         await update.message.reply_text("❌ You are not currently in a quiz session.")
#         return

#     score = user_data[user_id]["score"]
#     total_answered = user_data[user_id]["current"]

#     await update.message.reply_text(
#         f"✅ Quiz ended!\n\nYou answered {total_answered} questions.\nYour final score: {score}"
#     )

#     # Reset user session
#     user_data[user_id]["active"] = False

# # Send a question
# async def send_question(update, context, user_id):
#     current = user_data[user_id]["current"]

#     if current < len(QUIZ) and user_data[user_id]["active"]:
#         q = QUIZ[current]
#         keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         await context.bot.send_message(
#             chat_id=user_id,
#             text=f"❓ Question {current+1}: {q['question']}",
#             reply_markup=reply_markup
#         )
#     else:
#         score = user_data[user_id]["score"]
#         total = len(QUIZ)
#         await context.bot.send_message(
#             chat_id=user_id,
#             text=f"✅ Quiz finished!\nYour score: {score}/{total}"
#         )
#         user_data[user_id]["active"] = False

# # Handle answers
# async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()

#     user_id = query.from_user.id

#     if user_id not in user_data or not user_data[user_id].get("active", False):
#         await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
#         return

#     current = user_data[user_id]["current"]
#     correct = QUIZ[current]["answer"]

#     if query.data == correct:
#         user_data[user_id]["score"] += 1
#         await query.edit_message_text(f"✅ Correct! The answer is {correct}")
#     else:
#         await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

#     # Move to next question
#     user_data[user_id]["current"] += 1
#     await send_question(update, context, user_id)

# # Main entry
# def main():
#     print("Starting bot...")
#     app = Application.builder().token(TOKEN).build()

#     app.add_handler(CommandHandler("start", start_command))
#     app.add_handler(CommandHandler("end", end_command))
#     app.add_handler(CallbackQueryHandler(handle_answer))

#     print("Polling...")
#     app.run_polling()

# if __name__ == "__main__":
#     main()




















































import json
import asyncpg
import asyncio
from datetime import datetime
from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------
# CONFIG - replace with env vars in production
# ---------------------------
DB_URL = "postgresql://postgres:o7ssKZVE16PIKzZX@db.duvzrsxrhjbqqlvdwkyg.supabase.co:5432/postgres"  # from Supabase
TOKEN: Final = "7998359586:AAFBFpjdvmZqBEvZxNmeaWiEhTnCBthG_Rc"  # your bot token
BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"
# ---------------------------

# load question bank (ensure questions.json is in same folder)
with open("questions.json", "r", encoding="utf-8") as f:
    QUIZ = json.load(f)

# Globals
db_pool: asyncpg.pool.Pool | None = None
user_data = {}  # in-memory session state { telegram_id: {score, current, active} }

# ---------------------------
# Utility: working hours check
# ---------------------------
from datetime import datetime as _dt
def is_within_hours():
    now = _dt.now().hour
    return 8 <= now < 20  # between 8AM and 8PM

# ---------------------------
# Database helpers
# ---------------------------
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    # You should have created the tables beforehand (schema.sql). This function does not create tables.
    # If you prefer to auto-create tables here, I can add the SQL create statements.

async def register_user(pool, telegram_id: int, username: str, account_number: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, account_number)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username,
                account_number = EXCLUDED.account_number
        """, telegram_id, username, account_number)

async def save_score(pool, telegram_id: int, score: int, category: str = None):
    # Save a row linking the user (by telegram_id) to a score
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
        if user:
            user_id = user["id"]
            # If you have a scores table with (user_id, score, created_at) use this:
            await conn.execute("""
                INSERT INTO scores (user_id, score)
                VALUES ($1, $2)
            """, user_id, score)
        else:
            # User not registered: optionally create a user row with null username/account
            res = await conn.fetchrow(
                "INSERT INTO users (telegram_id, username, account_number) VALUES ($1, $2, $3) RETURNING id",
                telegram_id, None, None
            )
            if res:
                await conn.execute("INSERT INTO scores (user_id, score) VALUES ($1, $2)", res["id"], score)

async def get_leaderboard(pool, limit: int = 10):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.username, COALESCE(SUM(s.score),0) AS total_score
            FROM users u
            LEFT JOIN scores s ON u.id = s.user_id
            GROUP BY u.username
            ORDER BY total_score DESC
            LIMIT $1
        """, limit)
        return rows

# ---------------------------
# Bot commands & flow
# ---------------------------

# /register command
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_within_hours():
        await update.message.reply_text("⏳ The bot is available between 8AM and 8PM daily. Please come back then.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /register <username> <account_number>")
        return

    username = args[0]
    account_number = args[1]
    tg_id = update.effective_user.id

    if db_pool is None:
        await update.message.reply_text("Database not connected yet. Try again in a moment.")
        return

    await register_user(db_pool, tg_id, username, account_number)
    await update.message.reply_text(f"✅ Registered as *{username}* with account number *{account_number}*.", parse_mode="Markdown")

# /balance - optional helper if you add wallet column later
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db_pool is None:
        await update.message.reply_text("Database not connected yet.")
        return
    tg_id = update.effective_user.id
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT wallet_balance FROM users WHERE telegram_id=$1", tg_id)
        if not row:
            await update.message.reply_text("You are not registered. Use /register first.")
            return
        bal = row["wallet_balance"] or 0
        await update.message.reply_text(f"💰 Wallet balance: {bal:.2f}")

# Start (begin quiz) - reuses start flow but ensures hours
async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_within_hours():
        await update.message.reply_text("⏳ The bot is available between 8AM and 8PM daily. Please come back then.")
        return

    user_id = update.effective_user.id
    # initialize session (questions are taken in order from QUIZ for now)
    user_data[user_id] = {"score": 0, "current": 0, "active": True}
    await update.message.reply_text("🎉 Welcome to the Quiz! Let's begin...")
    await send_question(update, context, user_id)

# End command - ends quiz and saves score
async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data or not user_data[user_id].get("active", False):
        await update.message.reply_text("❌ You are not currently in a quiz session.")
        return

    score = user_data[user_id]["score"]
    total_answered = user_data[user_id]["current"]

    # Save to DB
    if db_pool is not None:
        await save_score(db_pool, user_id, score)

    await update.message.reply_text(
        f"✅ Quiz ended!\n\nYou answered {total_answered} questions.\nYour final score: {score}"
    )

    # Reset user session
    user_data[user_id]["active"] = False

# Send a question
async def send_question(update_or_context, context_or_user, user_id=None):
    """
    Called from either command context or callback context.
    We'll normalize parameters:
      - If called as send_question(update, context, user_id) earlier, keep that.
      - If called as send_question(context, tg_id), adjust.
    To keep it simple we accept two calling styles in your code base.
    """
    # Determine actual context and user_id
    # Case 1: called as send_question(update, context, user_id)
    if user_id is None:
        # update_or_context = update, context_or_user = context, user_id is None
        update = update_or_context
        context = context_or_user
        user_id = update.effective_user.id
    else:
        # called as send_question(update, context, user_id) OR send_question(context, user_id)
        update = None
        context = context_or_user

    if user_id not in user_data or not user_data[user_id].get("active", False):
        # nothing to do
        return

    current = user_data[user_id]["current"]

    if current < len(QUIZ) and user_data[user_id]["active"]:
        q = QUIZ[current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # send message via context.bot
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current+1}: {q['question']}",
            reply_markup=reply_markup
        )
    else:
        # finished all questions - save score and inform user
        score = user_data[user_id]["score"]
        total = len(QUIZ)
        if db_pool is not None:
            await save_score(db_pool, user_id, score)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Quiz finished!\nYour score: {score}/{total}"
        )
        user_data[user_id]["active"] = False

# Handle callback answers
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in user_data or not user_data[user_id].get("active", False):
        await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
        return

    current = user_data[user_id]["current"]
    # guard index
    if current >= len(QUIZ):
        await query.edit_message_text("No more questions left.")
        user_data[user_id]["active"] = False
        return

    correct = QUIZ[current]["answer"]
    selected = query.data

    if selected == correct:
        user_data[user_id]["score"] += 1
        await query.edit_message_text(f"✅ Correct! The answer is {correct}")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

    # Move to next question
    user_data[user_id]["current"] += 1
    # send next question (use context and user_id)
    await send_question(None, context, user_id)

# /table command - leaderboard
async def table_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db_pool is None:
        await update.message.reply_text("Database not available.")
        return
    rows = await get_leaderboard(db_pool)
    if not rows:
        await update.message.reply_text("No scores yet!")
        return
    message = "🏆 Leaderboard\n\n"
    for i, r in enumerate(rows, start=1):
        username = r["username"] or "unknown"
        total = float(r["total_score"] or 0)
        message += f"{i}. {username} — {total:.0f}\n"
    await update.message.reply_text(message)

# ---------------------------
# Main: init DB pool and start bot
# ---------------------------
def main():
    global db_pool
    print("Starting bot...")

    # Initialize DB pool (async) before starting the bot
    loop = asyncio.get_event_loop()
    db_pool = loop.run_until_complete(init_db())

    app = Application.builder().token(TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("start", start_quiz_command))  # start quiz
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("table", table_command))

    # Callback handler for answers (buttons)
    app.add_handler(CallbackQueryHandler(handle_answer))

    print("Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
