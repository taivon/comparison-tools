from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json
from .models import (
    Apartment, UserPreferences, UserProfile, Plan,
    user_has_premium, get_product_free_tier_limit
)
from .forms import ApartmentForm, UserPreferencesForm, CustomUserCreationForm, LoginForm
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Product slug for this app
PRODUCT_SLUG = 'apartments'


def get_or_create_profile(user):
    """Get or create UserProfile for a user"""
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def main_homepage(request):
    """Main landing page showcasing all comparison tools"""
    return render(request, "home.html")


def homes_coming_soon(request):
    """Placeholder for homes comparison tool"""
    return render(request, "coming_soon.html", {
        "tool_name": "Home Comparison",
        "tool_description": "Compare homes for purchase by price, features, location, and more.",
        "icon_path": "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
    })


def hotels_coming_soon(request):
    """Placeholder for hotels comparison tool"""
    return render(request, "coming_soon.html", {
        "tool_name": "Hotel Comparison",
        "tool_description": "Compare hotels by price, amenities, location, and reviews.",
        "icon_path": "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
    })


def calculate_net_effective_price(apt_data, discount_calculation='daily'):
    """Calculate net effective price for session apartments"""
    price = Decimal(str(apt_data.get('price', 0)))
    lease_length_months = apt_data.get('lease_length_months', 12)
    months_free = apt_data.get('months_free', 0)
    weeks_free = apt_data.get('weeks_free', 0)
    flat_discount = Decimal(str(apt_data.get('flat_discount', 0)))

    total_discount = Decimal('0')

    if discount_calculation == 'daily':
        daily_rate = price * Decimal('12') / Decimal('365')
        if months_free > 0:
            days_free_from_months = Decimal(str(months_free)) * Decimal('365') / Decimal('12')
            total_discount += daily_rate * days_free_from_months
        if weeks_free > 0:
            total_discount += daily_rate * Decimal('7') * Decimal(str(weeks_free))
    elif discount_calculation == 'weekly':
        weekly_rate = price * Decimal('12') / Decimal('52')
        if months_free > 0:
            weeks_free_from_months = Decimal(str(months_free)) * Decimal('52') / Decimal('12')
            total_discount += weekly_rate * weeks_free_from_months
        if weeks_free > 0:
            total_discount += weekly_rate * Decimal(str(weeks_free))
    else:  # monthly
        if months_free > 0:
            total_discount += price * Decimal(str(months_free))
        if weeks_free > 0:
            total_discount += price * Decimal(str(weeks_free / 4))

    total_discount += flat_discount
    total_lease_value = price * Decimal(str(lease_length_months))
    net_price = (total_lease_value - total_discount) / Decimal(str(lease_length_months))
    return float(round(net_price, 2))


def index(request):
    """Homepage - landing page with form and features"""
    if request.user.is_authenticated:
        apartments = Apartment.objects.filter(user=request.user)
        apartment_count = apartments.count()
        has_premium = user_has_premium(request.user, PRODUCT_SLUG)
        can_add_apartment = has_premium or apartment_count < 2
    else:
        apartment_count = 0
        can_add_apartment = True  # JavaScript will enforce the 2-apartment limit

    context = {
        "can_add_apartment": can_add_apartment,
        "is_anonymous": not request.user.is_authenticated,
        "apartment_count": apartment_count,
    }
    return render(request, "apartments/index.html", context)


