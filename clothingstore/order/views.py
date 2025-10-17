# your_app/views.py (or whichever app your views are in, likely 'order' or 'cart')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse # For AJAX response in add_to_cart_view
from django.views.decorators.http import require_POST

# Import your models correctly
from .models import CartItem, Order, OrderItem, Coupon
from user.models import CustomUser, Product, ProductColor # Ensure CustomUser, Product, ProductColor are imported

# --- Helper Function for Adding to Cart ---
# This helper is crucial and should reflect adding 'quantity_of_packs' of the product
# your_app/views.py (or whichever app your views are in, likely 'order' or 'cart')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse # For AJAX response in add_to_cart_view
from django.views.decorators.http import require_POST
from decimal import Decimal # Import Decimal for accurate currency calculations

# Import your models correctly
from .models import CartItem, Order, OrderItem, Coupon
from user.models import CustomUser, Product, ProductColor # Ensure CustomUser, Product, ProductColor are imported

# --- Helper Function for Adding to Cart ---
# This helper is crucial and should reflect adding 'quantity_of_packs' of the product
def add_product_pack_to_cart(request, product_id, color_id, quantity_of_packs):
    user = request.user
    product = get_object_or_404(Product, id=product_id)
    color = get_object_or_404(ProductColor, id=color_id) if color_id else None

    # Retrieve snapshot data from the Product and Color
    product_name = product.name
    product_image = product.primary_image.url if product.primary_image else ''
    actual_price = product.price
    discount_price = product.discount_price

    cart_item, created = CartItem.objects.get_or_create(
        user=user,
        product=product,
        color=color, # The color is still relevant for the pack
        defaults={
            'quantity': quantity_of_packs, # This is the quantity of the entire pack
            'product_name': product_name,
            'product_image': product_image,
            'actual_price': actual_price,
            'discount_price': discount_price
        }
    )
    if not created:
        # If item already exists (same product, same color), update its quantity of packs
        cart_item.quantity += quantity_of_packs
        cart_item.save()

    return cart_item

# --- End Helper Function ---


@login_required(login_url='login')
@require_POST # Ensure it only accepts POST requests
def add_to_cart_view(request):
    product_id = request.POST.get('product_id')
    color_id = request.POST.get('color_id')
    # This is the quantity of PACKS/SETS
    set_quantity_str = request.POST.get('set_quantity') 

    # Basic validation for product and color
    if not product_id or not color_id:
        return JsonResponse({'status': 'error', 'message': 'Product or color not selected.'}, status=400)

    # Validate set_quantity (quantity of packs)
    try:
        set_quantity = int(set_quantity_str)
        # --- REMOVED MINIMUM 10 CONSTRAINT ---
        if set_quantity < 1: # Changed from < 0 to < 1, and removed the "10" message
            return JsonResponse({'status': 'error', 'message': 'Quantity of sets must be at least 1.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid quantity provided for sets.'}, status=400)

    try:
        # Use the helper function that adds packs
        add_product_pack_to_cart(request, product_id, color_id, set_quantity)
        
        # Success response for AJAX call
        return JsonResponse({
            'status': 'success',
            'message': f'{set_quantity} sets added to bag!', # Changed "packs" to "sets"
            'cart_url': redirect('view_cart').url # Get the URL for the cart view
        })
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)
    except ProductColor.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Color not found.'}, status=404)
    except Exception as e:
        print(f"Error adding to cart: {e}") # For debugging
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)


@login_required(login_url='login')
def view_cart(request):
    cart_items_for_display = []
    total_cart_amount = Decimal('0.00') # Use Decimal for currency calculations

    if request.user.is_authenticated:
        # Each CartItem now represents a quantity of *packs*
        user_cart_items = CartItem.objects.filter(user=request.user).select_related('product', 'color')
        
        for item in user_cart_items:
            # The price is for ONE pack. Subtotal is price per pack * quantity of packs.
            price_per_pack = item.discount_price or item.actual_price
            subtotal = price_per_pack * item.quantity
            total_cart_amount += subtotal
            cart_items_for_display.append({
                'item': item,
                'subtotal': subtotal
            })
    else:
        messages.info(request, "Please log in to view and manage your cart. Session carts are not fully supported for packs without login.")
        return redirect('login') # Or render an empty cart
        
    return render(request, 'order/cart.html', {
        'cart_items': cart_items_for_display,
        'total': total_cart_amount
    })


