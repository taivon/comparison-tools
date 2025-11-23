from django.contrib.auth.backends import BaseBackend
from .firestore_service import FirestoreService
import logging

logger = logging.getLogger(__name__)


class FirestoreAuthBackend(BaseBackend):
    """Custom authentication backend for Firestore users"""

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate user against Firestore"""
        if username is None or password is None:
            return None

        try:
            firestore_service = FirestoreService()
            user = firestore_service.authenticate_user(username, password)
            return user
        except Exception as e:
            logger.error(f"Error authenticating user {username}: {e}")
            return None

    def get_user(self, user_id):
        """Get user by ID"""
        try:
            firestore_service = FirestoreService()
            return firestore_service.get_user(str(user_id))
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
