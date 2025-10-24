from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView
from django.contrib import messages
from django.conf import settings
from django.template.loader import render_to_string, get_template
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.db.models import Q
from datetime import datetime
import stripe
from weasyprint import HTML
from decimal import Decimal
from core.models import Product, Category, Color, ProductVariant, Order, OrderItem, ContactMessage # Consolidated imports

from .utils import create_grand_seller_stamp
# CRITICAL IMPORT: Include Category model (already done above, removing redundancy)

stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_your_key')

# --- Existing Views ---

def home(request):
    products = Product.objects.filter(stock__gt=0)[:3]
    return render(request, 'home.html', {'products': products})

class ProductListView(ListView):
    model = Product
    template_name = 'products.html'
    context_object_name = 'products'
    paginate_by = 10
    
    # Store the Category object here for use in get_context_data
    selected_category_obj = None 

    def get_queryset(self):
        # 1. Base Query: Get ALL in-stock products
        queryset = Product.objects.filter(stock__gt=0)
        
        # Search
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
            
        # 2. Filter by Category ID AND capture the object
        category_id = self.request.GET.get('category')
        if category_id:
            try:
                # Store the Category object as an instance attribute
                self.selected_category_obj = Category.objects.get(id=category_id)
                # Filter the queryset
                queryset = queryset.filter(category=self.selected_category_obj)
            except Category.DoesNotExist:
                # If category ID is invalid, treat it as no filter
                self.selected_category_obj = None
            

        # Sorting (Remains unchanged)
        sort = self.request.GET.get('sort', 'relevance')
        if sort == 'price_low':
            queryset = queryset.order_by('price')
        elif sort == 'price_high':
            queryset = queryset.order_by('-price')
        elif sort == 'rating':
            queryset = queryset.order_by('-rating')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pass all categories and ALL colors (for JS mapping)
        context['categories'] = Category.objects.all()
        context['all_colors'] = Color.objects.all()
        
        # CRITICAL FIX: Pass the Category object found in get_queryset()
        context['selected_category'] = self.selected_category_obj
        
        # Pass the currently selected filter values for persistence
        context['selected_color'] = self.request.GET.get('color')
        
        # Pass total product count for 'Products (Total)' on the main page
        context['all_products_count'] = Product.objects.count()
        
        context['query'] = self.request.GET.get('q', '')
        return context

def product_detail(request, pk):
    # ... (remains unchanged)
    product = get_object_or_404(Product, pk=pk, stock__gt=0)
    variants = ProductVariant.objects.filter(product=product, stock__gt=0)
    return render(request, 'product_detail.html', {'product': product, 'variants': variants})

# ... (rest of the views: contact, add_to_cart, remove_from_cart, cart, update_cart, checkout, payment_success_view, receipt_page, download_receipt_pdf) ...
def contact(request):
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            message=request.POST.get('message')
        )
        return JsonResponse({'success': True, 'message': "Thanks! We'll respond soon."})
    return render(request, 'contact.html')

def add_to_cart(request, pk):
    """Adds a product or variant to the session cart."""
    product = get_object_or_404(Product, pk=pk)
    
    pk_int = int(pk)
    variant_id_str = request.POST.get('variant_id') 
    variant_id = int(variant_id_str) if variant_id_str else None
    
    quantity = int(request.POST.get('quantity', 1))

    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        stock_available = variant.stock
        key = f"{pk_int}-{variant_id}" 
        image_url = variant.image.url if variant.image else (product.image.url if product.image else None)
        name = f"{product.name} ({variant.color.name})"
        price = variant.price or product.price  # Use variant price if set
    else:
        variant = None
        stock_available = product.stock
        key = str(pk_int)
        image_url = product.image.url if product.image else None
        name = product.name
        price = product.price

    cart = request.session.get('cart', {})

    if key in cart:
        if cart[key]['quantity'] + quantity > stock_available:
            return JsonResponse({'error': f'Not enough stock for {name}'}, status=400)
        cart[key]['quantity'] += quantity
    else:
        if quantity > stock_available:
            return JsonResponse({'error': f'Not enough stock for {name}'}, status=400)
        cart[key] = {
            'name': name,
            'price': float(price),
            'quantity': quantity,
            'stock': stock_available,
            'image': image_url,
            'product_id': pk_int,       
            'variant_id': variant_id,   
            'key_parts': key
        }
        
    request.session['cart'] = cart
    messages.success(request, f'{quantity} x {name} added!')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'cart_count': len(cart)})
    return redirect('product_detail', pk=pk)

def remove_from_cart(request, key_parts):
    cart = request.session.get('cart', {})
    key = str(key_parts)
    if key in cart:
        del cart[key]
        request.session['cart'] = cart
        messages.success(request, 'Item removed!')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'cart_count': len(cart)})
    return redirect('cart')

def cart(request):
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render(request, 'cart.html', {'cart': cart, 'total': total})
    
def update_cart(request):
    if request.method == 'POST':
        key = request.POST.get('key')
        quantity = int(request.POST.get('quantity', 1))
        cart = request.session.get('cart', {})
        if key in cart:
            # Check stock
            product_id = cart[key]['product_id']
            product = get_object_or_404(Product, id=product_id)
            stock_available = cart[key]['stock']
            if quantity > stock_available:
                return JsonResponse({'error': 'Not enough stock'}, status=400)
            cart[key]['quantity'] = quantity
            request.session['cart'] = cart
            total = sum(item['price'] * item['quantity'] for item in cart.values())
            line_total = cart[key]['price'] * quantity
            return JsonResponse({'success': True, 'new_total': total, 'line_total': line_total})
    return JsonResponse({'error': 'Invalid request'}, status=400)
    
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')
        
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    
    stripe_key = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', 'pk_test_your_key')
    return render(request, 'checkout.html', {'total': total, 'cart': cart, 'STRIPE_PUBLISHABLE_KEY': stripe_key})

