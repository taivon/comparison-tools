"""
Tests for the feedback app.

Run with: uv run python manage.py test feedback
"""

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from .forms import FeatureRequestForm, FeedbackForm
from .models import FeatureRequest, FeatureVote, Feedback

# =============================================================================
# Model Tests
# =============================================================================


class FeedbackModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_feedback_creation_with_user(self):
        feedback = Feedback.objects.create(
            user=self.user,
            category="bug",
            message="There is a bug in the app.",
            tool="apartments",
        )
        self.assertIn("Bug Report", str(feedback))
        self.assertIn("apartments", str(feedback))
        self.assertEqual(feedback.category, "bug")

    def test_feedback_creation_anonymous(self):
        feedback = Feedback.objects.create(
            email="anon@example.com",
            category="feature",
            message="I would like a new feature.",
            tool="apartments",
        )
        self.assertIsNone(feedback.user)
        self.assertEqual(feedback.email, "anon@example.com")

    def test_feedback_category_choices(self):
        bug = Feedback.objects.create(category="bug", message="Bug report")
        feature = Feedback.objects.create(category="feature", message="Feature request")
        other = Feedback.objects.create(category="other", message="Other feedback")

        self.assertEqual(bug.get_category_display(), "Bug Report")
        self.assertEqual(feature.get_category_display(), "Feature Request")
        self.assertEqual(other.get_category_display(), "Other")

    def test_feedback_ordering(self):
        feedback1 = Feedback.objects.create(message="First")
        feedback2 = Feedback.objects.create(message="Second")

        all_feedback = list(Feedback.objects.all())
        # Most recent first
        self.assertEqual(all_feedback[0], feedback2)
        self.assertEqual(all_feedback[1], feedback1)

    def test_feedback_page_url(self):
        feedback = Feedback.objects.create(
            message="Test message",
            page_url="https://example.com/apartments/dashboard/",
        )
        self.assertEqual(feedback.page_url, "https://example.com/apartments/dashboard/")


class FeatureRequestModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_feature_request_creation(self):
        feature = FeatureRequest.objects.create(
            user=self.user,
            title="Dark Mode",
            description="Add a dark mode theme to the app.",
            tool="apartments",
        )
        self.assertEqual(str(feature), "Dark Mode")
        self.assertEqual(feature.status, "open")

    def test_feature_request_status_choices(self):
        feature = FeatureRequest.objects.create(title="Test Feature")

        # Test all status transitions
        for status, _display in FeatureRequest.STATUS_CHOICES:
            feature.status = status
            feature.save()
            feature.refresh_from_db()
            self.assertEqual(feature.status, status)

    def test_feature_request_vote_count(self):
        feature = FeatureRequest.objects.create(title="Popular Feature")
        user2 = User.objects.create_user(username="user2", password="testpass123")
        user3 = User.objects.create_user(username="user3", password="testpass123")

        self.assertEqual(feature.vote_count, 0)

        FeatureVote.objects.create(feature=feature, user=self.user)
        self.assertEqual(feature.vote_count, 1)

        FeatureVote.objects.create(feature=feature, user=user2)
        FeatureVote.objects.create(feature=feature, user=user3)
        self.assertEqual(feature.vote_count, 3)

    def test_feature_request_ordering(self):
        feature1 = FeatureRequest.objects.create(title="First")
        feature2 = FeatureRequest.objects.create(title="Second")

        all_features = list(FeatureRequest.objects.all())
        # Most recent first
        self.assertEqual(all_features[0], feature2)
        self.assertEqual(all_features[1], feature1)

    def test_feature_request_anonymous(self):
        feature = FeatureRequest.objects.create(
            title="Anonymous Feature",
            description="From anonymous user",
        )
        self.assertIsNone(feature.user)


class FeatureVoteModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.feature = FeatureRequest.objects.create(title="Test Feature")

    def test_vote_creation(self):
        vote = FeatureVote.objects.create(feature=self.feature, user=self.user)
        self.assertEqual(str(vote), "testuser voted for Test Feature")

    def test_vote_unique_per_user_feature(self):
        FeatureVote.objects.create(feature=self.feature, user=self.user)
        with self.assertRaises(IntegrityError):
            FeatureVote.objects.create(feature=self.feature, user=self.user)

    def test_vote_multiple_features(self):
        feature2 = FeatureRequest.objects.create(title="Feature 2")

        FeatureVote.objects.create(feature=self.feature, user=self.user)
        FeatureVote.objects.create(feature=feature2, user=self.user)

        self.assertEqual(self.user.feature_votes.count(), 2)

    def test_vote_cascade_delete_feature(self):
        FeatureVote.objects.create(feature=self.feature, user=self.user)
        self.assertEqual(FeatureVote.objects.count(), 1)

        self.feature.delete()
        self.assertEqual(FeatureVote.objects.count(), 0)

    def test_vote_cascade_delete_user(self):
        FeatureVote.objects.create(feature=self.feature, user=self.user)
        self.assertEqual(FeatureVote.objects.count(), 1)

        self.user.delete()
        self.assertEqual(FeatureVote.objects.count(), 0)

    def test_vote_ordering(self):
        user2 = User.objects.create_user(username="user2", password="testpass123")

        vote1 = FeatureVote.objects.create(feature=self.feature, user=self.user)
        vote2 = FeatureVote.objects.create(feature=self.feature, user=user2)

        all_votes = list(FeatureVote.objects.all())
        # Most recent first
        self.assertEqual(all_votes[0], vote2)
        self.assertEqual(all_votes[1], vote1)


# =============================================================================
# Form Tests
# =============================================================================


class FeedbackFormTest(TestCase):
    def test_valid_form(self):
        form = FeedbackForm(
            data={
                "category": "bug",
                "message": "This is a detailed bug report with enough characters.",
                "email": "test@example.com",
            }
        )
        self.assertTrue(form.is_valid())

    def test_valid_form_without_email(self):
        form = FeedbackForm(
            data={
                "category": "feature",
                "message": "This is a feature request with enough detail.",
            }
        )
        self.assertTrue(form.is_valid())

    def test_message_too_short(self):
        form = FeedbackForm(
            data={
                "category": "other",
                "message": "Short",  # Less than 10 characters
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)

    def test_invalid_category(self):
        form = FeedbackForm(
            data={
                "category": "invalid",
                "message": "This message is long enough to pass validation.",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_invalid_email(self):
        form = FeedbackForm(
            data={
                "category": "bug",
                "message": "This message is long enough to pass validation.",
                "email": "not-an-email",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_page_url_included(self):
        form = FeedbackForm(
            data={
                "category": "bug",
                "message": "This message is long enough to pass validation.",
                "page_url": "https://example.com/page",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["page_url"], "https://example.com/page")


class FeatureRequestFormTest(TestCase):
    def test_valid_form(self):
        form = FeatureRequestForm(
            data={
                "title": "Dark Mode",
                "description": "Add a dark mode theme to reduce eye strain.",
            }
        )
        self.assertTrue(form.is_valid())

    def test_valid_form_without_description(self):
        form = FeatureRequestForm(
            data={
                "title": "Dark Mode",
            }
        )
        self.assertTrue(form.is_valid())

    def test_missing_title(self):
        form = FeatureRequestForm(
            data={
                "description": "Some description without a title.",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_title_too_long(self):
        form = FeatureRequestForm(
            data={
                "title": "A" * 201,  # More than 200 characters
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_description_too_long(self):
        form = FeatureRequestForm(
            data={
                "title": "Test Feature",
                "description": "A" * 2001,  # More than 2000 characters
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)
