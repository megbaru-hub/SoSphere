# /home/megbaru/Documents/SoSphere/core/models.py
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
import uuid
from decimal import Decimal # Import Decimal for safe subtotal calculation
from django.urls import reverse

# ==========================================================
# 1. NEW CATEGORY MODEL (Top Level)
# ==========================================================
from django.db import models

# Constants for predefined Bootstrap Icons (Icon Class Name: Descriptive Name)
# This expanded list provides over 30 options for the administrator to choose from.
ICON_CHOICES = [
    ('bi-tag-fill', 'Default / Miscellaneous'),
    
    # Technology & Gadgets
    ('bi-phone-fill', 'Mobile Phones'),
    ('bi-laptop-fill', 'Laptops & Computers'),
    ('bi-tablet-fill', 'Tables & E-Readers'),
    ('bi-watch', 'Smart Watches'),
    ('bi-headphones', 'Audio / Headphones'),
    ('bi-speaker-fill', 'Speakers & Sound'),
    ('bi-mouse-fill', 'Mice / Peripherals'),
    ('bi-keyboard-fill', 'Keyboards'),
    ('bi-controller', 'Gaming'),
    ('bi-camera-fill', 'Cameras / Photography'),
    ('bi-cpu-fill', 'Computer Components'),
    ('bi-tv-fill', 'Televisions'),
    
    # Home & Lifestyle
    ('bi-house-fill', 'Home & Decor'),
    ('bi-lightning-fill', 'Appliances / Electric'),
    ('bi-droplet-fill', 'Kitchenware'),
    ('bi-wrench-adjustable-fill', 'Tools & DIY'),
    ('bi-lamp-fill', 'Lighting'),
    ('bi-door-closed-fill', 'Furniture'),
    ('bi-plug-fill', 'Cables & Power'),

    # Fashion & Apparel
    ('bi-bag-fill', 'Bags & Luggage'),
    ('bi-tshirt-fill', 'Clothing / Apparel'),
    ('bi-gem', 'Jewelry & Accessories'),
    ('bi-eyeglasses', 'Eyewear'),
    ('bi-shoe-fill', 'Footwear'),

    # Books, Media & Office
    ('bi-book-fill', 'Books & Literature'),
    ('bi-journal-richtext', 'Office Supplies'),
    ('bi-vinyl-fill', 'Music & Media'),
    ('bi-pencil-fill', 'Art Supplies'),
    
    # Sports, Fitness & Outdoors
    ('bi-bicycle', 'Sports & Cycling'),
    ('bi-heart-pulse-fill', 'Fitness / Health'),
    ('bi-globe', 'Outdoors / Travel'),
    ('bi-sun-fill', 'Patio / Garden'),
]

class Category(models.Model):
    # Assuming you already have these fields
    name = models.CharField(max_length=100)
    # ... other fields ...

    # NEW FIELD: Stores the Bootstrap icon class name
    icon_class = models.CharField(
        max_length=50,
        choices=ICON_CHOICES,
        default='bi-tag-fill',
        help_text="Select a Bootstrap icon class to display next to the category name."
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

# IMPORTANT: After updating this file, run:
# python manage.py makemigrations
# python manage.py migrate

        
# ==========================================================
# 2. CORE MODELS
# ==========================================================
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} - {self.email}"

# 3. PRODUCT MODEL (Updated with ForeignKey to Category)
class Product(models.Model):
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(0)])
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0,validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Rating must be between 0 and 10.")
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    def is_available(self):
        return self.stock > 0

class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, blank=True, null=True)
    
    def __str__(self):
        return self.name
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    # Assuming size/width/gender fields were removed as requested
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Optional variant price
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='variants/', blank=True, null=True)

    def __str__(self):
        return f"{self.product.name} - {self.color.name if self.color else 'No Color'}"

# 4. ORDER MODEL (Unchanged)
class Order(models.Model):
    buyer_name = models.CharField(max_length=100)
    buyer_email = models.EmailField()
    buyer_phone = models.CharField(max_length=20)
    buyer_city = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=50) 
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    payment_status = models.CharField(max_length=20, default='Pending') 
    receipt_signature = models.CharField(max_length=32, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.receipt_signature:
            self.receipt_signature = uuid.uuid4().hex.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.id} - {self.buyer_name}"

# 5. ORDER ITEM MODEL (Fixed get_subtotal)
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_subtotal(self):
       # Ensure price is a Decimal (0) and quantity is an integer (0) if None
       price_val = self.price if self.price is not None else Decimal(0)
       quantity_val = self.quantity if self.quantity is not None else 0
       
       # CRITICAL: Ensure the result is a Decimal for compatibility
       if not isinstance(price_val, Decimal):
           try:
               price_val = Decimal(str(price_val))
           except:
               price_val = Decimal(0)
               
       return price_val * quantity_val

    def __str__(self):
        return f"{self.quantity} x {self.product_name} in Order {self.order.id}"