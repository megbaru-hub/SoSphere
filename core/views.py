from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView
from django.contrib import messages
from django.conf import settings
from django.template.loader import get_template
from django.urls import reverse
from django.db.models import Q
from django.views.decorators.http import require_POST
from datetime import datetime
import stripe
from weasyprint import HTML
from decimal import Decimal

# CRITICAL NEW IMPORTS: These must be present and correctly spelled!
import requests # Required for making external API calls to Chapa
import uuid     # Required for generating unique transaction references

from core.models import Product, Category, Color, ProductVariant, Order, OrderItem, ContactMessage

from .utils import create_grand_seller_stamp

# Initialize Stripe
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
    
    selected_category_obj = None 

    def get_queryset(self):
        # Explicitly include all fields we need in the queryset
        queryset = Product.objects.filter(stock__gt=0).select_related('category')
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
            
        category_id = self.request.GET.get('category')
        if category_id:
            try:
                self.selected_category_obj = Category.objects.get(id=category_id)
                queryset = queryset.filter(category=self.selected_category_obj)
            except Category.DoesNotExist:
                self.selected_category_obj = None
                
        condition = self.request.GET.get('condition')
        if condition in ['new', 'used']:
            queryset = queryset.filter(condition=condition)
            
        # Ensure we're getting all necessary fields
        queryset = queryset.only('id', 'name', 'description', 'price', 'stock', 'image', 'condition', 'rating', 'category__name')
            

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
        
        context['categories'] = Category.objects.all()
        context['all_colors'] = Color.objects.all()
        
        context['selected_category'] = self.selected_category_obj
        
        context['selected_color'] = self.request.GET.get('color')
        
        context['all_products_count'] = Product.objects.count()
        
        context['query'] = self.request.GET.get('q', '')
        return context

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    variants = ProductVariant.objects.filter(product=product)
    
    # Debug information
    print(f"Product ID: {product.id}, Name: {product.name}, Stock: {product.stock}")
    for i, variant in enumerate(variants, 1):
        print(f"Variant {i}: ID={variant.id}, Color={variant.color.name if variant.color else 'N/A'}, Stock={variant.stock}")
    
    return render(request, 'product_detail.html', {
        'product': product, 
        'variants': variants,
        'debug_info': {
            'product_stock': product.stock,
            'has_variants': variants.exists(),
            'variants_count': variants.count(),
            'variants_stock': [{'id': v.id, 'stock': v.stock} for v in variants]
        }
    })

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
    
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            return JsonResponse({'error': 'Quantity must be at least 1'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid quantity'}, status=400)
        
    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        stock_available = variant.stock
        name = f"{product.name} - {variant.color.name}"
        price = variant.price if variant.price is not None else product.price
        image_url = variant.image.url if variant.image else product.image.url
        key = f"{product.id}_{variant_id}"
    else:
        stock_available = product.stock
        name = product.name
        price = product.price
        image_url = product.image.url if product.image else ''
        key = str(product.id)  # Key for non-variant products

    cart = request.session.get('cart', {})

    # Check if requested quantity is available
    requested_quantity = (cart[key]['quantity'] + quantity) if key in cart else quantity
    if requested_quantity > stock_available:
        return JsonResponse({'error': f'Not enough stock for {name}. Only {stock_available} available.'}, status=400)
    
    # Update cart
    if key in cart:
        cart[key]['quantity'] += quantity
    else:
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
            product_id = cart[key]['product_id']
            product = get_object_or_404(Product, id=product_id) 
            
            variant_id = cart[key]['variant_id']
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id)
                stock_available = variant.stock
            else:
                stock_available = product.stock
                
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

# -----------------------------------------------------------------------------
# CORRECTED process_payment view with Chapa redirection logic
# -----------------------------------------------------------------------------

@require_POST
def process_payment(request):
    """
    Handles checkout AJAX: Stripe payment processing OR Chapa redirection.
    Order creation is DEFERRED for Chapa until payment_callback/webhook verification.
    """
    cart = request.session.get('cart', {})
    if not cart:
        return JsonResponse({'success': False, 'message': "Your cart is empty. Please restart checkout."}, status=400)

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

    payment_status_successful = False
    payment_method = checkout_data['payment_method']
    
    
    # 1. Chapa/Local Payment Initiation (Redirect Flow - Stops here if successful)
    if payment_method in ['cbe', 'abyssinia', 'telebirr', 'mpesa']:
        
        # 1a. Prepare Chapa API payload
        tx_ref = f"GS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}" 
        
        chapa_payload = {
            "amount": grand_total,
            "currency": "ETB", 
            "email": checkout_data['email'],
            "first_name": checkout_data['name'].split(' ')[0],
            "last_name": checkout_data['name'].split(' ')[-1] if len(checkout_data['name'].split(' ')) > 1 else 'Buyer',
            "tx_ref": tx_ref,
            # NOTE: You MUST define 'chapa_webhook' and 'payment_callback' in core/urls.py
            "callback_url": request.build_absolute_uri(reverse('chapa_webhook')), 
            "return_url": request.build_absolute_uri(reverse('payment_callback', kwargs={'tx_ref': tx_ref})),
            "customization[title]": "SoSphere Order",
            "customization[description]": "Payment for goods",
            "payment_type": payment_method 
        }
        
        # 1b. Call Chapa API
        try:
            chapa_response = requests.post(
                "https://api.chapa.co/v1/transaction/initialize",
                headers={"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}, 
                json=chapa_payload
            ).json()
            
            if chapa_response.get('status') == 'success':
                chapa_checkout_url = chapa_response['data']['checkout_url']
                
                # CRITICAL: We return the redirect URL. The order is NOT created yet.
                return JsonResponse({'success': True, 'redirect_url': chapa_checkout_url})
            else:
                # Chapa initialization failed (e.g., bad data, API key issue)
                return JsonResponse({'success': False, 'message': chapa_response.get('message', 'Chapa initialization failed.')}, status=400)

        except Exception as e:
            # This catches connection errors (if requests fails)
            print(f"Chapa API connection error: {e}")
            return JsonResponse({'success': False, 'message': 'Failed to connect to Chapa gateway.'}, status=500)
    
    
    # 2. Stripe Card Payment (Direct Flow - Insufficient funds handled by Stripe)
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
                payment_status_successful = True # Continue to order creation below
            else:
                return JsonResponse({'success': False, 'message': 'Stripe payment failed (not paid).'}, status=400)
        except stripe.error.CardError as e:
            # Handles insufficient funds, declined card, etc.
            return JsonResponse({'success': False, 'message': f'Card Error: {e.user_message}'}, status=400)
        except Exception as e:
            print(f"Stripe Processing Error: {e}")
            return JsonResponse({'success': False, 'message': 'Stripe processing error. Please contact support.'}, status=500)

    
    # 3. Test Success (Direct Flow)
    elif payment_method == 'TEST_SUCCESS':
        payment_status_successful = True # Continue to order creation below

    
    # --- Check for Failure to Proceed to Order Creation ---
    if not payment_status_successful:
        return JsonResponse({'success': False, 'message': 'Payment attempt failed or method is invalid.'}, status=400)
    
    
    # -----------------------------------------------------------
    # FINAL ORDER CREATION AND FINALIZATION BLOCK
    # (Only reached on Stripe success or TEST_SUCCESS)
    # -----------------------------------------------------------
    latest_order_id = None
    
    try:
        # Create main Order
        main_order = Order.objects.create(
            buyer_name=checkout_data['name'],
            buyer_email=checkout_data['email'],
            buyer_phone=checkout_data['phone'],
            buyer_city=checkout_data['city'],
            payment_method=payment_method,
            total=grand_total,
            payment_status='Completed', 
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
                variant_name=variant.color.name if variant else '', 
                price=item['price'],
                quantity=item['quantity']
            )
            
            if variant:
                variant.stock -= item['quantity']
                variant.save()
            else:
                product.stock -= item['quantity']
                product.save()

        # Clear cart only after successful order creation
        if 'cart' in request.session:
            del request.session['cart']
        
        # Success response: Redirect to the receipt page
        redirect_to_receipt_url = reverse('receipt_page', kwargs={'order_id': latest_order_id})
        
        return JsonResponse({'success': True, 'redirect_url': redirect_to_receipt_url})

    except Exception as e:
        print(f"Error during order creation: {e}")
        return JsonResponse({'success': False, 'message': "An unexpected server error occurred during order saving. Please contact support."}, status=500)


def receipt_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.orderitem_set.all()
    
    stamp_image_data = create_grand_seller_stamp()
    
    context = {
        'order': order,
        'order_date': order.created_at or datetime.now(),
        'total': order.total,
        'items': [{'name': item.product_name, 'quantity': item.quantity, 'price': item.price, 'subtotal': item.price * item.quantity} for item in order_items],
        'receipt_signature': order.receipt_signature,
        'stamp_image_b64': stamp_image_data,
        'organization_name_am': 'ታላቅ ሻጭ',
        'is_pdf': False
    }
    
    return render(request, 'receipt_page.html', context)

def download_receipt_pdf(request, order_id):
    # ... (code for PDF download) ...
    pass

def about_page(request):
    return render(request, 'about.html')

