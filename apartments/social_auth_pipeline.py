from apartments.firestore_service import FirestoreService
from apartments.auth_utils import firestore_login
import logging

logger = logging.getLogger(__name__)


def create_firestore_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Custom social auth pipeline step to create/sync user in Firestore
    This replaces Django's default user creation
    """
    if user:
        return {'is_new': False}
    
    firestore_service = FirestoreService()
    
    # Get user data from social auth
    email = details.get('email')
    if not email:
        logger.error("No email provided by social auth")
        return None
    
    # Check if user already exists in Firestore
    existing_user = firestore_service.get_user_by_email(email)
    
    if existing_user:
        # User exists, just log them in
        request = strategy.request
        firestore_login(request, existing_user)
        return {'is_new': False, 'user': existing_user}
    
    # Create new Firestore user
    first_name = details.get('first_name', '')
    last_name = details.get('last_name', '')
    username = details.get('username', email.split('@')[0])
    
    # Ensure username is unique
    counter = 1
    base_username = username
    while firestore_service.get_user_by_username(username):
        username = f"{base_username}{counter}"
        counter += 1
    
    user_data = {
        'username': username,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'is_staff': False,  # New users start as free tier
    }
    
    # Create user in Firestore
    firestore_user = firestore_service.create_firebase_user(user_data)
    
    # Log user into Django session
    request = strategy.request
    firestore_login(request, firestore_user)
    
    logger.info(f"Created new Firestore user: {firestore_user.username}")
    
    return {'is_new': True, 'user': firestore_user}


def associate_firestore_user(strategy, details, backend, uid, user=None, *args, **kwargs):
    """
    Skip Django's user association since we handle everything in Firestore
    """
    return None  # Don't create Django User objects