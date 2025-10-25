import requests
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings

# ---------------------------------------------------------------------
# CONFIGURATION (No changes here)
# ---------------------------------------------------------------------
ACCESS_TOKEN = getattr(settings, 'ITHINK_ACCESS_TOKEN', '51a908dc57d0246eb1a99926feccec20')
SECRET_KEY = getattr(settings, 'ITHINK_SECRET_KEY', '626c25081cbeeead0a6bbd1a395b0546')
PICKUP_ADDRESS_ID = getattr(settings, 'ITHINK_WAREHOUSE_ID', '91710')
STORE_ID = getattr(settings, 'ITHINK_STORE_ID', '23633')
FROM_PINCODE = getattr(settings, 'WAREHOUSE_PINCODE', '421302')
IS_STAGING = getattr(settings, 'ITHINK_IS_STAGING', True)

API_BASE_URL = (
    "https://my.ithinklogistics.com/api_v3"
)

# ---------------------------------------------------------------------
# HELPER (No changes here)
# ---------------------------------------------------------------------
def safe_amount(value):
    """
    Ensure clean numeric string like '1719.20'.
    Removes unwanted spaces, quotes, and commas before converting to Decimal.
    """
    try:
        clean_str = str(value).replace(',', '').replace("'", '').replace('"', '').replace(' ', '').strip()
        value = Decimal(clean_str)
    except Exception:
        value = Decimal('0.00')
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(rounded, '.2f')


# ---------------------------------------------------------------------
# RATE CHECKER
# ---------------------------------------------------------------------
def get_cheapest_rate(order):
    """Fetch cheapest courier rate from iThink Logistics."""
    url = f"{API_BASE_URL}/rate/check.json"

    # --- ✅ UPDATED: Get shipping details from the FIRST product ---
    representative_item = order.items.first()
    if not (representative_item and representative_item.product):
        return {"status": "error", "message": "Order contains no valid items to calculate shipping."}

    # Use values directly from this one product for the entire order
    shipping_weight = representative_item.product.weight
    shipping_length = representative_item.product.length
    shipping_width = representative_item.product.width
    shipping_height = representative_item.product.height
    
    payload_data = {
        "from_pincode": FROM_PINCODE,
        "to_pincode": order.pincode,
        "shipping_weight_kg": safe_amount(shipping_weight),
        "payment_method": order.payment_method,
        "product_mrp": safe_amount(order.subtotal),
        "access_token": ACCESS_TOKEN,
        "secret_key": SECRET_KEY,
        "shipping_length_cms": str(shipping_length),
        "shipping_width_cms": str(shipping_width),
        "shipping_height_cms": str(shipping_height),
        "order_type": "forward",
    }

    try:
        response = requests.post(url, json={"data": payload_data})
        response.raise_for_status()
        api_response = response.json()

        if api_response.get("status") == "success" and api_response.get("data"):
            valid_options = [opt for opt in api_response["data"] if Decimal(opt.get('rate', '0')) > 0]
            if not valid_options:
                return {"status": "error", "message": "No valid courier services found for this pincode."}

            cheapest_option = min(valid_options, key=lambda x: Decimal(x['rate']))
            return {
                "status": "success",
                "courier_name": cheapest_option['logistic_name'],
                "rate": cheapest_option['rate']
            }
        else:
            return {"status": "error", "message": api_response.get("message") or json.dumps(api_response)}

    except requests.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}


