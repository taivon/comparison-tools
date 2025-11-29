"""
Context processors for making data available to all templates.
"""
from django.conf import settings
from .models import user_has_premium


def subscription_status(request):
    """Add subscription status to all template contexts"""
    # Determine product slug from the URL path
    path = request.path
    if path.startswith('/apartments'):
        product_slug = 'apartments'
    elif path.startswith('/homes'):
        product_slug = 'homes'
    elif path.startswith('/cars'):
        product_slug = 'cars'
    elif path.startswith('/hotels'):
        product_slug = 'hotels'
    else:
        product_slug = 'apartments'  # Default

    has_premium = False
    if request.user.is_authenticated:
        has_premium = user_has_premium(request.user, product_slug)

    return {
        'user_has_premium': has_premium,
        'stripe_enabled': settings.STRIPE_ENABLED,
        'current_product_slug': product_slug,
    }
