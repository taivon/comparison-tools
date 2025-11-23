from google.cloud import firestore
from google.auth import default
from datetime import datetime
from decimal import Decimal
import os
import logging

logger = logging.getLogger(__name__)


class FirestoreClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreClient, cls).__new__(cls)
            try:
                # In production on App Engine, use default credentials
                # In development, use service account key file or Application Default Credentials
                if os.environ.get("GAE_ENV", "").startswith("standard"):
                    # Running on App Engine
                    cls._instance.db = firestore.Client(database="apartments-db")
                else:
                    # Local development - use Application Default Credentials
                    credentials, project = default()
                    cls._instance.db = firestore.Client(
                        credentials=credentials,
                        project=project,
                        database="apartments-db",
                    )

                # Test connection with a simple operation
                try:
                    # Try to list collections to verify database is accessible
                    collections = list(cls._instance.db.collections())
                    logger.info("Firestore client initialized and tested successfully")
                except Exception as test_e:
                    logger.warning(
                        f"Firestore client initialized but database may not be ready: {test_e}"
                    )

            except Exception as e:
                logger.error(f"Failed to initialize Firestore client: {e}")
                raise
        return cls._instance


class FirestoreApartment:
    def __init__(self, doc_id=None, **kwargs):
        self.doc_id = doc_id
        self.name = kwargs.get("name", "")
        self.price = Decimal(str(kwargs.get("price", "0")))
        self.square_footage = kwargs.get("square_footage", 0)
        self.lease_length_months = kwargs.get("lease_length_months", 12)
        self.months_free = kwargs.get("months_free", 0)
        self.weeks_free = kwargs.get("weeks_free", 0)
        self.flat_discount = Decimal(str(kwargs.get("flat_discount", "0")))
        self.created_at = kwargs.get("created_at", datetime.now())
        self.updated_at = kwargs.get("updated_at", datetime.now())
        self.user_id = kwargs.get("user_id", "")

    def to_dict(self):
        return {
            "name": self.name,
            "price": float(self.price),
            "square_footage": self.square_footage,
            "lease_length_months": self.lease_length_months,
            "months_free": self.months_free,
            "weeks_free": self.weeks_free,
            "flat_discount": float(self.flat_discount),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, doc_id, data):
        return cls(
            doc_id=doc_id,
            name=data.get("name", ""),
            price=data.get("price", 0),
            square_footage=data.get("square_footage", 0),
            lease_length_months=data.get("lease_length_months", 12),
            months_free=data.get("months_free", 0),
            weeks_free=data.get("weeks_free", 0),
            flat_discount=data.get("flat_discount", 0),
            created_at=data.get("created_at", datetime.now()),
            updated_at=data.get("updated_at", datetime.now()),
            user_id=data.get("user_id", ""),
        )

    @property
    def price_per_sqft(self):
        return (
            self.price / Decimal(str(self.square_footage))
            if self.square_footage > 0
            else Decimal("0")
        )

    def net_effective_price(self, user_preferences=None):
        if user_preferences is None:
            # Default preferences
            discount_calculation = "monthly"
        else:
            discount_calculation = user_preferences.discount_calculation

        total_discount = Decimal("0")

        if discount_calculation == "daily":
            daily_rate = self.price * Decimal("12") / Decimal("365")
            if self.weeks_free > 0:
                total_discount += (
                    daily_rate * Decimal("7") * Decimal(str(self.weeks_free))
                )
        elif discount_calculation == "weekly":
            weekly_rate = self.price * Decimal("12") / Decimal("52")
            if self.weeks_free > 0:
                total_discount += weekly_rate * Decimal(str(self.weeks_free))
        else:  # monthly
            if self.months_free > 0:
                total_discount += self.price * Decimal(str(self.months_free))
            if self.weeks_free > 0:
                total_discount += self.price * Decimal(str(self.weeks_free / 4))

        total_discount += self.flat_discount
        total_lease_value = self.price * Decimal(str(self.lease_length_months))
        return (total_lease_value - total_discount) / Decimal(
            str(self.lease_length_months)
        )