# ---------------------------------------------------------------------
# SHIPMENT CREATOR
# ---------------------------------------------------------------------
def create_ithink_order(order, courier_name):
    """Create shipment order in iThink Logistics."""
    url = f"{API_BASE_URL}/order/add.json"
    logistics_partner = "Delhivery" if IS_STAGING else courier_name

    # Product list creation is correct as it iterates through items
    products_list = [
        {
            "product_name": item.product_name,
            "product_sku": (
                item.product.sku if item.product and hasattr(item.product, 'sku')
                else f"PROD-{item.product.id if item.product else 'NA'}"
            ),
            "product_quantity": str(item.quantity),
            "product_price": safe_amount(item.discount_price or item.actual_price),
            "product_tax_rate": "0",
            "product_hsn_code": ""
        }
        for item in order.items.all()
    ]
    
    # --- ✅ UPDATED: Get shipping details from the FIRST product ---
    representative_item = order.items.first()
    if not (representative_item and representative_item.product):
        return {"status": "error", "message": "Order contains no valid items to create shipment."}
        
    shipping_weight = representative_item.product.weight
    shipping_length = representative_item.product.length
    shipping_width = representative_item.product.width
    shipping_height = representative_item.product.height

    # Total amount calculation is also correct
    total_amount_value = sum(
        (item.discount_price or item.actual_price) * item.quantity
        for item in order.items.all()
    )

    # --- Shipment Data ---
    shipments_list = [{
        "order": f"B2B-{order.id}",
        "order_date": order.created_at.strftime("%d-%m-%Y"),
        "total_amount": safe_amount(total_amount_value),
        "payment_mode": "COD" if order.payment_method.upper() == "COD" else "Prepaid",
        "cod_amount": safe_amount(total_amount_value if order.payment_method.upper() == "COD" else 0),
        "name": order.full_name,
        "add": order.address,
        "pin": order.pincode,
        "city": order.city,
        "state": order.state,
        "country": "India",
        "phone": order.phone,
        "email": order.email or "no-email@example.com",
        "weight": safe_amount(shipping_weight),
        "shipment_length": str(shipping_length),
        "shipment_width": str(shipping_width),
        "shipment_height": str(shipping_height),
        "products": products_list,
        "return_address_id": PICKUP_ADDRESS_ID,
        "is_billing_same_as_shipping": "yes",
        "store_id": STORE_ID,
        "api_source": "1",

        # Optional fields
        "add2": "", "add3": "", "company_name": "", "alt_phone": "",
        "waybill": "", "sub_order": "", "gst_number": "", "eway_bill_number": "",
        "reseller_name": "", "what3words": "",
        "shipping_charges": "0", "giftwrap_charges": "0", "transaction_charges": "0",
        "total_discount": "0", "first_attemp_discount": "0",
        "cod_charges": "0",
        "advance_amount": "0"
    }]

    payload_data = {
        "shipments": shipments_list,
        "pickup_address_id": PICKUP_ADDRESS_ID,
        "logistics": logistics_partner,
        "s_type": "",
        "access_token": ACCESS_TOKEN,
        "secret_key": SECRET_KEY
    }

    # Debug print
    print("\n==== IThink Order Payload ====")
    print(json.dumps(payload_data, indent=2))
    print("==============================\n")

    try:
        response = requests.post(url, json={"data": payload_data})
        response.raise_for_status()
        api_response = response.json()

        if api_response.get("status") == "success" and api_response.get("data"):
            shipment_result = api_response["data"]["1"]
            if shipment_result.get("status") == "success":
                return {
                    "status": "success",
                    "waybill": shipment_result.get("waybill"),
                    "courier": shipment_result.get("logistic_name")
                }
            else:
                return {"status": "error", "message": shipment_result.get("remark", "Shipment creation failed.")}
        else:
            return {"status": "error", "message": json.dumps(api_response)}

    except requests.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}
    


def get_rate_for_checkout(pincode, subtotal, cart_items):
    """
    (For Customer Checkout) Fetch cheapest COD rate using raw cart data.
    This function is safe to use before an order is created.
    """
    url = f"{API_BASE_URL}/rate/check.json"

    if not cart_items.exists():
        return {"status": "error", "message": "Cart is empty."}
    
    representative_item = cart_items.first()
    product = representative_item.product
    
    if not product:
        return {"status": "error", "message": "Cart contains an invalid item."}

    # Use details from the first product for the entire shipment
    shipping_weight = product.weight
    shipping_length = product.length
    shipping_width = product.width
    shipping_height = product.height
    
    payload_data = {
        "from_pincode": FROM_PINCODE,
        "to_pincode": pincode,
        "shipping_weight_kg": safe_amount(shipping_weight),
        "payment_method": "COD", # This function is specifically for COD checkout
        "product_mrp": safe_amount(subtotal),
        "access_token": ACCESS_TOKEN,
        "secret_key": SECRET_KEY,
        "shipping_length_cms": str(shipping_length),
        "shipping_width_cms": str(shipping_width),
        "shipping_height_cms": str(shipping_height),
        "order_type": "forward",
    }

    try:
        response = requests.post(url, json={"data": payload_data})
        response.raise_for_status()
        api_response = response.json()

        if api_response.get("status") == "success" and api_response.get("data"):
            valid_options = [opt for opt in api_response["data"] if Decimal(opt.get('rate', '0')) > 0]
            if not valid_options:
                return {"status": "error", "message": "No courier services found for this COD pincode."}

            cheapest_option = min(valid_options, key=lambda x: Decimal(x['rate']))
            # Return a standardized dictionary that the AJAX view can use
            return {
                "status": "success",
                "service_name": cheapest_option['logistic_name'],
                "total_charges": cheapest_option['rate']
            }
        else:
            return {"status": "error", "message": api_response.get("message") or "Could not get rates."}

    except requests.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}