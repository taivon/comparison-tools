"""
WSGI entry point for Google App Engine
"""
from config.wsgi import application

# App Engine expects a WSGI application called 'app'
app = application