def dashboard(request):
    """Dashboard view showing user's apartments in table/card format"""
    if request.user.is_authenticated:
        apartments = list(Apartment.objects.filter(user=request.user).order_by('-created_at'))
        preferences, _ = UserPreferences.objects.get_or_create(
            user=request.user,
            defaults={
                'price_weight': 50,
                'sqft_weight': 50,
                'distance_weight': 50,
                'discount_calculation': 'daily'
            }
        )
    else:
        apartments = []
        session_prefs = request.session.get('anonymous_preferences', {})
        if session_prefs:
            class SessionPreferences:
                def __init__(self, data):
                    self.price_weight = data.get('price_weight', 50)
                    self.sqft_weight = data.get('sqft_weight', 50)
                    self.distance_weight = data.get('distance_weight', 50)
                    self.discount_calculation = data.get('discount_calculation', 'daily')
            preferences = SessionPreferences(session_prefs)
        else:
            preferences = None

    # Handle preferences form submission
    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                "price_weight": form.cleaned_data["price_weight"],
                "sqft_weight": form.cleaned_data["sqft_weight"],
                "distance_weight": form.cleaned_data["distance_weight"],
                "discount_calculation": form.cleaned_data["discount_calculation"],
            }

            if request.user.is_authenticated:
                UserPreferences.objects.update_or_create(
                    user=request.user,
                    defaults=preferences_data
                )
            else:
                request.session['anonymous_preferences'] = preferences_data
                request.session.modified = True

            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:dashboard")
    else:
        initial_data = {}
        if preferences:
            initial_data = {
                "price_weight": preferences.price_weight,
                "sqft_weight": preferences.sqft_weight,
                "distance_weight": preferences.distance_weight,
                "discount_calculation": preferences.discount_calculation,
            }
        form = UserPreferencesForm(initial=initial_data)

    # Calculate net effective price for each apartment
    discount_calc_method = preferences.discount_calculation if preferences else 'daily'
    for apartment in apartments:
        # For Django model apartments, use the property
        if hasattr(apartment, 'net_effective_price'):
            apartment.calculated_net_effective = apartment.net_effective_price
        else:
            apt_data = {
                'price': getattr(apartment, 'price', 0),
                'lease_length_months': getattr(apartment, 'lease_length_months', 12),
                'months_free': getattr(apartment, 'months_free', 0),
                'weeks_free': getattr(apartment, 'weeks_free', 0),
                'flat_discount': getattr(apartment, 'flat_discount', 0),
            }
            apartment.calculated_net_effective = calculate_net_effective_price(apt_data, discount_calc_method)

    # Sort apartments based on user preferences
    if preferences and apartments:
        apartments = sorted(
            apartments,
            key=lambda x: (
                (float(x.net_effective_price) * preferences.price_weight)
                + (x.square_footage * preferences.sqft_weight)
                + (0 * preferences.distance_weight)
            ),
            reverse=True,
        )

    has_premium = user_has_premium(request.user, PRODUCT_SLUG) if request.user.is_authenticated else False
    if request.user.is_authenticated:
        can_add_apartment = has_premium or len(apartments) < 2
    else:
        can_add_apartment = len(apartments) < 2

    has_discounts = any(
        (
            getattr(apt, "months_free", 0) > 0
            or getattr(apt, "weeks_free", 0) > 0
            or getattr(apt, "flat_discount", 0) > 0
        )
        for apt in apartments
    )

    context = {
        "apartments": apartments,
        "preferences": preferences,
        "form": form,
        "is_premium": has_premium,
        "can_add_apartment": can_add_apartment,
        "apartment_count": len(apartments),
        "apartment_limit": 2 if not has_premium else None,
        "is_anonymous": not request.user.is_authenticated,
        "has_discounts": has_discounts,
    }
    return render(request, "apartments/dashboard.html", context)


def create_apartment(request):
    if request.method == "POST":
        form = ApartmentForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")

            if not request.user.is_authenticated:
                return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

            # Check free tier limit
            has_premium = user_has_premium(request.user, PRODUCT_SLUG)
            current_count = Apartment.objects.filter(user=request.user).count()
            if not has_premium and current_count >= 2:
                messages.error(
                    request,
                    "Free tier limit reached. Upgrade to premium to add more apartments.",
                )
                return redirect("apartments:index")

            try:
                apartment = Apartment.objects.create(
                    user=request.user,
                    name=form.cleaned_data["name"],
                    price=form.cleaned_data["price"],
                    square_footage=form.cleaned_data["square_footage"],
                    lease_length_months=form.cleaned_data["lease_length_months"],
                    months_free=form.cleaned_data["months_free"],
                    weeks_free=form.cleaned_data["weeks_free"],
                    flat_discount=form.cleaned_data["flat_discount"],
                )
                messages.success(request, "Apartment added successfully!")
                return redirect("apartments:dashboard")
            except Exception as e:
                logger.error(f"Error saving apartment: {str(e)}")
                messages.error(request, "An error occurred while saving the apartment.")
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = ApartmentForm()

    return render(request, "apartments/apartment_form.html", {"form": form})


@login_required
def update_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, user=request.user)

    if request.method == "POST":
        form = ApartmentForm(request.POST)
        if form.is_valid():
            apartment.name = form.cleaned_data["name"]
            apartment.price = form.cleaned_data["price"]
            apartment.square_footage = form.cleaned_data["square_footage"]
            apartment.lease_length_months = form.cleaned_data["lease_length_months"]
            apartment.months_free = form.cleaned_data["months_free"]
            apartment.weeks_free = form.cleaned_data["weeks_free"]
            apartment.flat_discount = form.cleaned_data["flat_discount"]
            apartment.save()
            messages.success(request, "Apartment updated successfully!")
            return redirect("apartments:index")
    else:
        initial_data = {
            "name": apartment.name,
            "price": apartment.price,
            "square_footage": apartment.square_footage,
            "lease_length_months": apartment.lease_length_months,
            "months_free": apartment.months_free,
            "weeks_free": apartment.weeks_free,
            "flat_discount": apartment.flat_discount,
        }
        form = ApartmentForm(initial=initial_data)

    return render(request, "apartments/apartment_form.html", {"form": form})


