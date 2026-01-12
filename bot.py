import asyncio
import logging
import json
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums.content_type import ContentType
from aiogram.filters import CommandStart
from aiogram.enums.parse_mode import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(os.getenv("TOKEN"))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    webAppInfo = types.WebAppInfo(url="https://176.109.104.88.sslip.io")
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text='PaaS Cloud manager', web_app=webAppInfo))
    await message.answer(text='Пройдите аутентификацию', reply_markup=builder.as_markup())

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def parse_data(message: types.Message):
    data = json.loads(message.web_app_data.data)

    # Build response with header from chosen option
    header = data.get("choice", "Не выбрано")
    title = data.get("title", "")
    desc = data.get("desc", "")
    text = data.get("text", "")
    subnet = data.get("subnet", "")
    flavor = data.get("flavor", "")

    reply = (
        f"<b>{header}</b>\n"
        f"<b>{title}</b>\n\n"
        f"<code>{desc}</code>\n\n"
        f"{text}\n\n"
        f"<b>Подсеть:</b> {subnet}\n"
        f"<b>Флейвор ВМ:</b> {flavor}"
    )

    await message.answer(reply, parse_mode=ParseMode.HTML)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())