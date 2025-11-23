#!/bin/bash

# Environment Security Validation Script
# This script checks for common security issues with environment variables

echo "🔒 Environment Security Validation"
echo "=================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found - copy from .env.example"
    exit 1
fi

# Check .env file permissions
if [ "$(stat -c %a .env 2>/dev/null || stat -f %A .env 2>/dev/null)" != "600" ]; then
    echo "⚠️  Warning: .env file should have 600 permissions"
    echo "   Run: chmod 600 .env"
fi

# Check if .env is in .gitignore
if ! grep -q "^\.env$" .gitignore; then
    echo "❌ .env not found in .gitignore - this is a security risk!"
    exit 1
fi

# Check for placeholder values
if grep -q "your_client_id_here\|your_client_secret_here\|your-.*-here" .env; then
    echo "⚠️  Warning: .env contains placeholder values"
    echo "   Update with actual credentials from Google Cloud Console"
fi

# Check for empty OAuth variables
if [ -f ".env" ]; then
    source .env
    if [ -z "$GOOGLE_OAUTH2_KEY" ] || [ -z "$GOOGLE_OAUTH2_SECRET" ]; then
        echo "⚠️  Warning: OAuth credentials not configured in .env"
        echo "   See ENVIRONMENT_SECURITY.md for setup instructions"
    else
        echo "✅ OAuth credentials configured"
    fi
fi

# Check git status for tracked .env
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "❌ CRITICAL: .env file is tracked by git!"
    echo "   Run: git rm --cached .env"
    echo "   Then commit the removal"
    exit 1
fi

echo ""
echo "🛡️  Security checks completed"
echo "   For more information, see ENVIRONMENT_SECURITY.md"