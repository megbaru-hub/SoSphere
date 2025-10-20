from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact, name='contact'),
]