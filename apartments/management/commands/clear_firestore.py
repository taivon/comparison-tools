from django.core.management.base import BaseCommand
from apartments.firestore_service import FirestoreService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clear all data from Firestore (users, apartments, preferences)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to delete ALL data from Firestore",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be deleted without actually deleting anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]

        if not dry_run and not confirm:
            self.stdout.write(
                self.style.ERROR("This command will DELETE ALL DATA from Firestore!")
            )
            self.stdout.write(
                self.style.ERROR(
                    "Use --confirm to actually delete data, or --dry-run to preview"
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No data will be deleted")
            )

        firestore_service = FirestoreService()

        # Count and delete apartments
        self.stdout.write("\n=== APARTMENTS ===")
        apartments = firestore_service.get_all_apartments()
        self.stdout.write(f"Found {len(apartments)} apartments")

        if apartments:
            for apartment in apartments:
                if dry_run:
                    self.stdout.write(
                        f"WOULD DELETE: {apartment.name} (ID: {apartment.doc_id})"
                    )
                else:
                    try:
                        firestore_service.delete_apartment(apartment.doc_id)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"DELETED: {apartment.name} (ID: {apartment.doc_id})"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"ERROR deleting apartment {apartment.name}: {e}"
                            )
                        )

        # Count and delete user preferences
        self.stdout.write("\n=== USER PREFERENCES ===")
        try:
            preferences_collection = firestore_service.db.collection("user_preferences")
            preferences_docs = list(preferences_collection.stream())
            self.stdout.write(f"Found {len(preferences_docs)} user preference records")

            for doc in preferences_docs:
                if dry_run:
                    self.stdout.write(f"WOULD DELETE: Preferences for user {doc.id}")
                else:
                    try:
                        doc.reference.delete()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"DELETED: Preferences for user {doc.id}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"ERROR deleting preferences for {doc.id}: {e}"
                            )
                        )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"ERROR accessing user preferences: {e}")
            )

        # Count and delete users
        self.stdout.write("\n=== USERS ===")
        try:
            users_collection = firestore_service.db.collection("users")
            user_docs = list(users_collection.stream())
            self.stdout.write(f"Found {len(user_docs)} users")

            for doc in user_docs:
                user_data = doc.to_dict()
                username = user_data.get("username", "Unknown")
                email = user_data.get("email", "No email")

                if dry_run:
                    self.stdout.write(
                        f"WOULD DELETE: {username} ({email}) - ID: {doc.id}"
                    )
                else:
                    try:
                        doc.reference.delete()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"DELETED: {username} ({email}) - ID: {doc.id}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"ERROR deleting user {username}: {e}")
                        )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"ERROR accessing users: {e}"))

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("DRY RUN COMPLETE - No data was actually deleted")
            )
            self.stdout.write("To actually delete the data, run:")
            self.stdout.write("python manage.py clear_firestore --confirm")
        else:
            self.stdout.write(self.style.SUCCESS("FIRESTORE CLEANUP COMPLETE"))
            self.stdout.write(
                "All users, apartments, and preferences have been deleted"
            )
