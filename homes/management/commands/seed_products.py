from decimal import Decimal

from django.core.management.base import BaseCommand

from apartments.models import Plan, Product


class Command(BaseCommand):
    help = "Seed homes product and homes-agent product/plans"

    def handle(self, *args, **options):
        self.stdout.write("Seeding homes products and plans...")

        # Create homes product
        homes_product, created = Product.objects.update_or_create(
            slug="homes",
            defaults={
                "name": "Home Comparison",
                "description": "Compare homes for purchase by price, features, location, and more.",
                "free_tier_limit": 2,
                "pro_tier_limit": 20,
                "is_active": True,
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(f"  {action} product: {homes_product.name}")

        # Create homes-agent product
        homes_agent_product, created = Product.objects.update_or_create(
            slug="homes-agent",
            defaults={
                "name": "Home Comparison - Agent",
                "description": "Real estate agent subscription for managing client home searches.",
                "free_tier_limit": 0,  # No free tier for agents
                "pro_tier_limit": 100,  # Agents can manage many clients
                "is_active": True,
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(f"  {action} product: {homes_agent_product.name}")

        # Define plans for homes product
        homes_plans = [
            {"name": "Free", "tier": "free", "price_amount": Decimal("0"), "billing_interval": ""},
            {"name": "Pro Monthly", "tier": "pro", "price_amount": Decimal("9.99"), "billing_interval": "month"},
            {"name": "Pro Annual", "tier": "pro", "price_amount": Decimal("99.99"), "billing_interval": "year"},
            {"name": "Pro Lifetime", "tier": "pro", "price_amount": Decimal("299.99"), "billing_interval": "lifetime"},
        ]

        # Define plans for homes-agent product
        agent_plans = [
            {"name": "Agent Monthly", "tier": "pro", "price_amount": Decimal("19.99"), "billing_interval": "month"},
            {"name": "Agent Annual", "tier": "pro", "price_amount": Decimal("199.99"), "billing_interval": "year"},
        ]

        # Create plans for homes product
        for plan_data in homes_plans:
            plan, created = Plan.objects.update_or_create(
                product=homes_product,
                tier=plan_data["tier"],
                billing_interval=plan_data["billing_interval"],
                defaults={
                    "name": plan_data["name"],
                    "price_amount": plan_data["price_amount"],
                    "stripe_price_id": "",  # To be filled in later
                    "is_active": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"    {action} plan: {homes_product.name} - {plan.name}")

        # Create plans for homes-agent product
        for plan_data in agent_plans:
            plan, created = Plan.objects.update_or_create(
                product=homes_agent_product,
                tier=plan_data["tier"],
                billing_interval=plan_data["billing_interval"],
                defaults={
                    "name": plan_data["name"],
                    "price_amount": plan_data["price_amount"],
                    "stripe_price_id": "",  # To be filled in later
                    "is_active": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"    {action} plan: {homes_agent_product.name} - {plan.name}")

        self.stdout.write(self.style.SUCCESS("\nSeeding complete!"))
        self.stdout.write(
            self.style.WARNING(
                "\nNOTE: Remember to update stripe_price_id for each plan after creating products in Stripe."
            )
        )
