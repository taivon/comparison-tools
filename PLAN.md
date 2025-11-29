# Implementation Plan: Favorite Places + Distance/Travel Time Feature

## Overview
Add a feature that lets users compare apartments based on distance from their favorite places (e.g., Work, Gym). Free users get 1 favorite place, Pro users get up to 5.

---

## Phase 1: Database Models

### 1.1 Create FavoritePlace Model
**File**: `apartments/models.py`

```python
class FavoritePlace(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_places')
    label = models.CharField(max_length=100)  # e.g., "Work", "Gym"
    address = models.CharField(max_length=500)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 1.2 Add Location Fields to Apartment Model
**File**: `apartments/models.py`

Add to existing Apartment model:
```python
address = models.CharField(max_length=500, blank=True, default='')
latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
```

### 1.3 Create ApartmentDistance Model (Cache)
**File**: `apartments/models.py`

```python
class ApartmentDistance(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='distances')
    favorite_place = models.ForeignKey(FavoritePlace, on_delete=models.CASCADE, related_name='apartment_distances')
    distance_miles = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    travel_time_minutes = models.IntegerField(null=True, blank=True)  # Optional for MVP
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['apartment', 'favorite_place']
```

---

## Phase 2: Geocoding Service

### 2.1 Install geopy
Add to requirements.txt: `geopy>=2.4.0`

### 2.2 Create Geocoding Service
**File**: `apartments/geocoding_service.py`

```python
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class GeocodingService:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="comparison-tools")

    def geocode_address(self, address):
        """Returns (latitude, longitude) or (None, None) if failed"""
        try:
            location = self.geolocator.geocode(address, timeout=10)
            if location:
                return (location.latitude, location.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            pass
        return (None, None)
```

---

## Phase 3: Distance Calculation Service

### 3.1 Create Distance Service
**File**: `apartments/distance_service.py`

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two points using Haversine formula"""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def calculate_and_cache_distances(apartment):
    """Calculate distances from apartment to all user's favorite places"""
    from .models import ApartmentDistance, FavoritePlace

    if not apartment.latitude or not apartment.longitude:
        return

    favorite_places = FavoritePlace.objects.filter(user=apartment.user)

    for place in favorite_places:
        if not place.latitude or not place.longitude:
            continue

        distance = haversine_distance(
            apartment.latitude, apartment.longitude,
            place.latitude, place.longitude
        )

        ApartmentDistance.objects.update_or_create(
            apartment=apartment,
            favorite_place=place,
            defaults={'distance_miles': round(distance, 2)}
        )

def recalculate_distances_for_favorite_place(favorite_place):
    """Recalculate distances when a favorite place is added/updated"""
    from .models import ApartmentDistance, Apartment

    if not favorite_place.latitude or not favorite_place.longitude:
        return

    apartments = Apartment.objects.filter(user=favorite_place.user)

    for apartment in apartments:
        if not apartment.latitude or not apartment.longitude:
            continue

        distance = haversine_distance(
            apartment.latitude, apartment.longitude,
            favorite_place.latitude, favorite_place.longitude
        )

        ApartmentDistance.objects.update_or_create(
            apartment=apartment,
            favorite_place=favorite_place,
            defaults={'distance_miles': round(distance, 2)}
        )

def get_apartment_distances(apartment):
    """Get all distances for an apartment, including average"""
    from .models import ApartmentDistance

    distances = ApartmentDistance.objects.filter(
        apartment=apartment
    ).select_related('favorite_place')

    distance_list = []
    total = 0
    count = 0

    for d in distances:
        if d.distance_miles is not None:
            distance_list.append({
                'label': d.favorite_place.label,
                'distance': float(d.distance_miles),
                'travel_time': d.travel_time_minutes
            })
            total += float(d.distance_miles)
            count += 1

    average = round(total / count, 2) if count > 0 else None

    return {
        'distances': distance_list,
        'average_distance': average
    }
```

---

## Phase 4: Limit Enforcement

### 4.1 Add Helper Function
**File**: `apartments/models.py`

```python
def get_favorite_place_limit(user, product_slug='apartments'):
    """Returns max favorite places allowed: 1 for free, 5 for pro"""
    if user_has_premium(user, product_slug):
        return 5
    return 1

def can_add_favorite_place(user, product_slug='apartments'):
    """Check if user can add another favorite place"""
    from .models import FavoritePlace
    current_count = FavoritePlace.objects.filter(user=user).count()
    limit = get_favorite_place_limit(user, product_slug)
    return current_count < limit
```

---

## Phase 5: Forms

### 5.1 Create FavoritePlaceForm
**File**: `apartments/forms.py`

```python
class FavoritePlaceForm(forms.ModelForm):
    class Meta:
        model = FavoritePlace
        fields = ['label', 'address']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg...',
                'placeholder': 'e.g., Work, Gym, Parents House'
            }),
            'address': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg...',
                'placeholder': 'Full address'
            }),
        }
```

### 5.2 Update ApartmentForm
**File**: `apartments/forms.py`

Add `address` field to ApartmentForm.

---

## Phase 6: Views & URLs

### 6.1 Favorite Places Views
**File**: `apartments/views.py`

- `favorite_places_list(request)` - List user's favorite places
- `create_favorite_place(request)` - Create with geocoding
- `update_favorite_place(request, pk)` - Update with re-geocoding
- `delete_favorite_place(request, pk)` - Delete and cascade distances

### 6.2 Update Apartment Views
- Modify `create_apartment()` to geocode address and calculate distances
- Modify `update_apartment()` to re-geocode if address changed

### 6.3 Add URLs
**File**: `apartments/urls.py`

```python
path('favorite-places/', views.favorite_places_list, name='favorite_places'),
path('favorite-places/create/', views.create_favorite_place, name='create_favorite_place'),
path('favorite-places/<int:pk>/update/', views.update_favorite_place, name='update_favorite_place'),
path('favorite-places/<int:pk>/delete/', views.delete_favorite_place, name='delete_favorite_place'),
```

---

## Phase 7: Template Updates

### 7.1 Favorite Places Management Page
**File**: `apartments/templates/apartments/favorite_places.html`

- List of favorite places with edit/delete
- Add new place form
- Show limit (1/1 for free, X/5 for pro)
- Upgrade prompt when at limit

### 7.2 Update Dashboard Template
**File**: `apartments/templates/apartments/dashboard.html`

Add to comparison table:
- Column for each favorite place distance
- Column for average distance
- Sorting by average distance
- Handle N/A for missing geocoding

### 7.3 Update Apartment Form Modal
**File**: `apartments/templates/apartments/index.html` and `dashboard.html`

- Add address field to apartment creation/edit form

### 7.4 Add Navigation Link
Add "Favorite Places" link to navigation/dashboard

---

## Phase 8: Signal Handlers (Auto-recalculation)

### 8.1 Create Signals
**File**: `apartments/signals.py`

```python
@receiver(post_save, sender=Apartment)
def apartment_saved(sender, instance, **kwargs):
    # Geocode if address changed and recalculate distances

@receiver(post_save, sender=FavoritePlace)
def favorite_place_saved(sender, instance, **kwargs):
    # Geocode if address changed and recalculate distances
```

---

## Migration Plan

1. Create migration for new models (FavoritePlace, ApartmentDistance)
2. Create migration for Apartment model changes (add address, latitude, longitude)
3. Run migrations

---

## Files to Create/Modify

### New Files:
- `apartments/geocoding_service.py`
- `apartments/distance_service.py`
- `apartments/signals.py`
- `apartments/templates/apartments/favorite_places.html`

### Modified Files:
- `apartments/models.py` - Add FavoritePlace, ApartmentDistance, update Apartment
- `apartments/forms.py` - Add FavoritePlaceForm, update ApartmentForm
- `apartments/views.py` - Add favorite place views, update apartment views
- `apartments/urls.py` - Add favorite place URLs
- `apartments/templates/apartments/dashboard.html` - Add distance columns
- `apartments/templates/apartments/index.html` - Add address field to form
- `apartments/templates/apartments/base.html` - Add navigation link
- `requirements.txt` - Add geopy

---

## Testing Checklist

- [ ] Free user can add exactly 1 favorite place
- [ ] Pro user can add up to 5 favorite places
- [ ] Geocoding works for valid addresses
- [ ] Geocoding gracefully fails for invalid addresses (shows N/A)
- [ ] Distances calculated correctly
- [ ] Distances recalculate when apartment address changes
- [ ] Distances recalculate when favorite place address changes
- [ ] Average distance calculated correctly
- [ ] Sorting by average distance works
- [ ] Anonymous users cannot use favorite places (requires login)
