# order/shiport_utils.py

import requests
import json
from decimal import Decimal
from django.conf import settings

def get_cheapest_shipping_rate(to_pincode, total_weight, length, width, height, payment_mode):
    """
    Calls the Shiport API to get shipping rates and returns the cheapest option.
    """
    url = f"{settings.SHIPORT_API_BASE_URL}/shipment_rate_time"
    
    headers = {
        "Content-Type": "application/json",
        "secretkey": settings.SHIPORT_API_SECRET_KEY,
        "customerid": settings.SHIPORT_API_CUSTOMER_ID
    }

    payload = {
        "from_postal_code": "421302",  # Your warehouse pincode
        "from_country_code": "IN",
        "to_postal_code": str(to_pincode),
        "to_country_code": "IN",
        "weight": float(total_weight),
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "sort_by": "default",
        "parcel_type": "Parcel",
        "mode": "Domestic",
        "payment_mode": payment_mode # "prepaid" or "cod"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status() # Raise an exception for bad status codes
        result = response.json()

        if result.get("status") and result.get("rate_list"):
            cheapest = min(result["rate_list"], key=lambda x: float(x["total_charges"]))
            return cheapest
        return None
    except requests.RequestException as e:
        print(f"Shiport API Error (get_rate): {e}")
        return None

def create_shiport_shipment(order, service):
    """
    Creates a shipment in Shiport using the final order details.
    """
    url = f"{settings.SHIPORT_API_BASE_URL}/new_shipment_create"

    headers = {
        "Content-Type": "application/json",
        "secretkey": settings.SHIPORT_API_SECRET_KEY,
        "customerid": settings.SHIPORT_API_CUSTOMER_ID
    }

    subtotal = order.subtotal - order.discount_amount
    cod_amount = 0
    payment_mode_shiport = "prepaid" # Note: Shiport expects 'prepaid' (lowercase p)

    if order.payment_method == "COD":
        cod_amount = float(subtotal)
        payment_mode_shiport = "cod"
        
    # Aggregate item details
    items_payload = []
    total_weight = 0
    for item in order.items.all():
        total_weight += item.product.weight * item.quantity
        items_payload.append({
            "item_name": item.product_name,
            "item_value": float(item.actual_price),
            "item_quantity": item.quantity,
            "weight": float(item.product.weight),
            "length": float(item.product.length),
            "width": float(item.product.width),
            "height": float(item.product.height),
        })

    payload = {
        "warehouse_name": "Trades", # Your warehouse name
        "address_id": settings.SHIPORT_WAREHOUSE_ADDRESS_ID,
        "carrier_id": service["carrier_id"],
        "courier_id": service.get("courier_id"),
        "company_name": service["service_name"],
        "mode": "Domestic",
        "payment_mode": payment_mode_shiport,
        "cod_amount": cod_amount,
        "product_type_name": service["product_type_name"],
        "receiver_address": order.address,
        "receiver_city": order.city,
        "receiver_country_code": "IN",
        "receiver_country_name": "India",
        "receiver_email": order.email,
        "receiver_mobile": order.phone,
        "receiver_name": order.full_name,
        "receiver_pincode": order.pincode,
        "receiver_state_name": order.state,
        "return_address": "Roshan Baugh", # Your return address
        "return_city": "Bhiwandi",
        "return_country_code": "IN",
        "return_country_name": "India",
        "return_email": "shop@example.com",
        "return_mobile": "7028885969",
        "return_name": "Shop Owner",
        "return_pincode": "421302",
        "return_state_name": "Maharashtra",
        "service_name": service["service_name"],
        "shipment_type": "Parcel",
        "type": "Parcel",
        "total_amount": float(subtotal),
        "total_weight": float(total_weight),
        "weight": float(total_weight),
        "length": 30, # Use aggregated/default dimensions
        "width": 20,
        "height": 10,
        "order_number": str(order.id),
        "product_id": service["service_provider_id"],
        "items": items_payload,
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        if result.get("status"):
            return result # Success
        else:
            print(f"Shiport API Error (create_shipment): {result}")
            return None # Failure
    except requests.RequestException as e:
        print(f"Shiport API Error (create_shipment): {e}")
        return None