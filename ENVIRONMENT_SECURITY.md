# Environment Security Guide

## 🔒 Security Overview

This document outlines secure practices for managing environment variables and sensitive credentials in the Comparison Tools project.

## ⚠️ Critical Security Rules

### 🚫 NEVER commit these files:
- `.env` (contains actual secrets)
- Any file with actual OAuth credentials
- Service account keys or API keys

### ✅ Safe to commit:
- `.env.example` (template with placeholder values)
- `ENVIRONMENT_SECURITY.md` (this documentation)
- Configuration files that reference environment variables

## 🛠️ Local Development Setup

### 1. Initial Setup
```bash
# Copy the example file
cp .env.example .env

# Set secure permissions (Unix/macOS)
chmod 600 .env

# Edit with your actual credentials
nano .env  # or your preferred editor
```

### 2. Get OAuth Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services → Credentials
3. Create OAuth 2.0 Client ID (Web application)
4. Add redirect URI: `http://localhost:8000/accounts/complete/google-oauth2/`
5. Copy Client ID and Client Secret to your `.env` file

### 3. Required Environment Variables
```bash
# Your .env file should contain:
GOOGLE_OAUTH2_KEY=your-actual-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_SECRET=your-actual-client-secret
DEBUG=True
SECRET_KEY=your-local-secret-key
```

## 🚀 Production Deployment

### Google App Engine
Set environment variables using gcloud:
```bash
gcloud app deploy --set-env-vars \
  GOOGLE_OAUTH2_KEY=your-prod-client-id,\
  GOOGLE_OAUTH2_SECRET=your-prod-client-secret
```

### GitHub Actions (CI/CD)
Add these as Repository Secrets:
- `GOOGLE_OAUTH2_KEY`
- `GOOGLE_OAUTH2_SECRET`
- `GCP_SA_KEY` (service account JSON)

## 🔄 Credential Rotation

### Quarterly Security Review
1. **Rotate OAuth credentials** every 3 months
2. **Update GitHub Secrets** with new values
3. **Deploy with new credentials** to App Engine
4. **Test authentication** on all environments

### Emergency Rotation
If credentials are compromised:
1. **Immediately revoke** old credentials in Google Cloud Console
2. **Generate new credentials**
3. **Update all environments** (local, staging, production)
4. **Verify functionality**

## 👥 Team Onboarding

### New Developer Setup
1. **Clone repository** (no secrets included)
2. **Copy `.env.example` to `.env`**
3. **Request access** to development OAuth app
4. **Get credentials** from team lead (never via chat/email)
5. **Test locally** before first commit

### Security Training
- Never commit `.env` files
- Use secure channels for credential sharing
- Report suspected credential exposure immediately
- Rotate credentials if accidentally exposed

## 🔍 Security Validation

### Pre-commit Checklist
- [ ] `.env` file is in `.gitignore`
- [ ] No hardcoded secrets in code
- [ ] Environment variables used for all sensitive data
- [ ] `.env.example` contains only placeholder values

### Monitoring
- Monitor authentication failures in logs
- Set up alerts for unusual OAuth usage
- Regular security audits of access patterns

## 🆘 Incident Response

### If Credentials Are Exposed
1. **DO NOT PANIC** - act quickly but carefully
2. **Revoke compromised credentials** immediately
3. **Generate new credentials**
4. **Update all environments**
5. **Document the incident**
6. **Review security practices**

### Contact Information
- **Security Issues**: [Your security contact]
- **Emergency Access**: [Emergency contact for credential reset]

## 📚 Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Django Environment Variables Best Practices](https://docs.djangoproject.com/en/stable/topics/settings/)
- [Google App Engine Environment Variables](https://cloud.google.com/appengine/docs/standard/python3/runtime#environment_variables)

---
**Remember**: Security is everyone's responsibility. When in doubt, ask the team!