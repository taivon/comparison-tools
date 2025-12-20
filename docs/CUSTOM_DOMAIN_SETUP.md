# Custom Domain Setup for apartments.comparison.tools

This guide explains how to configure your custom domain `apartments.comparison.tools` with Google App Engine.

## Prerequisites

- Domain `comparison.tools` is registered and managed by you
- Google Cloud project `comparison-tools-479102` is set up
- App Engine application is deployed

## Step 1: Add Custom Domain in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select project: `comparison-tools-479102`
3. Navigate to **App Engine** → **Settings** → **Custom Domains**
4. Click **"Add a custom domain"**
5. Enter: `apartments.comparison.tools`
6. Follow the verification process

## Step 2: Configure DNS Records

Google will provide you with DNS records to add. You'll need to add these to your domain registrar:

### Option A: Using CNAME (Recommended)
Add a CNAME record:
```
Type: CNAME
Name: apartments
Value: ghs.googlehosted.com
TTL: 3600 (or default)
```

### Option B: Using A Records (if CNAME not supported)
Google will provide specific A records - add those to your DNS.

## Step 3: SSL Certificate

Google App Engine automatically provisions SSL certificates for custom domains. This usually takes a few minutes to a few hours after DNS is configured.

## Step 4: Verify Configuration

After DNS propagation (can take up to 48 hours, usually much faster):

1. Check DNS propagation: `dig apartments.comparison.tools`
2. Verify SSL certificate: `curl -I https://apartments.comparison.tools`
3. Test the site: Visit `https://apartments.comparison.tools` in your browser

## Step 5: Update Configuration (Already Done)

The following files have been updated:
- `app.yaml` - Set `APPENGINE_URL` to `https://apartments.comparison.tools`
- `config/settings.py` - Added domain to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`

## Troubleshooting

### Domain not resolving
- Wait for DNS propagation (can take up to 48 hours)
- Verify DNS records are correct using `dig` or online DNS checker
- Check that the domain is verified in Google Cloud Console

### SSL certificate issues
- Wait a few hours for automatic certificate provisioning
- Check App Engine → Settings → Custom Domains for certificate status
- Ensure DNS is correctly configured

### 404 or App not found
- Verify the App Engine app is deployed
- Check that the custom domain is mapped to the correct service
- Review App Engine logs for errors

## Testing

Once configured, you can test:
```bash
# Test DNS
dig apartments.comparison.tools

# Test HTTPS
curl -I https://apartments.comparison.tools

# Test from browser
open https://apartments.comparison.tools
```

## Notes

- The App Engine default URL (`comparison-tools-479102.uc.r.appspot.com`) will continue to work as a fallback
- Both URLs are configured in `ALLOWED_HOSTS` for flexibility
- SSL is automatically managed by Google App Engine

