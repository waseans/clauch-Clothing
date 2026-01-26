from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

from django.shortcuts import render
from .models import Category

from django.shortcuts import render
from .models import Category, Product  # or your item model

import json
import os
import firebase_admin # type: ignore
from firebase_admin import credentials, auth as firebase_auth # type: ignore
from firebase_admin.auth import InvalidIdTokenError # type: ignore




from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

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




from django.shortcuts import render


def faq_view(request):
    return render(request, "faq.html")

def shipping_return_view(request):
    return render(request, "shipping_return.html")

def return_view(request):
    return render(request, "return.html")

def contact_view(request):
    return render(request, "contact.html")

def privacy_policy_view(request):
    return render(request, "privacy_policy.html")

def terms_and_condition_view(request):
    return render(request, "terms_and_condition.html")


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

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Product, ProductColor, Category  # ✅ Added Category
from django.db.models import Q

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)

    colors = ProductColor.objects.filter(product=product).exclude(slug__isnull=True).exclude(slug__exact='')
    primary_color = colors.filter(is_primary=True).first() or colors.first()
    sizes = sorted(filter(None, map(str.strip, product.sizes.split(',')))) if product.sizes else []

    # ✅ Get all categories for the sidebar/menu
    all_categories = Category.objects.all()

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
        'all_categories': all_categories, # ✅ Pass to template
    }
    return render(request, 'product_detail.html', context)

def product_detail_by_color(request, product_slug, color_slug):
    product = get_object_or_404(Product, slug=product_slug)
    color = get_object_or_404(ProductColor, product=product, slug=color_slug)
    
    colors = ProductColor.objects.filter(product=product).exclude(slug__isnull=True).exclude(slug__exact='')
    sizes = sorted(filter(None, map(str.strip, product.sizes.split(',')))) if product.sizes else []
    
    # ✅ Get all categories here as well
    all_categories = Category.objects.all()

    context = {
        'product': product,
        'colors': colors,
        'primary_color': color,
        'sizes': sizes,
        'primary_image': product.primary_image.url if product.primary_image else '',
        'color_images': color.images.all(),
        'all_categories': all_categories, # ✅ Pass to template
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


import os
import json

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

# This correctly gets your CustomUser model
User = get_user_model()

# --- Initialize Firebase Admin ---
cred_path = os.path.join(settings.BASE_DIR, "user/serviceAccountKey.json")

if not firebase_admin._apps:
    try:
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            print(f"CRITICAL: Service account file not found at {cred_path}")
    except Exception as e:
        print(f"Firebase Init Error: {e}")

def login_view(request):
    """Renders the Clauch Partner Login page."""
    return render(request, "login.html")

@csrf_exempt
@require_POST
def verify_otp_firebase(request):
    """
    Verifies the Firebase ID Token and logs the user into the B2B site.
    """
    try:
        data = json.loads(request.body)
        id_token = data.get("token")
        
        if not id_token:
            return JsonResponse({"status": "error", "message": "Token missing."}, status=400)

        # 1. Verify the token with Google/Firebase
        decoded_token = firebase_auth.verify_id_token(id_token)
        phone_number = decoded_token.get("phone_number") 
        
        if not phone_number:
            return JsonResponse({"status": "error", "message": "Phone number missing in Firebase token."}, status=400)

        # 2. Get or Create User (FIXED: Used Uppercase 'User')
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={'is_active': True}
        )
        
        # 3. Log the user into Django session
        login(request, user)
        
        return JsonResponse({"status": "success", "redirect": "/"}, status=200)

    except InvalidIdTokenError:
        return JsonResponse({"status": "error", "message": "Invalid or expired token."}, status=401)
    except Exception as e:
        # Logging the error to terminal for you to see
        print(f"Verification Error: {e}")
        return JsonResponse({"status": "error", "message": f"Server error: {str(e)}"}, status=500)

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
import razorpay

from .models import Course, CourseEnrollment

# Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def course_list(request):
    courses = Course.objects.all()
    user_enrollments = []
    if request.user.is_authenticated:
        user_enrollments = CourseEnrollment.objects.filter(user=request.user, status="active").values_list("course_id", flat=True)
    return render(request, "course.html", {"courses": courses, "user_enrollments": user_enrollments})


@login_required
def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug)
    enrolled = CourseEnrollment.objects.filter(user=request.user, course=course, status="active").exists()
    if not enrolled:
        return redirect("course_list")
    return render(request, "course_detail.html", {"course": course})


@login_required
def create_order(request, slug):
    course = get_object_or_404(Course, slug=slug)
    amount = int(course.get_display_price() * 100)  # in paise

    # Create Razorpay order
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": "1"
    })

    return JsonResponse({
        "order_id": order["id"],
        "amount": amount,
        "currency": "INR",
        "course_slug": slug
    })


@login_required
def payment_success(request, slug):
    course = get_object_or_404(Course, slug=slug)
    CourseEnrollment.objects.update_or_create(
        user=request.user,
        course=course,
        defaults={"status": "active", "price_paid": course.get_display_price()},
    )
    return redirect("course_detail", slug=slug)



# views.py
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CourseVideo, CourseEnrollment

@login_required
def protected_video(request, video_id):
    video = get_object_or_404(CourseVideo, id=video_id)
    enrolled = CourseEnrollment.objects.filter(user=request.user, course=video.course, status="active").exists()
    if not enrolled:
        raise Http404("Video not found or you are not enrolled.")
    
    return FileResponse(video.video_file.open(), content_type="video/mp4")
