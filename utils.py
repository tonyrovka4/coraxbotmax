"""
Utility functions for GitLab project setup and management.
Extracted from bot.py for reuse in app.py (Backend API).
"""

import os
import re
import json
import logging
import ipaddress

import gitlab
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitLab configuration
GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
GITLAB_GROUP_ID = os.getenv("GITLAB_GROUP_ID", "")
GITLAB_INCLUDE_PROJECT = os.getenv("GITLAB_INCLUDE_PROJECT", "")
GITLAB_INCLUDE_FILE = os.getenv("GITLAB_INCLUDE_FILE", ".gitlab-ci.yml")

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

workflow:
  rules:
  - if: $CI_PIPELINE_SOURCE == "trigger"
    when: always
  - if: $CI_PIPELINE_SOURCE == "web"
    when: always
  - if: $CI_PIPELINE_SOURCE == "api"
    when: always
  - when: never

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
    - cp -r $ENGINE_TEMP_DIR/terraform-sg .
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
    file: terraform-ci/jobs/terraform-sg.yml 
  - project: matveykolchuk/coraxci
    ref: main
    file: terraform-ci/jobs/terraform.yml  # Job для Terraform
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/deploy_node_init.yml     # Job инициализации деплой ноды
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
    logger.info(f"CLUSTER_GATEWAY: {subnet_config['CLUSTER_GATEWAY']}")
    logger.info(f"DEPLOY_NODE_HOST: {subnet_config['DEPLOY_NODE_HOST']}")
    logger.info(f"CORAX_NODES: {subnet_config['CORAX_NODES']}")
    
    # Create .gitlab-ci.yml
    create_gitlab_ci_file(project)
    
    # Trigger the pipeline
    pipeline = trigger_pipeline(project)
    
    return {
        "project_url": project.web_url,
        "project_id": project.id,
        "pipeline_id": pipeline.id,
        "pipeline_url": f"{project.web_url}/-/pipelines/{pipeline.id}",
    }


def get_pipeline_status(project_id: int, pipeline_id: int) -> dict:
    """
    Get the status of a GitLab pipeline.
    
    Args:
        project_id: GitLab project ID
        pipeline_id: Pipeline ID to check
    
    Returns:
        Dictionary with pipeline status information
    """
    gl = get_gitlab_client()
    project = gl.projects.get(project_id)
    pipeline = project.pipelines.get(pipeline_id)
    
    # Calculate approximate progress based on status
    status = pipeline.status
    progress_map = {
        "pending": 0,
        "running": 50,
        "success": 100,
        "failed": 100,
        "canceled": 100,
        "skipped": 100,
        "manual": 0,
        "scheduled": 0,
    }
    
    return {
        "status": status,
        "percent": progress_map.get(status, 0),
        "web_url": pipeline.web_url,
    }
