# order/shiport_shipment_task.py

import json
import logging
import requests  # <-- Moved import to the top
from decimal import Decimal

from django.conf import settings
# Unused 'messages' import removed
from .models import Order
from .shiport_utils import get_cheapest_shipping_rate

logger = logging.getLogger(__name__)

def process_shipment_for_order(order_id):
    """
    Takes an order ID, gets the cheapest rate, and creates a shipment with Shiport.
    Updates the order object based on the success or failure of the API call.
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("Order #%s not found in process_shipment_for_order.", order_id)
        return False, "Order not found."

    # --- 1. Calculate Dimensions and Weight from the Order ---
    total_weight = sum([item.product.weight * item.quantity for item in order.items.all()])
    max_length = max([item.product.length for item in order.items.all()] or [30.0])
    max_width = max([item.product.width for item in order.items.all()] or [20.0])
    total_height = sum([item.product.height * item.quantity for item in order.items.all()])

    # --- 2. Get the Cheapest Service ---
    shiport_payment_mode = "prepaid" if order.payment_method == "RZP" else "cod"
    service = get_cheapest_shipping_rate(
        to_pincode=order.pincode, total_weight=total_weight, length=max_length,
        width=max_width, height=total_height, payment_mode=shiport_payment_mode
    )

    if not service:
        order.status = "SHIPMENT_FAILED"
        order.save()
        logger.warning("Could not find a shipping service for Order #%s.", order.id)
        return False, f"Could not find a shipping service for Order #{order.id}."

    # --- 3. Build the Payload with Sanitized Data ---
    cod_amount = 0
    if order.payment_method == "COD":
        cod_amount = float(order.subtotal - order.discount_amount)

    items_payload = []
    for item in order.items.all():
        items_payload.append({
            "item_name": item.product_name, "item_value": float(item.actual_price),
            "item_quantity": item.quantity, "weight": float(item.product.weight),
            "length": float(item.product.length), "width": float(item.product.width),
            "height": float(item.product.height)
        })

    # --- ADDED: Automatic Phone Number Sanitization ---
    original_phone = order.phone
    digits_only = ''.join(filter(str.isdigit, original_phone))
    sanitized_phone = digits_only[-10:]
    if sanitized_phone != original_phone:
        logger.warning(
            "Phone for Order #%s sanitized from '%s' to '%s' for Shiport API.",
            order.id, original_phone, sanitized_phone
        )
    # ------------------------------------------------

    payload = {
        "warehouse_name": "Trades", "address_id": settings.SHIPORT_WAREHOUSE_ADDRESS_ID,
        "carrier_id": service["carrier_id"], "courier_id": service.get("courier_id"),
        "company_name": service["service_name"], "mode": "Domestic",
        "payment_mode": shiport_payment_mode, "cod_amount": cod_amount,
        "product_type_name": service["product_type_name"], "receiver_address": order.address,
        "receiver_city": order.city, "receiver_country_code": "IN",
        "receiver_country_name": "India", "receiver_email": order.email,
        "receiver_mobile": sanitized_phone,  # <-- USING THE SANITIZED PHONE
        "receiver_name": order.full_name, "receiver_pincode": order.pincode,
        "receiver_state_name": order.state, "return_address": "Roshan Baugh",
        "return_city": "Bhiwandi", "return_country_code": "IN",
        "return_country_name": "India", "return_email": "shop@example.com",
        "return_mobile": "7028885969", "return_name": "Shop Owner",
        "return_pincode": "421302", "return_state_name": "Maharashtra",
        "service_name": service["service_name"], "shipment_type": "Parcel",
        "type": "Parcel", "total_amount": float(service["total_charges"]),
        "total_weight": float(total_weight), "weight": float(total_weight),
        "length": float(max_length), "width": float(max_width), "height": float(total_height),
        "order_number": str(order.id), "product_id": service["service_provider_id"],
        "items": items_payload,
    }
    
    # --- 4. Make the API Call and Update the Order ---
    logger.info("➡️ Creating Shiport shipment for Order #%s...", order.id)
    logger.debug("Shipment creation payload: %s", json.dumps(payload, indent=2))
    
    try:
        headers = {
            "Content-Type": "application/json",
            "secretkey": settings.SHIPORT_API_SECRET_KEY,
            "customerid": settings.SHIPORT_API_CUSTOMER_ID
        }
        response = requests.post(
            f"{settings.SHIPORT_API_BASE_URL}/new_shipment_create",
            headers=headers, json=payload, timeout=300
        )
        if response.status_code == 400:
             logger.error("❌ Shiport returned 400 Bad Request. Raw Response: %s", response.text)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status"):
            order.tracking_id = result.get('awb_number') or result.get('data', {}).get('awb_number')
            order.shipping_label_url = result.get('label_url') or result.get('data', {}).get('label_url')
            order.shipping_service_name = service['service_name']
            order.shipping_charge = Decimal(service['total_charges'])
            order.status = "SHIPPED"
            order.save()
            logger.info("✅ Shipment created successfully for Order #%s", order.id)
            return True, f"Shipment created for Order #{order.id}. Tracking ID: {order.tracking_id}"
        else:
            order.status = "SHIPMENT_FAILED"
            order.save()
            logger.warning("⚠️ Shiport shipment creation failed for Order #%s. Response: %s", order.id, result)
            return False, f"Shiport error for Order #{order.id}: {result.get('message', 'Unknown error')}"

    except requests.RequestException as e:
        order.status = "SHIPMENT_FAILED"
        order.save()
        logger.error("❌ Shiport API Error (create_shipment) for Order #%s: %s", order.id, e)
        return False, f"API connection error for Order #{order.id}."