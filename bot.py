import asyncio
import logging
import json
import os
import re
import ipaddress

import gitlab
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums.content_type import ContentType
from aiogram.filters import CommandStart
from aiogram.enums.parse_mode import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(os.getenv("TOKEN"))
dp = Dispatcher()

# GitLab configuration
GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
GITLAB_GROUP_ID = os.getenv("GITLAB_GROUP_ID", "")
GITLAB_INCLUDE_PROJECT = os.getenv("GITLAB_INCLUDE_PROJECT", "")  # e.g., "my-group/ci-templates"
GITLAB_INCLUDE_FILE = os.getenv("GITLAB_INCLUDE_FILE", ".gitlab-ci.yml")  # template file path

ENGINE_REPO = os.getenv("ENGINE_REPO")
ENGINE_TEMP_DIR = os.getenv("ENGINE_TEMP_DIR")

CI_JOB_TOKEN = os.getenv("CI_JOB_TOKEN", "")

def parse_flavor(flavor: str) -> dict:
    """Parse flavor string like '2/4 30%' into CPU, RAM, and overcommit values."""
    result = {"cpu": "", "ram": "", "overcommit": ""}
    if not flavor:
        return result
    
    # Pattern: "2/4 30%" -> cpu=2, ram=4, overcommit=30
    match = re.match(r"(\d+)/(\d+)\s*(\d+)%?", flavor)
    if match:
        result["cpu"] = match.group(1)
        result["ram"] = match.group(2)
        result["overcommit"] = match.group(3)
        if result["overcommit"] == "30":
            result["overcommit"] = "1:3"
    return result


def parse_subnet(subnet: str) -> dict:
    """Parse subnet string like '10.10.10.0/24' and return gateway, deploy node host, and corax nodes."""
    if not subnet:
        return {
            "CLUSTER_GATEWAY": "",
            "DEPLOY_NODE_HOST": "",
            "CORAX_NODES": ""
        }
    
    # Parse the subnet
    network = ipaddress.IPv4Network(subnet, strict=False)
    
    # Get the IP addresses starting from the network, skipping first 4
    all_addresses = list(network)[4:]  # Skip first 4 addresses
    
    if len(all_addresses) < 3:
        raise ValueError(f"Not enough IP addresses available in subnet {subnet}. Need at least 3 addresses after skipping first 4.")
    
    # Gateway is the first usable address (after skipping first 3)
    cluster_gateway = str(list(network)[1])  # Second address in subnet (first after network address)
    
    # Deploy node host is the 4th address (index 3 after network start)
    deploy_node_host = str(list(network)[4])  # Fifth address in subnet (4th after skipping first)
    
    # Define the node names and roles
    node_names = [
        "kafka-bpmx-01.testgis-platform.tech.pd33.testowner.gtn",
        "kafka-bpmx-02.testgis-platform.tech.pd33.testowner.gtn", 
        "kafka-bpmx-03.testgis-platform.tech.pd33.testowner.gtn"
    ]
    roles = ["kafka", "zookeeper", "crxsr", "crxui"]
    
    # Create corax nodes list
    corax_nodes = []
    for i in range(3):
        node_info = {
            "name": node_names[i],
            "host": str(all_addresses[i]),  # Use addresses starting from 4th position
            "user": "root",
            "roles": roles
        }
        corax_nodes.append(node_info)
    
    # Convert to JSON string format
    corax_nodes_json = json.dumps(corax_nodes)
    
    return {
        "CLUSTER_GATEWAY": cluster_gateway,
        "DEPLOY_NODE_HOST": deploy_node_host,
        "CORAX_NODES": corax_nodes_json
    }


def get_gitlab_client():
    """Create and return a GitLab client instance."""
    if not GITLAB_URL or not GITLAB_TOKEN:
        raise ValueError("GitLab configuration missing: GITLAB_URL and GITLAB_TOKEN required")
    return gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)


def create_gitlab_project(gl, project_name: str, description: str = "") -> object:
    """Create a new project in the configured GitLab group."""
    if not GITLAB_GROUP_ID:
        raise ValueError("GITLAB_GROUP_ID not configured")
    
    try:
        group_id = int(GITLAB_GROUP_ID)
    except ValueError:
        raise ValueError(f"GITLAB_GROUP_ID must be a valid integer, got: {GITLAB_GROUP_ID}")
    
    project_data = {
        "name": project_name,
        "namespace_id": group_id,
        "description": description,
        "visibility": "internal",
        "initialize_with_readme": True,  # Ensures default branch exists
    }
    project = gl.projects.create(project_data)
    logger.info(f"Created GitLab project: {project.web_url}")
    return project


def set_project_variables(project, variables: dict) -> None:
    """Set CI/CD variables on a GitLab project."""
    for key, value in variables.items():
        try:
            project.variables.create({
                "key": key,
                "value": str(value),
                "protected": False,
                "masked": False,
            })
            logger.info(f"Set variable {key} on project {project.name}")
        except gitlab.exceptions.GitlabCreateError as e:
            logger.warning(f"Variable {key} may already exist: {e}")
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to set variable {key}: {e}")
            raise


