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

# Pangolin configuration
PANGOLIN_GITLAB_TOKEN = os.getenv("PANGOLIN_GITLAB_TOKEN", "")
PANGOLIN_GITLAB_GROUP_ID = os.getenv("PANGOLIN_GITLAB_GROUP_ID", "")

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


def get_gitlab_client(token=None):
    """Create and return a GitLab client instance."""
    if not GITLAB_URL:
        raise ValueError("GitLab configuration missing: GITLAB_URL required")
    
    target_token = token if token else GITLAB_TOKEN
    if not target_token:
        raise ValueError("GitLab Token is missing")
        
    return gitlab.Gitlab(GITLAB_URL, private_token=target_token)


def create_gitlab_project(gl, project_name: str, group_id: int, description: str = "") -> object:
    """Create a new project in the specific GitLab group."""
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
  - project: matveykolchuk/coraxci
    ref: main
    file: ci/jobs/restart.yml


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
    if not GITLAB_GROUP_ID:
        raise ValueError("GITLAB_GROUP_ID not configured for Corax")
        
    project = create_gitlab_project(gl, project_name, int(GITLAB_GROUP_ID), description)
    
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


def create_pangolin_config_file(project, config_data: dict) -> None:
    """
    Creates envs/pangolin_config.yml in the repository.
    GitLab API automatically creates directories if they are in the file_path.
    """
    project_name = config_data.get('project_name', '')
    cluster_number = config_data.get('cluster_number', '')
    subnet = config_data.get('subnet', '')
    cloud_project_id = config_data.get('cloud_project_id', '')
    
    # Parse flavor logic specifically for Pangolin
    # We take CPU and RAM from flavor string (e.g. "2/4 30%")
    # BUT we IGNORE the percentages and force 1:1 ratio
    flavor_str = config_data.get('flavor', '')
    parsed_flavor = parse_flavor(flavor_str)
    
    # Defaults if parsing fails
    cpu = parsed_flavor.get('cpu', '4')
    ram = parsed_flavor.get('ram', '8')
    
    # Data Disk from user input (or default 10)
    data_disk_gb = config_data.get('data_disk_gb', 10)

    yaml_content = f"""
version: '0.2'
cluster:
  name: pangolin_etc_pgbouncer
  deploy_node_enabled: true
infra:
  ssh:
    public_key: ''
  nodes:
    pangolin_node1:
      cpu_cores: {cpu}
      ram_gb: {ram}
      oversubscription_ratio: '1:1'
      data_disk_gb: {data_disk_gb}
      ip: ''
    pangolin_node2:
      cpu_cores: {cpu}
      ram_gb: {ram}
      oversubscription_ratio: '1:1'
      data_disk_gb: {data_disk_gb}
      ip: ''
    arbiter:
      cpu_cores: 2
      ram_gb: 4
      oversubscription_ratio: '1:1'
      ip: ''
    deploy:
      cpu_cores: 4
      ram_gb: 8
      oversubscription_ratio: '1:1'
      ip: ''
  cloud:
    project_name: maxgis
    cluster_number: '{cluster_number}'
    cluster_subnet: {subnet}
    vpc_name: Default
    default_gateway: ''
    vip: ''
    users_subnet: 10.20.32.0/24
    infra_subnet_gitlab: 172.18.0.0/24
    infra_subnet_jumphost: 10.10.11.0/24
    cloudru_project_id: {cloud_project_id}
security:
  password_mode: generate
  reuse_single_password: false
  etcd_password:
    value: ''
  pgbouncer_scram_password:
    value: ''
  pgbouncer_scram_password_orig:
    value: ''
  postgres_linux_pass:
    value: ''
  postgres_linux_pass_orig:
    value: ''
  kmadmin_pg_linux_pass:
    value: ''
  kmadmin_pg_linux_pass_orig:
    value: ''
  postgres_db_pass:
    value: ''
  patroni_password:
    value: ''
  pg_backup_user_passwd:
    value: ''
  patroni_yml_pass:
    value: ''
postgresql:
  databases:
  - name: db1
    owner_group: backend_app_admins
    encoding: UTF8
    lc_collate: ru_RU.UTF-8
    lc_ctype: ru_RU.UTF-8
    template: template0
    users_in_group:
    - admin
  users:
  - name: admin
    password:
      value: ''
"""
    
    default_branch = project.default_branch or "main"
    
    project.files.create({
        "file_path": "envs/pangolin_config.yml",
        "branch": default_branch,
        "content": yaml_content.strip(),
        "commit_message": "Add pangolin_config.yml",
    })
    logger.info(f"Created envs/pangolin_config.yml in project {project.name}")


def create_pangolin_gitlab_ci_file(project) -> None:
    """Create .gitlab-ci.yml for Pangolin project."""
    gitlab_ci_content = """workflow: 
  rules:
  - if: $CI_PIPELINE_SOURCE == "trigger"
    when: always
  - if: $CI_PIPELINE_SOURCE == "web"
    when: always
  - if: $CI_PIPELINE_SOURCE == "api"
    when: always
  - when: never
include:
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: stages/stages.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: templates/templates.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: validate/validate.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: generate/generate.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: api/api.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: connectivity/connectivity.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: terraform-sg/terraform-sg.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: terraform/terraform.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: repo/repo.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: cloud-api/cloud-api.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: lvm/lvm.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: packages/packages.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: deploynode/deploynode.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: fix/fix.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: install/install.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: usersdb/usersdb.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: lb/lb.yml
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: jam/jam.yml
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: restart/restart.yml
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: db-conn-test/db-conn-test.yml
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: cleanup/cleanup.yml
- project: paas-platform/ci-templates/pangolin
  ref: v0.1
  file: finalize/finalize.yml
- project: paas-platform/ci-templates/pangolin
  ref: main
  file: audit/audit.yml  
"""
    
    # Get the project's default branch
    default_branch = project.default_branch or "main"
    
    project.files.create({
        "file_path": ".gitlab-ci.yml",
        "branch": default_branch,
        "content": gitlab_ci_content,
        "commit_message": "Add .gitlab-ci.yml for Pangolin",
    })
    logger.info(f"Created .gitlab-ci.yml in project {project.name}")


