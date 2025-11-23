from django.core.management.base import BaseCommand
from apartments.firestore_service import FirestoreService
import json


class Command(BaseCommand):
    help = 'Manage Firestore data - list, view, and delete apartments and preferences'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['list', 'view', 'delete', 'clear'],
            help='Action to perform'
        )
        parser.add_argument(
            '--type',
            choices=['apartments', 'preferences', 'all'],
            default='all',
            help='Data type to operate on'
        )
        parser.add_argument(
            '--id',
            help='ID of specific document to view/delete'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm destructive operations'
        )

    def handle(self, *args, **options):
        service = FirestoreService()
        action = options['action']
        data_type = options['type']
        doc_id = options['id']

        if action == 'list':
            self.list_data(service, data_type)
        elif action == 'view':
            self.view_document(service, data_type, doc_id)
        elif action == 'delete':
            self.delete_document(service, data_type, doc_id, options['confirm'])
        elif action == 'clear':
            self.clear_collection(service, data_type, options['confirm'])

    def list_data(self, service, data_type):
        """List all documents in collection(s)"""
        if data_type in ['apartments', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- APARTMENTS ---'))
            apartments = service.get_all_apartments()
            if apartments:
                for apt in apartments:
                    self.stdout.write(f"ID: {apt.doc_id}")
                    self.stdout.write(f"  Name: {apt.name}")
                    self.stdout.write(f"  Price: ${apt.price}")
                    self.stdout.write(f"  Square Feet: {apt.square_footage}")
                    self.stdout.write("")
            else:
                self.stdout.write("No apartments found")

        if data_type in ['preferences', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- USER PREFERENCES ---'))
            # Get all preferences (we'll need to list users first)
            try:
                from django.contrib.auth.models import User
                users = User.objects.all()
                for user in users:
                    prefs = service.get_user_preferences(user.pk)
                    if prefs:
                        self.stdout.write(f"User ID: {user.pk} ({user.username})")
                        self.stdout.write(f"  Price Weight: {prefs.price_weight}")
                        self.stdout.write(f"  Sqft Weight: {prefs.sqft_weight}")
                        self.stdout.write(f"  Distance Weight: {prefs.distance_weight}")
                        self.stdout.write(f"  Discount Calculation: {prefs.discount_calculation}")
                        self.stdout.write("")
                if not users:
                    self.stdout.write("No users found")
            except Exception as e:
                self.stdout.write(f"Error listing preferences: {e}")

    def view_document(self, service, data_type, doc_id):
        """View a specific document"""
        if not doc_id:
            self.stdout.write(self.style.ERROR("Document ID required for view action"))
            return

        try:
            if data_type == 'apartments':
                apartment = service.get_apartment(doc_id)
                if apartment:
                    self.stdout.write(self.style.SUCCESS(f"Apartment {doc_id}:"))
                    self.stdout.write(json.dumps({
                        'doc_id': apartment.doc_id,
                        'name': apartment.name,
                        'price': float(apartment.price),
                        'square_footage': apartment.square_footage,
                        'lease_length_months': apartment.lease_length_months,
                        'months_free': apartment.months_free,
                        'weeks_free': apartment.weeks_free,
                        'flat_discount': float(apartment.flat_discount),
                        'user_id': apartment.user_id,
                        'created_at': apartment.created_at.isoformat() if apartment.created_at else None
                    }, indent=2))
                else:
                    self.stdout.write(self.style.ERROR(f"Apartment {doc_id} not found"))
                    
            elif data_type == 'preferences':
                prefs = service.get_user_preferences(int(doc_id))
                if prefs:
                    self.stdout.write(self.style.SUCCESS(f"User Preferences {doc_id}:"))
                    self.stdout.write(json.dumps({
                        'user_id': prefs.user_id,
                        'price_weight': prefs.price_weight,
                        'sqft_weight': prefs.sqft_weight,
                        'distance_weight': prefs.distance_weight,
                        'discount_calculation': prefs.discount_calculation
                    }, indent=2))
                else:
                    self.stdout.write(self.style.ERROR(f"Preferences for user {doc_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error viewing document: {e}"))

    def delete_document(self, service, data_type, doc_id, confirm):
        """Delete a specific document"""
        if not doc_id:
            self.stdout.write(self.style.ERROR("Document ID required for delete action"))
            return

        if not confirm:
            self.stdout.write(self.style.WARNING("Use --confirm to confirm deletion"))
            return

        try:
            if data_type == 'apartments':
                success = service.delete_apartment(doc_id)
                if success:
                    self.stdout.write(self.style.SUCCESS(f"Deleted apartment {doc_id}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to delete apartment {doc_id}"))
                    
            elif data_type == 'preferences':
                success = service.delete_user_preferences(int(doc_id))
                if success:
                    self.stdout.write(self.style.SUCCESS(f"Deleted preferences for user {doc_id}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to delete preferences for user {doc_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error deleting document: {e}"))

    def clear_collection(self, service, data_type, confirm):
        """Clear entire collection(s)"""
        if not confirm:
            self.stdout.write(self.style.WARNING("Use --confirm to confirm clearing collections"))
            return

        try:
            if data_type in ['apartments', 'all']:
                apartments = service.get_all_apartments()
                count = 0
                for apt in apartments:
                    if service.delete_apartment(apt.id):
                        count += 1
                self.stdout.write(self.style.SUCCESS(f"Cleared {count} apartments"))

            if data_type in ['preferences', 'all']:
                from django.contrib.auth.models import User
                users = User.objects.all()
                count = 0
                for user in users:
                    if service.delete_user_preferences(user.pk):
                        count += 1
                self.stdout.write(self.style.SUCCESS(f"Cleared {count} user preferences"))
                        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error clearing collections: {e}"))