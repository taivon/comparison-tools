"""
WSGI entry point for Google App Engine
"""

import os

import django
from django.conf import settings
from django.core.management import execute_from_command_line

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Initialize Google Cloud Profiler in production
if not settings.DEBUG:
    try:
        import logging

        logger = logging.getLogger(__name__)

        from google.cloud import profiler

        # Get version from App Engine environment
        version = os.environ.get("GAE_VERSION", os.environ.get("GAE_DEPLOYMENT_ID", "default"))

        logger.info(f"Initializing Cloud Profiler for service: comparison-tools, version: {version}")

        profiler.start(
            service="comparison-tools",
            service_version=version,
            verbose=1,  # Enable verbose logging to see what's happening
        )

        logger.info("Cloud Profiler initialized successfully")
    except ImportError as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Cloud Profiler package not available: {e}")
    except Exception as e:
        # Profiler initialization is optional, but log the error for debugging
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to initialize Cloud Profiler: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")

# Initialize database on App Engine startup (only in production)
if not settings.DEBUG:
    try:
        import sys
        from io import StringIO

        from django.core.management.base import CommandError

        # Capture output to avoid cluttering logs
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()

        try:
            execute_from_command_line(["manage.py", "init_db"])
        except CommandError:
            pass  # Ignore command errors during startup
        finally:
            sys.stdout = old_stdout

    except Exception as e:
        # Don't fail startup if database initialization fails
        print(f"Warning: Database initialization failed: {e}")

from config.wsgi import application

# App Engine expects a WSGI application called 'app'
app = application
