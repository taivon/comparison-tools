"""
Stripe service for handling subscription payments and customer management.
"""

import logging
from datetime import datetime

import stripe
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for managing Stripe subscriptions and customers."""

    def get_or_create_profile(self, user):
        """Get or create UserProfile for a user"""
        from .models import UserProfile

        profile, created = UserProfile.objects.get_or_create(user=user)
        return profile

    def get_or_create_customer(self, user):
        """
        Get or create a Stripe customer for a Django user.

        Args:
            user: Django User object

        Returns:
            Stripe Customer object
        """
        profile = self.get_or_create_profile(user)

        # If user already has a Stripe customer ID, retrieve it
        if profile.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(profile.stripe_customer_id)
                if not getattr(customer, "deleted", False):
                    return customer
            except stripe.error.StripeError as e:
                logger.error(f"Error retrieving Stripe customer: {e}")

        # Create new Stripe customer
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                metadata={
                    "user_id": str(user.id),
                    "username": user.username,
                },
            )

            # Update profile with Stripe customer ID
            profile.stripe_customer_id = customer.id
            profile.save()

            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer: {e}")
            raise

    def create_checkout_session(self, user, plan_id, success_url, cancel_url):
        """
        Create a Stripe Checkout session for subscription.

        Args:
            user: Django User object
            plan_id: Django Plan model ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled

        Returns:
            Stripe Checkout Session object
        """
        from .models import Plan

        try:
            # Get the plan
            plan = Plan.objects.select_related("product").get(id=plan_id)

            if not plan.stripe_price_id:
                raise ValueError(f"Plan {plan.name} has no Stripe price ID configured")

            # Get or create Stripe customer
            customer = self.get_or_create_customer(user)

            logger.info(f"Creating checkout session for plan: {plan.name}, price_id: {plan.stripe_price_id}")

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user.id),
                    "plan_id": str(plan.id),
                    "product_slug": plan.product.slug,
                },
                subscription_data={
                    "metadata": {
                        "user_id": str(user.id),
                        "plan_id": str(plan.id),
                        "product_slug": plan.product.slug,
                    }
                },
            )

            logger.info(f"Created checkout session {session.id} for user {user.id}, plan {plan.name}")
            return session

        except Plan.DoesNotExist:
            logger.error(f"Plan {plan_id} not found")
            raise ValueError(f"Plan {plan_id} not found") from None
        except stripe.error.StripeError as e:
            logger.error(f"Error creating checkout session: {e}")
            raise

    def create_billing_portal_session(self, user, return_url):
        """
        Create a Stripe billing portal session for customer to manage subscription.

        Args:
            user: Django User object
            return_url: URL to return to after managing subscription

        Returns:
            Stripe BillingPortal.Session object
        """
        try:
            profile = self.get_or_create_profile(user)

            if not profile.stripe_customer_id:
                raise ValueError("User does not have a Stripe customer ID")

            session = stripe.billing_portal.Session.create(
                customer=profile.stripe_customer_id,
                return_url=return_url,
            )

            logger.info(f"Created billing portal session for user {user.id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Error creating billing portal session: {e}")
            raise

    def sync_subscription_status(self, stripe_subscription):
        """
        Sync subscription status from Stripe to Subscription model.

        Args:
            stripe_subscription: Stripe Subscription object
        """
        from django.contrib.auth.models import User

        from .models import Plan, Subscription

        try:
            # Get user ID and plan ID from subscription metadata
            user_id = stripe_subscription.metadata.get("user_id")
            plan_id = stripe_subscription.metadata.get("plan_id")

            if not user_id:
                logger.warning(f"Subscription {stripe_subscription.id} has no user_id in metadata")
                return

            if not plan_id:
                logger.warning(f"Subscription {stripe_subscription.id} has no plan_id in metadata")
                return

            # Get user and plan
            try:
                user = User.objects.get(id=int(user_id))
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found")
                return

            try:
                plan = Plan.objects.get(id=int(plan_id))
            except Plan.DoesNotExist:
                logger.warning(f"Plan {plan_id} not found")
                return

            # Get or create subscription
            subscription, created = Subscription.objects.update_or_create(
                user=user,
                plan__product=plan.product,  # One subscription per product
                defaults={
                    "plan": plan,
                    "stripe_subscription_id": stripe_subscription.id,
                    "status": stripe_subscription.status,
                    "current_period_end": timezone.make_aware(
                        datetime.fromtimestamp(stripe_subscription.current_period_end)
                    ),
                    "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
                },
            )

            action = "Created" if created else "Updated"
            logger.info(f"{action} subscription for user {user_id}, plan {plan.name}: {stripe_subscription.status}")

        except Exception as e:
            logger.error(f"Error syncing subscription status: {e}")
            raise

    def cancel_subscription(self, user, product_slug, at_period_end=True):
        """
        Cancel a user's subscription for a product.

        Args:
            user: Django User object
            product_slug: Product slug
            at_period_end: If True, cancel at end of billing period. If False, cancel immediately.

        Returns:
            Stripe Subscription object
        """
        from .models import Subscription

        try:
            subscription = Subscription.objects.select_related("plan__product").get(
                user=user, plan__product__slug=product_slug, status__in=["active", "trialing"]
            )

            if not subscription.stripe_subscription_id:
                raise ValueError("Subscription has no Stripe subscription ID")

            if at_period_end:
                stripe_sub = stripe.Subscription.modify(subscription.stripe_subscription_id, cancel_at_period_end=True)
            else:
                stripe_sub = stripe.Subscription.delete(subscription.stripe_subscription_id)

            # Sync status
            self.sync_subscription_status(stripe_sub)

            logger.info(f"Cancelled subscription for user {user.id}, product {product_slug}")
            return stripe_sub

        except Subscription.DoesNotExist:
            raise ValueError(f"User does not have an active subscription for {product_slug}") from None
        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling subscription: {e}")
            raise

    def change_subscription_plan(self, user, product_slug, new_plan_id):
        """
        Change user's subscription plan for a product (upgrade/downgrade with proration).

        Args:
            user: Django User object
            product_slug: Product slug
            new_plan_id: New Plan model ID

        Returns:
            Stripe Subscription object
        """
        from .models import Plan, Subscription

        try:
            subscription = Subscription.objects.select_related("plan__product").get(
                user=user, plan__product__slug=product_slug, status__in=["active", "trialing"]
            )

            new_plan = Plan.objects.get(id=new_plan_id)

            if not new_plan.stripe_price_id:
                raise ValueError(f"New plan {new_plan.name} has no Stripe price ID configured")

            if not subscription.stripe_subscription_id:
                raise ValueError("Subscription has no Stripe subscription ID")

            # Get current Stripe subscription
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

            # Update subscription with new price
            updated_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[
                    {
                        "id": stripe_sub["items"]["data"][0].id,
                        "price": new_plan.stripe_price_id,
                    }
                ],
                proration_behavior="create_prorations",
                metadata={
                    "user_id": str(user.id),
                    "plan_id": str(new_plan.id),
                    "product_slug": product_slug,
                },
            )

            # Update local subscription
            subscription.plan = new_plan
            subscription.save()

            # Sync full status
            self.sync_subscription_status(updated_sub)

            logger.info(f"Changed subscription plan for user {user.id} to {new_plan.name}")
            return updated_sub

        except Subscription.DoesNotExist:
            raise ValueError(f"User does not have an active subscription for {product_slug}") from None
        except Plan.DoesNotExist:
            raise ValueError(f"Plan {new_plan_id} not found") from None
        except stripe.error.StripeError as e:
            logger.error(f"Error changing subscription plan: {e}")
            raise

    @staticmethod
    def has_active_subscription(user, product_slug: str) -> bool:
        """
        Check if user has an active subscription for a product.
        This is a convenience method that wraps user_has_premium from models.

        Args:
            user: Django User object
            product_slug: Product slug

        Returns:
            Boolean indicating if user has premium access
        """
        from .models import user_has_premium

        return user_has_premium(user, product_slug)

    def get_subscription_info(self, user, product_slug: str):
        """
        Get formatted subscription information for a product.

        Args:
            user: Django User object
            product_slug: Product slug

        Returns:
            Dictionary with subscription details
        """
        from .models import Product, get_user_subscription

        try:
            product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            return {
                "has_subscription": False,
                "product": None,
                "status": "",
                "plan": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
                "status_message": "Product not found",
            }

        subscription = get_user_subscription(user, product_slug)

        if not subscription:
            return {
                "has_subscription": False,
                "product": product,
                "status": "",
                "plan": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
                "status_message": "No active subscription",
            }

        has_premium = subscription.is_premium_active

        info = {
            "has_subscription": has_premium,
            "product": product,
            "status": subscription.status,
            "plan": subscription.plan,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        }

        # Add human-readable status message
        if subscription.status == "active" and subscription.cancel_at_period_end:
            info["status_message"] = (
                f"Your subscription will end on {subscription.current_period_end.strftime('%B %d, %Y')}"
            )
        elif subscription.status == "active":
            info["status_message"] = (
                f"Active {subscription.plan.name} (renews {subscription.current_period_end.strftime('%B %d, %Y')})"
            )
        elif subscription.status == "past_due":
            info["status_message"] = "Payment failed - please update your payment method"
        elif subscription.status == "canceled":
            if subscription.current_period_end and subscription.current_period_end > timezone.now():
                info["status_message"] = (
                    f"Subscription cancelled (access until {subscription.current_period_end.strftime('%B %d, %Y')})"
                )
            else:
                info["status_message"] = "No active subscription"
        else:
            info["status_message"] = "No active subscription"

        return info

    def get_available_plans(self, product_slug: str):
        """
        Get available plans for a product.

        Args:
            product_slug: Product slug

        Returns:
            QuerySet of Plan objects
        """
        from .models import Plan

        return Plan.objects.filter(
            product__slug=product_slug,
            is_active=True,
            tier="pro",  # Only return paid plans
        ).order_by("billing_interval")

    @staticmethod
    def get_price_from_stripe(stripe_price_id: str, fallback_amount: float = None):
        """
        Fetch price from Stripe API with caching.

        Args:
            stripe_price_id: Stripe Price ID
            fallback_amount: Fallback price if Stripe call fails

        Returns:
            dict with 'amount' (float), 'currency' (str), 'interval' (str)
        """
        from django.core.cache import cache

        if not stripe_price_id:
            logger.warning("No Stripe price ID provided, using fallback")
            return {
                "amount": fallback_amount or 0.0,
                "currency": "usd",
                "interval": None,
            }

        cache_key = f"stripe_price_{stripe_price_id}"
        cached_price = cache.get(cache_key)

        if cached_price:
            logger.debug(f"Using cached price for {stripe_price_id}")
            return cached_price

        try:
            price_obj = stripe.Price.retrieve(stripe_price_id)
            price_data = {
                "amount": price_obj.unit_amount / 100,  # Convert cents to dollars
                "currency": price_obj.currency,
                "interval": price_obj.recurring.interval if price_obj.recurring else None,
            }
            # Cache for 1 hour
            cache.set(cache_key, price_data, 3600)
            logger.info(f"Fetched price from Stripe for {stripe_price_id}: ${price_data['amount']}")
            return price_data

        except stripe.error.StripeError as e:
            logger.error(f"Error fetching price from Stripe: {e}")
            if fallback_amount is not None:
                logger.warning(f"Using fallback price: ${fallback_amount}")
                return {
                    "amount": fallback_amount,
                    "currency": "usd",
                    "interval": None,
                }
            raise
