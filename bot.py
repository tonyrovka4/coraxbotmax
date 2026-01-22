import asyncio
import logging
import json
import os

from maxapi import Bot, Dispatcher, types, F
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import gitlab

# Import shared utility functions
from utils import (
    setup_gitlab_project,
    GITLAB_URL,
    GITLAB_TOKEN,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()


@dp.message_created(types.CommandStart())
async def start(message: types.MessageCreated):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.OpenAppButton(
            text="PaaS Cloud Manager", 
            web_app=message.bot.me.username, 
            contact_id=message.bot.me.user_id
        )
    )
    await message.message.answer(
        "Пройдите аутентификацию",
        attachments=[builder.as_markup()],
    )

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
