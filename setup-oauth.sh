#!/bin/bash

# Google OAuth Setup Script for App Engine
# This script helps configure OAuth credentials for production deployment

echo "🔧 Google OAuth Configuration for App Engine"
echo "============================================="
echo ""

# Get current App Engine URL
APP_ENGINE_URL=$(gcloud app describe --format="value(defaultHostname)" 2>/dev/null)

if [ -z "$APP_ENGINE_URL" ]; then
    echo "❌ Error: Could not determine App Engine URL. Make sure you're logged into gcloud."
    exit 1
fi

echo "📍 Your App Engine URL: https://$APP_ENGINE_URL"
echo ""

# Show required redirect URIs
echo "🔗 Required OAuth Redirect URIs:"
echo "Add these to your Google Cloud Console OAuth client:"
echo ""
echo "  1. http://localhost:8000/accounts/complete/google-oauth2/"
echo "  2. http://127.0.0.1:8000/accounts/complete/google-oauth2/"
echo "  3. https://$APP_ENGINE_URL/accounts/complete/google-oauth2/"
echo "  4. https://apartments.comparison.tools/accounts/complete/google-oauth2/"
echo ""

# Check if OAuth credentials are set
echo "🔍 Checking current App Engine environment variables..."
CURRENT_VARS=$(gcloud app versions describe $(gcloud app versions list --service=default --limit=1 --format="value(version.id)") --service=default --format="yaml(envVariables)" 2>/dev/null)

if echo "$CURRENT_VARS" | grep -q "GOOGLE_OAUTH2_KEY"; then
    echo "✅ OAuth credentials appear to be set in App Engine"
else
    echo "⚠️  OAuth credentials not found in App Engine environment"
    echo ""
    echo "To set OAuth credentials for App Engine, run:"
    echo ""
    echo "  gcloud app deploy --set-env-vars \\"
    echo "    GOOGLE_OAUTH2_KEY=your-client-id.apps.googleusercontent.com,\\"
    echo "    GOOGLE_OAUTH2_SECRET=your-client-secret"
    echo ""
fi

# Instructions
echo ""
echo "📋 Setup Steps:"
echo "1. Go to: https://console.cloud.google.com/apis/credentials"
echo "2. Find your OAuth 2.0 Client ID and click Edit"
echo "3. Add the redirect URIs shown above"
echo "4. Set the environment variables in App Engine (if not already done)"
echo "5. Redeploy your app: gcloud app deploy"
echo ""
echo "🎯 After completing these steps, try signing in again at:"
echo "   https://$APP_ENGINE_URL"