@login_required(login_url='login')
def remove_from_cart(request, item_id):
    # This now removes a CartItem record, which represents a product pack
    CartItem.objects.filter(id=item_id, user=request.user).delete()
    messages.success(request, "Set removed from cart.") # Changed "Pack" to "Set"
    return redirect('view_cart')

@login_required(login_url='login')
@require_POST
def update_cart_quantity(request):
    item_id = request.POST.get('item_id')
    action = request.POST.get('action')
    
    item = get_object_or_404(CartItem, id=item_id, user=request.user)

    # --- REMOVED MINIMUM 10 CONSTRAINT ---
    min_qty_sets = 1 # Minimum quantity of sets is 1
    
    if action == 'increase':
        item.quantity += 1
    elif action == 'decrease':
        if item.quantity > min_qty_sets: # Check against new minimum (1)
            item.quantity -= 1
        else:
            messages.warning(request, f"Minimum quantity for this set is {min_qty_sets}.") # Changed "pack" to "set"
            return redirect('view_cart')

    item.save()
    messages.success(request, "Cart quantity updated.")
    return redirect('view_cart')

# --- Checkout View ---
from decimal import Decimal
import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import CartItem, Coupon, Order, OrderItem # Assuming these are your models

import razorpay
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem, Order, OrderItem, Coupon
from .shiport_utils import get_cheapest_shipping_rate, create_shiport_shipment
# order/views.py

import razorpay
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem, Order, OrderItem, Coupon
# We no longer need to import the shiport utils here
# from .shiport_utils import get_cheapest_shipping_rate, create_shiport_shipment 
# order/views.py

import razorpay
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem, Order, OrderItem, Coupon
# Re-import the get_cheapest_shipping_rate function
from .shiport_utils import get_cheapest_shipping_rate, create_shiport_shipment 

# In order/views.py
# In order/views.py

# --- Cleaned up Imports ---
import razorpay
import json
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem, Order, OrderItem
from .shiport_utils import get_cheapest_shipping_rate as get_shiport_rate
from .ithink_services import get_rate_for_checkout as get_ithink_rate_for_checkout


# This view is already correct and does not need changes
@login_required(login_url='login')
@require_POST
def ajax_calculate_shipping(request):
    # ... (code is correct as is)
    data = json.loads(request.body)
    pincode = data.get('pincode')
    payment_method = data.get('payment_method', 'RZP') 
    
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        return JsonResponse({'error': 'Please enter a valid 6-digit pincode.'}, status=400)

    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        return JsonResponse({'error': 'Your cart is empty.'}, status=400)

    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    shipping_service = None

    if payment_method == "RZP":
        rep_item = cart_items.first()
        if not (rep_item and rep_item.product):
            return JsonResponse({'error': 'Cart contains an invalid item.'}, status=400)
        shipping_service = get_shiport_rate(
            to_pincode=pincode, total_weight=rep_item.product.weight, length=rep_item.product.length,
            width=rep_item.product.width, height=rep_item.product.height, payment_mode="prepaid"
        )
    elif payment_method == "COD":
        ithink_result = get_ithink_rate_for_checkout(
            pincode=pincode, subtotal=subtotal, cart_items=cart_items
        )
        if ithink_result.get('status') == 'success':
            shipping_service = ithink_result 
        else:
            return JsonResponse({'error': ithink_result.get('message', 'Could not calculate COD shipping.')}, status=400)

    if not shipping_service:
        return JsonResponse({'error': 'Sorry, we do not ship to this pincode.'}, status=400)

    shipping_charge = Decimal(shipping_service['total_charges'])
    request.session['shipping_info'] = {
        'charge': str(shipping_charge),
        'service': shipping_service
    }
    grand_total = subtotal + shipping_charge

    return JsonResponse({
        'shipping_charge': f"{shipping_charge:.2f}",
        'grand_total': f"{grand_total:.2f}",
    })


