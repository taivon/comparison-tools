from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apartments.firestore_service import FirestoreService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update apartment user_ids from SQLite IDs to Firestore document IDs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the migration without actually updating apartments",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No apartments will be updated")
            )

        firestore_service = FirestoreService()

        # Build mapping from SQLite ID to Firestore document ID
        sqlite_users = User.objects.all()
        id_mapping = {}

        self.stdout.write("Building user ID mapping:")
        for sqlite_user in sqlite_users:
            firestore_user = firestore_service.get_user_by_username(
                sqlite_user.username
            )
            if firestore_user:
                id_mapping[str(sqlite_user.id)] = firestore_user.doc_id
                self.stdout.write(
                    f"  SQLite ID {sqlite_user.id} ({sqlite_user.username}) -> Firestore ID {firestore_user.doc_id}"
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  SQLite ID {sqlite_user.id} ({sqlite_user.username}) -> NOT FOUND in Firestore"
                    )
                )

        # Get all apartments and update their user_ids
        apartments = firestore_service.get_all_apartments()
        self.stdout.write(f"\nFound {len(apartments)} apartments to process:")
        self.stdout.write("-" * 80)

        updated_count = 0
        skipped_count = 0

        for apartment in apartments:
            old_user_id = apartment.user_id

            if old_user_id in id_mapping:
                new_user_id = id_mapping[old_user_id]

                if dry_run:
                    self.stdout.write(
                        f"WOULD UPDATE: {apartment.name} - User ID {old_user_id} -> {new_user_id}"
                    )
                else:
                    try:
                        # Update the apartment with new user_id
                        update_data = {"user_id": new_user_id}
                        firestore_service.update_apartment(
                            apartment.doc_id, update_data
                        )

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"UPDATED: {apartment.name} - User ID {old_user_id} -> {new_user_id}"
                            )
                        )
                        updated_count += 1

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"ERROR updating {apartment.name}: {e}")
                        )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIPPING: {apartment.name} - Unknown user ID {old_user_id}"
                    )
                )
                skipped_count += 1

        self.stdout.write("-" * 80)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN COMPLETE: Would update {len(apartments) - skipped_count} apartments"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"MIGRATION COMPLETE: {updated_count} apartments updated, {skipped_count} skipped"
                )
            )
