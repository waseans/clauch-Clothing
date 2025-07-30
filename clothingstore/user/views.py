from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

from django.shortcuts import render
from .models import Category

from django.shortcuts import render
from .models import Category, Product  # or your item model

def home_view(request):
    categories = Category.objects.all()
    query = request.GET.get('q')
    selected_category = request.GET.get('category', 'all')

    results = []
    if query:
        results = Product.objects.filter(title__icontains=query)[:10]

    if selected_category == 'all':
        popular_products = Product.objects.all()[:12]  # You can use a `popular=True` filter if available
    else:
        popular_products = Product.objects.filter(categories__name__iexact=selected_category)[:12]

    context = {
        'categories': categories,
        'query': query,
        'results': results,
        'popular_products': popular_products,
        'selected_category': selected_category,
    }
    return render(request, "home.html", context)


from django.template.loader import render_to_string
from django.http import JsonResponse

def filter_popular_products(request):
    category = request.GET.get("category", "all")

    if category == "all":
        products = Product.objects.all()[:12]
    else:
        products = Product.objects.filter(categories__name__iexact=category)[:12]

    html = render_to_string("partials/popular_products_grid.html", {"products": products}, request=request)
    return JsonResponse({"html": html})


from django.shortcuts import render
from .models import Category, Product

# ✅ views.py
from django.shortcuts import render
from .models import Product
from django.shortcuts import render
from django.db.models import Q
from .models import Product, Category

def new_view(request):
    # Get filter parameters
    selected_sizes = request.GET.getlist('size')
    selected_colors = request.GET.getlist('color')
    selected_sleeves = request.GET.getlist('sleeves')
    selected_categories = request.GET.getlist('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort')

    # Base queryset
    products = Product.objects.all()

    # --- Apply size filter ---
    if selected_sizes:
        size_q = Q()
        for size in selected_sizes:
            size_q |= Q(sizes__icontains=size)
        products = products.filter(size_q)

    # --- Apply category filter ---
    if selected_categories:
        products = products.filter(categories__name__in=selected_categories)

    # --- Apply color filter ---
    if selected_colors:
        products = products.filter(colors__name__in=selected_colors)

    # --- Apply sleeves filter ---
    if selected_sleeves:
        sleeve_q = Q()
        for sleeve in selected_sleeves:
            sleeve_q |= Q(description__icontains=sleeve)  # Adjust this based on your model field
        products = products.filter(sleeve_q)

    # --- Apply price filters ---
    if min_price:
        products = products.filter(Q(discount_price__gte=min_price) | Q(price__gte=min_price))

    if max_price:
        products = products.filter(Q(discount_price__lte=max_price) | Q(price__lte=max_price))

    # --- Sort logic ---
    if sort_by == "low":
        products = products.order_by('discount_price', 'price')
    elif sort_by == "high":
        products = products.order_by('-discount_price', '-price')
    elif sort_by == "new":
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-id')

    # Static filter values
    sizes = ["XS", "S", "M", "L", "XL", "XXL", "26", "28", "30", "32", "34", "36", "38", "40", "42"]
    colors = ["Black", "White", "Grey", "Beige", "Blue", "Green", "Red", "Yellow", "Brown", "Orange"]
    sleeves = ["Full Sleeve", "Half Sleeve", "Sleeveless"]
    categories = Category.objects.all()

    return render(request, 'new.html', {
        'products': products.distinct(),
        'categories': categories,
        'sizes': sizes,
        'colors': colors,
        'sleeves': sleeves,
        'selected_category': 'ALL',
        'filters': {
            'sizes': selected_sizes,
            'colors': selected_colors,
            'sleeves': selected_sleeves,
            'categories': selected_categories,
            'min_price': min_price,
            'max_price': max_price,
            'sort_by': sort_by,
        }
    })




def cart_view(request):
    return render(request, "cart.html")


def showroom_view(request):
    return render(request, "showroom.html")

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def account_view(request):
    edit_mode = request.GET.get('edit') == 'true'
    return render(request, 'account.html', {'edit_mode': edit_mode})




from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Product, ProductColor

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Product, ProductColor
from django.db.models import Q

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)

    colors = ProductColor.objects.filter(product=product).exclude(slug__isnull=True).exclude(slug__exact='')
    primary_color = colors.filter(is_primary=True).first() or colors.first()
    sizes = sorted(filter(None, map(str.strip, product.sizes.split(',')))) if product.sizes else []

    # ✅ Get related products with shared categories
    related_products = Product.objects.filter(
        categories__in=product.categories.all()
    ).exclude(id=product.id).distinct()[:4]

    context = {
        'product': product,
        'colors': colors,
        'primary_color': primary_color,
        'sizes': sizes,
        'primary_image': product.primary_image.url if product.primary_image else '',
        'color_images': primary_color.images.all() if primary_color else [],
        'related_products': related_products,
    }
    return render(request, 'product_detail.html', context)

