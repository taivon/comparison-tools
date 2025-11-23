#!/usr/bin/env python
"""
Test script to verify Firestore integration is working correctly.
Run this after the Firestore database is created in Native mode.

Usage:
python test_firestore.py
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apartments.firestore_service import FirestoreService


def test_firestore_connection():
    """Test basic Firestore connectivity"""
    print("Testing Firestore connection...")

    try:
        firestore_service = FirestoreService()
        print("✓ Firestore client initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize Firestore client: {str(e)}")
        return False


def test_apartment_operations():
    """Test apartment CRUD operations"""
    print("\nTesting apartment operations...")

    try:
        firestore_service = FirestoreService()

        # Test create apartment
        test_apartment_data = {
            "name": "Test Apartment",
            "price": Decimal("1500.00"),
            "square_footage": 800,
            "lease_length_months": 12,
            "months_free": 1,
            "weeks_free": 0,
            "flat_discount": Decimal("200.00"),
            "user_id": "999",  # Test user ID
        }

        apartment = firestore_service.create_apartment(test_apartment_data)
        print(f"✓ Created apartment: {apartment.name} (ID: {apartment.doc_id})")

        # Test get apartment
        retrieved = firestore_service.get_apartment(apartment.doc_id)
        if retrieved and retrieved.name == test_apartment_data["name"]:
            print("✓ Retrieved apartment successfully")
        else:
            print("✗ Failed to retrieve apartment")
            return False

        # Test update apartment
        update_data = {"name": "Updated Test Apartment", "price": 1600.00}
        updated = firestore_service.update_apartment(apartment.doc_id, update_data)
        if updated and updated.name == "Updated Test Apartment":
            print("✓ Updated apartment successfully")
        else:
            print("✗ Failed to update apartment")
            return False

        # Test get user apartments
        user_apartments = firestore_service.get_user_apartments("999")
        if len(user_apartments) >= 1:
            print(f"✓ Retrieved {len(user_apartments)} user apartments")
        else:
            print("✗ Failed to retrieve user apartments")
            return False

        # Test delete apartment
        firestore_service.delete_apartment(apartment.doc_id)
        deleted_check = firestore_service.get_apartment(apartment.doc_id)
        if deleted_check is None:
            print("✓ Deleted apartment successfully")
        else:
            print("✗ Failed to delete apartment")
            return False

        return True

    except Exception as e:
        print(f"✗ Apartment operations failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_preferences_operations():
    """Test user preferences operations"""
    print("\nTesting user preferences operations...")

    try:
        firestore_service = FirestoreService()

        # Test create preferences
        preferences_data = {
            "user_id": "999",
            "price_weight": 60,
            "sqft_weight": 30,
            "distance_weight": 10,
            "discount_calculation": "weekly",
        }

        preferences = firestore_service.create_user_preferences(preferences_data)
        print(f"✓ Created user preferences (ID: {preferences.doc_id})")

        # Test get preferences
        retrieved_prefs = firestore_service.get_user_preferences("999")
        if retrieved_prefs and retrieved_prefs.price_weight == 60:
            print("✓ Retrieved user preferences successfully")
        else:
            print("✗ Failed to retrieve user preferences")
            return False

        # Test update preferences
        update_data = {"price_weight": 70, "sqft_weight": 25}
        updated_prefs = firestore_service.update_user_preferences("999", update_data)
        if updated_prefs and updated_prefs.price_weight == 70:
            print("✓ Updated user preferences successfully")
        else:
            print("✗ Failed to update user preferences")
            return False

        return True

    except Exception as e:
        print(f"✗ User preferences operations failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_apartment_calculations():
    """Test apartment price calculations"""
    print("\nTesting apartment calculations...")

    try:
        firestore_service = FirestoreService()

        # Create test apartment
        test_apartment_data = {
            "name": "Calculation Test Apartment",
            "price": Decimal("2000.00"),
            "square_footage": 1000,
            "lease_length_months": 12,
            "months_free": 2,
            "weeks_free": 1,
            "flat_discount": Decimal("500.00"),
            "user_id": "999",
        }

        apartment = firestore_service.create_apartment(test_apartment_data)

        # Create test preferences
        preferences_data = {
            "user_id": "999",
            "price_weight": 50,
            "sqft_weight": 50,
            "distance_weight": 50,
            "discount_calculation": "monthly",
        }
        preferences = firestore_service.create_user_preferences(preferences_data)

        # Test price per sqft
        price_per_sqft = apartment.price_per_sqft
        expected_price_per_sqft = Decimal("2.00")  # 2000 / 1000
        if abs(price_per_sqft - expected_price_per_sqft) < Decimal("0.01"):
            print(f"✓ Price per sqft calculation correct: ${price_per_sqft}")
        else:
            print(
                f"✗ Price per sqft incorrect. Expected: ${expected_price_per_sqft}, Got: ${price_per_sqft}"
            )
            return False

        # Test net effective price
        net_price = apartment.net_effective_price(preferences)
        print(f"✓ Net effective price calculated: ${net_price}")

        # Clean up
        firestore_service.delete_apartment(apartment.doc_id)

        return True

    except Exception as e:
        print(f"✗ Apartment calculations failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("=== Firestore Integration Test Suite ===\n")

    tests = [
        test_firestore_connection,
        test_apartment_operations,
        test_preferences_operations,
        test_apartment_calculations,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=== Test Results ===")
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Firestore integration is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
