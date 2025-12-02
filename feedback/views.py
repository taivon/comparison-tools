from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FeatureRequestForm, FeedbackForm
from .models import FeatureRequest, FeatureVote, Feedback

# Default tool scope
DEFAULT_TOOL = "apartments"


def get_tool_from_request(request):
    """Extract tool context from the URL path or default to apartments"""
    path = request.path
    if path.startswith("/apartments/"):
        return "apartments"
    elif path.startswith("/homes/"):
        return "homes"
    elif path.startswith("/hotels/"):
        return "hotels"
    return DEFAULT_TOOL


def feedback_create(request):
    """Display and handle the feedback form"""
    tool = get_tool_from_request(request)

    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            Feedback.objects.create(
                user=request.user if request.user.is_authenticated else None,
                email=form.cleaned_data.get("email", ""),
                category=form.cleaned_data["category"],
                message=form.cleaned_data["message"],
                page_url=form.cleaned_data.get("page_url", ""),
                tool=tool,
            )
            messages.success(request, "Thank you for your feedback!")
            return redirect("apartments:dashboard")
    else:
        # Pre-populate page_url from referer
        initial_data = {
            "page_url": request.META.get("HTTP_REFERER", ""),
        }
        form = FeedbackForm(initial=initial_data)

    context = {
        "form": form,
        "tool": tool,
        "show_email_field": not request.user.is_authenticated,
    }
    return render(request, "feedback/feedback_form.html", context)


def feature_list(request):
    """List feature requests with vote counts, ordered by popularity"""
    tool = get_tool_from_request(request)

    # Base queryset with vote count annotation
    features = (
        FeatureRequest.objects.filter(tool=tool)
        .annotate(votes_count=Count("votes"))
        .order_by("-votes_count", "-created_at")
    )

    # If user is authenticated, annotate whether they've voted
    if request.user.is_authenticated:
        features = features.annotate(
            user_has_voted=Exists(FeatureVote.objects.filter(feature=OuterRef("pk"), user=request.user))
        )

    context = {
        "features": features,
        "tool": tool,
    }
    return render(request, "feedback/feature_list.html", context)


@login_required
def feature_create(request):
    """Create a new feature request"""
    tool = get_tool_from_request(request)

    if request.method == "POST":
        form = FeatureRequestForm(request.POST)
        if form.is_valid():
            feature = FeatureRequest.objects.create(
                user=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data.get("description", ""),
                tool=tool,
            )
            # Auto-vote for your own feature
            FeatureVote.objects.create(feature=feature, user=request.user)
            messages.success(request, "Your idea has been submitted!")
            return redirect("feedback:feature_list")
    else:
        form = FeatureRequestForm()

    context = {
        "form": form,
        "tool": tool,
    }
    return render(request, "feedback/feature_form.html", context)


@login_required
@require_POST
def feature_vote_toggle(request, pk):
    """Toggle vote on a feature request (add/remove)"""
    tool = get_tool_from_request(request)
    feature = get_object_or_404(FeatureRequest, pk=pk, tool=tool)

    vote, created = FeatureVote.objects.get_or_create(feature=feature, user=request.user)

    if not created:
        # Vote exists, remove it
        vote.delete()
        action = "removed"
    else:
        action = "added"

    # Return JSON for AJAX requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "action": action,
                "vote_count": feature.votes.count(),
            }
        )

    # Regular form submission
    if action == "added":
        messages.success(request, f'Voted for "{feature.title}"')
    else:
        messages.info(request, f'Removed vote for "{feature.title}"')

    return redirect("feedback:feature_list")
