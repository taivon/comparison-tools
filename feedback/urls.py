from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    # Feedback form
    path("feedback/", views.feedback_create, name="feedback_create"),
    # Feature ideas/roadmap
    path("ideas/", views.feature_list, name="feature_list"),
    path("ideas/new/", views.feature_create, name="feature_create"),
    path("ideas/<int:pk>/vote/", views.feature_vote_toggle, name="feature_vote_toggle"),
]
