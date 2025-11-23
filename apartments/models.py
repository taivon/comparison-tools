from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class Apartment(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    square_footage = models.IntegerField(validators=[MinValueValidator(0)])
    lease_length_months = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Discount fields
    months_free = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    weeks_free = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    flat_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def price_per_sqft(self):
        if self.square_footage > 0:
            return round(self.price / Decimal(str(self.square_footage)), 2)
        else:
            return Decimal('0')
    
    @property
    def net_effective_price(self):
        total_discount = Decimal('0')
        user_preferences, _ = UserPreferences.objects.get_or_create(
            user=self.user,
            defaults={
                'price_weight': 50,
                'sqft_weight': 50,
                'distance_weight': 50,
                'discount_calculation': 'daily'
            }
        )

        if user_preferences.discount_calculation == 'daily':
            # Calculate annual rent divided by 365 days
            daily_rate = self.price * Decimal('12') / Decimal('365')
            # Convert months_free to days (using 365/12 for precision)
            if self.months_free > 0:
                days_free_from_months = Decimal(str(self.months_free)) * Decimal('365') / Decimal('12')
                total_discount += daily_rate * days_free_from_months
            # Convert weeks_free to days
            if self.weeks_free > 0:
                total_discount += daily_rate * Decimal('7') * Decimal(str(self.weeks_free))
        elif user_preferences.discount_calculation == 'weekly':
            # Calculate annual rent divided by 52 weeks
            weekly_rate = self.price * Decimal('12') / Decimal('52')
            # Convert months_free to weeks (using 52/12 for precision)
            if self.months_free > 0:
                weeks_free_from_months = Decimal(str(self.months_free)) * Decimal('52') / Decimal('12')
                total_discount += weekly_rate * weeks_free_from_months
            # Add weeks_free directly
            if self.weeks_free > 0:
                total_discount += weekly_rate * Decimal(str(self.weeks_free))
        else:  # monthly
            if self.months_free > 0:
                total_discount += self.price * Decimal(str(self.months_free))
            if self.weeks_free > 0:
                total_discount += self.price * Decimal(str(self.weeks_free / 4))

        total_discount += self.flat_discount
        total_lease_value = self.price * Decimal(str(self.lease_length_months))
        net_price = (total_lease_value - total_discount) / Decimal(str(self.lease_length_months))
        # Round to 2 decimal places
        return round(net_price, 2)

class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    price_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    sqft_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    distance_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_calculation = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('weekly', 'Weekly'),
            ('daily', 'Daily')
        ],
        default='monthly'
    )
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