def setup_pangolin_project(
    cloud_project_id: str,
    project_name: str,
    description: str,
    subnet: str,
    flavor: str,
    data_disk_gb: int
) -> dict:
    """
    Orchestrator for Pangolin deployment.
    Uses specific Token and Group ID.
    """
    pangolin_token = PANGOLIN_GITLAB_TOKEN
    
    try:
        pangolin_group_id = int(PANGOLIN_GITLAB_GROUP_ID)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid PANGOLIN_GITLAB_GROUP_ID: {PANGOLIN_GITLAB_GROUP_ID}")

    # Initialize client with Pangolin token
    gl = get_gitlab_client(token=pangolin_token)
    
    # Create project in Pangolin group
    project = create_gitlab_project(gl, project_name, pangolin_group_id, description)
    
    # Set variables (reusing logic if appropriate, otherwise customize)
    # variables = {
    #     "CLOUDRU_PROJECT_ID": cloud_project_id,
    #     "CLUSTER_SUBNET": subnet,
    #     "GIS_PROJECT_NAME": project_name,
    #     # Add other specific variables if needed
    # }
    # set_project_variables(project, variables)
    
    # Create .gitlab-ci.yml
    create_pangolin_gitlab_ci_file(project)
    
    # Create Pangolin specific config
    create_pangolin_config_file(project, {
        "subnet": subnet,
        "flavor": flavor,
        "data_disk_gb": data_disk_gb,
        "project_name": project_name,
        "cloud_project_id": cloud_project_id,
        "cluster_number": description
    })
    
    # Trigger pipeline
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
    try:
        # Try default (Corax) token first
        gl = get_gitlab_client()
        project = gl.projects.get(project_id)
    except gitlab.exceptions.GitlabGetError:
        # If not found, try Pangolin token
        logger.info(f"Project {project_id} not found with default token, trying Pangolin token")
        gl = get_gitlab_client(token=PANGOLIN_GITLAB_TOKEN)
        project = gl.projects.get(project_id)
        
    pipeline = project.pipelines.get(pipeline_id)
    jobs = pipeline.jobs.list(per_page=100)
    
    status = pipeline.status
    completed_statuses = {"success", "failed", "canceled", "skipped"}
    running_statuses = {"running"}
    pending_statuses = {"pending", "manual", "scheduled"}
    min_running_progress = 5
    almost_complete_threshold = 95
    unknown_stage = "unknown"

    stage_order = []
    stage_buckets = {}
    for job in jobs:
        stage_name = job.stage or unknown_stage
        stage_buckets.setdefault(stage_name, []).append(job)
        if stage_name not in stage_order:
            stage_order.append(stage_name)

    stages = []
    for stage_name in stage_order:
        stage_jobs = stage_buckets[stage_name]
        stage_total = len(stage_jobs)
        stage_done = len([job for job in stage_jobs if job.status in completed_statuses])
        stage_running = len([job for job in stage_jobs if job.status in running_statuses])
        stage_failed = len([job for job in stage_jobs if job.status == "failed"])
        stage_canceled = len([job for job in stage_jobs if job.status == "canceled"])
        stage_percent = int((stage_done / stage_total) * 100) if stage_total > 0 else 0
        if stage_running and stage_percent < almost_complete_threshold:
            stage_percent = max(stage_percent, min_running_progress)
        if stage_failed:
            stage_status = "failed"
        elif stage_canceled:
            stage_status = "canceled"
        elif stage_done == stage_total and stage_total:
            stage_status = "completed"
        elif stage_running:
            stage_status = "running"
        elif stage_done:
            stage_status = "queued"
        else:
            stage_status = "pending"
        stages.append({
            "name": stage_name,
            "status": stage_status,
            "percent": stage_percent,
            "completed_jobs": stage_done,
            "total_jobs": stage_total,
        })

    completed_stages = len([stage for stage in stages if stage["status"] in {"completed", "failed", "canceled"}])
    total_stages = len(stages)
    running_stage_info = next((stage for stage in stages if stage["status"] == "running"), None)
    running_stage_names = [stage["name"] for stage in stages if stage["status"] == "running"]
    running_stage = ", ".join(running_stage_names) if running_stage_names else None
    if status in completed_statuses:
        percent = 100
    elif status in pending_statuses and completed_stages == 0 and not running_stage_info:
        percent = 0
    elif total_stages:
        running_progress = (running_stage_info["percent"] / 100) if running_stage_info else 0
        percent = int(((completed_stages + running_progress) / total_stages) * 100)
        if running_stage_info and percent < almost_complete_threshold:
            percent = max(percent, min_running_progress)
    else:
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
        percent = progress_map.get(status, 0)

    return {
        "status": status,
        "percent": percent,
        "web_url": pipeline.web_url,
        "running_stage": running_stage,
        "completed_stages": completed_stages,
        "total_stages": total_stages,
        "stages": stages,
    }
