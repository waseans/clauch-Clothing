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
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CartItem, Order, OrderItem, Coupon
from .shiport_utils import get_cheapest_shipping_rate, create_shiport_shipment # Import the new functions

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required(login_url='login')
def checkout_view(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user).select_related('product', 'color')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('view_cart')

    # --- Calculate Subtotal and Cart Details (Same as before) ---
    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    subtotal = Decimal(str(subtotal))

    # --- Initial State for Shipping and Payment ---
    shipping_charge = Decimal("0.00")
    shipping_service = None
    amount_to_pay_now = subtotal # Start with subtotal
    
    # --- POST Request: Main Logic for Placing Order ---
    if request.method == 'POST':
        data = request.POST
        required_fields = ['full_name', 'phone', 'address', 'city', 'state', 'pincode', 'payment_method']
        if not all(data.get(field) for field in required_fields):
            messages.error(request, "Please fill all required address fields.")
            return redirect('checkout_view')

        # 1. Calculate Total Weight and Dimensions for Shipping API
        total_weight = sum([item.product.weight * item.quantity for item in cart_items])
        # Note: A simple heuristic for dimensions. For a real app, consider a packing algorithm.
        max_length = max([item.product.length for item in cart_items] or [0])
        max_width = max([item.product.width for item in cart_items] or [0])
        total_height = sum([item.product.height * item.quantity for item in cart_items])

        # 2. Get Shipping Rate from Shiport
        payment_method = data['payment_method']
        shiport_payment_mode = "prepaid" if payment_method == "RZP" else "cod"
        shipping_service = get_cheapest_shipping_rate(
            to_pincode=data['pincode'],
            total_weight=total_weight,
            length=max_length,
            width=max_width,
            height=total_height,
            payment_mode=shiport_payment_mode
        )

        if not shipping_service:
            messages.error(request, "Could not find a shipping service for your pincode. Please try again.")
            return redirect('checkout_view')
        
        shipping_charge = Decimal(shipping_service['total_charges'])

        # 3. Handle Coupon
        coupon_code = data.get("coupon_code", "")
        discount = Decimal("0.00")
        if coupon_code:
            # (Coupon logic remains the same, applied to subtotal)
            try:
                coupon = Coupon.objects.get(code=coupon_code, active=True)
                if subtotal >= coupon.min_order_amount:
                    if coupon.discount_type == 'FLAT': discount = min(coupon.discount_value, subtotal)
                    elif coupon.discount_type == 'PERCENT': discount = (coupon.discount_value / 100) * subtotal
            except Coupon.DoesNotExist: pass

        # 4. Determine Final Amounts and Amount to Pay NOW
        grand_total = subtotal + shipping_charge - discount
        
        if payment_method == "COD":
            # For COD, user pays only shipping fee in advance
            amount_to_pay_now = shipping_charge
        elif payment_method == "RZP":
            # For Prepaid, user pays the full grand total
            amount_to_pay_now = grand_total
        
        razorpay_amount = int(amount_to_pay_now * 100)

        # 5. Create Order in Database (Status: PENDING)
        order = Order.objects.create(
            user=user,
            full_name=data['full_name'], phone=data['phone'], email=data.get('email', ''),
            address=data['address'], city=data['city'], state=data['state'], pincode=data['pincode'],
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_charge=shipping_charge,
            coupon_code=coupon_code or None,
            discount_amount=discount,
            grand_total=grand_total,
            shipping_service_name=shipping_service['service_name'],
            payment_id=data.get("razorpay_payment_id", ""),
            status="PENDING",
        )
        # Create OrderItems
        for item in cart_items:
            OrderItem.objects.create(order=order, product=item.product, color=item.color, quantity=item.quantity,
                                     product_name=item.product.name, product_image=item.product.primary_image,
                                     actual_price=item.actual_price, discount_price=item.discount_price,
                                     price_per_piece_at_purchase=item.product.get_current_price_per_piece(),
                                     total_pieces_in_set_at_purchase=item.product.get_total_pieces_in_set())

        # 6. Check for Razorpay Payment ID and Process Shipment
        if data.get("razorpay_payment_id"):
            order.status = "PAID"
            order.save()

            # Create Shiport shipment AFTER payment is confirmed
            shipment_result = create_shiport_shipment(order, shipping_service)
            if shipment_result and shipment_result.get('data', {}).get('awb_number'):
                order.tracking_id = shipment_result['data']['awb_number']
                order.shipping_label_url = shipment_result['data'].get('label_url')
                order.status = "SHIPPED"
                order.save()
            else:
                # Payment was made but shipment failed. Flag for manual action.
                messages.error(request, "Payment successful, but failed to book shipment. Please contact support.")
            
            cart_items.delete()
            return redirect('order_success', order_id=order.id)
        else:
            # This part is for when the user needs to be sent to Razorpay
            # The order is created, now we generate the Razorpay order to be paid
            try:
                razorpay_order = razorpay_client.order.create({
                    "amount": razorpay_amount,
                    "currency": "INR",
                    "payment_capture": 1,
                    "notes": {"order_id": order.id}
                })
                # We render the page again, but this time with the Razorpay order details
                # The user will now see the Razorpay popup to complete the payment
                context = {
                    "cart_items": cart_items, "subtotal": subtotal, "shipping_charge": shipping_charge,
                    "discount": discount, "grand_total": grand_total, "razorpay_order": razorpay_order,
                    "razorpay_key": settings.RAZORPAY_KEY_ID, "amount_to_pay_now": razorpay_amount,
                    "order": order, # Pass the created order to the template
                }
                return render(request, 'order/checkout.html', context)
            except Exception as e:
                messages.error(request, f"Could not create payment order: {e}")
                order.status = "CANCELLED"
                order.save()
                return redirect('checkout_view')

    # --- GET Request: Display the Initial Checkout Page ---
    context = {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping_charge": shipping_charge, # Initially 0
        "grand_total": subtotal, # Initially same as subtotal
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