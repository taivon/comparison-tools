from django.shortcuts import redirect
from django.contrib import messages
from .firestore_service import FirestoreService
from .middleware import AnonymousFirestoreUser
import logging

logger = logging.getLogger(__name__)


def firestore_login(request, user):
    """Log in a Firestore user by storing their ID in the session"""
    if user and user.is_authenticated and user.is_active:
        request.session['user_id'] = user.doc_id
        request.user = user
        return True
    return False


def firestore_logout(request):
    """Log out the current user by clearing the session"""
    request.session.flush()
    request.user = AnonymousFirestoreUser()


def firestore_authenticate(username, password):
    """Authenticate user with Firestore"""
    try:
        firestore_service = FirestoreService()
        return firestore_service.authenticate_user(username, password)
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


def login_required_firestore(view_func):
    """Decorator to require Firestore authentication"""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper