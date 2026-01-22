# Corax Bot - Cloud Manager

Max bot with mini-app for managing cloud resources and deploying Corax clusters via GitLab CI/CD.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Max Bot
TOKEN=your_max_bot_token

# Flask
SECRET_KEY=your_secret_key

# Traditional Login (Optional)
APP_USERNAME=admin
APP_PASSWORD=password

# Keycloak OAuth
KEYCLOAK_URL=https://keycloak.example.com
KEYCLOAK_REALM=my-realm
KEYCLOAK_CLIENT_ID=client-id
KEYCLOAK_CLIENT_SECRET=client-secret

# App Configuration
APP_ORIGIN=https://your-app-domain.com

# Cloud.ru API
CLOUD_CLIENT_ID=key-id
CLOUD_CLIENT_SECRET=secret

# GitLab Integration (for Corax deployment)
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=your-gitlab-personal-access-token
GITLAB_GROUP_ID=123  # Group ID where projects will be created
GITLAB_INCLUDE_PROJECT=my-group/ci-templates  # Path to central CI templates repo
GITLAB_INCLUDE_FILE=.gitlab-ci.yml  # Template file to include (default: .gitlab-ci.yml)
```

## Running

```bash
./start.sh
```

Or manually:

```bash
python3 bot.py &
python3 app.py
```

## Corax GitLab Integration

When a user selects "Corax" in the mini-app and submits the form, the bot will:

1. Create a new GitLab project in the configured group
2. Set CI/CD variables:
   - `CLOUD_PROJECT_ID` - User's cloud project ID from KeyCloak
   - `SUBNET_ADDRESS` - Network subnet address (e.g., "10.10.10.0")
   - `SUBNET_MASK` - Subnet mask (e.g., "24")
   - `VM_CPU` - Number of CPU cores
   - `VM_RAM` - RAM in GB
   - `VM_OVERCOMMIT` - Overcommit percentage
3. Create a `.gitlab-ci.yml` file with include directive to central templates
4. Trigger the pipeline

---

To deactivate the virtual environment:

```bash
deactivate
```
