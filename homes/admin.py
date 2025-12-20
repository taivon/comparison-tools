from django.contrib import admin

from .models import (
    AgentClientRelationship,
    AgentInviteCode,
    Home,
    HomeDistance,
    HomePreferences,
    HomeScore,
    HomeSuggestion,
    RealEstateAgent,
)


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "square_footage", "user", "source", "created_at")
    list_filter = ("user", "source", "created_at")
    search_fields = ("name", "user__username", "mls_number", "zillow_id", "redfin_id")
    ordering = ("-created_at",)


@admin.register(HomePreferences)
class HomePreferencesAdmin(admin.ModelAdmin):
    list_display = ("user", "price_weight", "sqft_weight", "distance_weight")
    search_fields = ("user__username",)


@admin.register(HomeScore)
class HomeScoreAdmin(admin.ModelAdmin):
    list_display = ("home", "user", "score", "calculated_at")
    list_filter = ("user", "calculated_at")
    search_fields = ("home__name", "user__username")
    readonly_fields = ("calculated_at",)
    ordering = ("-score", "home__name")


@admin.register(HomeDistance)
class HomeDistanceAdmin(admin.ModelAdmin):
    list_display = ("home", "favorite_place", "distance_miles", "travel_time_minutes")
    list_filter = ("favorite_place",)
    search_fields = ("home__name", "favorite_place__label")


@admin.register(RealEstateAgent)
class RealEstateAgentAdmin(admin.ModelAdmin):
    list_display = ("user", "license_number", "brokerage_name", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "user__email", "license_number", "brokerage_name")


@admin.register(AgentClientRelationship)
class AgentClientRelationshipAdmin(admin.ModelAdmin):
    list_display = ("agent", "client", "status", "linked_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("agent__username", "client__username", "invite_code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AgentInviteCode)
class AgentInviteCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "agent", "is_active", "uses_count", "max_uses", "expires_at", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("code", "agent__username")
    readonly_fields = ("created_at",)


@admin.register(HomeSuggestion)
class HomeSuggestionAdmin(admin.ModelAdmin):
    list_display = ("agent", "client", "home", "status", "suggested_at", "responded_at")
    list_filter = ("status", "suggested_at")
    search_fields = ("agent__username", "client__username", "home__name")
    readonly_fields = ("suggested_at",)
