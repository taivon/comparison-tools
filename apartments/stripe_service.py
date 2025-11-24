"""
Stripe service for handling subscription payments and customer management.
"""

import stripe
import logging
from datetime import datetime
from django.conf import settings
from apartments.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for managing Stripe subscriptions and customers."""

    def __init__(self):
        self.firestore_service = FirestoreService()

    def get_or_create_customer(self, user):
        """
        Get or create a Stripe customer for a Firestore user.

        Args:
            user: FirestoreUser object

        Returns:
            Stripe Customer object
        """
        # If user already has a Stripe customer ID, retrieve it
        if user.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
                if not getattr(customer, 'deleted', False):
                    return customer
            except stripe.error.StripeError as e:
                logger.error(f"Error retrieving Stripe customer: {e}")

        # Create new Stripe customer
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                metadata={
                    'firestore_user_id': user.doc_id,
                    'username': user.username,
                }
            )

            # Update user with Stripe customer ID
            user.stripe_customer_id = customer.id
            self.firestore_service.update_user(user.doc_id, {
                'stripe_customer_id': customer.id
            })

            logger.info(f"Created Stripe customer {customer.id} for user {user.doc_id}")
            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer: {e}")
            raise

    def create_checkout_session(self, user, price_id, success_url, cancel_url):
        """
        Create a Stripe Checkout session for subscription.

        Args:
            user: FirestoreUser object
            price_id: Stripe Price ID (monthly or annual)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled

        Returns:
            Stripe Checkout Session object
        """
        try:
            # Get or create Stripe customer
            customer = self.get_or_create_customer(user)

            # Determine which plan is being purchased
            plan_type = 'monthly' if price_id == settings.STRIPE_MONTHLY_PRICE_ID else 'annual'

            logger.info(f"About to create checkout session with price_id: {price_id}, customer: {customer.id}")

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'firestore_user_id': user.doc_id,
                    'plan_type': plan_type,
                },
                subscription_data={
                    'metadata': {
                        'firestore_user_id': user.doc_id,
                        'plan_type': plan_type,
                    }
                }
            )

            logger.info(f"Created checkout session {session.id} for user {user.doc_id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Error creating checkout session: {e}")
            logger.error(f"Stripe error type: {type(e).__name__}")
            logger.error(f"Stripe error message: {e.user_message if hasattr(e, 'user_message') else 'No user message'}")
            logger.error(f"Stripe error code: {e.code if hasattr(e, 'code') else 'No code'}")
            raise

    def create_billing_portal_session(self, user, return_url):
        """
        Create a Stripe billing portal session for customer to manage subscription.

        Args:
            user: FirestoreUser object
            return_url: URL to return to after managing subscription

        Returns:
            Stripe BillingPortal.Session object
        """
        try:
            if not user.stripe_customer_id:
                raise ValueError("User does not have a Stripe customer ID")

            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )

            logger.info(f"Created billing portal session for user {user.doc_id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Error creating billing portal session: {e}")
            raise

    def sync_subscription_status(self, subscription):
        """
        Sync subscription status from Stripe to Firestore user.

        Args:
            subscription: Stripe Subscription object
        """
        try:
            # Get Firestore user ID from subscription metadata
            user_id = subscription.metadata.get('firestore_user_id')
            if not user_id:
                logger.warning(f"Subscription {subscription.id} has no firestore_user_id in metadata")
                return

            # Get user from Firestore
            user = self.firestore_service.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found in Firestore")
                return

            # Determine plan type
            plan_type = subscription.metadata.get('plan_type', '')

            # Update user subscription data
            update_data = {
                'stripe_subscription_id': subscription.id,
                'subscription_status': subscription.status,
                'subscription_plan': plan_type,
                'subscription_current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                'subscription_cancel_at_period_end': subscription.cancel_at_period_end,
            }

            self.firestore_service.update_user(user_id, update_data)
            logger.info(f"Synced subscription status for user {user_id}: {subscription.status}")

        except Exception as e:
            logger.error(f"Error syncing subscription status: {e}")
            raise

    def cancel_subscription(self, user, at_period_end=True):
        """
        Cancel a user's subscription.

        Args:
            user: FirestoreUser object
            at_period_end: If True, cancel at end of billing period. If False, cancel immediately.

        Returns:
            Stripe Subscription object
        """
        try:
            if not user.stripe_subscription_id:
                raise ValueError("User does not have an active subscription")

            if at_period_end:
                # Cancel at end of billing period (default behavior)
                subscription = stripe.Subscription.modify(
                    user.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            else:
                # Cancel immediately
                subscription = stripe.Subscription.delete(user.stripe_subscription_id)

            # Sync status to Firestore
            self.sync_subscription_status(subscription)

            logger.info(f"Cancelled subscription for user {user.doc_id}")
            return subscription

        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling subscription: {e}")
            raise

    def change_subscription_plan(self, user, new_price_id):
        """
        Change user's subscription plan (upgrade/downgrade with proration).

        Args:
            user: FirestoreUser object
            new_price_id: New Stripe Price ID

        Returns:
            Stripe Subscription object
        """
        try:
            if not user.stripe_subscription_id:
                raise ValueError("User does not have an active subscription")

            # Get current subscription
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

            # Update subscription with new price (prorated by default)
            updated_subscription = stripe.Subscription.modify(
                user.stripe_subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations',  # Prorate the change
                metadata={
                    'firestore_user_id': user.doc_id,
                    'plan_type': 'monthly' if new_price_id == settings.STRIPE_MONTHLY_PRICE_ID else 'annual',
                }
            )

            # Sync status to Firestore
            self.sync_subscription_status(updated_subscription)

            logger.info(f"Changed subscription plan for user {user.doc_id}")
            return updated_subscription

        except stripe.error.StripeError as e:
            logger.error(f"Error changing subscription plan: {e}")
            raise

    @staticmethod
    def has_active_subscription(user):
        """
        Check if user has an active subscription with access.

        This checks if the user has an active subscription OR if they're in the grace period
        after cancellation (access until end of paid period).

        Args:
            user: FirestoreUser object

        Returns:
            Boolean indicating if user has premium access
        """
        # Check legacy is_staff field (for backward compatibility)
        if user.is_staff:
            return True

        # Check if user has active subscription
        if user.subscription_status == 'active':
            return True

        # Check if subscription is cancelled but still in grace period
        if user.subscription_status == 'canceled' and user.subscription_current_period_end:
            # Allow access until end of paid period
            if user.subscription_current_period_end > datetime.now():
                return True

        # Check if subscription is past_due but still in grace period
        if user.subscription_status == 'past_due' and user.subscription_current_period_end:
            # Allow access until end of paid period
            if user.subscription_current_period_end > datetime.now():
                return True

        return False

    def get_subscription_info(self, user):
        """
        Get formatted subscription information for display.

        Args:
            user: FirestoreUser object

        Returns:
            Dictionary with subscription details
        """
        has_subscription = self.has_active_subscription(user)

        info = {
            'has_subscription': has_subscription,
            'status': user.subscription_status,
            'plan': user.subscription_plan,
            'current_period_end': user.subscription_current_period_end,
            'cancel_at_period_end': user.subscription_cancel_at_period_end,
        }

        # Add human-readable status message
        if user.subscription_status == 'active' and user.subscription_cancel_at_period_end:
            info['status_message'] = f"Your subscription will end on {user.subscription_current_period_end.strftime('%B %d, %Y')}"
        elif user.subscription_status == 'active':
            info['status_message'] = f"Active {user.subscription_plan} subscription (renews {user.subscription_current_period_end.strftime('%B %d, %Y')})"
        elif user.subscription_status == 'past_due':
            info['status_message'] = "Payment failed - please update your payment method"
        elif user.subscription_status == 'canceled':
            if user.subscription_current_period_end and user.subscription_current_period_end > datetime.now():
                info['status_message'] = f"Subscription cancelled (access until {user.subscription_current_period_end.strftime('%B %d, %Y')})"
            else:
                info['status_message'] = "No active subscription"
        else:
            info['status_message'] = "No active subscription"

        return info
