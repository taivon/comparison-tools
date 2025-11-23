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
   - For production: `https://apartments.comparison.tools/accounts/complete/google-oauth2/`

## 3. Set Environment Variables

### Local Development
Create a `.env` file in your project root:
```bash
GOOGLE_OAUTH2_KEY=your_client_id_here
GOOGLE_OAUTH2_SECRET=your_client_secret_here
```

### Production (Google App Engine)
Add to your app.yaml:
```yaml
env_variables:
  GOOGLE_OAUTH2_KEY: your_client_id_here
  GOOGLE_OAUTH2_SECRET: your_client_secret_here
```

Or set via GitHub Secrets for CI/CD:
- `GOOGLE_OAUTH2_KEY`
- `GOOGLE_OAUTH2_SECRET`

## 4. Test the Setup

1. Start your development server
2. Go to the login page
3. Click "Continue with Google"
4. You should be redirected to Google for authentication

## Troubleshooting

- Ensure redirect URIs match exactly (including trailing slash)
- Check that the Google+ API is enabled
- Verify environment variables are loaded correctly