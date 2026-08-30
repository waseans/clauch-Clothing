# your_app/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from decimal import Decimal
import math
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import hmac
import hashlib
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django import forms
from django.views.decorators.http import require_POST
from django.utils import timezone

# --- Stock Management Imports ---
from django.db import transaction, IntegrityError
from django.db.models import F

# --- Model Imports ---
from .models import CartItem, Order, OrderItem, Coupon
from user.models import CustomUser, Product, ProductColor

# --- Service/Util Imports ---
from .shiport_utils import get_cheapest_shipping_rate as get_shiport_rate
from .ithink_services import get_rate_for_checkout as get_ithink_rate_for_checkout
from .shiport_shipment_task import process_shipment_for_order
from . import ithink_services
from django.template.loader import get_template
from xhtml2pdf import pisa


# ####################################################################
# STOCK REDUCTION UTILITY FUNCTION
# ####################################################################

@transaction.atomic
def reduce_product_stock(order):
    """
    Atomically reduces stock for each item in a given order.
    This function is safe from race conditions.
    
    If any item is out of stock, it raises an IntegrityError,
    which rolls back the entire transaction.
    """
    print(f"Attempting to reduce stock for Order #{order.id}")
    
    for item in order.items.all():
        if item.color:
            try:
                # Atomically update the stock
                rows_updated = ProductColor.objects.filter(
                    id=item.color.id,
                    stock__gte=item.quantity # Check: stock >= quantity
                ).update(
                    stock=F('stock') - item.quantity # Atomic update
                )
                
                if rows_updated == 0:
                    # Filter failed, meaning stock was insufficient
                    current_stock = ProductColor.objects.get(id=item.color.id).stock
                    print(f"Stock reduction FAILED for {item.product_name} ({item.color.name})")
                    raise IntegrityError(
                        f"Insufficient stock for {item.product_name} ({item.color.name}). "
                        f"Wanted {item.quantity}, but only {current_stock} sets are available."
                    )
                
                print(f"Successfully reduced stock for {item.product_name} ({item.color.name})")

            except ProductColor.DoesNotExist:
                raise IntegrityError(f"ProductColor with id {item.color.id} does not exist.")


# ####################################################################
# CART & CHECKOUT VIEWS
# ####################################################################

def add_product_pack_to_cart(request, product_id, color_id, quantity_of_packs):
    """
    Helper function to add a specific quantity of product packs to the cart.
    Stock checking should be done *before* calling this.
    """
    user = request.user
    product = get_object_or_404(Product, id=product_id)
    color = get_object_or_404(ProductColor, id=color_id) if color_id else None

    # Retrieve snapshot data
    product_name = product.name
    product_image = product.primary_image.url if product.primary_image else ''
    actual_price = product.price
    discount_price = product.discount_price

    cart_item, created = CartItem.objects.get_or_create(
        user=user,
        product=product,
        color=color,
        defaults={
            'quantity': quantity_of_packs,
            'product_name': product_name,
            'product_image': product_image,
            'actual_price': actual_price,
            'discount_price': discount_price
        }
    )
    if not created:
        # Item already exists, update its quantity
        cart_item.quantity += quantity_of_packs
        cart_item.save()

    return cart_item


@login_required(login_url='login')
@require_POST
def add_to_cart_view(request):
    product_id = request.POST.get('product_id')
    color_id = request.POST.get('color_id')
    set_quantity_str = request.POST.get('set_quantity') 

    if not product_id or not color_id:
        return JsonResponse({'status': 'error', 'message': 'Product or color not selected.'}, status=400)

    try:
        set_quantity = int(set_quantity_str)
        if set_quantity < 1:
            return JsonResponse({'status': 'error', 'message': 'Quantity of sets must be at least 1.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid quantity provided for sets.'}, status=400)

    try:
        product = get_object_or_404(Product, id=product_id)
        color = get_object_or_404(ProductColor, id=color_id)

        # --- ✅ STOCK CHECK ---
        # Find existing cart item to check total quantity
        cart_item = CartItem.objects.filter(user=request.user, product=product, color=color).first()
        current_cart_qty = cart_item.quantity if cart_item else 0
        total_qty_needed = current_cart_qty + set_quantity

        if color.stock < total_qty_needed:
            message = f"Not enough stock. Only {color.stock} sets are available."
            if current_cart_qty > 0:
                message += f" You already have {current_cart_qty} in your cart."
            return JsonResponse({'status': 'error', 'message': message}, status=400)
        # --- END STOCK CHECK ---

        is_buy_now = request.POST.get('buy_now') == 'true'
        
        if is_buy_now:
            request.session['buy_now_item'] = {
                'product_id': product_id,
                'color_id': color_id,
                'quantity': set_quantity
            }
            response_data = {
                'status': 'success',
                'checkout_url': redirect('buy_now_checkout').url
            }
        else:
            # Use the helper function
            add_product_pack_to_cart(request, product_id, color_id, set_quantity)
            response_data = {
                'status': 'success',
                'message': f'{set_quantity} sets added to bag!',
                'cart_url': redirect('view_cart').url
            }
            
        return JsonResponse(response_data)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)
    except ProductColor.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Color not found.'}, status=404)
    except Exception as e:
        print(f"Error adding to cart: {e}")
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)


