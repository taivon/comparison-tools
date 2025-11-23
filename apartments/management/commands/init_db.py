from django.core.management.base import BaseCommand
from django.core.management import execute_from_command_line
from django.conf import settings
from django.db import connection
import os
import sys


class Command(BaseCommand):
    help = "Initialize database for App Engine deployment"

    def handle(self, *args, **options):
        """Initialize the database with necessary tables for Django auth/admin"""

        if settings.DEBUG:
            self.stdout.write(self.style.SUCCESS("Skipping init_db in DEBUG mode"))
            return

        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]

            # Check if we have the essential tables
            essential_tables = ["auth_user", "django_session", "django_content_type"]
            missing_tables = [
                table for table in essential_tables if table not in tables
            ]

            if missing_tables:
                self.stdout.write(f"Missing tables: {missing_tables}")
                self.stdout.write("Running migrations...")

                # Run migrations
                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                execute_from_command_line(["manage.py", "migrate", "--run-syncdb"])

                self.stdout.write(
                    self.style.SUCCESS("Database initialized successfully")
                )
            else:
                self.stdout.write(self.style.SUCCESS("Database already initialized"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error initializing database: {e}"))
            # Don't fail the startup, just log the error
            pass
