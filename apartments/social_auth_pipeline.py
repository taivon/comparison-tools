from apartments.firestore_service import FirestoreService
from apartments.auth_utils import firestore_login
import logging

logger = logging.getLogger(__name__)


def create_firestore_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Custom social auth pipeline step to create/sync user in Firestore
    This replaces Django's default user creation
    """
    firestore_service = FirestoreService()
    
    # Get user data from social auth
    email = details.get('email')
    if not email:
        logger.error("No email provided by social auth")
        return None
    
    # Check if user already exists in Firestore
    existing_user = firestore_service.get_user_by_email(email)
    
    if existing_user:
        # User exists, log them into Django session
        request = strategy.request
        firestore_login(request, existing_user)
        logger.info(f"Existing Firestore user logged in: {existing_user.username}")
        return {'is_new': False, 'user': existing_user}
    
    # Create new Firestore user
    first_name = details.get('first_name', '')
    last_name = details.get('last_name', '')
    full_name = details.get('fullname', '')
    
    # Try to split full name if first/last not provided
    if not first_name and not last_name and full_name:
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
    
    # Generate username from email
    username = email.split('@')[0]
    
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
    
    try:
        # Create user in Firestore
        firestore_user = firestore_service.create_firebase_user(user_data)
        
        # Log user into Django session
        request = strategy.request
        firestore_login(request, firestore_user)
        
        logger.info(f"Created new Firestore user: {firestore_user.username} ({firestore_user.email})")
        
        return {'is_new': True, 'user': firestore_user}
        
    except Exception as e:
        logger.error(f"Error creating Firestore user: {e}")
        return None


def associate_firestore_user(strategy, details, backend, uid, user=None, *args, **kwargs):
    """
    Skip Django's user association since we handle everything in Firestore
    """
    return None  # Don't create Django User objects