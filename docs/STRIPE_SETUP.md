# Stripe Subscription Setup Guide

This guide walks you through setting up Stripe subscriptions for the Apartment Comparison Tool.

## Table of Contents

- [Development Setup](#development-setup)
- [Production Setup](#production-setup)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Stripe Account

1. Sign up at https://stripe.com
2. Complete your account setup
3. Switch to **Test Mode** (toggle in top right of dashboard)

### 3. Get Test API Keys

From https://dashboard.stripe.com/test/apikeys:

- Copy **Publishable key** (starts with `pk_test_`)
- Copy **Secret key** (starts with `sk_test_`)

### 4. Create Test Products & Prices

1. Go to https://dashboard.stripe.com/test/products
2. Click **+ Add product**
3. Create product:
   - Name: `Premium Subscription`
   - Description: `Unlimited apartment comparisons and premium features`
   - Pricing model: `Recurring`

4. Add two prices to the product:

   **Monthly Price:**
   - Price: `$9.99`
   - Billing period: `Monthly`
   - Copy the Price ID (starts with `price_`)

   **Annual Price:**
   - Price: `$99`
   - Billing period: `Yearly`
   - Copy the Price ID (starts with `price_`)

### 5. Set Up Local Webhook (Optional for Development)

To test webhooks locally:

```bash
# Install Stripe CLI
brew install stripe/stripe-brew/stripe

# Login to Stripe
stripe login

# Forward webhooks to your local server
stripe listen --forward-to http://localhost:8000/webhook/stripe/
```

This will give you a webhook secret starting with `whsec_`.

### 6. Configure Environment Variables

Add to your `.env` file:

```bash
# Stripe Test/Sandbox Keys (for local development)
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_MONTHLY_PRICE_ID=price_your_monthly_price_id_here
STRIPE_ANNUAL_PRICE_ID=price_your_annual_price_id_here
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

Visit http://localhost:8000/pricing/ to see the pricing page!

### 8. Test with Test Cards

Stripe provides test card numbers:

- **Success:** `4242 4242 4242 4242`
- **Decline:** `4000 0000 0000 0002`
- **Requires authentication:** `4000 0025 0000 3155`

Use any future expiration date and any 3-digit CVC.

---

## Production Setup

### 1. Switch to Live Mode in Stripe

1. In your Stripe Dashboard, toggle from **Test mode** to **Live mode**
2. Complete your business information and activate your account

### 2. Get Live API Keys

From https://dashboard.stripe.com/apikeys:

- Copy **Publishable key** (starts with `pk_live_`)
- Copy **Secret key** (starts with `sk_live_`)

### 3. Create Live Products & Prices

1. Go to https://dashboard.stripe.com/products
2. Create the same product structure as in test mode:
   - Product: `Premium Subscription`
   - Monthly Price: `$9.99/month` → Copy Price ID
   - Annual Price: `$99/year` → Copy Price ID

### 4. Set Up Production Webhook

1. Go to https://dashboard.stripe.com/webhooks
2. Click **+ Add endpoint**
3. Endpoint URL: `https://apartments.comparison.tools/webhook/stripe/`
4. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_`)

### 5. Add Secrets to Google Secret Manager

**Option A: Use the Setup Script (Recommended)**

```bash
./scripts/setup-stripe-secrets.sh
```

This interactive script will guide you through adding all secrets.

**Option B: Manually Add Secrets**

```bash
# Set your project ID
PROJECT_ID="comparison-tools-479102"

# Add Stripe Publishable Key
echo -n "pk_live_your_key" | gcloud secrets create stripe-publishable-key \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

# Add Stripe Secret Key
echo -n "sk_live_your_key" | gcloud secrets create stripe-secret-key \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

# Add Webhook Secret
echo -n "whsec_your_secret" | gcloud secrets create stripe-webhook-secret \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

# Add Monthly Price ID
echo -n "price_monthly_id" | gcloud secrets create stripe-monthly-price-id \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

# Add Annual Price ID
echo -n "price_annual_id" | gcloud secrets create stripe-annual-price-id \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic"
```

### 6. Grant App Engine Access to Secrets

```bash
PROJECT_ID="comparison-tools-479102"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant access to each secret
for SECRET in stripe-publishable-key stripe-secret-key stripe-webhook-secret stripe-monthly-price-id stripe-annual-price-id; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
done
```

### 7. Deploy to Production

```bash
gcloud app deploy
```

### 8. Verify Production Setup

1. Visit https://apartments.comparison.tools/pricing/
2. Test the subscription flow with a real card (you can cancel immediately)
3. Check Stripe Dashboard → Events to verify webhook delivery
4. Check App Engine logs for any errors:
   ```bash
   gcloud app logs tail -s default
   ```

---

## Testing

### Test Subscription Flow

1. **Sign up for account** → Create a new user
2. **Visit pricing page** → `/pricing/`
3. **Click "Get Started"** → Should redirect to Stripe Checkout
4. **Complete payment** → Use test card `4242 4242 4242 4242`
5. **Verify redirect** → Should return to dashboard with success message
6. **Check premium status** → Should see "Premium" badge in header
7. **Add apartments** → Should be able to add unlimited apartments

### Test Webhook Events

Monitor webhook delivery in Stripe Dashboard:
- Go to https://dashboard.stripe.com/webhooks
- Click on your webhook endpoint
- View recent deliveries
- Check for any failed deliveries

### Test Billing Portal

1. As a premium user, click the **Premium** badge in header
2. Should redirect to Stripe Customer Portal
3. Test features:
   - Update payment method
   - View invoices
   - Cancel subscription

### Test Cancellation Flow

1. Cancel subscription via billing portal
2. Verify access is maintained until end of billing period
3. After period ends, verify user returns to free tier

---

## Troubleshooting

### Webhook Signature Verification Fails

**Symptoms:** Webhook endpoint returns 400 error

**Solutions:**
1. Verify `STRIPE_WEBHOOK_SECRET` matches the webhook signing secret in Stripe Dashboard
2. Check that the webhook secret in Secret Manager is correct
3. Ensure no extra whitespace in the secret value

### Secrets Not Loading in Production

**Symptoms:** Error in logs: "Failed to fetch Stripe credentials from Secret Manager"

**Solutions:**
1. Verify secrets exist:
   ```bash
   gcloud secrets list --project=comparison-tools-479102
   ```
2. Check IAM permissions:
   ```bash
   gcloud secrets get-iam-policy stripe-secret-key --project=comparison-tools-479102
   ```
3. Ensure App Engine service account has `secretAccessor` role

### Checkout Session Creation Fails

**Symptoms:** Error when clicking "Get Started" button

**Solutions:**
1. Check browser console for JavaScript errors
2. Verify `STRIPE_PUBLISHABLE_KEY` is set correctly
3. Check that Price IDs are valid in Stripe Dashboard
4. Review App Engine logs for backend errors

### Subscription Status Not Syncing

**Symptoms:** User payment succeeded but still shows as free tier

**Solutions:**
1. Check webhook delivery in Stripe Dashboard
2. Verify webhook endpoint is accessible (not blocked by firewall)
3. Check App Engine logs for webhook processing errors
4. Manually trigger a webhook resend from Stripe Dashboard

### Price Mismatch

**Symptoms:** Checkout shows wrong price

**Solutions:**
1. Verify `STRIPE_MONTHLY_PRICE_ID` and `STRIPE_ANNUAL_PRICE_ID` are correct
2. Check that price IDs match between Secret Manager and Stripe Dashboard
3. Update secrets if price IDs changed:
   ```bash
   echo -n "price_new_id" | gcloud secrets versions add stripe-monthly-price-id --data-file=-
   ```

---

## Architecture Overview

### Flow Diagram

```
User clicks "Get Started"
    ↓
Frontend calls /subscription/create-checkout-session/
    ↓
Backend creates Stripe Checkout Session
    ↓
User redirected to Stripe Checkout
    ↓
User completes payment
    ↓
Stripe sends webhook to /webhook/stripe/
    ↓
Backend syncs subscription to Firestore
    ↓
User redirected to /subscription/success/
    ↓
User sees premium features
```

### Key Components

- **`stripe_service.py`** - Core Stripe integration logic
- **`views.py`** - Checkout and webhook endpoints
- **`firestore_service.py`** - User model with subscription fields
- **`pricing.html`** - Frontend pricing page with Stripe.js

### Data Model

User document in Firestore:
```python
{
    "stripe_customer_id": "cus_...",
    "stripe_subscription_id": "sub_...",
    "subscription_status": "active",  # active, canceled, past_due
    "subscription_plan": "monthly",   # monthly, annual
    "subscription_current_period_end": datetime,
    "subscription_cancel_at_period_end": False,
}
```

---

## Support

For issues or questions:
- Stripe Documentation: https://stripe.com/docs
- Google Secret Manager: https://cloud.google.com/secret-manager/docs
- Project Issues: https://github.com/yourusername/comparison-tools/issues
