from django.contrib.auth.models import User
from django.db import models


class Feature(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Property(models.Model):
    LISTING_TYPE_CHOICES = [
        ("sale", "For Sale"),
        ("rent", "For Rent"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    PROPERTY_TYPE_CHOICES = [
        ("apartment", "Apartment"),
        ("studio", "Studio"),
        ("house", "House"),
        ("villa", "Villa"),
        ("land", "Land"),
        ("commercial", "Commercial"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    description = models.TextField()

    price = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    area = models.DecimalField(max_digits=8, decimal_places=2)

    rooms = models.IntegerField(null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)

    city = models.CharField(max_length=100, db_index=True)
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Neighborhood / area"
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    property_type = models.CharField(
        max_length=20,
        choices=PROPERTY_TYPE_CHOICES,
        default="apartment"
    )

    features = models.ManyToManyField(
        Feature,
        blank=True,
        related_name="properties"
    )

    custom_features = models.TextField(
        blank=True,
        null=True,
        help_text="Additional features entered by the user"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    listing_type = models.CharField(
        max_length=10,
        choices=LISTING_TYPE_CHOICES,
        default="sale"
    )

    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"

    def __str__(self):
        return self.name

    @property
    def formatted_price(self):
        try:
            value = int(self.price)
            suffix = "/month" if self.listing_type == "rent" else ""
            return f"${value:,}{suffix}"
        except (TypeError, ValueError):
            return f"${self.price}"

    def cover_image(self):
        images = list(self.images.all())
        cover = next((img for img in images if img.is_cover), None)
        return cover or (images[0] if images else None)


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="properties/gallery/")
    is_cover = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.property.name}"


class TourRequest(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="tour_requests"
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tour request from {self.name} for {self.property.name}"

    class Meta:
        ordering = ["-created_at"]
