import logging
import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SPREADSHEET_NAME).worksheet("Test June 2025")

AMOUNT, CATEGORY, COMMENT = range(3)

CATEGORIES = ["Groceries", "Entertainment"]

async def track_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END

    await update.message.reply_text("How much did you spend today?")
    return AMOUNT

# Handle amount input
async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount

        keyboard = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select a category:", reply_markup=reply_markup)
        return CATEGORY

    except ValueError:
        await update.message.reply_text("Please enter a valid number from 0")
        return AMOUNT

# Handle category selection
async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    context.user_data['category'] = category

    await query.edit_message_text("Got it. Now add a comment (optional, or type nothing to skip):")
    return COMMENT

# Handle comment and save to Google Sheet
async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    if comment.strip() == "":
        comment = ""
    context.user_data['comment'] = comment

    amount = context.user_data['amount']
    category = context.user_data['category']
    date_str = update.message.date.strftime("%Y-%m-%d")

    try:
        sheet.append_row([date_str, amount, category, comment])
        await update.message.reply_text(
            f"✅ You spent €{amount:.2f} on {category}, with comment: \"{comment}\""
        )
    except Exception as e:
        logger.error(f"Error writing to sheet: {e}")
        await update.message.reply_text("Something went wrong saving to Google Sheets.")

    context.user_data.clear()
    return ConversationHandler.END

# Handle /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ALLOWED_USER_ID:
        await update.message.reply_text(
            "Hello! Use /track to log an expense.\n"
            "You will be asked for amount, then category, then an optional comment.\n"
            "Use /cancel anytime to stop."
        )
    else:
        await update.message.reply_text("Unauthorized.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("track", track_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            CATEGORY: [CallbackQueryHandler(receive_category)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
