from django.core.management.base import BaseCommand
from apartments.models import Product, Plan
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed products and plans for the comparison tools'

    def handle(self, *args, **options):
        self.stdout.write('Seeding products and plans...')

        # Define products
        products_data = [
            {
                'slug': 'apartments',
                'name': 'Apartment Comparison',
                'description': 'Compare apartments by price, square footage, and lease terms.',
                'free_tier_limit': 2,
            },
            {
                'slug': 'homes',
                'name': 'Home Comparison',
                'description': 'Compare homes for purchase by price, features, and location.',
                'free_tier_limit': 2,
            },
            {
                'slug': 'cars',
                'name': 'Car Comparison',
                'description': 'Compare cars by price, mileage, and features.',
                'free_tier_limit': 2,
            },
            {
                'slug': 'hotels',
                'name': 'Hotel Comparison',
                'description': 'Compare hotels by price, amenities, and ratings.',
                'free_tier_limit': 2,
            },
            {
                'slug': 'bundle',
                'name': 'All Products Bundle',
                'description': 'Access all comparison tools with a single subscription.',
                'free_tier_limit': 0,  # Bundle has no free tier
            },
        ]

        # Create products
        for product_data in products_data:
            product, created = Product.objects.update_or_create(
                slug=product_data['slug'],
                defaults={
                    'name': product_data['name'],
                    'description': product_data['description'],
                    'free_tier_limit': product_data['free_tier_limit'],
                    'is_active': True,
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} product: {product.name}')

        # Define plans for each product (except bundle which has no free tier)
        # Stripe price IDs will need to be filled in after creating products in Stripe
        plan_templates = [
            {'name': 'Free', 'tier': 'free', 'price_amount': Decimal('0'), 'billing_interval': ''},
            {'name': 'Pro Monthly', 'tier': 'pro', 'price_amount': Decimal('5.00'), 'billing_interval': 'month'},
            {'name': 'Pro Annual', 'tier': 'pro', 'price_amount': Decimal('50.00'), 'billing_interval': 'year'},
        ]

        bundle_plans = [
            {'name': 'Pro Monthly', 'tier': 'pro', 'price_amount': Decimal('15.00'), 'billing_interval': 'month'},
            {'name': 'Pro Annual', 'tier': 'pro', 'price_amount': Decimal('150.00'), 'billing_interval': 'year'},
        ]

        for product in Product.objects.all():
            plans = bundle_plans if product.slug == 'bundle' else plan_templates

            for plan_data in plans:
                plan, created = Plan.objects.update_or_create(
                    product=product,
                    tier=plan_data['tier'],
                    billing_interval=plan_data['billing_interval'],
                    defaults={
                        'name': plan_data['name'],
                        'price_amount': plan_data['price_amount'],
                        'stripe_price_id': '',  # To be filled in later
                        'is_active': True,
                    }
                )
                action = 'Created' if created else 'Updated'
                self.stdout.write(f'    {action} plan: {product.name} - {plan.name}')

        self.stdout.write(self.style.SUCCESS('\nSeeding complete!'))
        self.stdout.write(self.style.WARNING(
            '\nNOTE: Remember to update stripe_price_id for each Pro plan after creating products in Stripe.'
        ))
