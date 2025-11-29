from django.contrib import admin

from .models import Apartment, ApartmentScore, Plan, Product, Subscription, UserPreferences, UserProfile


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "free_tier_limit", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class PlanInline(admin.TabularInline):
    model = Plan
    extra = 0
    fields = ("name", "tier", "stripe_price_id", "price_amount", "billing_interval", "is_active")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "tier", "price_amount", "billing_interval", "stripe_price_id", "is_active")
    list_filter = ("product", "tier", "billing_interval", "is_active")
    search_fields = ("name", "product__name", "stripe_price_id")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end", "cancel_at_period_end", "created_at")
    list_filter = ("status", "plan__product", "plan__tier", "cancel_at_period_end")
    search_fields = ("user__username", "user__email", "stripe_subscription_id")
    readonly_fields = ("stripe_subscription_id", "created_at", "updated_at")
    raw_id_fields = ("user", "plan")


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "square_footage", "user", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("name", "user__username")
    ordering = ("-created_at",)


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("user", "price_weight", "sqft_weight", "discount_calculation")
    list_filter = ("discount_calculation",)
    search_fields = ("user__username",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "stripe_customer_id")
    search_fields = ("user__username", "user__email", "stripe_customer_id")
    readonly_fields = ("stripe_customer_id",)


@admin.register(ApartmentScore)
class ApartmentScoreAdmin(admin.ModelAdmin):
    list_display = ("apartment", "user", "score", "calculated_at")
    list_filter = ("user", "calculated_at")
    search_fields = ("apartment__name", "user__username")
    readonly_fields = ("calculated_at",)
    ordering = ("-score", "apartment__name")
