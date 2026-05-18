#!/bin/bash
set -e
cd "$(dirname "$0")"

BRAINSTEM_HOME="$HOME/.brainstem"
VENV_PYTHON="$BRAINSTEM_HOME/venv/bin/python"

# Use venv if available; create it if missing
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Setting up virtual environment..."
    PYTHON_CMD=$(command -v python3.11 || command -v python3.12 || command -v python3.13 || command -v python3)
    "$PYTHON_CMD" -m venv "$BRAINSTEM_HOME/venv" 2>/dev/null || {
        echo "Failed to create venv — run the installer: curl -fsSL https://microsoft.github.io/aibast-agents-library/install.sh | bash"
        exit 1
    }
fi

# Install deps if needed
if ! "$VENV_PYTHON" -c "import flask, requests, dotenv" 2>/dev/null; then
    echo "Installing dependencies..."
    "$BRAINSTEM_HOME/venv/bin/pip" install -r requirements.txt -q
fi

# Create .env from example if missing
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || true
fi

# ── MEA (Managed Environment Admin) Login ─────────────────────────────────────
# The MEA is the tenant-native admin account required for Azure/Fabric/Purview
# operations. Guest users (#EXT#) cannot perform capacity assignments, etc.
# The SE remains themselves locally; only cloud API calls run as MEA.

get_mea_admin() {
    local env_yaml="./env.yaml"
    if [ ! -f "$env_yaml" ]; then
        echo ""
        return
    fi
    local mea=$(grep -oP 'mea_admin:\s*"?\K[^"\r\n]+' "$env_yaml" 2>/dev/null | head -1)
    if [ -n "$mea" ]; then
        echo "$mea"
        return
    fi
    # Fallback: derive from tenant domain
    local domain=$(grep -oP 'domain:\s*"?\K[^"\r\n]+' "$env_yaml" 2>/dev/null | head -1)
    if [ -n "$domain" ] && [ "$domain" != "MngEnvMCAPXXXXXX.onmicrosoft.com" ]; then
        echo "admin@$domain"
    fi
}

confirm_mea_login() {
    local mea_admin="$1"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MEA (Managed Environment Admin) Authentication"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Azure/Fabric/Purview operations require the tenant-native"
    echo "  admin account. Your SE identity is used locally/GitHub."
    echo ""
    echo "  MEA Account: $mea_admin"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Check if already logged in as MEA
    local current_user
    current_user=$(az account show --query "user.name" -o tsv 2>/dev/null || echo "")
    if [ "$current_user" = "$mea_admin" ]; then
        echo "  ✓ Already authenticated as MEA."
        echo ""
        export BRAINSTEM_MEA_AUTHENTICATED=true
        return 0
    fi
    
    if [ -n "$current_user" ]; then
        echo "  Currently logged in as: $current_user"
    else
        echo "  No active Azure CLI session."
    fi
    
    echo ""
    read -rp "  Login as MEA for cloud operations? (Y/n): " response
    if [ -n "$response" ] && [ "${response,,}" != "y" ]; then
        echo "  Skipping MEA login — admin operations may be limited."
        echo ""
        return 1
    fi
    
    # Extract tenant domain
    local tenant="${mea_admin#*@}"
    
    echo ""
    echo "  Launching Azure CLI login for MEA..."
    echo "  Sign in as: $mea_admin"
    echo ""
    
    if ! az login --tenant "$tenant" --allow-no-subscriptions >/dev/null 2>&1; then
        echo "  ✗ MEA login failed. Continuing without admin privileges."
        return 1
    fi
    
    # Verify
    current_user=$(az account show --query "user.name" -o tsv 2>/dev/null || echo "")
    if [ "$current_user" = "$mea_admin" ]; then
        echo "  ✓ MEA authenticated successfully."
        echo ""
        export BRAINSTEM_MEA_AUTHENTICATED=true
        return 0
    else
        echo "  ⚠ Logged in as $current_user (expected $mea_admin)"
        return 1
    fi
}

MEA_ADMIN=$(get_mea_admin)
if [ -n "$MEA_ADMIN" ]; then
    confirm_mea_login "$MEA_ADMIN"
else
    echo "No MEA configured — set mea_admin in env.yaml for admin operations."
fi

exec "$VENV_PYTHON" brainstem.py
