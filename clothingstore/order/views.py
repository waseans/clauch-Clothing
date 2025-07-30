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

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)) # Corrected typo here

@login_required(login_url='login')
def checkout_view(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user).select_related('product', 'color')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('view_cart')

    # Prepare cart items with additional product details for the template
    # and calculate subtotal based on these items
    processed_cart_items = []
    total = Decimal("0.00")

    for item in cart_items:
        item_total_price = (item.discount_price or item.actual_price) * item.quantity
        total += item_total_price
        processed_cart_items.append({
            'item_id': item.id, # Keep item_id for potential future use if needed
            'product_name': item.product.name,
            'product_image': item.product.primary_image, # Assuming primary_image field on Product
            'color': item.color,
            'size': item.product.sizes, # Use product.sizes to represent set composition
            'quantity': item.quantity, # Quantity of sets
            'actual_price': item.actual_price, # Price per set
            'discount_price': item.discount_price, # Discounted price per set
            'price_per_piece': item.product.get_current_price_per_piece(), # Get price per piece
            'total_pieces_in_set': item.product.get_total_pieces_in_set(), # Get total pieces in set
            'total_price': item_total_price, # Total price for this line item (sets * price_per_set)
            'product': item.product, # Pass the full product object for other details like slug if needed
        })


    coupon_code = request.POST.get("coupon_code", "")
    discount = Decimal("0.00")

    # Coupon handling
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, active=True)
            if total >= coupon.min_order_amount:
                if coupon.discount_type == 'FLAT':
                    discount = min(coupon.discount_value, total) # Discount shouldn't exceed total
                elif coupon.discount_type == 'PERCENT':
                    discount = (coupon.discount_value / 100) * total
                messages.success(request, f"Coupon '{coupon.code}' applied!")
            else:
                messages.warning(request, f"Minimum order ₹{coupon.min_order_amount} required for this coupon.")
        except Coupon.DoesNotExist:
            messages.warning(request, "Invalid coupon code.")

    total_after_discount = total - discount
    total_after_discount = max(total_after_discount, Decimal("0.00")) # Ensure total doesn't go negative
    
    razorpay_amount = int(total_after_discount * 100)

    if request.method == 'POST' and request.POST.get("place_order") == "1":
        data = request.POST
        required_fields = ['full_name', 'phone', 'address', 'city', 'state', 'pincode', 'payment_method']
        if not all(data.get(field) for field in required_fields):
            messages.error(request, "Please fill all required fields.")
            return redirect('checkout_view') # Use the correct view name

        # Validate total amount again to prevent manipulation
        # This is important if coupon was applied via AJAX or on GET and then submitted with POST
        recalculated_total = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
        recalculated_total = Decimal(str(recalculated_total))
        recalculated_discount = Decimal("0.00")
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, active=True)
                if recalculated_total >= coupon.min_order_amount:
                    if coupon.discount_type == 'FLAT':
                        recalculated_discount = min(coupon.discount_value, recalculated_total)
                    elif coupon.discount_type == 'PERCENT':
                        recalculated_discount = (coupon.discount_value / 100) * recalculated_total
            except Coupon.DoesNotExist:
                pass # Coupon not valid, discount remains 0

        final_total_amount = max(recalculated_total - recalculated_discount, Decimal("0.00"))

        # Save order
        order = Order.objects.create(
            user=user,
            full_name=data['full_name'],
            phone=data['phone'],
            email=data.get('email', ''),
            address=data['address'],
            city=data['city'],
            state=data['state'],
            pincode=data['pincode'],
            payment_method=data['payment_method'],
            total_amount=final_total_amount, # Use the recalculated total
            coupon_code=coupon_code or None,
            discount_amount=recalculated_discount,
            payment_id=data.get("razorpay_payment_id", ""),
            status="PENDING",
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                color=item.color,
                # Removed 'size' from OrderItem creation
                quantity=item.quantity, # This is the quantity of packs
                product_name=item.product.name, # Use product.name
                product_image=item.product.primary_image, # Use product.primary_image
                actual_price=item.actual_price, # This is the price per set
                discount_price=item.discount_price, # This is the discounted price per set
                # New fields for order item to store price per piece and total pieces in set
                price_per_piece_at_purchase=item.product.get_current_price_per_piece(),
                total_pieces_in_set_at_purchase=item.product.get_total_pieces_in_set(),
            )

        # Clear cart
        cart_items.delete()
        messages.success(request, "Your order has been placed successfully!")


        if data['payment_method'] == "COD":
            order.status = "PAID" # COD orders are typically marked paid once delivered or confirmed, but for your flow, marking as PAID means "order placed via COD"
            order.save()
            return redirect('order_success', order_id=order.id)
        elif data['payment_method'] == "RZP":
            if data.get("razorpay_payment_id"):
                order.status = "PAID" # Mark as paid if Razorpay ID exists
                order.save()
                return redirect('order_success', order_id=order.id)
            else:
                messages.error(request, "Razorpay payment ID missing.")
                order.status = "CANCELLED" # Mark as cancelled if payment failed or ID is missing
                order.save()
                return redirect('order_failure')

    # ✅ Create Razorpay order on GET (or when rendering checkout page)
    # This should be inside a try-except block for robustness
    try:
        razorpay_order = razorpay_client.order.create({
            "amount": razorpay_amount,
            "currency": "INR",
            "payment_capture": 1
        })
    except Exception as e:
        messages.error(request, f"Could not create payment order: {e}")
        razorpay_order = None # Set to None if creation fails

    return render(request, 'order/checkout.html', {
        "cart_items": processed_cart_items, # Pass the processed list here
        "total": total,
        "discount": discount,
        "total_after_discount": total_after_discount,
        "razorpay_order": razorpay_order,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": razorpay_amount, # Amount sent to Razorpay in paise
        "currency": "INR", # Explicitly pass currency
        "user_profile": user # Pass user object if needed for pre-filling form
    })


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