@login_required(login_url='login')
def remove_from_cart(request, item_id=None, key=None):
    if item_id:
        CartItem.objects.filter(id=item_id, user=request.user).delete()
    
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'
    
    if is_ajax:
        cart_items = list(CartItem.objects.filter(user=request.user).select_related('product', 'color'))
        subtotal = sum([(i.discount_price or i.actual_price) * i.quantity for i in cart_items])
        return JsonResponse({'status': 'success', 'cart_subtotal': f"{subtotal:.2f}", 'item_count': len(cart_items)})
        
    messages.success(request, "Set removed from cart.")
    return redirect('view_cart')


@login_required(login_url='login')
@require_POST
def update_cart_quantity(request):
    import json
    # Handle both normal POST and JSON
    if request.content_type == 'application/json':
        data = json.loads(request.body)
        item_id = data.get('item_id')
        action = data.get('action')
        is_ajax = True
    else:
        item_id = request.POST.get('item_id')
        action = request.POST.get('action')
        is_ajax = False
        
    item = get_object_or_404(CartItem, id=item_id, user=request.user, color__isnull=False)
    min_qty_sets = 1
    
    if action == 'increase':
        new_qty = item.quantity + 1
        if item.color.stock < new_qty:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': f'Not enough stock. Only {item.color.stock} sets available.'}, status=400)
            messages.warning(request, f"Not enough stock. Only {item.color.stock} sets are available.")
            return redirect('view_cart')
        item.quantity = new_qty
        
    elif action == 'decrease':
        if item.quantity > min_qty_sets:
            item.quantity -= 1
        else:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': f'Minimum quantity is {min_qty_sets}.'}, status=400)
            messages.warning(request, f"Minimum quantity for this set is {min_qty_sets}.")
            return redirect('view_cart')

    item.save()
    
    if is_ajax:
        # Calculate new totals
        cart_items = list(CartItem.objects.filter(user=request.user).select_related('product', 'color'))
        subtotal = sum([(i.discount_price or i.actual_price) * i.quantity for i in cart_items])
        item_subtotal = (item.discount_price or item.actual_price) * item.quantity
        return JsonResponse({
            'status': 'success',
            'new_quantity': item.quantity,
            'item_subtotal': f"{item_subtotal:.2f}",
            'cart_subtotal': f"{subtotal:.2f}"
        })
        
    messages.success(request, "Cart quantity updated.")
    return redirect('view_cart')


def get_checkout_items(request, is_buy_now=False):
    """
    Returns a list of cart_items based on whether it is a buy_now flow or not.
    """
    if is_buy_now:
        buy_now_data = request.session.get('buy_now_item')
        if buy_now_data:
            try:
                product = Product.objects.get(id=buy_now_data['product_id'])
                color = ProductColor.objects.get(id=buy_now_data['color_id']) if buy_now_data.get('color_id') else None
                
                # Create an in-memory CartItem instance (not saved to DB)
                cart_item = CartItem(
                    user=request.user if request.user.is_authenticated else None,
                    product=product,
                    color=color,
                    quantity=buy_now_data['quantity'],
                    product_name=product.name,
                    product_image=product.primary_image.url if product.primary_image else '',
                    actual_price=product.price,
                    discount_price=product.discount_price
                )
                return [cart_item]
            except (Product.DoesNotExist, ProductColor.DoesNotExist):
                del request.session['buy_now_item']
        return []
            
    # Fallback to normal cart
    return list(CartItem.objects.filter(user=request.user).select_related('product', 'color'))


