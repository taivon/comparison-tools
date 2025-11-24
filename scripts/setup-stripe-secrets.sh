#!/bin/bash
# Setup Stripe secrets in Google Secret Manager for production
# Run this script once you have your live Stripe credentials

set -e

PROJECT_ID="comparison-tools-479102"

echo "=========================================="
echo "Stripe Secret Manager Setup"
echo "=========================================="
echo ""
echo "This script will add your Stripe credentials to Google Secret Manager."
echo "Make sure you have:"
echo "  1. gcloud CLI installed and authenticated"
echo "  2. Your Stripe LIVE credentials ready (from Stripe Dashboard)"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Function to create or update a secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    # Check if secret exists
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        echo "Secret '$secret_name' already exists. Adding new version..."
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --data-file=- \
            --project="$PROJECT_ID"
    else
        echo "Creating secret '$secret_name'..."
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --data-file=- \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"
    fi
}

echo ""
echo "Enter your Stripe LIVE credentials:"
echo "(You can find these at: https://dashboard.stripe.com/apikeys)"
echo ""

# Publishable Key
read -p "Stripe Publishable Key (pk_live_...): " STRIPE_PUBLISHABLE_KEY
if [[ ! $STRIPE_PUBLISHABLE_KEY == pk_live_* ]]; then
    echo "Warning: This doesn't look like a LIVE publishable key (should start with pk_live_)"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! $confirm == "y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Secret Key
read -sp "Stripe Secret Key (sk_live_...): " STRIPE_SECRET_KEY
echo ""
if [[ ! $STRIPE_SECRET_KEY == sk_live_* ]]; then
    echo "Warning: This doesn't look like a LIVE secret key (should start with sk_live_)"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! $confirm == "y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Webhook Secret
echo ""
echo "Go to: https://dashboard.stripe.com/webhooks"
echo "Create an endpoint for: https://apartments.comparison.tools/webhook/stripe/"
echo "Select these events:"
echo "  - checkout.session.completed"
echo "  - customer.subscription.updated"
echo "  - customer.subscription.deleted"
echo "  - invoice.payment_succeeded"
echo "  - invoice.payment_failed"
echo ""
read -sp "Stripe Webhook Secret (whsec_...): " STRIPE_WEBHOOK_SECRET
echo ""
if [[ ! $STRIPE_WEBHOOK_SECRET == whsec_* ]]; then
    echo "Warning: This doesn't look like a webhook secret (should start with whsec_)"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! $confirm == "y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Price IDs
echo ""
echo "Go to: https://dashboard.stripe.com/products"
echo "Create a product called 'Premium Subscription' with two prices:"
echo "  - Monthly: \$9.99/month recurring"
echo "  - Annual: \$99/year recurring"
echo ""
read -p "Monthly Price ID (price_...): " STRIPE_MONTHLY_PRICE_ID
if [[ ! $STRIPE_MONTHLY_PRICE_ID == price_* ]]; then
    echo "Warning: This doesn't look like a price ID (should start with price_)"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! $confirm == "y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

read -p "Annual Price ID (price_...): " STRIPE_ANNUAL_PRICE_ID
if [[ ! $STRIPE_ANNUAL_PRICE_ID == price_* ]]; then
    echo "Warning: This doesn't look like a price ID (should start with price_)"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! $confirm == "y" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "Creating secrets in Google Secret Manager..."
echo "=========================================="
echo ""

create_or_update_secret "stripe-publishable-key" "$STRIPE_PUBLISHABLE_KEY"
create_or_update_secret "stripe-secret-key" "$STRIPE_SECRET_KEY"
create_or_update_secret "stripe-webhook-secret" "$STRIPE_WEBHOOK_SECRET"
create_or_update_secret "stripe-monthly-price-id" "$STRIPE_MONTHLY_PRICE_ID"
create_or_update_secret "stripe-annual-price-id" "$STRIPE_ANNUAL_PRICE_ID"

echo ""
echo "=========================================="
echo "✅ All Stripe secrets created successfully!"
echo "=========================================="
echo ""
echo "Secrets created:"
echo "  - stripe-publishable-key"
echo "  - stripe-secret-key"
echo "  - stripe-webhook-secret"
echo "  - stripe-monthly-price-id"
echo "  - stripe-annual-price-id"
echo ""
echo "Next steps:"
echo "  1. Deploy your application to App Engine"
echo "  2. Test the subscription flow on your live site"
echo "  3. Monitor webhooks in Stripe Dashboard"
echo ""
