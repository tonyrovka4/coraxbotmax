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
        types.LinkButton(
            text="PaaS Cloud manager",
            url="https://176.123.163.57.sslip.io",
        )
    )
    await message.message.answer(
        "Пройдите аутентификацию",
        attachments=[builder.as_markup()],
    )

# @dp.message_created(F.message.body.text)
# async def parse_data(message: types.MessageCreated):
#     data = json.loads(message.message.body.text)

#     # Build response with header from chosen option
#     header = data.get("choice", "Не выбрано")
#     title = data.get("title", "")
#     desc = data.get("desc", "")
#     text = data.get("text", "")
#     subnet = data.get("subnet", "")
#     flavor = data.get("flavor", "")
#     cloud_project_id = data.get("cloud_project_id", "")

#     reply = (
#         f"<b>{header}</b>\n"
#         f"<b>{title}</b>\n\n"
#         f"<code>{desc}</code>\n\n"
#         f"{text}\n\n"
#         f"<b>Подсеть:</b> {subnet}\n"
#         f"<b>Флейвор ВМ:</b> {flavor}"
#     )

#     await message.message.answer(reply, parse_mode="HTML")

#     # Process Corax requests - create GitLab project and trigger pipeline
#     if header == "Corax" and cloud_project_id:
#     #print(cloud_project_id)
#     #if header == "Corax":
#         if not GITLAB_URL or not GITLAB_TOKEN:
#             await message.message.answer(
#                 "⚠️ <b>GitLab не настроен</b>\n\n"
#                 "Для создания проекта необходимо настроить переменные окружения GitLab.",
#                 parse_mode="HTML"
#             )
#             return

#         await message.message.answer(
#             "⏳ <b>Создание проекта в GitLab...</b>",
#             parse_mode="HTML"
#         )

#         try:
#             result = setup_gitlab_project(
#                 cloud_project_id=cloud_project_id,
#                 project_name=title,
#                 description=desc,
#                 subnet=subnet,
#                 flavor=flavor
#             )

#             success_reply = (
#                 f"✅ <b>Проект успешно создан!</b>\n\n"
#                 f"📁 <b>Проект:</b> {result['project_url']}\n"
#                 f"🚀 <b>Pipeline:</b> {result['pipeline_url']}\n\n"
#                 f"<b>CI/CD переменные установлены:</b>\n"
#                 f"• CLOUD_PROJECT_ID\n"
#                 f"• SUBNET_ADDRESS, SUBNET_MASK\n"
#                 f"• VM_CPU, VM_RAM, VM_OVERCOMMIT"
#             )
#             await message.message.answer(success_reply, parse_mode="HTML")

#         except ValueError as e:
#             await message.message.answer(
#                 f"❌ <b>Ошибка конфигурации:</b>\n{str(e)}",
#                 parse_mode="HTML"
#             )
#         except gitlab.exceptions.GitlabError as e:
#             logger.error(f"GitLab API error: {e}")
#             await message.message.answer(
#                 f"❌ <b>Ошибка GitLab API:</b>\n{str(e)}",
#                 parse_mode="HTML"
#             )
#         except Exception as e:
#             logger.error(f"Unexpected error during GitLab setup: {e}")
#             await message.message.answer(
#                 f"❌ <b>Неожиданная ошибка:</b>\n{str(e)}",
#                 parse_mode="HTML"
#             )

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
