#!/bin/bash

# Deploy OAuth credentials to App Engine (Smart Version)
# This script updates the existing env_variables section in app.yaml

echo "🚀 Smart OAuth Deployment to App Engine"
echo "======================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

# Read OAuth credentials from .env file
source .env

# Check if credentials are set
if [ -z "$GOOGLE_OAUTH2_KEY" ] || [ -z "$GOOGLE_OAUTH2_SECRET" ]; then
    echo "❌ Error: OAuth credentials not found in .env file"
    exit 1
fi

echo "✅ Found OAuth credentials in .env file"
echo "📝 Updating app.yaml with OAuth credentials..."

# Backup app.yaml
cp app.yaml app.yaml.bak

# Create new app.yaml with OAuth credentials
python3 << EOF
import yaml
import os

# Load current app.yaml
with open('app.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ensure env_variables exists
if 'env_variables' not in config:
    config['env_variables'] = {}

# Add OAuth credentials
config['env_variables']['GOOGLE_OAUTH2_KEY'] = '$GOOGLE_OAUTH2_KEY'
config['env_variables']['GOOGLE_OAUTH2_SECRET'] = '$GOOGLE_OAUTH2_SECRET'

# Write updated app.yaml
with open('app.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print("✅ Updated app.yaml with OAuth credentials")
EOF

echo "🚀 Deploying to App Engine..."
gcloud app deploy --quiet

# Restore original app.yaml
echo "🔄 Restoring original app.yaml..."
mv app.yaml.bak app.yaml

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "🎯 Important: Make sure your Google OAuth client includes:"
    echo "   https://comparison-tools-479102.uc.r.appspot.com/accounts/complete/google-oauth2/"
    echo ""
    echo "🔗 Go to: https://console.cloud.google.com/apis/credentials"
    echo "📝 Add the redirect URI above to your OAuth 2.0 Client ID"
    echo ""
    echo "🧪 Test at: https://comparison-tools-479102.uc.r.appspot.com"
else
    echo "❌ Deployment may have failed. Check messages above."
fi