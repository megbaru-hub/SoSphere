# /home/megbaru/Documents/SoSphere/core/models.py

from django.db import models
from django.utils import timezone
import uuid # Import uuid for generating a unique identifier

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} - {self.email}"

class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    def is_available(self):
        return self.stock > 0

class Color(models.Model):
    name = models.CharField(max_length=50)
    hex_code = models.CharField(max_length=7)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    color = models.ForeignKey(Color, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='variants/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {self.color.name}"

# --- UPDATED ORDER MODEL for Receipt Signature Persistence ---
class Order(models.Model):
    buyer_name = models.CharField(max_length=100)
    buyer_email = models.EmailField()
    buyer_phone = models.CharField(max_length=20)
    buyer_city = models.CharField(max_length=100)
    
    payment_method = models.CharField(max_length=50) 
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    payment_status = models.CharField(max_length=20, default='Pending') 
    
    # CRITICAL ADDITION: Field to store the unique, persistent signature
    receipt_signature = models.CharField(max_length=32, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Generate the signature ONLY if it does not exist (i.e., first time save)
        if not self.receipt_signature:
            # Using UUID4 for high uniqueness. We can use the full UUID string.
            self.receipt_signature = uuid.uuid4().hex.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.id} - {self.buyer_name}"

# --- CRITICAL OrderItem MODEL (Details - unchanged) ---
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_subtotal(self):
    # CRITICAL FIX: Use 0 if price or quantity is None (for corrupted data)
       price = self.price if self.price is not None else 0
       quantity = self.quantity if self.quantity is not None else 0
    
       return price * quantity

    def __str__(self):
        return f"{self.quantity} x {self.product_name} in Order {self.order.id}"