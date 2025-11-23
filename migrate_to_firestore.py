#!/usr/bin/env python
"""
Migration script to move data from SQLite to Firestore.
This script should be run in the Django environment.

Usage:
python manage.py shell < migrate_to_firestore.py
"""

import os
import sys
import django
from datetime import datetime
from decimal import Decimal

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User
from apartments.models import Apartment, UserPreferences
from apartments.firestore_service import FirestoreService


def migrate_data():
    """Migrate all data from SQLite to Firestore"""
    firestore_service = FirestoreService()

    print("Starting migration from SQLite to Firestore...")

    # Migrate apartments
    print("\nMigrating apartments...")
    apartments = Apartment.objects.all()
    apartment_count = 0

    for apartment in apartments:
        try:
            apartment_data = {
                "name": apartment.name,
                "price": apartment.price,
                "square_footage": apartment.square_footage,
                "lease_length_months": apartment.lease_length_months,
                "months_free": apartment.months_free,
                "weeks_free": apartment.weeks_free,
                "flat_discount": apartment.flat_discount,
                "created_at": apartment.created_at,
                "updated_at": apartment.updated_at,
                "user_id": str(apartment.user.id),
            }

            firestore_apartment = firestore_service.create_apartment(apartment_data)
            print(
                f"  ✓ Migrated apartment: {apartment.name} (ID: {firestore_apartment.doc_id})"
            )
            apartment_count += 1

        except Exception as e:
            print(f"  ✗ Failed to migrate apartment {apartment.name}: {str(e)}")

    # Migrate user preferences
    print("\nMigrating user preferences...")
    preferences = UserPreferences.objects.all()
    preferences_count = 0

    for pref in preferences:
        try:
            preferences_data = {
                "user_id": str(pref.user.id),
                "price_weight": pref.price_weight,
                "sqft_weight": pref.sqft_weight,
                "distance_weight": pref.distance_weight,
                "discount_calculation": pref.discount_calculation,
            }

            firestore_prefs = firestore_service.create_user_preferences(
                preferences_data
            )
            print(
                f"  ✓ Migrated preferences for user: {pref.user.username} (ID: {firestore_prefs.doc_id})"
            )
            preferences_count += 1

        except Exception as e:
            print(
                f"  ✗ Failed to migrate preferences for user {pref.user.username}: {str(e)}"
            )

    print(f"\nMigration completed!")
    print(f"  - Apartments migrated: {apartment_count}")
    print(f"  - User preferences migrated: {preferences_count}")

    return apartment_count, preferences_count


def verify_migration():
    """Verify that data was migrated correctly"""
    firestore_service = FirestoreService()

    print("\nVerifying migration...")

    # Check apartments for each user
    users = User.objects.all()
    for user in users:
        # Count SQLite apartments
        sqlite_apartments = Apartment.objects.filter(user=user).count()

        # Count Firestore apartments
        firestore_apartments = firestore_service.get_user_apartments(user.id)
        firestore_count = len(firestore_apartments)

        if sqlite_apartments == firestore_count:
            print(f"  ✓ User {user.username}: {sqlite_apartments} apartments match")
        else:
            print(
                f"  ✗ User {user.username}: SQLite={sqlite_apartments}, Firestore={firestore_count}"
            )

        # Check preferences
        sqlite_prefs = UserPreferences.objects.filter(user=user).exists()
        firestore_prefs = firestore_service.get_user_preferences(user.id)

        if sqlite_prefs and firestore_prefs:
            print(f"  ✓ User {user.username}: preferences migrated")
        elif not sqlite_prefs and firestore_prefs:
            print(f"  ✓ User {user.username}: default preferences created")
        else:
            print(f"  ✗ User {user.username}: preferences issue")


if __name__ == "__main__":
    try:
        # Check if there's existing data to migrate
        apartment_count = Apartment.objects.count()
        preferences_count = UserPreferences.objects.count()

        print(
            f"Found {apartment_count} apartments and {preferences_count} user preferences to migrate"
        )

        if apartment_count == 0 and preferences_count == 0:
            print("No data to migrate.")
        else:
            # Perform migration
            migrate_data()
            verify_migration()

    except Exception as e:
        print(f"Migration failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
