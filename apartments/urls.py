from django.urls import path

from . import views

app_name = "apartments"

urlpatterns = [
    # Main apartment comparison pages
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Apartment CRUD operations
    path("apartment/create/", views.create_apartment, name="create_apartment"),
    path("apartment/<str:pk>/update/", views.update_apartment, name="update_apartment"),
    path("apartment/<str:pk>/delete/", views.delete_apartment, name="delete_apartment"),
    # Favorite Places
    path("favorite-places/", views.favorite_places_list, name="favorite_places"),
    path("favorite-places/create/", views.create_favorite_place, name="create_favorite_place"),
    path("favorite-places/<int:pk>/update/", views.update_favorite_place, name="update_favorite_place"),
    path("favorite-places/<int:pk>/delete/", views.delete_favorite_place, name="delete_favorite_place"),
    # API endpoints
    path("api/transfer-apartments/", views.transfer_apartments, name="transfer_apartments"),
    path("api/address-autocomplete/", views.address_autocomplete, name="address_autocomplete"),
    path("api/place-details/", views.place_details, name="place_details"),
    path("api/google-maps-status/", views.google_maps_status, name="google_maps_status"),
    path(
        "api/apartment/<int:pk>/distances/", views.calculate_apartment_distances, name="calculate_apartment_distances"
    ),
    # Static pages
    path("privacy/", views.privacy_policy, name="privacy"),
    path("terms/", views.terms_of_service, name="terms"),
    # Subscription URLs (pricing redirects to signup)
    path("pricing/", views.pricing_redirect, name="pricing"),
    path("subscription/create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path("subscription/success/", views.checkout_success, name="checkout_success"),
    path("subscription/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("subscription/billing-portal/", views.billing_portal, name="billing_portal"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
