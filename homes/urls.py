from django.urls import path

from . import views

app_name = "homes"

urlpatterns = [
    # Main home comparison pages
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Home CRUD operations
    path("home/create/", views.create_home, name="create_home"),
    path("home/<int:pk>/update/", views.update_home, name="update_home"),
    path("home/<int:pk>/delete/", views.delete_home, name="delete_home"),
    # Agent features
    path("agent/dashboard/", views.agent_dashboard, name="agent_dashboard"),
    path("agent/invite-code/", views.generate_invite_code, name="generate_invite_code"),
    path("agent/suggest-home/", views.suggest_home, name="suggest_home"),
    # Client agent features
    path("agent/enter-code/", views.enter_invite_code, name="enter_invite_code"),
    path("agent/suggestions/", views.view_suggestions, name="view_suggestions"),
    path("agent/suggestion/<int:pk>/approve/", views.approve_suggestion, name="approve_suggestion"),
    path("agent/suggestion/<int:pk>/reject/", views.reject_suggestion, name="reject_suggestion"),
    # API endpoints
    path("api/import-zillow/", views.import_zillow_property, name="import_zillow"),
    path("api/import-mls/", views.import_mls_listing, name="import_mls"),
    path("api/import-redfin/", views.import_redfin_property, name="import_redfin"),
    # Favorite places
    path("favorite-places/", views.favorite_places_list, name="favorite_places"),
    path("favorite-places/create/", views.create_favorite_place, name="create_favorite_place"),
    path("favorite-places/<int:pk>/update/", views.update_favorite_place, name="update_favorite_place"),
    path("favorite-places/<int:pk>/delete/", views.delete_favorite_place, name="delete_favorite_place"),
    # Google Maps API endpoints
    path("api/address-autocomplete/", views.address_autocomplete, name="address_autocomplete"),
    path("api/place-details/", views.place_details, name="place_details"),
    # Subscription URLs
    path("pricing/", views.pricing_redirect, name="pricing"),
    path("subscription/create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path("subscription/success/", views.checkout_success, name="checkout_success"),
    path("subscription/cancel/", views.checkout_cancel, name="checkout_cancel"),
]
