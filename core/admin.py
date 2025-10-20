# /home/megbaru/Documents/SoSphere/core/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import Product, Color, ProductVariant, ContactMessage, Order, OrderItem

# --- 1. INLINE DEFINITIONS (Must come first) ---

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    # Make order items read-only and include the subtotal method
    readonly_fields = ('product', 'variant', 'product_name', 'variant_name', 'price', 'quantity', 'order_subtotal')
    can_delete = False
    extra = 0
    
    # Custom method to call the robust get_subtotal from the model
    def order_subtotal(self, obj):
        # We call the model method, and format the output for display
        return f"${obj.get_subtotal():.2f}"
    order_subtotal.short_description = "Subtotal" 

# --- 2. MODEL ADMIN DEFINITIONS ---

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stock', 'rating', 'is_available')
    list_filter = ('created_at', 'stock')
    search_fields = ('name', 'description')
    inlines = [ProductVariantInline]

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code')
    search_fields = ('name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # CRITICAL CHANGE: Added 'view_receipt' to list_display
    list_display = ('id', 'buyer_name', 'buyer_email', 'buyer_phone', 'buyer_city', 'total', 'payment_status', 'created_at', 'view_receipt')
    
    list_filter = ('payment_status', 'created_at', 'payment_method')
    search_fields = ('buyer_name', 'buyer_email', 'buyer_phone', 'buyer_city', 'id')
    
    readonly_fields = ('created_at', 'total')
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'

    # Method to generate a link to the receipt
    def view_receipt(self, obj):
        if obj.id:
            # URL for the customer-facing receipt page
            receipt_url = reverse('receipt_page', kwargs={'order_id': obj.id})
            # URL for the PDF download view
            pdf_url = reverse('download_receipt_pdf', kwargs={'order_id': obj.id})
            
            return format_html(
                '<a class="button" href="{}" target="_blank">View Receipt</a>&nbsp;'
                '<a class="button" href="{}" target="_blank">Download PDF</a>',
                receipt_url,
                pdf_url
            )
        return "-"
    view_receipt.short_description = "Receipt Actions" 
    
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'email', 'message')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'variant_name', 'quantity', 'price')
    list_filter = ('order',)
    search_fields = ('order__id', 'product_name', 'variant_name')