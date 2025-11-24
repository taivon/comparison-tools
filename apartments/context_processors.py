"""
Context processors for making data available to all templates.
"""
from django.conf import settings
from .stripe_service import StripeService


def subscription_status(request):
    """Add subscription status to all template contexts"""
    has_premium = False

    if request.user.is_authenticated:
        has_premium = StripeService.has_active_subscription(request.user)

    return {
        'user_has_premium': has_premium,
        'stripe_enabled': settings.STRIPE_ENABLED,
    }
