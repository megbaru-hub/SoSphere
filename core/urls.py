# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact, name='contact'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    # FIX: Use a string parameter for the composite cart key
    path('remove-from-cart/<str:key_parts>/', views.remove_from_cart, name='remove_from_cart'), 
    path('cart/', views.cart, name='cart'),
    
    # STEP 1: Renders the checkout form (GET request)
    path('checkout/', views.checkout, name='checkout'),
    
    # STEP 2: Handles the AJAX POST request, processes payment/order, and returns redirect URL (JSON)
    path('order/process/', views.payment_success_view, name='payment_success'), 
    
    # STEP 3: Renders the final receipt page (GET request after success)
    path('order/receipt/<int:order_id>/', views.receipt_page, name='receipt_page'),
    
    # PDF Download
    path('receipt/download/<int:order_id>/pdf/', views.download_receipt_pdf, name='download_receipt_pdf'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('payment-success/', views.payment_success_view, name='payment_success_view'),
    path('about/', views.about_page, name='about'),
]