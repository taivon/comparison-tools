from django.urls import path
from . import views

app_name = "apartments"

urlpatterns = [
    path("", views.index, name="index"),
    path("apartment/create/", views.create_apartment, name="create_apartment"),
    path("apartment/<int:pk>/update/", views.update_apartment, name="update_apartment"),
    path("apartment/<int:pk>/delete/", views.delete_apartment, name="delete_apartment"),
]
