from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from .firestore_service import FirestoreService
import logging

logger = logging.getLogger(__name__)


class FirestoreSessionMiddleware:
    """Custom middleware to handle Firestore user sessions"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Get user from session
        user_id = request.session.get('user_id')
        if user_id:
            try:
                firestore_service = FirestoreService()
                request.user = firestore_service.get_user(user_id)
                if request.user is None:
                    # User not found, clear session
                    request.session.flush()
                    request.user = AnonymousFirestoreUser()
            except Exception as e:
                logger.error(f"Error loading user from session: {e}")
                request.user = AnonymousFirestoreUser()
        else:
            request.user = AnonymousFirestoreUser()
            
        response = self.get_response(request)
        return response


class AnonymousFirestoreUser:
    """Anonymous user class for Firestore authentication"""
    
    def __init__(self):
        self.id = None
        self.doc_id = None
        self.username = ""
        self.email = ""
        self.first_name = ""
        self.last_name = ""
        self.is_staff = False
        self.is_active = False
        self.is_authenticated = False
        self.is_anonymous = True
        
    def __str__(self):
        return "AnonymousUser"
        
    def get_full_name(self):
        return ""
        
    def get_short_name(self):
        return ""