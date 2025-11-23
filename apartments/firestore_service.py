from google.cloud import firestore
from google.auth import default
from datetime import datetime
from decimal import Decimal
import os
import logging
import hashlib
import secrets

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
    def pk(self):
        """Return doc_id as pk for Django template compatibility"""
        return self.doc_id or ""

    @property
    def price_per_sqft(self):
        if self.square_footage > 0:
            return round(self.price / Decimal(str(self.square_footage)), 2)
        else:
            return Decimal("0")

    def net_effective_price(self, user_preferences=None):
        if user_preferences is None:
            # Default preferences
            discount_calculation = "daily"
        else:
            discount_calculation = user_preferences.discount_calculation

        total_discount = Decimal("0")

        if discount_calculation == "daily":
            # Calculate annual rent divided by 365 days
            daily_rate = self.price * Decimal("12") / Decimal("365")
            # Convert months_free to days (using 365/12 for precision)
            if self.months_free > 0:
                days_free_from_months = Decimal(str(self.months_free)) * Decimal("365") / Decimal("12")
                total_discount += daily_rate * days_free_from_months
            # Convert weeks_free to days
            if self.weeks_free > 0:
                total_discount += daily_rate * Decimal("7") * Decimal(str(self.weeks_free))
        elif discount_calculation == "weekly":
            # Calculate annual rent divided by 52 weeks
            weekly_rate = self.price * Decimal("12") / Decimal("52")
            # Convert months_free to weeks (using 52/12 for precision)
            if self.months_free > 0:
                weeks_free_from_months = Decimal(str(self.months_free)) * Decimal("52") / Decimal("12")
                total_discount += weekly_rate * weeks_free_from_months
            # Add weeks_free directly
            if self.weeks_free > 0:
                total_discount += weekly_rate * Decimal(str(self.weeks_free))
        else:  # monthly
            if self.months_free > 0:
                total_discount += self.price * Decimal(str(self.months_free))
            if self.weeks_free > 0:
                total_discount += self.price * Decimal(str(self.weeks_free / 4))

        total_discount += self.flat_discount
        total_lease_value = self.price * Decimal(str(self.lease_length_months))
        net_price = (total_lease_value - total_discount) / Decimal(str(self.lease_length_months))
        # Round to 2 decimal places
        return round(net_price, 2)


class FirestoreUserPreferences:
    def __init__(self, doc_id=None, **kwargs):
        self.doc_id = doc_id
        self.user_id = kwargs.get("user_id", "")
        self.price_weight = kwargs.get("price_weight", 50)
        self.sqft_weight = kwargs.get("sqft_weight", 50)
        self.distance_weight = kwargs.get("distance_weight", 50)
        self.discount_calculation = kwargs.get("discount_calculation", "daily")

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
            discount_calculation=data.get("discount_calculation", "daily"),
        )


