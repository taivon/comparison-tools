from django.urls import path
from . import views

app_name = "apartments"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("apartment/create/", views.create_apartment, name="create_apartment"),
    path("apartment/<str:pk>/update/", views.update_apartment, name="update_apartment"),
    path("apartment/<str:pk>/delete/", views.delete_apartment, name="delete_apartment"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("auth/callback/", views.google_oauth_callback, name="google_oauth_callback"),
    path(
        "api/sync-firebase-user/", views.sync_firebase_user, name="sync_firebase_user"
    ),
    path("api/transfer-apartments/", views.transfer_apartments, name="transfer_apartments"),
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
