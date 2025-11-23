# Google OAuth Setup Instructions

To enable Google Sign-In, you need to create OAuth credentials in the Google Cloud Console.

## 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API (or Google Identity API)

## 2. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client IDs**
3. Choose **Web application**
4. Add authorized redirect URIs:
   - For development: `http://localhost:8000/accounts/complete/google-oauth2/`
   - For development (127.0.0.1): `http://127.0.0.1:8000/accounts/complete/google-oauth2/`
   - For App Engine: `https://comparison-tools-479102.uc.r.appspot.com/accounts/complete/google-oauth2/`
   - For custom domain: `https://apartments.comparison.tools/accounts/complete/google-oauth2/`

## 3. Set Environment Variables

### Local Development
⚠️ **SECURITY WARNING**: Never commit actual credentials to git!

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your actual credentials:
```bash
GOOGLE_OAUTH2_KEY=your_actual_client_id_here.apps.googleusercontent.com
GOOGLE_OAUTH2_SECRET=your_actual_client_secret_here
```

3. Set secure permissions:
```bash
chmod 600 .env  # Unix/macOS only
```

### Production (Google App Engine)
🚫 **NEVER put actual secrets in app.yaml!**

Set via gcloud command:
```bash
gcloud app deploy --set-env-vars \
  GOOGLE_OAUTH2_KEY=your-prod-client-id,\
  GOOGLE_OAUTH2_SECRET=your-prod-client-secret
```

### CI/CD (GitHub Actions)
Add these as Repository Secrets in GitHub:
- `GOOGLE_OAUTH2_KEY`
- `GOOGLE_OAUTH2_SECRET`

📖 **For detailed security practices, see `ENVIRONMENT_SECURITY.md`**

## 4. Test the Setup

1. Start your development server
2. Go to the login page
3. Click "Continue with Google"
4. You should be redirected to Google for authentication

## Troubleshooting

- Ensure redirect URIs match exactly (including trailing slash)
- Check that the Google+ API is enabled
- Verify environment variables are loaded correctly