def get_valid_coupon_discount(request, cart_items):
    """
    Helper function to validate and recalculate the coupon discount based on current cart items.
    Updates the session if the coupon becomes invalid or the amount changes.
    Returns (coupon_code, discount_amount_decimal)
    """
    coupon_code = request.session.get('coupon_code', '').strip()
    if not coupon_code:
        return '', Decimal('0.00')
        
    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
        if coupon.expires_at and coupon.expires_at < timezone.now():
            raise ValueError("Expired")
            
        eligible_subtotal = Decimal('0.00')
        total_subtotal = Decimal('0.00')
        
        if coupon.is_product_specific:
            applicable_product_ids = set(coupon.applicable_products.values_list('id', flat=True))
        else:
            applicable_product_ids = None

        for item in cart_items:
            item_total = (item.discount_price or item.actual_price) * item.quantity
            total_subtotal += item_total
            if applicable_product_ids is None or item.product_id in applicable_product_ids:
                eligible_subtotal += item_total
                
        if (coupon.is_product_specific and eligible_subtotal == 0) or total_subtotal < coupon.min_order_amount:
            raise ValueError("Ineligible")
            
        discount_amount = Decimal('0.00')
        if coupon.discount_type == 'PERCENT':
            discount_amount = (eligible_subtotal * coupon.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        elif coupon.discount_type == 'FLAT':
            discount_amount = min(coupon.discount_value, eligible_subtotal)
            
        request.session['coupon_discount'] = str(discount_amount)
        return coupon.code, discount_amount
        
    except (Coupon.DoesNotExist, ValueError):
        if 'coupon_code' in request.session: del request.session['coupon_code']
        if 'coupon_discount' in request.session: del request.session['coupon_discount']
        return '', Decimal('0.00')


@login_required(login_url='login')
@require_POST
def ajax_apply_coupon(request):
    data = json.loads(request.body)
    code = data.get('coupon_code', '').strip()
    is_buy_now = data.get('is_buy_now', False)
    
    if not code:
        return JsonResponse({'status': 'error', 'message': 'Please enter a coupon code.'}, status=400)
        
    try:
        coupon = Coupon.objects.get(code__iexact=code, active=True)
    except Coupon.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid or inactive coupon code.'}, status=400)
        
    if coupon.expires_at and coupon.expires_at < timezone.now():
        return JsonResponse({'status': 'error', 'message': 'This coupon has expired.'}, status=400)
        
    cart_items = get_checkout_items(request, is_buy_now=is_buy_now)
    if not cart_items:
        return JsonResponse({'status': 'error', 'message': 'Your cart is empty.'}, status=400)
        
    eligible_subtotal = Decimal('0.00')
    total_subtotal = Decimal('0.00')
    
    if coupon.is_product_specific:
        applicable_product_ids = set(coupon.applicable_products.values_list('id', flat=True))
    else:
        applicable_product_ids = None

    for item in cart_items:
        item_total = (item.discount_price or item.actual_price) * item.quantity
        total_subtotal += item_total
        if applicable_product_ids is None or item.product_id in applicable_product_ids:
            eligible_subtotal += item_total
            
    if coupon.is_product_specific and eligible_subtotal == 0:
        return JsonResponse({'status': 'error', 'message': 'This coupon is not applicable to any products in your cart.'}, status=400)
        
    if total_subtotal < coupon.min_order_amount:
        return JsonResponse({'status': 'error', 'message': f'Minimum order amount of ₹{coupon.min_order_amount} is required.'}, status=400)
        
    discount_amount = Decimal('0.00')
    if coupon.discount_type == 'PERCENT':
        discount_amount = (eligible_subtotal * coupon.discount_value / Decimal('100')).quantize(Decimal('0.01'))
    elif coupon.discount_type == 'FLAT':
        discount_amount = min(coupon.discount_value, eligible_subtotal)
        
    request.session['coupon_code'] = coupon.code
    request.session['coupon_discount'] = str(discount_amount)
    # Clear shipping info since total changed
    if 'shipping_info' in request.session: del request.session['shipping_info']
    
    return JsonResponse({
        'status': 'success', 
        'message': 'Coupon applied successfully!',
        'discount_amount': str(discount_amount),
        'new_subtotal': str(total_subtotal - discount_amount)
    })

@login_required(login_url='login')
@require_POST
def ajax_remove_coupon(request):
    data = json.loads(request.body) if request.body else {}
    is_buy_now = data.get('is_buy_now', False)
    
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
    if 'coupon_discount' in request.session:
        del request.session['coupon_discount']
    # Clear shipping info since total changed
    if 'shipping_info' in request.session: del request.session['shipping_info']
        
    cart_items = get_checkout_items(request, is_buy_now=is_buy_now)
    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
        
    return JsonResponse({
        'status': 'success', 
        'message': 'Coupon removed.',
        'subtotal': str(subtotal)
    })

@login_required(login_url='login')
@require_POST
def ajax_calculate_shipping(request):
    data = json.loads(request.body)
    pincode = data.get('pincode')
    is_buy_now = data.get('is_buy_now', False)
    # Map 'RZP' (Razorpay) to 'Prepaid' for iThink compatibility
    raw_method = data.get('payment_method', 'RZP') 
    payment_method = "Prepaid" if raw_method == "RZP" else "COD"
    
    # 1. Validation
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        return JsonResponse({'error': 'Please enter a valid 6-digit pincode.'}, status=400)

    cart_items = get_checkout_items(request, is_buy_now=is_buy_now)
    if not cart_items:
        return JsonResponse({'error': 'Your cart is empty.'}, status=400)

    # 2. Calculate Subtotal
    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    _, coupon_discount = get_valid_coupon_discount(request, cart_items)
    discounted_subtotal = subtotal - coupon_discount

    # Calculate total weight and max dimensions (for debugging & verification)
    items = [item for item in cart_items if item.product]
    total_weight = sum((item.product.weight * item.quantity) for item in items) if items else 0
    max_length = max((item.product.length for item in items), default=0)
    max_width = max((item.product.width for item in items), default=0)
    max_height = max((item.product.height for item in items), default=0)

    # Log the computed shipping parameters so we can verify them in logs
    print(f"[shipping-debug] subtotal={subtotal}, discounted_subtotal={discounted_subtotal}, total_weight={total_weight}, length={max_length}, width={max_width}, height={max_height}")

    # 3. Calculate Shipping using iThink for BOTH methods
    # We pass the payment_method ("Prepaid" or "COD") directly to the iThink wrapper
    ithink_result = get_ithink_rate_for_checkout(
        pincode=pincode, 
        subtotal=discounted_subtotal, 
        cart_items=cart_items,
        payment_method=payment_method  # Ensure your helper accepts this
    )

    if ithink_result.get('status') != 'success':
        error_msg = ithink_result.get('message', f'Could not calculate {payment_method} shipping.')
        return JsonResponse({'error': error_msg}, status=400)

    # 4. Process Charges
    shipping_service = ithink_result
    shipping_charge = Decimal(shipping_service['total_charges'])

    # --- Fallback shipping calculation (per-weight) ---
    per_kg_rate = Decimal(str(getattr(settings, 'SHIPPING_PER_KG_RATE', 25)))
    min_charge = Decimal(str(getattr(settings, 'SHIPPING_MIN_CHARGE', 40)))

    # total_weight was computed above
    fallback_charge = (Decimal(str(total_weight)) * per_kg_rate).quantize(Decimal('0.01'))
    if fallback_charge < min_charge:
        fallback_charge = min_charge

    # Use whichever is higher: carrier quote or our fallback per-weight charge
    final_shipping_charge = max(shipping_charge, fallback_charge)

    # Log the decision
    print(f"[shipping-debug] carrier_rate={shipping_charge}, fallback_rate={fallback_charge}, final_rate={final_shipping_charge}")

    # Store in session for the final checkout/place order step
    request.session['shipping_info'] = {
        'charge': str(final_shipping_charge),
        'carrier_charge': str(shipping_charge),
        'fallback_charge': str(fallback_charge),
        'service': shipping_service,
        'method': payment_method
    }
    
    grand_total = discounted_subtotal + final_shipping_charge

    return JsonResponse({
        # 'shipping_charge' is the FINAL applied charge (may be carrier rate or our fallback)
        'shipping_charge': f"{final_shipping_charge:.2f}",
        'grand_total': f"{grand_total:.2f}",
        'discount_amount': f"{coupon_discount:.2f}",
        'carrier_rate': f"{shipping_charge:.2f}",
        'fallback_rate': f"{fallback_charge:.2f}",
        # Expose computed shipping parameters for verification
        'shipping_weight': f"{total_weight}",
        'shipping_dimensions': {
            'length': max_length,
            'width': max_width,
            'height': max_height,
        }
    })

@login_required(login_url='login')
def checkout_view(request):
    user = request.user
    cart_items = get_checkout_items(request, is_buy_now=False)

    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('view_cart')

    # --- ✅ STOCK CHECK ON PAGE LOAD ---
    for item in cart_items:
        if item.color and item.color.stock < item.quantity:
            messages.error(request, f"Item {item.product_name} ({item.color.name}) is out of stock "
                                     f"or you have too many in your cart (Only {item.color.stock} left).")
            return redirect('view_cart')
    # --- END STOCK CHECK ---

    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    subtotal = Decimal(str(subtotal))
    
    # On a fresh GET request, clear any stale coupon from a previous session so totals are accurate
    if request.method == 'GET':
        request.session.pop('coupon_code', None)
        request.session.pop('coupon_discount', None)
        request.session.pop('shipping_info', None)

    # Recalculate to ensure accurate discount if cart changed
    coupon_code, coupon_discount = get_valid_coupon_discount(request, cart_items)
    discounted_subtotal = subtotal - coupon_discount

    if request.method == 'POST':
        data = request.POST
        
        # --- THIS BLOCK IS FOR AFTER PAYMENT IS COMPLETED (CLIENT-SIDE) ---
        if data.get("razorpay_payment_id"):
            order_id = request.session.get('order_id')
            if not order_id:
                messages.error(request, "Your session expired. Please try again.")
                return redirect('view_cart')

            order = get_object_or_404(Order, id=order_id, user=user)
            
            # --- ✅ ATOMIC STOCK REDUCTION & ORDER UPDATE ---
            try:
                # We only process if the order is still pending.
                # This prevents double-processing if the webhook runs first.
                if order.shipping_status == 'PENDING':
                    # 1. Attempt to reduce stock first
                    reduce_product_stock(order)
                
                    # 2. If stock reduction succeeds, update order
                    order.payment_id = data.get("razorpay_payment_id")
                    if order.payment_method == 'RZP':
                        order.payment_status = 'PAID'
                    elif order.payment_method == 'COD':
                        order.payment_status = 'SHIPPING_FEE_PAID'
                    
                    order.shipping_status = 'READY_TO_SHIP'
                    order.save()
                
                # 3. Clean up cart & session
                CartItem.objects.filter(user=user).delete()
                if 'order_id' in request.session: del request.session['order_id']
                if 'shipping_info' in request.session: del request.session['shipping_info']
                if 'coupon_code' in request.session: del request.session['coupon_code']
                if 'coupon_discount' in request.session: del request.session['coupon_discount']
                
                # 4. Redirect to success
                return redirect('order_success', order_id=order.id)
            
            except IntegrityError as e:
                # STOCK REDUCTION FAILED!
                messages.error(request, f"Error processing order: {e}. Please contact support. "
                                        "Your order has been cancelled, and payment will be refunded if captured.")
                # Mark order as failed
                order.payment_status = 'FAILED'
                order.shipping_status = 'CANCELLED'
                order.save()
                # Don't delete cart, let user fix it
                return redirect('order_failure_view')
            # --- END ATOMIC BLOCK ---


        # --- THIS BLOCK IS FOR CREATING THE ORDER BEFORE PAYMENT ---
        shipping_info = request.session.get('shipping_info')
        if not shipping_info:
            messages.error(request, "Please calculate shipping before proceeding to pay.")
            return redirect('view_cart')

        shipping_charge = Decimal(shipping_info['charge'])
        shipping_service = shipping_info['service']
        
        grand_total = discounted_subtotal + shipping_charge
        payment_method = data.get('payment_method', 'RZP')
        amount_to_pay_now = grand_total if payment_method == "RZP" else shipping_charge
        razorpay_amount = int(amount_to_pay_now * 100)

        # Create Order (but don't reduce stock yet)
        order = Order.objects.create(
            user=user, full_name=data['full_name'], phone=data['phone'], email=data.get('email', ''),
            address=data['address'], city=data['city'], state=data['state'], pincode=data['pincode'],
            payment_method=payment_method, 
            subtotal=subtotal,
            coupon_code=coupon_code,
            discount_amount=coupon_discount,
            shipping_charge=shipping_charge, 
            grand_total=grand_total,
            shipping_service_name=shipping_service['service_name'],
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
                "amount": razorpay_amount, "currency": "INR", "payment_capture": 1, "notes": {"order_id": str(order.id)}
            })
            order.razorpay_order_id = razorpay_order['id'] # Save Razorpay Order ID
            order.save()
            
            processed_cart_items = []
            for item in cart_items:
                price = item.discount_price or item.actual_price
                processed_cart_items.append({
                    'id': item.id,
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
            return render(request, 'order/cart.html', context)
        except Exception as e:
            messages.error(request, f"Could not create payment order: {e}")
            order.payment_status = 'FAILED'
            order.shipping_status = 'CANCELLED'
            order.save()
            return redirect('view_cart')

    # --- GET Request logic ---
    processed_cart_items = []
    for item in cart_items:
        price = item.discount_price or item.actual_price
        processed_cart_items.append({
            'id': item.id,
            'product': item.product,
            'color': item.color,
            'quantity': item.quantity,
            'total_price': price * item.quantity
        })

    context = { 
        "cart_items": processed_cart_items,
        "subtotal": subtotal,
        "coupon_code": coupon_code,
        "coupon_discount": coupon_discount,
        "discounted_subtotal": discounted_subtotal,
        "shipping_charge": Decimal("0.00"), 
        "grand_total": discounted_subtotal,
        "razorpay_key": settings.RAZORPAY_KEY_ID, 
        "user_profile": user 
    }
    return render(request, 'order/cart.html', context)


@login_required(login_url='login')
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order/success.html', {'order': order})

def order_failure_view(request):
    return render(request, 'order/failure.html')


@csrf_exempt
def razorpay_webhook(request):
    if request.method == "POST":
        payload = request.body
        received_signature = request.headers.get('X-Razorpay-Signature')

        if not received_signature:
            return HttpResponse("Signature header missing", status=400)
            
        generated_signature = hmac.new(
            key=bytes(settings.RAZORPAY_WEBHOOK_SECRET, 'utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(received_signature, generated_signature):
            return HttpResponse("Invalid signature", status=403)

        data = json.loads(payload)
        event_type = data.get('event')

        # --- ✅ HANDLE 'payment.captured' ---
        if event_type == 'payment.captured':
            payment_entity = data.get('payload', {}).get('payment', {}).get('entity', {})
            rzp_order_id = payment_entity.get('order_id')
            rzp_payment_id = payment_entity.get('id')
            
            if not rzp_order_id:
                return HttpResponse("No order_id in payload", status=400)

            try:
                order = Order.objects.get(razorpay_order_id=rzp_order_id)

                # --- ✅ Idempotency Check ---
                # Only process if the order is still PENDING.
                # If it's already 'READY_TO_SHIP', checkout_view handled it.
                if order.shipping_status == 'PENDING':
                    try:
                        # 1. Reduce stock
                        reduce_product_stock(order)
                        
                        # 2. Update order
                        order.payment_id = rzp_payment_id
                        if order.payment_method == 'RZP':
                            order.payment_status = 'PAID'
                        elif order.payment_method == 'COD':
                            order.payment_status = 'SHIPPING_FEE_PAID'
                        
                        order.shipping_status = 'READY_TO_SHIP'
                        order.save()
                        
                        # 3. Clear cart (optional but good practice)
                        CartItem.objects.filter(user=order.user).delete()
                        
                        print(f"Webhook processed stock for order: {order.id}")
                        return HttpResponse(status=200)

                    except IntegrityError as e:
                        # Stock reduction failed
                        print(f"Webhook stock failure for order {order.id}: {e}")
                        order.payment_status = 'FAILED'
                        order.shipping_status = 'CANCELLED'
                        order.save()
                        # Still return 200 so Razorpay stops sending
                        return HttpResponse(status=200)
                else:
                    # Already processed, just acknowledge
                    print(f"Webhook: Order {order.id} already processed.")
                    return HttpResponse(status=200)

            except Order.DoesNotExist:
                print(f"Webhook: Order not found for Razorpay order_id: {rzp_order_id}")
                return HttpResponse(status=404)
        
        else:
            print(f"Webhook: Unhandled event type: {event_type}")
            return HttpResponse(status=200) # Acknowledge other events

    return HttpResponse("Only POST allowed", status=405)


# ####################################################################
# USER ACCOUNT & ADMIN DASHBOARD VIEWS
# ####################################################################

@login_required
def my_orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at').prefetch_related('items')
    return render(request, 'my_orders.html', {'orders': orders})

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
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






@staff_member_required
def admin_shipment_dashboard(request, status_filter='pending'):
    """Dashboard for PREPAID (Shiport) orders."""
    base_query = Order.objects.filter(payment_method='RZP')
    base_query = base_query.exclude(
        shipping_status__in=['PENDING', 'CANCELLED'] # <--- MODIFIED: Removed 'DELIVERED'
    )

    if status_filter == 'pending':
        orders_to_display = base_query.filter(
            payment_status='PAID',
            shipping_status__in=['READY_TO_SHIP', 'SHIPMENT_FAILED']
        )
        active_tab = 'pending'
    elif status_filter == 'shipped':
        orders_to_display = base_query.filter(shipping_status='SHIPPED')
        active_tab = 'shipped'
    
    # --- ADDED THIS BLOCK ---
    elif status_filter == 'delivered':
        orders_to_display = base_query.filter(shipping_status='DELIVERED')
        active_tab = 'delivered'
        
    else: # 'all'
        orders_to_display = base_query # 'all' now includes delivered
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


# --- ADD THIS NEW VIEW ---
@staff_member_required
@require_POST  # Ensures this view can only be accessed via POST
def admin_shipment_mark_as_delivered(request, order_id):
    """Allows admin to manually mark a SHIPPED prepaid order as DELIVERED."""
    # Ensure we only modify RZP (Prepaid) orders here
    order = get_object_or_404(Order, id=order_id, payment_method='RZP')

    if order.shipping_status == 'SHIPPED':
        order.shipping_status = 'DELIVERED'
        order.save()
        messages.success(request, f"Order #{order.id} has been manually marked as DELIVERED.")
    else:
        messages.warning(request, f"Order #{order.id} was not in 'SHIPPED' state. No change made.")
    
    # Redirect back to the shipped tab of the prepaid dashboard
    return redirect('admin_shipment_dashboard', status_filter='shipped')


@staff_member_required
def create_shipment_for_order(request, order_id):
    """Triggers the shipment creation task for a PREPAID order."""
    success, message = process_shipment_for_order(order_id)
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect('admin_shipment_dashboard_default')

@staff_member_required
def admin_ithink_dashboard(request, status_filter='pending'):
    """Dashboard for COD (iThink) orders."""
    base_query = Order.objects.filter(payment_method='COD')
    base_query = base_query.exclude(
        shipping_status__in=['CANCELLED']  # <--- MODIFIED: Only exclude CANCELLED
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
    
    # --- ADDED THIS BLOCK ---
    elif status_filter == 'delivered':
        orders_to_display = base_query.filter(shipping_status='DELIVERED')
        active_tab = 'delivered'
    
    else: # 'all'
        orders_to_display = base_query # 'all' will now include pending, shipped, and delivered
        active_tab = 'all'

    orders_to_display = orders_to_display.prefetch_related('items__product').order_by('-created_at')

    processed_orders = []
    for order in orders_to_display:
        representative_item = order.items.first()
        display_weight = 0
        if representative_item and representative_item.product:
            display_weight = representative_item.product.weight
            
        processed_orders.append({
            'order': order,
            'total_weight': display_weight,
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
        order.shipping_status = 'SHIPMENT_FAILED'
        order.save()
        messages.error(request, f"Order #{order.id} Failed: Could not get shipping rates. Reason: {rate_response['message']}")
        return redirect('admin_ithink_dashboard_default')

    cheapest_courier = rate_response['courier_name']
    shipping_rate = Decimal(rate_response['rate'])
    shipment_response = ithink_services.create_ithink_order(order, cheapest_courier)

    if shipment_response['status'] == 'error':
        order.shipping_status = 'SHIPMENT_FAILED'
        order.save()
        messages.error(request, f"Order #{order.id} Failed: Could not create shipment. Reason: {shipment_response['message']}")
        return redirect('admin_ithink_dashboard_default')

    order.tracking_id = shipment_response['waybill']
    order.shipping_service_name = shipment_response['courier']
    order.shipping_charge = shipping_rate
    order.shipping_status = 'SHIPPED'
    order.save()

    messages.success(request, f"Successfully created shipment for Order #{order.id}! AWB: {order.tracking_id}")
    return redirect('admin_ithink_dashboard_default')


@login_required(login_url='login')
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    template_path = 'invoice_template.html' 
    context = {'order': order}
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_#{order.id}.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(
       html,
       dest=response
    )
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


# --- ADD THIS NEW VIEW ---
@staff_member_required
@require_POST  # Ensures this view can only be accessed via POST
def admin_mark_as_delivered(request, order_id):
    """Allows admin to manually mark a SHIPPED order as DELIVERED."""
    order = get_object_or_404(Order, id=order_id, payment_method='COD')

    if order.shipping_status == 'SHIPPED':
        order.shipping_status = 'DELIVERED'
        order.save()
        messages.success(request, f"Order #{order.id} has been manually marked as DELIVERED.")
    else:
        messages.warning(request, f"Order #{order.id} was not in 'SHIPPED' state. No change made.")
    
    # Redirect back to the shipped tab, where the user just was
    return redirect('admin_ithink_dashboard', status_filter='shipped')




@login_required(login_url='login')
def buy_now_checkout_view(request):
    user = request.user
    cart_items = get_checkout_items(request, is_buy_now=True)

    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('home') # Redirect home if no buy now item

    # --- ✅ STOCK CHECK ON PAGE LOAD ---
    for item in cart_items:
        if item.color and item.color.stock < item.quantity:
            messages.error(request, f"Item {item.product_name} ({item.color.name}) is out of stock "
                                     f"or you have too many in your cart (Only {item.color.stock} left).")
            return redirect('home') # Redirect home if no buy now item
    # --- END STOCK CHECK ---

    subtotal = sum([(item.discount_price or item.actual_price) * item.quantity for item in cart_items])
    subtotal = Decimal(str(subtotal))

    # On a fresh GET request, clear any stale coupon from a previous session so totals are accurate
    if request.method == 'GET':
        request.session.pop('coupon_code', None)
        request.session.pop('coupon_discount', None)
        request.session.pop('shipping_info', None)
    
    # Recalculate to ensure accurate discount if cart changed
    coupon_code, coupon_discount = get_valid_coupon_discount(request, cart_items)
    discounted_subtotal = subtotal - coupon_discount

    if request.method == 'POST':
        data = request.POST
        
        # --- THIS BLOCK IS FOR AFTER PAYMENT IS COMPLETED (CLIENT-SIDE) ---
        if data.get("razorpay_payment_id"):
            order_id = request.session.get('order_id')
            if not order_id:
                messages.error(request, "Your session expired. Please try again.")
                return redirect('buy_now_checkout')

            order = get_object_or_404(Order, id=order_id, user=user)
            
            # --- ✅ ATOMIC STOCK REDUCTION & ORDER UPDATE ---
            try:
                # We only process if the order is still pending.
                # This prevents double-processing if the webhook runs first.
                if order.shipping_status == 'PENDING':
                    # 1. Attempt to reduce stock first
                    reduce_product_stock(order)
                
                    # 2. If stock reduction succeeds, update order
                    order.payment_id = data.get("razorpay_payment_id")
                    if order.payment_method == 'RZP':
                        order.payment_status = 'PAID'
                    elif order.payment_method == 'COD':
                        order.payment_status = 'SHIPPING_FEE_PAID'
                    
                    order.shipping_status = 'READY_TO_SHIP'
                    order.save()
                
                # 3. Clean up cart & session
                if 'buy_now_item' in request.session: del request.session['buy_now_item']
                if 'order_id' in request.session: del request.session['order_id']
                if 'shipping_info' in request.session: del request.session['shipping_info']
                if 'coupon_code' in request.session: del request.session['coupon_code']
                if 'coupon_discount' in request.session: del request.session['coupon_discount']
                
                # 4. Redirect to success
                return redirect('order_success', order_id=order.id)
            
            except IntegrityError as e:
                # STOCK REDUCTION FAILED!
                messages.error(request, f"Error processing order: {e}. Please contact support. "
                                        "Your order has been cancelled, and payment will be refunded if captured.")
                # Mark order as failed
                order.payment_status = 'FAILED'
                order.shipping_status = 'CANCELLED'
                order.save()
                # Don't delete cart, let user fix it
                return redirect('order_failure_view')
            # --- END ATOMIC BLOCK ---


        # --- THIS BLOCK IS FOR CREATING THE ORDER BEFORE PAYMENT ---
        shipping_info = request.session.get('shipping_info')
        if not shipping_info:
            messages.error(request, "Please calculate shipping before proceeding to pay.")
            return redirect('buy_now_checkout')

        shipping_charge = Decimal(shipping_info['charge'])
        shipping_service = shipping_info['service']
        
        grand_total = discounted_subtotal + shipping_charge
        payment_method = data.get('payment_method', 'RZP')
        amount_to_pay_now = grand_total if payment_method == "RZP" else shipping_charge
        razorpay_amount = int(amount_to_pay_now * 100)

        # Create Order (but don't reduce stock yet)
        order = Order.objects.create(
            user=user, full_name=data['full_name'], phone=data['phone'], email=data.get('email', ''),
            address=data['address'], city=data['city'], state=data['state'], pincode=data['pincode'],
            payment_method=payment_method, 
            subtotal=subtotal,
            coupon_code=coupon_code,
            discount_amount=coupon_discount,
            shipping_charge=shipping_charge, 
            grand_total=grand_total,
            shipping_service_name=shipping_service['service_name'],
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
                "amount": razorpay_amount, "currency": "INR", "payment_capture": 1, "notes": {"order_id": str(order.id)}
            })
            order.razorpay_order_id = razorpay_order['id'] # Save Razorpay Order ID
            order.save()
            
            processed_cart_items = []
            for item in cart_items:
                price = item.discount_price or item.actual_price
                processed_cart_items.append({
                    'id': item.id,
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
            return render(request, 'order/buy_now_checkout.html', context)
        except Exception as e:
            messages.error(request, f"Could not create payment order: {e}")
            order.payment_status = 'FAILED'
            order.shipping_status = 'CANCELLED'
            order.save()
            return redirect('buy_now_checkout')

    # --- GET Request logic ---
    processed_cart_items = []
    for item in cart_items:
        price = item.discount_price or item.actual_price
        processed_cart_items.append({
            'id': item.id,
            'product': item.product,
            'color': item.color,
            'quantity': item.quantity,
            'total_price': price * item.quantity
        })

    context = { 
        "cart_items": processed_cart_items,
        "subtotal": subtotal,
        "coupon_code": coupon_code,
        "coupon_discount": coupon_discount,
        "discounted_subtotal": discounted_subtotal,
        "shipping_charge": Decimal("0.00"), 
        "grand_total": discounted_subtotal,
        "razorpay_key": settings.RAZORPAY_KEY_ID, 
        "user_profile": user 
    }
    return render(request, 'order/buy_now_checkout.html', context)