def create_gitlab_ci_file(project) -> None:
    """Create .gitlab-ci.yml with include directive to central template."""
    if not GITLAB_INCLUDE_PROJECT:
        raise ValueError("GITLAB_INCLUDE_PROJECT not configured")
    
    gitlab_ci_content = """# Auto-generated .gitlab-ci.yml
# Includes pipeline configuration from central repository

# Этот блок выполняется перед КАЖДЫМ джобом в пайплайне
default:
  before_script:
    - echo "🔄 [Engine] Подтягиваю файлы ядра из $ENGINE_REPO..."
    # 1. Очищаем старое (на случай перезапуска на том же раннере)
    - rm -rf $ENGINE_TEMP_DIR
    # 2. Клонируем репозиторий-движок во временную папку
    - git clone https://gitlab-ci-token:${CI_JOB_TOKEN}@${ENGINE_REPO} $ENGINE_TEMP_DIR
    
    # 3. Копируем нужные папки (ci, terraform-ci) в корень текущего воркспейса
    # Это создает иллюзию, что мы находимся внутри моно-репозитория
    - cp -r $ENGINE_TEMP_DIR/ci .
    - cp -r $ENGINE_TEMP_DIR/terraform-ci .
    - cp -r $ENGINE_TEMP_DIR/terraform .
    # 4. Выдаем права на исполнение
    - chmod +x ci/scripts/*.sh
    - echo "✅ [Engine] Среда подготовлена. Файлы на месте."


include:
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/stages.yml                  # Определение stages
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/variables.yml                 # Глобальные переменные
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/templates.yml                 # Переиспользуемые шаблоны
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/templates/ssh_functions.yml   # SSH функции (переиспользуемые)
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/config_generation.yml    # Job генерации конфигов
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/api_magic_router.yml     # Job for Magic Router
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/connectivity.yml         # Job for Connectivity
  - project: matveykolchuk/coraxci
    ref: main
    file: terraform-ci/jobs/terraform.yml  # Job для Terraform
  #- local: 'ci/jobs/node_preparation.yml'   # Job подготовки ноды
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/deploy_node_init.yml     # Job инициализации деплой ноды
# - local: lvm
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/archive_deployment.yml   # Job развертывания архива
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/cluster_setup.yml        # Job настройки кластера
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/corax_deployment.yml     # Job развертывания Corax
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/jam.yml

"""
    
    # Get the project's default branch
    default_branch = project.default_branch or "main"
    
    project.files.create({
        "file_path": ".gitlab-ci.yml",
        "branch": default_branch,
        "content": gitlab_ci_content,
        "commit_message": "Add .gitlab-ci.yml with include from central repository",
    })
    logger.info(f"Created .gitlab-ci.yml in project {project.name}")


def trigger_pipeline(project) -> object:
    """Trigger a pipeline run on the project's default branch."""
    default_branch = project.default_branch or "main"
    pipeline = project.pipelines.create({"ref": default_branch})
    logger.info(f"Triggered pipeline {pipeline.id} for project {project.name}")
    return pipeline


def setup_gitlab_project(
    cloud_project_id: str,
    project_name: str,
    description: str,
    subnet: str,
    flavor: str
) -> dict:
    """
    Main function to set up a GitLab project for Corax deployment.
    
    Args:
        cloud_project_id: Cloud project ID from KeyCloak
        project_name: Name for the new GitLab project
        description: Project description
        subnet: Subnet configuration (e.g., '10.10.10.0/24')
        flavor: VM flavor configuration (e.g., '2/4 30%')
    
    Returns:
        Dictionary with project URL and pipeline ID
    """
    gl = get_gitlab_client()
    
    # Create the project
    project = create_gitlab_project(gl, project_name, description)
    
    # Parse configurations
    subnet_config = parse_subnet(subnet)
    flavor_config = parse_flavor(flavor)
    
    # Set CI/CD variables
    variables = {
        "ENGINE_REPO": ENGINE_REPO,
        "ENGINE_TEMP_DIR": ENGINE_TEMP_DIR,
        "CI_JOB_TOKEN": CI_JOB_TOKEN,
        "CLOUDRU_PROJECT_ID": cloud_project_id,
        "project_id": cloud_project_id,
        #"SUBNET_ADDRESS": subnet_config["address"],
        #"SUBNET_MASK": subnet_config["mask"],
        "CLUSTER_SUBNET": subnet,
        "CLUSTER_GATEWAY": subnet_config["CLUSTER_GATEWAY"],
        "DEPLOY_NODE_HOST": subnet_config["DEPLOY_NODE_HOST"],
        "CORAX_NODES": subnet_config["CORAX_NODES"],
        "GIS_PROJECT_NAME": project_name,
        "CLUSTER_NUMBER": description,
        "KAFKA_BROKER_CPU": flavor_config["cpu"],
        "KAFKA_BROKER_RAM": flavor_config["ram"],
        "KAFKA_BROKER_OVERSUBSCRIPTION": flavor_config["overcommit"],
    }
    set_project_variables(project, variables)
    print(subnet_config["CLUSTER_GATEWAY"])
    print(subnet_config["DEPLOY_NODE_HOST"])
    print(subnet_config["CORAX_NODES"])
    # Create .gitlab-ci.yml
    create_gitlab_ci_file(project)
    
    # Trigger the pipeline
    pipeline = trigger_pipeline(project)
    
    return {
        "project_url": project.web_url,
        "pipeline_id": pipeline.id,
        "pipeline_url": f"{project.web_url}/-/pipelines/{pipeline.id}",
    }

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