# -----------------------------
# Product Page by Specific Color URL
# e.g., /product/shirt/black/
# -----------------------------
def product_detail_by_color(request, product_slug, color_slug):
    product = get_object_or_404(Product, slug=product_slug)
    color = get_object_or_404(ProductColor, product=product, slug=color_slug)

    # Apply the same exclusion for slug filtering
    colors = ProductColor.objects.filter(product=product).exclude(slug__isnull=True).exclude(slug__exact='')

    sizes = sorted(filter(None, map(str.strip, product.sizes.split(',')))) if product.sizes else []

    context = {
        'product': product,
        'colors': colors,
        'primary_color': color,
        'sizes': sizes,
        'primary_image': product.primary_image.url if product.primary_image else '',
        'color_images': color.images.all(),
    }
    return render(request, 'product_detail.html', context)


# -----------------------------
# AJAX Endpoint to Get Images of a Color
# -----------------------------
def get_color_images(request, color_id):
    try:
        color = ProductColor.objects.get(id=color_id)
        primary = color.product.primary_image.url if color.product.primary_image else ''
        images = [img.image.url for img in color.images.all()]
        return JsonResponse({'primary': primary, 'images': images})
    except ProductColor.DoesNotExist:
        return JsonResponse({'error': 'Color not found'}, status=404)


from django.shortcuts import render, get_object_or_404
from .models import Category, Product  # Adjust `Product` to your actual model

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(categories=category)
    return render(request, 'category_detail.html', {
        'category': category,
        'products': products,
    })


from django.shortcuts import render, get_object_or_404
from .models import Product, Category

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)

    # Fetch products in this category
    products = Product.objects.filter(categories=category).distinct()

    # Static or pre-defined filter options
    sizes = ["XS", "S", "M", "L", "XL", "XXL", "26", "28", "30", "32", "34", "36", "38", "40", "42"]
    colors = ["Black", "White", "Grey", "Beige", "Blue", "Green", "Red", "Yellow", "Brown", "Orange"]
    sleeves = ["Full Sleeve", "Half Sleeve", "Sleeveless"]

    # Load all categories for the category bar & filter panel
    all_categories = Category.objects.all()

    return render(request, 'category_detail.html', {
        'category': category,
        'products': products,
        'categories': all_categories,
        'sizes': sizes,
        'colors': colors,
        'sleeves': sleeves,
    })




from django.shortcuts import render
from django.db.models import Q
from .models import Product, Category
import re

# Define trending/popular suggestions
POPULAR_SEARCH_TERMS = [
    "Tshirt", "White", "Oversized", "Dresses",
    "Cotton", "Black",  "Formal", "Jeans"
]


def search_view(request):
    popular_categories = Category.objects.all().order_by('?')[:6]
    popular_products = Product.objects.all().order_by('-rating', '-reviews_count')[:8]

    context = {
        'popular_searches': POPULAR_SEARCH_TERMS,
        'popular_categories': popular_categories,
        'popular_products': popular_products,
    }
    return render(request, "search.html", context)


def parse_price_filter(query: str):
    """
    Parses natural language price filters from the query
    Returns (min_price, max_price) tuple or None
    """
    query = query.lower()

    # Match "under 2000"
    match = re.search(r'under\s+(\d+)', query)
    if match:
        return (None, int(match.group(1)))

    # Match "above 1500"
    match = re.search(r'above\s+(\d+)', query)
    if match:
        return (int(match.group(1)), None)

    # Match "between 1000 and 3000"
    match = re.search(r'between\s+(\d+)\s+and\s+(\d+)', query)
    if match:
        return (int(match.group(1)), int(match.group(2)))

    return None
from django.shortcuts import render
from django.db.models import Q
from .models import Product, Category
import re

# Parse price filter from query string
def parse_price_filter(query: str):
    query = query.lower()
    match = re.search(r'under\s+(\d+)', query)
    if match:
        return (None, int(match.group(1)))
    match = re.search(r'above\s+(\d+)', query)
    if match:
        return (int(match.group(1)), None)
    match = re.search(r'between\s+(\d+)\s+and\s+(\d+)', query)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return None, None

