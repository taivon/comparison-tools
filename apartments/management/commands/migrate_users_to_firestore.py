from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apartments.firestore_service import FirestoreService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate users from SQLite to Firestore"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the migration without actually creating users",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No users will be created")
            )

        firestore_service = FirestoreService()
        sqlite_users = User.objects.all()

        self.stdout.write(f"Found {sqlite_users.count()} users in SQLite")
        self.stdout.write("-" * 80)

        migrated_count = 0
        skipped_count = 0

        for sqlite_user in sqlite_users:
            # Check if user already exists in Firestore
            existing_user = firestore_service.get_user_by_username(sqlite_user.username)
            if existing_user:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIPPING: User {sqlite_user.username} already exists in Firestore"
                    )
                )
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"WOULD MIGRATE: {sqlite_user.username} ({sqlite_user.email}) - "
                    f"Staff: {sqlite_user.is_staff} - Joined: {sqlite_user.date_joined}"
                )
            else:
                try:
                    # Create user data
                    user_data = {
                        "username": sqlite_user.username,
                        "email": sqlite_user.email,
                        "first_name": sqlite_user.first_name,
                        "last_name": sqlite_user.last_name,
                        "is_staff": sqlite_user.is_staff,
                        "is_active": sqlite_user.is_active,
                        "date_joined": sqlite_user.date_joined,
                        "last_login": sqlite_user.last_login,
                    }

                    # Create Firestore user with a default password
                    # Note: Users will need to reset their passwords
                    default_password = "temppassword123"
                    firestore_user = firestore_service.create_user(
                        user_data, default_password
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"MIGRATED: {sqlite_user.username} -> {firestore_user.doc_id}"
                        )
                    )
                    migrated_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"ERROR migrating {sqlite_user.username}: {e}")
                    )

        self.stdout.write("-" * 80)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN COMPLETE: Would migrate {sqlite_users.count() - skipped_count} users"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"MIGRATION COMPLETE: {migrated_count} users migrated, {skipped_count} skipped"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'IMPORTANT: All migrated users have the temporary password "temppassword123"'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "Users will need to reset their passwords on first login"
                )
            )