def delete_apartment(request, pk):
    """Delete an apartment - handles both authenticated users and anonymous session apartments"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    # Check if this is a session apartment (starts with "session_")
    if str(pk).startswith("session_"):
        # Anonymous user deleting session apartment - handled by JavaScript
        return JsonResponse({"success": True})
    else:
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

        apartment = get_object_or_404(Apartment, pk=pk, user=request.user)
        apartment.delete()
        messages.success(request, "Apartment deleted successfully!")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            remaining_count = Apartment.objects.filter(user=request.user).count()
            return JsonResponse({
                "success": True,
                "remaining_count": remaining_count
            })

        remaining_apartments = Apartment.objects.filter(user=request.user).exists()
        if remaining_apartments:
            return redirect("apartments:dashboard")
        else:
            return redirect("apartments:index")


@login_required
def update_preferences(request):
    preferences, _ = UserPreferences.objects.get_or_create(
        user=request.user,
        defaults={
            'price_weight': 50,
            'sqft_weight': 50,
            'distance_weight': 50,
            'discount_calculation': 'daily'
        }
    )

    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences.price_weight = form.cleaned_data["price_weight"]
            preferences.sqft_weight = form.cleaned_data["sqft_weight"]
            preferences.distance_weight = form.cleaned_data["distance_weight"]
            preferences.discount_calculation = form.cleaned_data["discount_calculation"]
            preferences.save()
            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:index")
    else:
        initial_data = {
            "price_weight": preferences.price_weight,
            "sqft_weight": preferences.sqft_weight,
            "distance_weight": preferences.distance_weight,
            "discount_calculation": preferences.discount_calculation,
        }
        form = UserPreferencesForm(initial=initial_data)

    return render(request, "apartments/preferences_form.html", {"form": form})


@require_http_methods(["POST"])
def transfer_apartments(request):
    """Transfer apartments from sessionStorage to database after user signs up"""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        apartments = data.get("apartments", [])

        transferred_count = 0

        for apartment in apartments:
            try:
                Apartment.objects.create(
                    user=request.user,
                    name=apartment["name"],
                    price=Decimal(str(apartment["price"])),
                    square_footage=int(apartment["square_footage"]),
                    lease_length_months=int(apartment.get("lease_length_months", 12)),
                    months_free=int(apartment.get("months_free", 0)),
                    weeks_free=int(apartment.get("weeks_free", 0)),
                    flat_discount=Decimal(str(apartment.get("flat_discount", 0))),
                )
                transferred_count += 1
            except Exception as e:
                logger.error(f"Error transferring apartment: {e}")

        return JsonResponse({
            "success": True,
            "transferred_count": transferred_count
        })
    except Exception as e:
        logger.error(f"Error in transfer_apartments: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def signup_view(request):
    """Handle user registration"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # Create UserProfile for the new user
                UserProfile.objects.get_or_create(user=user)
                # Specify backend since we have multiple auth backends
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                messages.success(
                    request,
                    f"Welcome {user.first_name or user.username}! Your account has been created successfully.",
                )

                from django.utils.http import url_has_allowed_host_and_scheme
                next_url = request.POST.get('next') or request.GET.get('next')

                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                else:
                    return redirect("home")
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                messages.error(
                    request,
                    "An error occurred while creating your account. Please try again.",
                )
    else:
        form = CustomUserCreationForm()

    apartment_count = 0

    # Fetch plans from database
    plans = Plan.objects.filter(
        product__slug=PRODUCT_SLUG,
        is_active=True,
        tier='pro'
    ).order_by('billing_interval')

    monthly_plan = plans.filter(billing_interval='month').first()
    annual_plan = plans.filter(billing_interval='year').first()

    monthly_price = float(monthly_plan.price_amount) if monthly_plan else 5.00
    annual_price = float(annual_plan.price_amount) if annual_plan else 50.00
    annual_savings = (monthly_price * 12) - annual_price

    next_url = request.GET.get('next', '')

    context = {
        "form": form,
        "apartment_count": apartment_count,
        "has_apartments_to_save": apartment_count > 0,
        "monthly_price": monthly_price,
        "annual_price": annual_price,
        "annual_savings": annual_savings,
        "monthly_plan_id": monthly_plan.id if monthly_plan else None,
        "annual_plan_id": annual_plan.id if annual_plan else None,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "stripe_enabled": settings.STRIPE_ENABLED,
        "next": next_url,
    }

    return render(request, "apartments/signup.html", context)