# --- UPDATED checkout_view ---
@login_required(login_url='login')
def checkout_view(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user).select_related('product', 'color')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('view_cart')

    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    subtotal = Decimal(str(subtotal))

    if request.method == 'POST':
        data = request.POST
        
        # --- THIS BLOCK IS FOR AFTER PAYMENT IS COMPLETED ---
        if data.get("razorpay_payment_id"):
            order_id = request.session.get('order_id')
            if not order_id:
                messages.error(request, "Your session expired. Please try again.")
                return redirect('checkout')

            order = get_object_or_404(Order, id=order_id, user=user)
            order.payment_id = data.get("razorpay_payment_id")

            # ✅ UPDATED: Conditional status logic
            if order.payment_method == 'RZP':
                order.payment_status = 'PAID'
            elif order.payment_method == 'COD':
                order.payment_status = 'SHIPPING_FEE_PAID'
            
            order.shipping_status = 'READY_TO_SHIP'
            order.save()

            cart_items.delete()
            
            if 'order_id' in request.session: del request.session['order_id']
            if 'shipping_info' in request.session: del request.session['shipping_info']
            
            return redirect('order_success', order_id=order.id)

        # --- THIS BLOCK IS FOR CREATING THE ORDER BEFORE PAYMENT ---
        shipping_info = request.session.get('shipping_info')
        if not shipping_info:
            messages.error(request, "Please calculate shipping before proceeding to pay.")
            return redirect('checkout')

        shipping_charge = Decimal(shipping_info['charge'])
        shipping_service = shipping_info['service']
        
        grand_total = subtotal + shipping_charge
        payment_method = data.get('payment_method', 'RZP')
        amount_to_pay_now = grand_total if payment_method == "RZP" else shipping_charge
        razorpay_amount = int(amount_to_pay_now * 100)

        order = Order.objects.create(
            user=user, full_name=data['full_name'], phone=data['phone'], email=data.get('email', ''),
            address=data['address'], city=data['city'], state=data['state'], pincode=data['pincode'],
            payment_method=payment_method, 
            subtotal=subtotal, 
            shipping_charge=shipping_charge, 
            grand_total=grand_total,
            shipping_service_name=shipping_service['service_name'],
            # ✅ UPDATED: Set correct initial statuses
            payment_status='UNPAID',
            shipping_status='PENDING',
        )
        for item in cart_items:
            order.items.create(
                 product=item.product, color=item.color, quantity=item.quantity,
                 product_name=item.product.name, product_image=item.product.primary_image,
                 actual_price=item.actual_price, discount_price=item.discount_price,
                 price_per_piece_at_purchase=item.product.get_current_price_per_piece(),
                 total_pieces_in_set_at_purchase=item.product.get_total_pieces_in_set()
            )
        
        request.session['order_id'] = order.id

        try:
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = razorpay_client.order.create({
                "amount": razorpay_amount, "currency": "INR", "payment_capture": 1, "notes": {"order_id": order.id}
            })
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            
            processed_cart_items = []
            for item in cart_items:
                price = item.discount_price or item.actual_price
                processed_cart_items.append({
                    'product': item.product,
                    'color': item.color,
                    'quantity': item.quantity,
                    'total_price': price * item.quantity
                })

            context = {
                "cart_items": processed_cart_items, "subtotal": subtotal, "shipping_charge": shipping_charge,
                "grand_total": grand_total, "razorpay_order": razorpay_order,
                "razorpay_key": settings.RAZORPAY_KEY_ID, "amount_to_pay_now": razorpay_amount,
                "order": order, "form_data": data,
            }
            return render(request, 'order/checkout.html', context)
        except Exception as e:
            messages.error(request, f"Could not create payment order: {e}")
            # ✅ UPDATED: Set correct failure statuses
            order.payment_status = 'FAILED'
            order.shipping_status = 'CANCELLED'
            order.save()
            return redirect('checkout')

    # --- GET Request logic (no changes needed) ---
    processed_cart_items = []
    for item in cart_items:
        price = item.discount_price or item.actual_price
        processed_cart_items.append({
            'product': item.product,
            'color': item.color,
            'quantity': item.quantity,
            'total_price': price * item.quantity
        })

    context = { 
        "cart_items": processed_cart_items,
        "subtotal": subtotal,
        "shipping_charge": Decimal("0.00"), 
        "grand_total": subtotal,
        "razorpay_key": settings.RAZORPAY_KEY_ID, 
        "user_profile": user 
    }
    return render(request, 'order/checkout.html', context)

# --- Other views (keep as is, but ensure consistency with no 'size' field) ---
from django.shortcuts import render, get_object_or_404
from .models import Order

@login_required(login_url='login')
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order/success.html', {'order': order})

def order_failure_view(request):
    return render(request, 'order/failure.html')


import hmac
import hashlib
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from .models import Order
from django.conf import settings
import json

