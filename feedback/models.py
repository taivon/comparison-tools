from django.contrib.auth.models import User
from django.db import models


class Feedback(models.Model):
    """General user feedback for any tool"""

    CATEGORY_CHOICES = [
        ("bug", "Bug Report"),
        ("feature", "Feature Request"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feedback_submissions",
    )
    email = models.EmailField(blank=True, help_text="Contact email for anonymous users")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    message = models.TextField()
    page_url = models.URLField(blank=True, help_text="Page where feedback was submitted")
    tool = models.CharField(max_length=50, default="apartments", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Feedback"

    def __str__(self):
        return f"{self.get_category_display()} - {self.tool} ({self.created_at.strftime('%Y-%m-%d')})"


class FeatureRequest(models.Model):
    """Feature ideas that users can vote on"""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feature_requests",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    tool = models.CharField(max_length=50, default="apartments", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def vote_count(self):
        """Returns the number of votes for this feature"""
        return self.votes.count()


class FeatureVote(models.Model):
    """User votes on feature requests"""

    feature = models.ForeignKey(
        FeatureRequest,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="feature_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("feature", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} voted for {self.feature.title}"
