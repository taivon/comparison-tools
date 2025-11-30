"""
Context processors for making data available to all templates.
"""

from django.conf import settings

from .models import user_has_premium


def subscription_status(request):
    """Add subscription status to all template contexts"""
    # Determine product slug from the URL path
    path = request.path

    # Store current path in session for OAuth redirect (One Tap support)
    # Skip auth-related paths to avoid redirect loops
    auth_paths = ["/login/", "/logout/", "/signup/", "/auth/"]
    if not request.user.is_authenticated and not any(path.startswith(p) for p in auth_paths):
        request.session["oauth_next"] = request.get_full_path()
    if path.startswith("/apartments"):
        product_slug = "apartments"
    elif path.startswith("/homes"):
        product_slug = "homes"
    elif path.startswith("/cars"):
        product_slug = "cars"
    elif path.startswith("/hotels"):
        product_slug = "hotels"
    else:
        product_slug = "apartments"  # Default

    has_premium = False
    if request.user.is_authenticated:
        has_premium = user_has_premium(request.user, product_slug)

    return {
        "user_has_premium": has_premium,
        "is_premium": has_premium,  # Alias for convenience
        "stripe_enabled": settings.STRIPE_ENABLED,
        "current_product_slug": product_slug,
        "google_client_id": getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", ""),
    }
