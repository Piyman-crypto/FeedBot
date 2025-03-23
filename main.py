import asyncio
import logging
import sqlite3
import ssl
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router
from aiogram.client.default import DefaultBotProperties

# Bot Token from BotFather
TOKEN = "7368574598:AAHfSaHrz6iZ--sfZpVpctqEJwaUO2lwxvQ"

# Initialize bot and dispatcher with SSL support
ssl_context = ssl.create_default_context()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Define states
class UserData(StatesGroup):
    user_id = State()
    channel_id = State()
    keywords = State()

# Function to save data in database
def save_data(user_id, channel_id, keywords):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id TEXT, channel_id TEXT, keywords TEXT)")
    cursor.execute("INSERT INTO users (user_id, channel_id, keywords) VALUES (?, ?, ?)", (user_id, channel_id, keywords))
    conn.commit()
    conn.close()

# Start command
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await message.answer("Hello! I can forward messages from channels. Please enter the target Telegram **User ID**:")
    await state.set_state(UserData.user_id)

# Capture User ID
@router.message(UserData.user_id, F.text.isdigit())  # Ensure it's a number
async def get_user_id(message: Message, state: FSMContext):
    await state.update_data(user_id=message.text)
    await message.answer("Now, send me your **Private Channel ID** (starts with -100):")
    await state.set_state(UserData.channel_id)

# Capture Channel ID
@router.message(UserData.channel_id, F.text.startswith("-100"))  # Ensure valid format
async def get_channel_id(message: Message, state: FSMContext):
    await state.update_data(channel_id=message.text)
    await message.answer("Now, enter **keywords** separated by commas (optional, leave empty for all messages):")
    await state.set_state(UserData.keywords)

# Capture Keywords
@router.message(UserData.keywords)
async def get_keywords(message: Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data["user_id"]
    channel_id = user_data["channel_id"]
    keywords = message.text if message.text.strip() else None
    
    # Save data to database
    save_data(user_id, channel_id, keywords)
    
    await message.answer(f"✅ Data saved!\n- **User ID:** {user_id}\n- **Channel ID:** {channel_id}\n- **Keywords:** {keywords if keywords else 'No filter'}")
    await state.clear()

# Forward messages from saved channel to user with keyword filtering
@router.channel_post()
async def forward_messages(message: Message):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, keywords FROM users WHERE channel_id = ?", (str(message.chat.id),))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        user_id, keywords = user[0], user[1]
        
        # Apply keyword filtering if keywords exist
        if keywords:
            keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
            if not any(kw in message.text.lower() for kw in keyword_list if message.text):
                return  # Skip message if no keyword matches
        
        try:
            await bot.forward_message(chat_id=int(user_id), from_chat_id=message.chat.id, message_id=message.message_id)
            logging.info(f"✅ Forwarded message {message.message_id} to {user_id}")
        except Exception as e:
            logging.error(f"❌ Failed to forward message: {e}")

# Main function to run the bot
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

# Run the bot, handling active event loop
if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.get_event_loop().run_until_complete(main())
        else:
            raise