class FirestoreUser:
    def __init__(self, doc_id=None, **kwargs):
        self.doc_id = doc_id
        self.username = kwargs.get("username", "")
        self.email = kwargs.get("email", "")
        self.first_name = kwargs.get("first_name", "")
        self.last_name = kwargs.get("last_name", "")
        self.password_hash = kwargs.get("password_hash", "")
        self.firebase_uid = kwargs.get("firebase_uid", "")  # For Firebase Auth
        self.photo_url = kwargs.get("photo_url", "")  # For Google profile photo
        self.is_staff = kwargs.get("is_staff", False)  # Premium status
        self.is_active = kwargs.get("is_active", True)
        self.date_joined = kwargs.get("date_joined", datetime.now())
        self.last_login = kwargs.get("last_login", None)

    @property
    def id(self):
        """Return doc_id as id for compatibility"""
        return self.doc_id

    @property
    def is_authenticated(self):
        """Always return True for authenticated users"""
        return True

    @property
    def is_anonymous(self):
        """Always return False for authenticated users"""
        return False

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "password_hash": self.password_hash,
            "firebase_uid": self.firebase_uid,
            "photo_url": self.photo_url,
            "is_staff": self.is_staff,
            "is_active": self.is_active,
            "date_joined": self.date_joined,
            "last_login": self.last_login,
        }

    @classmethod
    def from_dict(cls, doc_id, data):
        return cls(
            doc_id=doc_id,
            username=data.get("username", ""),
            email=data.get("email", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            password_hash=data.get("password_hash", ""),
            firebase_uid=data.get("firebase_uid", ""),
            photo_url=data.get("photo_url", ""),
            is_staff=data.get("is_staff", False),
            is_active=data.get("is_active", True),
            date_joined=data.get("date_joined", datetime.now()),
            last_login=data.get("last_login", None),
        )

    def set_password(self, raw_password):
        """Hash and set password"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        self.password_hash = salt + ":" + password_hash.hex()

    def check_password(self, raw_password):
        """Check if the provided password matches the stored hash"""
        if not self.password_hash:
            return False
        try:
            salt, stored_hash = self.password_hash.split(":", 1)
            password_hash = hashlib.pbkdf2_hmac(
                "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 100000
            )
            return password_hash.hex() == stored_hash
        except ValueError:
            return False

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between"""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user"""
        return self.first_name


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

    def get_all_apartments(self):
        """Get all apartments in the system"""
        docs = (
            self.db.collection("apartments")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        apartments = []
        for doc in docs:
            apartments.append(FirestoreApartment.from_dict(doc.id, doc.to_dict()))
        return apartments

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
        try:
            self.db.collection("apartments").document(doc_id).delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting apartment {doc_id}: {e}")
            return False

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
                    "discount_calculation": "daily",
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

    def delete_user_preferences(self, user_id):
        """Delete user preferences"""
        try:
            docs = list(
                self.db.collection("user_preferences")
                .where("user_id", "==", str(user_id))
                .limit(1)
                .stream()
            )

            if docs:
                doc = docs[0]
                self.db.collection("user_preferences").document(doc.id).delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting preferences for user {user_id}: {e}")
            return False

    # User management operations
    def create_user(self, user_data, password):
        """Create a new user with hashed password"""
        user = FirestoreUser(**user_data)
        user.set_password(password)
        user.date_joined = datetime.now()

        doc_ref = self.db.collection("users").add(user.to_dict())
        user.doc_id = doc_ref[1].id
        return user

    def create_firebase_user(self, user_data):
        """Create a new user authenticated via Firebase (no password needed)"""
        user = FirestoreUser(**user_data)
        user.date_joined = datetime.now()

        doc_ref = self.db.collection("users").add(user.to_dict())
        user.doc_id = doc_ref[1].id
        return user

    def get_user(self, doc_id):
        """Get a user by document ID"""
        doc = self.db.collection("users").document(doc_id).get()
        if doc.exists:
            return FirestoreUser.from_dict(doc.id, doc.to_dict())
        return None

    def get_user_by_username(self, username):
        """Get a user by username"""
        docs = list(
            self.db.collection("users")
            .where("username", "==", username)
            .limit(1)
            .stream()
        )

        if docs:
            doc = docs[0]
            return FirestoreUser.from_dict(doc.id, doc.to_dict())
        return None

    def get_user_by_email(self, email):
        """Get a user by email"""
        docs = list(
            self.db.collection("users").where("email", "==", email).limit(1).stream()
        )

        if docs:
            doc = docs[0]
            return FirestoreUser.from_dict(doc.id, doc.to_dict())
        return None

    def authenticate_user(self, username, password):
        """Authenticate user with username/password"""
        user = self.get_user_by_username(username)
        if user and user.check_password(password) and user.is_active:
            # Update last login
            self.update_user_last_login(user.doc_id)
            return user
        return None

    def update_user_last_login(self, user_id):
        """Update user's last login timestamp"""
        self.db.collection("users").document(user_id).update(
            {"last_login": datetime.now()}
        )

    def update_user(self, user_id, user_data):
        """Update user data"""
        self.db.collection("users").document(user_id).update(user_data)
        return self.get_user(user_id)

    def get_all_users(self):
        """Get all users in the system"""
        docs = (
            self.db.collection("users")
            .order_by("date_joined", direction=firestore.Query.DESCENDING)
            .stream()
        )
        users = []
        for doc in docs:
            users.append(FirestoreUser.from_dict(doc.id, doc.to_dict()))
        return users

    def delete_user(self, user_id):
        """Delete a user and all their data"""
        try:
            # Delete user's apartments
            apartments = self.get_user_apartments(user_id)
            for apartment in apartments:
                self.delete_apartment(apartment.doc_id)

            # Delete user's preferences
            self.delete_user_preferences(user_id)

            # Delete user
            self.db.collection("users").document(user_id).delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
