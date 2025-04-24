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
        return self.price / Decimal(str(self.square_footage)) if self.square_footage > 0 else Decimal('0')
    
    @property
    def net_effective_price(self):
        total_discount = Decimal('0')
        if self.months_free > 0:
            total_discount += (self.price * Decimal(str(self.months_free)))
        if self.weeks_free > 0:
            total_discount += (self.price * Decimal(str(self.weeks_free / 4)))
        total_discount += self.flat_discount
        
        total_lease_value = self.price * Decimal(str(self.lease_length_months))
        return (total_lease_value - total_discount) / Decimal(str(self.lease_length_months))

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