def payment_success_view(request):
    """
    Finalizes the order: creates one Order (header) and multiple OrderItem (details) records.
    The Order.save() method handles the generation of the unique receipt_signature.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    cart = request.session.get('cart', {})
    if not cart:
        return JsonResponse({'success': False, 'message': "Your cart is empty. Please restart checkout."}, status=400)

    # Gather checkout data and calculate grand total
    checkout_data = {
        'name': request.POST.get('name'),
        'email': request.POST.get('email'),
        'phone': request.POST.get('phone'),
        'city': request.POST.get('other_city') if request.POST.get('city') == 'other' else request.POST.get('city'),
        'payment_method': request.POST.get('payment_method'),
        'stripe_token': request.POST.get('stripeToken'),
    }
    
    grand_total_decimal = sum(Decimal(str(item['price'])) * item['quantity'] for item in cart.values())
    grand_total = float(grand_total_decimal)

    # Payment validation/processing
    payment_status_successful = False
    payment_method = checkout_data['payment_method']
    
    # Test/Local Payment Bypass
    if payment_method == 'TEST_SUCCESS' or payment_method in ['cbe', 'abyssinia', 'telebirr', 'mpesa']:
        payment_status_successful = True 
        
    # Card Payment (Stripe)
    elif payment_method == 'card' and checkout_data.get('stripe_token'):
        total_amount_cents = int(grand_total_decimal * 100)
        
        try:
            charge = stripe.Charge.create(
                amount=total_amount_cents,
                currency="usd",
                description=f"Order from {checkout_data['name']}",
                source=checkout_data['stripe_token'],
            )
            if charge.paid:
                payment_status_successful = True
            else:
                return JsonResponse({'success': False, 'message': 'Stripe payment failed.'}, status=400)
        except stripe.error.CardError as e:
            return JsonResponse({'success': False, 'message': f'Card Error: {e.user_message}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Stripe processing error: {e}'}, status=500)

    if not payment_status_successful:
        return JsonResponse({'success': False, 'message': 'Payment failed. Please try again or choose another method.'}, status=400)
    
    # Order creation
    latest_order_id = None
    
    try:
        # Create main Order
        # The Order.save() method will automatically set the receipt_signature here.
        main_order = Order.objects.create(
            buyer_name=checkout_data['name'],
            buyer_email=checkout_data['email'],
            buyer_phone=checkout_data['phone'],
            buyer_city=checkout_data['city'],
            payment_method=payment_method,
            total=grand_total,
            payment_status='Completed', # Set status to completed upon successful payment
        )
        latest_order_id = main_order.id 
        
        # Create OrderItems and update stock
        for key, item in cart.items():
            product_id = item.get('product_id')
            variant_id = item.get('variant_id')
            product = get_object_or_404(Product, id=product_id)
            variant = None
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id)
            
            OrderItem.objects.create(
                order=main_order,
                product=product,
                variant=variant,
                product_name=item.get('name'),
                variant_name=item.get('variant_name', ''),
                price=item['price'],
                quantity=item['quantity']
            )
            
            if variant:
                variant.stock -= item['quantity']
                variant.save()
            else:
                product.stock -= item['quantity']
                product.save()

        # Clear cart
        if 'cart' in request.session:
            del request.session['cart']
        
        # CRITICAL: Redirect to receipt using the latest order ID
        redirect_to_receipt_url = reverse('receipt_page', kwargs={'order_id': latest_order_id})
        
        return JsonResponse({'success': True, 'redirect_url': redirect_to_receipt_url})

    except Exception as e:
        print(f"Error during order creation: {e}")
        return JsonResponse({'success': False, 'message': f"An unexpected server error occurred during order saving. Please contact support. Error: {e}"}, status=500)

def receipt_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.orderitem_set.all()
    
    # CRITICAL FIX: Use the PERSISTENT signature from the database
    stamp_image_data = create_grand_seller_stamp()
    
    context = {
        'order': order,
        'order_date': order.created_at or datetime.now(),
        'total': order.total,
        'items': [{'name': item.product_name, 'quantity': item.quantity, 'price': item.price, 'subtotal': item.price * item.quantity} for item in order_items],
        'receipt_signature': order.receipt_signature, # Use the saved signature
        'stamp_image_b64': stamp_image_data,
        'organization_name_am': 'ታላቅ ሻጭ',
        'is_pdf': False
    }
    
    return render(request, 'receipt_page.html', context)

def download_receipt_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.orderitem_set.all()

    # CRITICAL FIX: Use the PERSISTENT signature from the database
    stamp_image_data = create_grand_seller_stamp()
    
    context = {
        'order': order,
        'order_date': order.created_at or datetime.now(),
        'total': order.total,
        'items': [{'name': item.product_name, 'quantity': item.quantity, 'price': item.price, 'subtotal': item.price * item.quantity} for item in order_items],
        'receipt_signature': order.receipt_signature, # Use the saved signature
        'stamp_image_b64': stamp_image_data,
        'organization_name_am': 'ታላቅ ሻጭ',
        'is_pdf': True
    }

    html_template = get_template('receipt_page.html')
    html_content = html_template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_grand_seller_{order_id}.pdf"'
    
    HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf(response)

    return response

def about_page(request):
    return render(request, 'about.html')
# REMOVED: The redundant function-based `product_list` is removed here.