def search_results_view(request):
    query = request.GET.get('q', '').strip()
    query_lower = query.lower()
    matched_categories = []

    # Filters
    selected_sizes = request.GET.getlist('size')
    selected_colors = request.GET.getlist('color')
    selected_sleeves = request.GET.getlist('sleeves')
    selected_categories = request.GET.getlist('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort')

    # Static filter options
    sizes = ["XS", "S", "M", "L", "XL", "XXL", "26", "28", "30", "32", "34", "36", "38", "40", "42"]
    colors = ["Black", "White", "Grey", "Beige", "Blue", "Green", "Red", "Yellow", "Brown", "Orange"]
    sleeves = ["Full Sleeve", "Half Sleeve", "Sleeveless"]
    all_categories = Category.objects.all()

    products = Product.objects.all()

    # Search filtering
    if query:
        min_price_query, max_price_query = parse_price_filter(query)
        if min_price_query is not None:
            min_price = min_price_query
        if max_price_query is not None:
            max_price = max_price_query

        base_filter = (
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(html_description__icontains=query)
        )

        matched_categories = Category.objects.filter(name__icontains=query)
        if matched_categories.exists():
            base_filter |= Q(categories__in=matched_categories)

        products = products.filter(base_filter).distinct()

    # Apply filters
    if selected_sizes:
        products = products.filter(
            Q(sizes__iregex=r'\b(' + '|'.join(selected_sizes) + r')\b')
        )

    if selected_colors:
        products = products.filter(colors__name__in=selected_colors)

    if selected_sleeves:
        products = products.filter(description__icontains=selected_sleeves[0])  # You can improve this

    if selected_categories:
        products = products.filter(categories__name__in=selected_categories)

    if min_price:
        products = products.filter(Q(price__gte=min_price) | Q(discount_price__gte=min_price))

    if max_price:
        products = products.filter(Q(price__lte=max_price) | Q(discount_price__lte=max_price))

    # Sorting
    if sort_by == "low":
        products = products.order_by('discount_price', 'price')
    elif sort_by == "high":
        products = products.order_by('-discount_price', '-price')
    elif sort_by == "new":
        products = products.order_by('-id')
    else:
        products = products.order_by('-id')

    return render(request, 'search_results.html', {
        'query': query,
        'products': products.distinct(),
        'result_count': products.count(),
        'matched_categories': matched_categories,
        'categories': all_categories,
        'sizes': sizes,
        'colors': colors,
        'sleeves': sleeves,
        'filters': {
            'sizes': selected_sizes,
            'colors': selected_colors,
            'sleeves': selected_sleeves,
            'categories': selected_categories,
            'min_price': min_price,
            'max_price': max_price,
            'sort_by': sort_by,
        }
    })




from django.http import JsonResponse
from .models import Product

def search_suggestions(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(name__icontains=query)[:3]

    data = {
        "products": [
            {
                "name": p.name,
                "slug": p.slug,
                "image": p.primary_image.url,
                "price_display": f"₹{p.discount_price} (₹{p.price})" if p.discount_price else f"₹{p.price}"
            }
            for p in products
        ]
    }
    return JsonResponse(data)


# views.py

import os
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.conf import settings
from twilio.rest import Client
from .models import OTP
import random
User = get_user_model()

client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))

TWILIO_TEMPLATE_SID = "HXcd8a4c539a039e2e6ea4d77b056d609f"  # Your approved template SID

def login_view(request):
    context = {
        'show_otp': request.session.get('phone_number') is not None
    }
    return render(request, "login.html", context)

import os
import random
import json
from django.shortcuts import redirect
from django.contrib import messages
from .models import OTP
from twilio.rest import Client

import os
import json
import random
from django.shortcuts import redirect
from django.contrib import messages
from .models import OTP
from twilio.rest import Client

# Twilio setup
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def send_otp(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number")
        if not phone:
            messages.error(request, "Phone number is required.")
            return redirect("login")

        code = str(random.randint(100000, 999999))

        # Save OTP in DB
        OTP.objects.create(phone_number=phone, code=code)

        # Save phone in session
        request.session['phone_number'] = phone

        try:
            client.messages.create(
                to=f"whatsapp:+91{phone}",
                from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                content_sid="HXcd8a4c539a039e2e6ea4d77b056d609f",  # ✅ Approved template SID
                content_variables=json.dumps({"1": code})  # ✅ JSON string for template
            )
            messages.success(request, "OTP sent successfully!")
        except Exception as e:
            messages.error(request, "Failed to send OTP. Please try again.")
            print("Twilio error:", e)

    return redirect("login")

def verify_otp(request):
    if request.method == "POST":
        phone = request.session.get('phone_number')
        otp_input = request.POST.get("otp")

        if not phone or not otp_input:
            messages.error(request, "Missing phone number or OTP.")
            return redirect("login")

        # Get latest OTP for phone
        otp_obj = OTP.objects.filter(phone_number=phone).order_by('-created_at').first()

        if not otp_obj or otp_obj.is_expired() or otp_obj.code != otp_input:
            messages.error(request, "Invalid or expired OTP.")
            return redirect("login")

        # OTP valid - login user
        user, created = User.objects.get_or_create(phone_number=phone)
        login(request, user)

        # Clean up session and redirect
        del request.session['phone_number']
        messages.success(request, "Login successful!")
        return redirect("home")  # Change to your homepage

    return redirect("login")


def change_number(request):
    request.session.pop('phone_number', None)
    return redirect('login')


from django.contrib.auth import logout

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")
