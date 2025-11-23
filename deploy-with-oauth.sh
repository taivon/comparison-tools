#!/bin/bash

# Deploy OAuth credentials to App Engine
# This script reads from .env file and deploys to App Engine securely

echo "🚀 Deploying OAuth Credentials to App Engine"
echo "============================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please create a .env file with your OAuth credentials first."
    exit 1
fi

# Read OAuth credentials from .env file
source .env

# Check if credentials are set
if [ -z "$GOOGLE_OAUTH2_KEY" ] || [ -z "$GOOGLE_OAUTH2_SECRET" ]; then
    echo "❌ Error: OAuth credentials not found in .env file"
    echo "Please set GOOGLE_OAUTH2_KEY and GOOGLE_OAUTH2_SECRET in your .env file"
    exit 1
fi

echo "✅ Found OAuth credentials in .env file"
echo "📤 Deploying to App Engine with environment variables..."
echo ""

# Deploy with OAuth credentials
# First, update app.yaml with environment variables, then deploy
echo "📝 Creating temporary app.yaml with environment variables..."

# Backup original app.yaml
cp app.yaml app.yaml.bak

# Add environment variables to app.yaml
cat >> app.yaml << EOF

# OAuth Environment Variables (added by deploy script)
env_variables:
  GOOGLE_OAUTH2_KEY: "$GOOGLE_OAUTH2_KEY"
  GOOGLE_OAUTH2_SECRET: "$GOOGLE_OAUTH2_SECRET"
  APPENGINE_URL: "https://apartments.comparison.tools"
EOF

echo "🚀 Deploying to App Engine..."
gcloud app deploy --quiet

# Restore original app.yaml
mv app.yaml.bak app.yaml

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Make sure your Google OAuth client includes this redirect URI:"
    echo "   https://comparison-tools-479102.uc.r.appspot.com/accounts/complete/google-oauth2/"
    echo ""
    echo "2. Test OAuth login at:"
    echo "   https://comparison-tools-479102.uc.r.appspot.com"
    echo ""
else
    echo ""
    echo "❌ Deployment failed. Check the error messages above."
    exit 1
fi