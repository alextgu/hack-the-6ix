import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GREETING = (
    "Kon'nichiwa! I am Tabi! plan your trip to your japan "
    "or I will be very unhappy"
)


async def on_added_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_id = context.bot.id
    for member in update.message.new_chat_members:
        if member.id == bot_id:
            await update.message.chat.send_message(GREETING)


async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    print(f"{user.full_name}: {update.message.text}")


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_added_to_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_group_message))
    app.run_polling()


if __name__ == "__main__":
    main()
