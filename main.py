

# from typing import Final
# from telegram import Update
# from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# TOKEN: Final = '7998359586:AAFBFpjdvmZqBEvZxNmeaWiEhTnCBthG_Rc'
# BOT_USERNAME: Final = '@Icon_Ayce_Org_Bot'


# #Commands
# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text('I am your quiz bot! Please type something so i can respond!')

# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text('I am your quiz bot! Please type something so i can respond!')

# async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text('This is a custom command!')


#     #Responses

# def handle_response(text: str) -> str:
#         processed: str = text.lower()

#         if 'hello' in processed:
#             return 'Hey there!'
        
#         if 'how are you' in processed:
#             return 'I am good!'
        
#         if 'i love python' in processed:
#             return 'Remember to suscribe!'
        
#         return 'I do not understand what you wrote...'
    

# async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     message_type: str = update.message.chat.type
#     text: str = update.message.text

#     print(f'User ({update.message.chat.id}) in {message_type}: "{text}"')

#     if message_type == 'group':
#         if BOT_USERNAME in text:
#             new_text: str = text.replace(BOT_USERNAME, "").strip()
#             responce: str = handle_response(new_text)
#         else:
#             return
#     else:
#         responce: str = handle_response(text)

#     print('Bot:', responce)
#     await update.message.reply_text(responce)


# async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     print(f'Update {update} caused error {context.error}')


# if __name__ == '__main__':
#     print('Starting bot...')
#     app = Application.builder().token(TOKEN).build()

#     app.add_handler(CommandHandler('start', start_command))
#     app.add_handler(CommandHandler('help', help_command))
#     app.add_handler(CommandHandler('custom', custom_command))

#     #Messages
#     app.add_handler(MessageHandler(filters.TEXT, handle_message))

#     #Errors
#     app.add_error_handler(error)

#     #Polls the bot
#     print('Polling...') 
#     app.run_polling(poll_interval=3)






import json
from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


TOKEN: Final = "7998359586:AAFBFpjdvmZqBEvZxNmeaWiEhTnCBthG_Rc"  # use env variable in production
BOT_USERNAME: Final = "@Icon_Ayce_Org_Bot"

# Question Bank
with open("questions.json", "r") as f:
    QUIZ = json.load(f)

# Store user progress
user_data = {}

# Start the quiz
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"score": 0, "current": 0, "active": True}
    await update.message.reply_text("🎉 Welcome to the Quiz! Let's begin...")
    await send_question(update, context, user_id)

# End the quiz anytime
async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    if user_id not in user_data or not user_data[user_id].get("active", False):
        await update.message.reply_text("❌ You are not currently in a quiz session.")
        return

    score = user_data[user_id]["score"]
    total_answered = user_data[user_id]["current"]

    await update.message.reply_text(
        f"✅ Quiz ended!\n\nYou answered {total_answered} questions.\nYour final score: {score}"
    )

    # Reset user session
    user_data[user_id]["active"] = False

# Send a question
async def send_question(update, context, user_id):
    current = user_data[user_id]["current"]

    if current < len(QUIZ) and user_data[user_id]["active"]:
        q = QUIZ[current]
        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in q["options"]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"❓ Question {current+1}: {q['question']}",
            reply_markup=reply_markup
        )
    else:
        score = user_data[user_id]["score"]
        total = len(QUIZ)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Quiz finished!\nYour score: {score}/{total}"
        )
        user_data[user_id]["active"] = False

# Handle answers
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in user_data or not user_data[user_id].get("active", False):
        await query.edit_message_text("❌ You are not in an active quiz. Type /start to begin.")
        return

    current = user_data[user_id]["current"]
    correct = QUIZ[current]["answer"]

    if query.data == correct:
        user_data[user_id]["score"] += 1
        await query.edit_message_text(f"✅ Correct! The answer is {correct}")
    else:
        await query.edit_message_text(f"❌ Wrong! The correct answer is {correct}")

    # Move to next question
    user_data[user_id]["current"] += 1
    await send_question(update, context, user_id)

# Main entry
def main():
    print("Starting bot...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CallbackQueryHandler(handle_answer))

    print("Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()