@csrf_exempt
def razorpay_webhook(request):
    if request.method == "POST":
        payload = request.body
        received_signature = request.headers.get('X-Razorpay-Signature')

        generated_signature = hmac.new(
            key=bytes(settings.RAZORPAY_WEBHOOK_SECRET, 'utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(received_signature, generated_signature):
            data = json.loads(payload)

            # Ensure event structure is as expected, typically 'payment.captured'
            event_type = data.get('event')
            if event_type == 'payment.captured':
                payment_entity = data.get('payload', {}).get('payment', {}).get('entity', {})
                payment_id = payment_entity.get('id')
                order_id_from_razorpay = payment_entity.get('order_id') # Get Razorpay order_id

                # Find the order by Razorpay order_id if you store it in your 'payment_id' field for linking
                order = Order.objects.filter(payment_id=order_id_from_razorpay).first() 

                if order:
                    order.status = 'PAID'
                    order.payment_id = payment_id # Update with the actual Razorpay payment ID
                    order.save()
                    return HttpResponse(status=200)
                else:
                    # Log if order not found for debugging
                    print(f"Webhook: Order not found for Razorpay order_id: {order_id_from_razorpay}")
                    return HttpResponse(status=404) # Not Found
            elif event_type == 'order.paid':
                # Handle cases where Razorpay webhook sends 'order.paid' event (sometimes before payment.captured)
                order_entity = data.get('payload', {}).get('order', {}).get('entity', {})
                order_id_from_razorpay = order_entity.get('id')
                order = Order.objects.filter(payment_id=order_id_from_razorpay).first()
                if order:
                    order.status = 'PAID'
                    order.save()
                    return HttpResponse(status=200)
                else:
                    print(f"Webhook: Order not found for Razorpay order.paid event order_id: {order_id_from_razorpay}")
                    return HttpResponse(status=404)
            else:
                # Handle other events if necessary, or log them
                print(f"Webhook: Unhandled event type: {event_type}")
                return HttpResponse(status=200) # Acknowledge receipt even for unhandled events
        else:
            return HttpResponse("Invalid signature", status=403)

    return HttpResponse("Only POST allowed", status=405)


@login_required
def my_orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at').prefetch_related('items')
    # In template, when looping through order.items, remember 'item.size' is no longer available.
    # The 'product.sizes' field should be used to describe the pack composition.
    return render(request, 'my_orders.html', {'orders': orders})

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    # In template, when looping through order.items, remember 'item.size' is no longer available.
    # The 'product.sizes' field should be used to describe the pack composition.
    return render(request, 'order_detail.html', {'order': order})


@login_required
def update_profile(request):
    if request.method == "POST":
        user = request.user 

        user.full_name = request.POST.get("full_name", user.full_name)
        user.email = request.POST.get("email", user.email)

        user.company_name = request.POST.get("company_name", user.company_name)
        user.gst_number = request.POST.get("gst_number", user.gst_number) 

        user.address = request.POST.get("address", user.address)
        user.city = request.POST.get("city", user.city)
        user.state = request.POST.get("state", user.state)
        user.zip_code = request.POST.get("zip_code", user.zip_code)
        user.country = request.POST.get("country", user.country)

        try:
            user.save()
            messages.success(request, "Your company profile was updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")

    return redirect("account")




# ... (at the top of the file, with other imports)
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q

# ... (all your existing views like checkout_view, etc.)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Q
from .models import Order
from .shiport_shipment_task import process_shipment_for_order
from . import ithink_services

# ---------------------------------------------------------------------
# PREPAID (Shiport) SHIPMENT DASHBOARD
# ---------------------------------------------------------------------

@staff_member_required
def admin_shipment_dashboard(request, status_filter='pending'):
    """Dashboard for PREPAID (Shiport) orders."""
    # Base queryset filters for Prepaid (RZP) orders only
    base_query = Order.objects.filter(payment_method='RZP')

    # ✅ UPDATED: Use the new shipping_status field
    base_query = base_query.exclude(
        shipping_status__in=['PENDING', 'CANCELLED', 'DELIVERED']
    )

    if status_filter == 'pending':
        # A pending shipment is one where payment is 'PAID' and shipping is 'READY_TO_SHIP' or 'SHIPMENT_FAILED'
        orders_to_display = base_query.filter(
            payment_status='PAID',
            shipping_status__in=['READY_TO_SHIP', 'SHIPMENT_FAILED']
        )
        active_tab = 'pending'
    elif status_filter == 'shipped':
        # ✅ UPDATED: Use the new shipping_status field
        orders_to_display = base_query.filter(shipping_status='SHIPPED')
        active_tab = 'shipped'
    else: # 'all'
        orders_to_display = base_query
        active_tab = 'all'

    orders_to_display = orders_to_display.prefetch_related('items__product').order_by('-created_at')

    processed_orders = []
    for order in orders_to_display:
        total_weight = sum([item.product.weight * item.quantity for item in order.items.all() if item.product])
        processed_orders.append({
            'order': order,
            'total_weight': total_weight,
        })

    context = {
        'orders': processed_orders,
        'active_tab': active_tab,
    }
    return render(request, 'order/admin_shipments.html', context)


@staff_member_required
def create_shipment_for_order(request, order_id):
    """Triggers the shipment creation task for a PREPAID order."""
    # This view delegates the work, so it doesn't need changes.
    # We assume 'process_shipment_for_order' is also updated to use the new statuses.
    success, message = process_shipment_for_order(order_id)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('admin_shipment_dashboard_default')


# ---------------------------------------------------------------------
# COD (iThink) SHIPMENT DASHBOARD
# ---------------------------------------------------------------------
# In your views.py

@staff_member_required
def admin_ithink_dashboard(request, status_filter='pending'):
    """Dashboard for COD (iThink) orders."""
    # Base queryset filters for COD orders only
    base_query = Order.objects.filter(payment_method='COD')
    
    base_query = base_query.exclude(
        shipping_status__in=['CANCELLED', 'DELIVERED']
    )

    if status_filter == 'pending':
        orders_to_display = base_query.filter(
            payment_status='SHIPPING_FEE_PAID',
            shipping_status__in=['READY_TO_SHIP', 'SHIPMENT_FAILED']
        )
        active_tab = 'pending'
    elif status_filter == 'shipped':
        orders_to_display = base_query.filter(shipping_status='SHIPPED')
        active_tab = 'shipped'
    else: # 'all'
        orders_to_display = base_query
        active_tab = 'all'

    # Use prefetch_related for better performance
    orders_to_display = orders_to_display.prefetch_related('items__product').order_by('-created_at')

    processed_orders = []
    for order in orders_to_display:
        # ✅ UPDATED: Use the same weight calculation as the API call for consistency
        representative_item = order.items.first()
        display_weight = 0
        if representative_item and representative_item.product:
            display_weight = representative_item.product.weight
            
        processed_orders.append({
            'order': order,
            'total_weight': display_weight, # Use the consistent weight
        })

    context = {
        'orders': processed_orders,
        'active_tab': active_tab,
    }
    return render(request, 'order/admin_ithink.html', context)

@staff_member_required
def create_ithink_shipment(request, order_id):
    """Handles the 'Create Shipment' button click for a COD order."""
    order = get_object_or_404(Order, id=order_id, payment_method='COD')

    rate_response = ithink_services.get_cheapest_rate(order)

    if rate_response['status'] == 'error':
        # ✅ UPDATED: Set shipping_status on failure
        order.shipping_status = 'SHIPMENT_FAILED'
        order.save()
        messages.error(request, f"Order #{order.id} Failed: Could not get shipping rates. Reason: {rate_response['message']}")
        return redirect('admin_ithink_dashboard_default')

    cheapest_courier = rate_response['courier_name']
    shipping_rate = Decimal(rate_response['rate'])

    shipment_response = ithink_services.create_ithink_order(order, cheapest_courier)

    if shipment_response['status'] == 'error':
        # ✅ UPDATED: Set shipping_status on failure
        order.shipping_status = 'SHIPMENT_FAILED'
        order.save()
        messages.error(request, f"Order #{order.id} Failed: Could not create shipment. Reason: {shipment_response['message']}")
        return redirect('admin_ithink_dashboard_default')

    # ✅ UPDATED: Set shipping_status on success
    order.tracking_id = shipment_response['waybill']
    order.shipping_service_name = shipment_response['courier']
    order.shipping_charge = shipping_rate
    order.shipping_status = 'SHIPPED'
    order.save()

    messages.success(request, f"Successfully created shipment for Order #{order.id}! AWB: {order.tracking_id}")
    return redirect('admin_ithink_dashboard_default')


from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa  # You'd need to 'pip install xhtml2pdf'
from .models import Order

def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # You would create a new, simpler template just for the PDF
    template_path = 'invoice_template.html' 
    context = {'order': order}

    # Create a Django response object, and set the PDF content type
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_#{order.id}.pdf"'

    # Find the template and render it
    template = get_template(template_path)
    html = template.render(context)

    # Create a PDF
    pisa_status = pisa.CreatePDF(
       html,                # the HTML to convert
       dest=response        # file-like object to receive result
    )

    # If error, return an error
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response