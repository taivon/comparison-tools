"""
Custom social auth pipeline steps for Django authentication.
"""
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)


def create_user_profile(strategy, details, backend, user=None, *args, **kwargs):
    """
    Custom social auth pipeline step to create UserProfile after user creation.
    This is called after the standard user creation pipeline.
    """
    if user is None:
        return None

    from .models import UserProfile

    # Get or create UserProfile
    profile, created = UserProfile.objects.get_or_create(user=user)

    # Update photo URL from Google if available
    response = kwargs.get('response', {})
    picture = response.get('picture') or details.get('picture')

    if picture and profile.photo_url != picture:
        profile.photo_url = picture
        profile.save()

    if created:
        logger.info(f"Created UserProfile for user: {user.username}")
    else:
        logger.info(f"UserProfile already exists for user: {user.username}")

    return None
