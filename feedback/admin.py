from django.contrib import admin

from .models import FeatureRequest, FeatureVote, Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("category", "tool", "user", "email", "created_at", "message_preview")
    list_filter = ("category", "tool", "created_at")
    search_fields = ("message", "email", "user__username", "user__email")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    message_preview.short_description = "Message"


@admin.register(FeatureRequest)
class FeatureRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "tool", "user", "vote_count_display", "created_at")
    list_filter = ("status", "tool", "created_at")
    search_fields = ("title", "description", "user__username")
    readonly_fields = ("created_at", "updated_at", "vote_count_display")
    ordering = ("-created_at",)

    def vote_count_display(self, obj):
        return obj.vote_count

    vote_count_display.short_description = "Votes"


@admin.register(FeatureVote)
class FeatureVoteAdmin(admin.ModelAdmin):
    list_display = ("feature", "user", "created_at")
    list_filter = ("created_at", "feature__tool")
    search_fields = ("feature__title", "user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    raw_id_fields = ("feature", "user")
