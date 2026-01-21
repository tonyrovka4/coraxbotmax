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

bot = Bot(os.getenv("TOKEN"))
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    webAppInfo = types.WebAppInfo(url="https://176.123.163.57.sslip.io")
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
    cloud_project_id = data.get("cloud_project_id", "")

    reply = (
        f"<b>{header}</b>\n"
        f"<b>{title}</b>\n\n"
        f"<code>{desc}</code>\n\n"
        f"{text}\n\n"
        f"<b>Подсеть:</b> {subnet}\n"
        f"<b>Флейвор ВМ:</b> {flavor}"
    )

    await message.answer(reply, parse_mode=ParseMode.HTML)

    # Process Corax requests - create GitLab project and trigger pipeline
    if header == "Corax" and cloud_project_id:
    #print(cloud_project_id)
    #if header == "Corax":
        if not GITLAB_URL or not GITLAB_TOKEN:
            await message.answer(
                "⚠️ <b>GitLab не настроен</b>\n\n"
                "Для создания проекта необходимо настроить переменные окружения GitLab.",
                parse_mode=ParseMode.HTML
            )
            return

        await message.answer(
            "⏳ <b>Создание проекта в GitLab...</b>",
            parse_mode=ParseMode.HTML
        )

        try:
            result = setup_gitlab_project(
                cloud_project_id=cloud_project_id,
                project_name=title,
                description=desc,
                subnet=subnet,
                flavor=flavor
            )

            success_reply = (
                f"✅ <b>Проект успешно создан!</b>\n\n"
                f"📁 <b>Проект:</b> {result['project_url']}\n"
                f"🚀 <b>Pipeline:</b> {result['pipeline_url']}\n\n"
                f"<b>CI/CD переменные установлены:</b>\n"
                f"• CLOUD_PROJECT_ID\n"
                f"• SUBNET_ADDRESS, SUBNET_MASK\n"
                f"• VM_CPU, VM_RAM, VM_OVERCOMMIT"
            )
            await message.answer(success_reply, parse_mode=ParseMode.HTML)

        except ValueError as e:
            await message.answer(
                f"❌ <b>Ошибка конфигурации:</b>\n{str(e)}",
                parse_mode=ParseMode.HTML
            )
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"GitLab API error: {e}")
            await message.answer(
                f"❌ <b>Ошибка GitLab API:</b>\n{str(e)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Unexpected error during GitLab setup: {e}")
            await message.answer(
                f"❌ <b>Неожиданная ошибка:</b>\n{str(e)}",
                parse_mode=ParseMode.HTML
            )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
