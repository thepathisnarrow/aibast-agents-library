# SE Environment Setup

Each Solutions Engineer gets their own **MCAPS managed environment** (`MngEnvMCAPXXXXXX`). This repo is configured so you can run it against your own tenant without editing shared code.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/microsoft/aibast-agents-library.git
cd aibast-agents-library

# 2. Copy the environment template
cp env.yaml.example env.yaml

# 3. Fill in YOUR values (see below)
code env.yaml

# 4. Install dependencies
pip install -r requirements.txt

# 5. Authenticate to GitHub (for Copilot API) and Azure
gh auth login
az login --tenant MngEnvMCAPXXXXXX.onmicrosoft.com

# 6. Run
./start.sh   # or: python brainstem.py
```

## Finding Your Values

| Field | Where to find it |
|-------|-----------------|
| `tenant.domain` | Azure Portal → Entra ID → Overview → Primary domain (e.g. `MngEnvMCAP874580.onmicrosoft.com`) |
| `tenant.login_hint` | Your `@microsoft.com` email |
| `subscription.id` | `az account list --query "[].{name:name, id:id}" -o table` — pick the one matching your MngEnv |
| `subscription.default_region` | Your preferred region (most MCAPS envs use `westus3` or `eastus2`) |
| `owner_name` | Your first name — used in safety-constraint prompts ("requires approval from X") |

## Configuration Precedence

1. **Environment variables** (`MCAPS_TENANT_DOMAIN`, `MCAPS_SUBSCRIPTION_ID`, etc.) — highest priority
2. **`env.yaml`** — recommended for most SEs
3. **Built-in defaults** — placeholder values that remind you to configure

## Files

| File | Committed? | Purpose |
|------|-----------|---------|
| `env.yaml.example` | ✅ Yes | Template — copy this |
| `env.yaml` | ❌ No (gitignored) | Your personal config |
| `.env` | ❌ No (gitignored) | Optional env-var overrides |

## Safety Note

The `owner_name` field controls whose approval is required before destructive operations (delete resources, purge data, etc.). Set it to your own name so the agent asks *you* before doing anything irreversible.