class FirestoreUserPreferences:
    def __init__(self, doc_id=None, **kwargs):
        self.doc_id = doc_id
        self.user_id = kwargs.get("user_id", "")
        self.price_weight = kwargs.get("price_weight", 50)
        self.sqft_weight = kwargs.get("sqft_weight", 50)
        self.distance_weight = kwargs.get("distance_weight", 50)
        self.discount_calculation = kwargs.get("discount_calculation", "monthly")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "price_weight": self.price_weight,
            "sqft_weight": self.sqft_weight,
            "distance_weight": self.distance_weight,
            "discount_calculation": self.discount_calculation,
        }

    @classmethod
    def from_dict(cls, doc_id, data):
        return cls(
            doc_id=doc_id,
            user_id=data.get("user_id", ""),
            price_weight=data.get("price_weight", 50),
            sqft_weight=data.get("sqft_weight", 50),
            distance_weight=data.get("distance_weight", 50),
            discount_calculation=data.get("discount_calculation", "monthly"),
        )


class FirestoreService:
    def __init__(self):
        self.client = FirestoreClient()
        self.db = self.client.db

    # Apartment operations
    def create_apartment(self, apartment_data):
        """Create a new apartment document"""
        apartment = FirestoreApartment(**apartment_data)
        apartment.created_at = datetime.now()
        apartment.updated_at = datetime.now()

        doc_ref = self.db.collection("apartments").add(apartment.to_dict())
        apartment.doc_id = doc_ref[1].id
        return apartment

    def get_apartment(self, doc_id):
        """Get an apartment by document ID"""
        doc = self.db.collection("apartments").document(doc_id).get()
        if doc.exists:
            return FirestoreApartment.from_dict(doc.id, doc.to_dict())
        return None

    def get_user_apartments(self, user_id):
        """Get all apartments for a specific user"""
        docs = (
            self.db.collection("apartments")
            .where("user_id", "==", str(user_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        apartments = []
        for doc in docs:
            apartments.append(FirestoreApartment.from_dict(doc.id, doc.to_dict()))
        return apartments

    def update_apartment(self, doc_id, apartment_data):
        """Update an existing apartment"""
        apartment_data["updated_at"] = datetime.now()
        self.db.collection("apartments").document(doc_id).update(apartment_data)
        return self.get_apartment(doc_id)

    def delete_apartment(self, doc_id):
        """Delete an apartment"""
        self.db.collection("apartments").document(doc_id).delete()

    # User preferences operations
    def get_user_preferences(self, user_id):
        """Get user preferences, create default if not exists"""
        docs = list(
            self.db.collection("user_preferences")
            .where("user_id", "==", str(user_id))
            .limit(1)
            .stream()
        )

        if docs:
            doc = docs[0]
            return FirestoreUserPreferences.from_dict(doc.id, doc.to_dict())
        else:
            # Create default preferences
            return self.create_user_preferences(
                {
                    "user_id": str(user_id),
                    "price_weight": 50,
                    "sqft_weight": 50,
                    "distance_weight": 50,
                    "discount_calculation": "monthly",
                }
            )

    def create_user_preferences(self, preferences_data):
        """Create user preferences"""
        preferences = FirestoreUserPreferences(**preferences_data)
        doc_ref = self.db.collection("user_preferences").add(preferences.to_dict())
        preferences.doc_id = doc_ref[1].id
        return preferences

    def update_user_preferences(self, user_id, preferences_data):
        """Update user preferences"""
        docs = list(
            self.db.collection("user_preferences")
            .where("user_id", "==", str(user_id))
            .limit(1)
            .stream()
        )

        if docs:
            doc = docs[0]
            self.db.collection("user_preferences").document(doc.id).update(
                preferences_data
            )
            return self.get_user_preferences(user_id)
        else:
            preferences_data["user_id"] = str(user_id)
            return self.create_user_preferences(preferences_data)
