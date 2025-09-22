import os
import json
import asyncio
from decimal import Decimal
from typing import Final
from dotenv import load_dotenv

import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# -----------------------
# Config
# -----------------------
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # Railway-provided Postgres URL

if not TOKEN:
    raise RuntimeError("Environment variable TOKEN is required.")
if not DATABASE_URL:
    raise RuntimeError("Environment variable DATABASE_URL is required.")

QUIZ_FEE: Final = Decimal("100")  # quiz entry fee

# -----------------------
# Load questions.json
# -----------------------
QUESTIONS_FILE = "questions.json"
try:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        QUIZ = json.load(f)
except FileNotFoundError:
    print(f"ERROR: {QUESTIONS_FILE} not found. Place questions.json alongside main.py.")
    QUIZ = []

# -----------------------
# In-memory user state
# -----------------------
user_data: dict = {}  # telegram_id -> {"score": int, "current": int, "active": bool}

db_pool: asyncpg.pool.Pool | None = None  # global pool


# -----------------------
# Database
# -----------------------
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    print("✅ Connected to PostgreSQL")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                account_number TEXT,
                first_name TEXT,
                wallet NUMERIC DEFAULT 0,
                total_score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )

    print("📦 DB tables ensured")


async def get_user_record(telegram_id: int):
    global db_pool
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", telegram_id)


async def create_or_update_user(telegram_id, username, account_number, first_name):
    global db_pool
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, account_number, first_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username,
                account_number = COALESCE(EXCLUDED.account_number, users.account_number),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name)
            """,
            telegram_id, username, account_number, first_name,
        )


async def add_funds(telegram_id: int, amount: Decimal):
    global db_pool
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", telegram_id)
        await conn.execute(
            "UPDATE users SET wallet = wallet + $1 WHERE telegram_id = $2",
            str(amount), telegram_id,
        )
        row = await conn.fetchrow("SELECT wallet FROM users WHERE telegram_id=$1", telegram_id)
        return Decimal(row["wallet"])


async def deduct_fee(telegram_id: int, fee: Decimal):
    global db_pool
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT wallet FROM users WHERE telegram_id=$1 FOR UPDATE", telegram_id)
        if not row:
            return None
        balance = Decimal(row["wallet"])
        if balance < fee:
            return None
        new_balance = balance - fee
        await conn.execute("UPDATE users SET wallet = $1 WHERE telegram_id = $2", str(new_balance), telegram_id)
        return new_balance


async def save_score_db(telegram_id: int, score: int):
    global db_pool
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
        if not user:
            await conn.execute("INSERT INTO users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", telegram_id)
            user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id=$1", telegram_id)
        if user:
            await conn.execute("INSERT INTO scores (user_id, score) VALUES ($1, $2)", user["id"], score)
            await conn.execute("UPDATE users SET total_score = total_score + $1 WHERE id = $2", score, user["id"])


async def get_leaderboard_db(limit: int = 10):
    global db_pool
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT $1", limit
        )


# -----------------------
# Quiz logic
# -----------------------
async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if user_id not in user_data:
        return
    state = user_data[user_id]
    current = state["current"]
    if state.get("active") and current < len(QUIZ):
        q = QUIZ[current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current + 1}: {q['question']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        score = state["score"]
        total = len(QUIZ)
        await context.bot.send_message(chat_id=user_id, text=f"✅ Quiz finished!\nYour score: {score}/{total}")
        state["active"] = False
        await save_score_db(user_id, score)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data or not user_data[user_id].get("active"):
        await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
        return

    state = user_data[user_id]
    current = state["current"]
    if current >= len(QUIZ):
        await query.edit_message_text("This quiz is already finished.")
        return

    correct = QUIZ[current]["answer"]
    selected = query.data
    if selected == correct:
        state["score"] += 1
        await query.edit_message_text(f"✅ Correct! The answer is {correct}")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

    state["current"] += 1
    await send_question(context, user_id)


# -----------------------
# Commands
# -----------------------
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    username = args[0] if len(args) >= 1 else user.username
    account_number = args[1] if len(args) >= 2 else None
    await create_or_update_user(user.id, username, account_number, user.first_name)
    await update.message.reply_text("✅ Registered successfully!")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = await get_user_record(update.effective_user.id)
    if not row:
        await update.message.reply_text("⚠️ Not registered. Use /register.")
        return
    await update.message.reply_text(f"💰 Balance: {Decimal(row['wallet'])}")


async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /fund <amount>")
        return
    try:
        amount = Decimal(context.args[0])
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("Invalid amount.")
        return
    await create_or_update_user(update.effective_user.id, update.effective_user.username, None, update.effective_user.first_name)
    new_balance = await add_funds(update.effective_user.id, amount)
    await update.message.reply_text(f"✅ New balance: {new_balance}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = await get_user_record(user.id)
    if not row:
        await update.message.reply_text("⚠️ Not registered. Use /register.")
        return
    balance = Decimal(row["wallet"])
    if balance < QUIZ_FEE:
        await update.message.reply_text(f"💰 Insufficient funds ({balance}). Need {QUIZ_FEE}. Use /fund <amount>.")
        return
    new_balance = await deduct_fee(user.id, QUIZ_FEE)
    if new_balance is None:
        await update.message.reply_text("⚠️ Could not deduct fee.")
        return
    user_data[user.id] = {"score": 0, "current": 0, "active": True}
    await update.message.reply_text(f"✅ Fee deducted. Starting quiz. Balance: {new_balance}")
    await send_question(context, user.id)


async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data or not user_data[user_id].get("active"):
        await update.message.reply_text("Not in a quiz session.")
        return
    score = user_data[user_id]["score"]
    await save_score_db(user_id, score)
    user_data[user_id]["active"] = False
    await update.message.reply_text(f"✅ Quiz ended. Score: {score}")


async def table_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await get_leaderboard_db()
    if not rows:
        await update.message.reply_text("No scores yet.")
        return
    msg = "🏆 Leaderboard 🏆\n"
    for i, r in enumerate(rows, start=1):
        msg += f"{i}. {r['username'] or 'Anonymous'} — {r['total_score']} pts\n"
    await update.message.reply_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/register [username] - Register\n"
        "/fund <amount> - Add funds\n"
        "/balance - Check balance\n"
        f"/start - Pay {QUIZ_FEE} and play\n"
        "/end - End quiz\n"
        "/table - Leaderboard\n"
    )


async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /help for commands.")


# -----------------------
# Setup + run
# ... your imports remain the same ...

# -----------------------
# Setup + run
# -----------------------
# -----------------------
# Setup + run
# -----------------------
# -----------------------
# Setup + run
# -----------------------
async def on_startup(app: Application):
    """Runs when the bot starts (inside PTB's loop)."""
    await init_db()   # Now db_pool lives in the correct loop
    print("🚀 Startup tasks done")


def main():
    # Create application
    app = Application.builder().token(TOKEN).post_init(on_startup).build()

    # Handlers
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("table", table_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

    print("🤖 Bot is running...")
    app.run_polling(close_loop=False)  # keep loop open


if __name__ == "__main__":
    main()














