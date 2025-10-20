from django.contrib import admin
from .models import Product, ContactMessage

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'created_at']
    search_fields = ['name', 'description']

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'created_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'