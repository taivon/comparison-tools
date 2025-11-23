from django.urls import path
from . import views

app_name = "apartments"

urlpatterns = [
    path("", views.index, name="index"),
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
]
