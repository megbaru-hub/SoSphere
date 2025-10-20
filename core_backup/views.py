from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView
from .models import Product, ContactMessage

def home(request):
    products = Product.objects.all()[:3]  # Featured products
    return render(request, 'home.html', {'products': products})

class ProductListView(ListView):
    model = Product
    template_name = 'products.html'
    context_object_name = 'products'
    paginate_by = 10

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'product_detail.html', {'product': product})

def contact(request):
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            message=request.POST.get('message')
        )
        return JsonResponse({'success': True, 'message': "Thanks! We'll respond soon."})
    return render(request, 'contact.html')