def login_view(request):
    """Handle user login"""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")

                from django.utils.http import url_has_allowed_host_and_scheme
                next_url = request.POST.get('next') or request.GET.get('next')

                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                else:
                    return redirect("home")
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    next_url = request.GET.get('next', '')
    return render(request, "apartments/login.html", {"form": form, "next": next_url})


def logout_view(request):
    """Handle user logout with GET and POST requests"""
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("apartments:index")


def google_oauth_callback(request):
    """Handle Google OAuth callback and redirect after social auth"""
    if request.user.is_authenticated:
        logger.info(f"OAuth callback successful for user: {request.user.username}")
        messages.success(request, f"Welcome back, {request.user.username}!")

        from django.utils.http import url_has_allowed_host_and_scheme
        next_url = request.session.get('oauth_next')

        if 'oauth_next' in request.session:
            del request.session['oauth_next']

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        else:
            return redirect("home")
    else:
        logger.warning("OAuth callback failed - user not authenticated")
        messages.error(request, "Authentication failed. Please try again.")
        return redirect("login")


def privacy_policy(request):
    """Display privacy policy page"""
    from datetime import datetime
    return render(request, "apartments/privacy.html", {
        "current_date": datetime.now().strftime("%B %d, %Y")
    })


def terms_of_service(request):
    """Display terms of service page"""
    from datetime import datetime
    return render(request, "apartments/terms.html", {
        "current_date": datetime.now().strftime("%B %d, %Y")
    })


def robots_txt(request):
    """Generate robots.txt file dynamically"""
    from django.http import HttpResponse

    protocol = "https" if request.is_secure() else "http"
    host = request.get_host()
    sitemap_url = f"{protocol}://{host}/sitemap.xml"

    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {sitemap_url}",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")


# Subscription Views

def pricing_redirect(request):
    """Redirect pricing page to signup page (all pricing info is on signup page)"""
    return redirect('signup')


@login_required
def create_checkout_session(request):
    """Create a Stripe checkout session for subscription"""
    from .stripe_service import StripeService
    import stripe as stripe_lib

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        plan_id = data.get('plan_id')

        if not plan_id:
            return JsonResponse({'error': 'Plan ID is required'}, status=400)

        # Verify plan exists and is active
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, tier='pro')
        except Plan.DoesNotExist:
            return JsonResponse({'error': 'Invalid plan'}, status=400)

        success_url = request.build_absolute_uri('/apartments/subscription/success/')
        cancel_url = request.build_absolute_uri('/apartments/subscription/cancel/')

        stripe_service = StripeService()
        session = stripe_service.create_checkout_session(
            user=request.user,
            plan_id=plan_id,
            success_url=success_url,
            cancel_url=cancel_url
        )

        return JsonResponse({'sessionId': session.id})

    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@login_required
def checkout_success(request):
    """Handle successful checkout"""
    messages.success(request, "Thank you for subscribing! Your premium access is now active.")
    return redirect('apartments:dashboard')


@login_required
def checkout_cancel(request):
    """Handle cancelled checkout"""
    messages.info(request, "Checkout cancelled. You can upgrade to premium anytime.")
    return redirect('apartments:pricing')


@login_required
def billing_portal(request):
    """Redirect to Stripe billing portal for subscription management"""
    from .stripe_service import StripeService
    import stripe as stripe_lib

    try:
        stripe_service = StripeService()
        return_url = request.build_absolute_uri('/apartments/dashboard/')

        session = stripe_service.create_billing_portal_session(
            user=request.user,
            return_url=return_url
        )

        return redirect(session.url)

    except ValueError as e:
        messages.error(request, "You don't have an active subscription.")
        return redirect('apartments:pricing')
    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        messages.error(request, "Unable to access billing portal. Please try again.")
        return redirect('apartments:dashboard')
    except Exception as e:
        logger.error(f"Error creating billing portal session: {e}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('apartments:dashboard')


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    from .stripe_service import StripeService
    import stripe as stripe_lib

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe_lib.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    stripe_service = StripeService()
    event_type = event['type']

    try:
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            subscription_id = session.get('subscription')

            if subscription_id:
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.info(f"Checkout completed: {subscription_id}")

        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            stripe_service.sync_subscription_status(subscription)
            logger.info(f"Subscription updated: {subscription.id}")

        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            stripe_service.sync_subscription_status(subscription)
            logger.info(f"Subscription deleted: {subscription.id}")

        elif event_type == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            if subscription_id:
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.info(f"Payment succeeded for subscription: {subscription_id}")

        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            if subscription_id:
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.warning(f"Payment failed for subscription: {subscription_id}")

        else:
            logger.info(f"Unhandled webhook event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {e}")
        return JsonResponse({'error': 'Webhook processing failed'}, status=500)

    return JsonResponse({'status': 'success'})
