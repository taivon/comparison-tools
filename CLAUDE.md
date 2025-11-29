# Project Context for Claude

## Deployment
- **Platform**: Google App Engine
- **Database**: Supabase PostgreSQL
- **Authentication**: Google OAuth only (via social-auth-app-django)

## Architecture
- Django 5.x web application
- Multi-product comparison tools (apartments, homes, hotels)
- Stripe integration for subscriptions
- Tailwind CSS for styling

## Key Commands
```bash
# Run locally
python manage.py runserver

# Run migrations
python manage.py migrate

# Seed subscription products/plans
python manage.py seed_products

# Deploy to App Engine
gcloud app deploy
```

## Environment Variables (Production)
- `DATABASE_URL` - Supabase PostgreSQL connection string
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `SOCIAL_AUTH_GOOGLE_OAUTH2_KEY` - Google OAuth client ID
- `SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET` - Google OAuth client secret
- `SECRET_KEY` - Django secret key
- `GOOGLE_MAPS_API_KEY` - Google Maps API key (for address autocomplete and driving distances)
