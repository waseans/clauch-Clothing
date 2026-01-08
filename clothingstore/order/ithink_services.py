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

    # ✅ UPDATED: Aggregate shipping details across all items so shipping scales with quantity
    items = [it for it in order.items.all() if it.product]
    if not items:
        return {"status": "error", "message": "Order contains no valid items to calculate shipping."}

    # Total weight should be sum(product.weight * quantity) across items
    total_weight = sum((it.product.weight * it.quantity) for it in items)

    # Compute volumetric weight: sum(volume) / volumetric_divisor
    volumetric_divisor = 5000.0  # common divisor for cm to kg (can be tuned per carrier)
    total_volume = sum((it.product.length * it.product.width * it.product.height) * it.quantity for it in items)
    volumetric_weight = (total_volume / volumetric_divisor) if total_volume > 0 else 0

    # Choose the greater of actual or volumetric weight (carrier uses the higher)
    shipping_weight = max(total_weight, volumetric_weight)

    # For parcel dimensions, we use a simple heuristic: keep max dimensions and
    # scale one dimension proportionally to accommodate multiple items.
    # NOTE: This is a heuristic; a more accurate packing algorithm may be desired.
    shipping_length = max((it.product.length for it in items), default=0)
    shipping_width = max((it.product.width for it in items), default=0)
    # scale height by enough to roughly fit total volume
    base_box_volume = shipping_length * shipping_width * max((it.product.height for it in items), default=0)
    if base_box_volume > 0:
        height_multiplier = max(1, (total_volume / base_box_volume))
    else:
        height_multiplier = 1
    shipping_height = int(max((it.product.height for it in items), default=0) * height_multiplier)
    
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
        # Debug: print payload and computed weights
        print('\n[iThink-debug] get_cheapest_rate payload:', json.dumps(payload_data))
        print('[iThink-debug] computed total_volume(cm3)=', total_volume, 'volumetric_weight(kg)=', round(volumetric_weight,3), 'final_shipping_weight(kg)=', round(float(safe_amount(shipping_weight)),3))

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
    
    # ✅ UPDATED: Aggregate shipping details across all items for accurate shipment creation
    items = [it for it in order.items.all() if it.product]
    if not items:
        return {"status": "error", "message": "Order contains no valid items to create shipment."}

    total_weight = sum((it.product.weight * it.quantity) for it in items)
    volumetric_divisor = 5000.0
    total_volume = sum((it.product.length * it.product.width * it.product.height) * it.quantity for it in items)
    volumetric_weight = (total_volume / volumetric_divisor) if total_volume > 0 else 0
    shipping_weight = max(total_weight, volumetric_weight)

    shipping_length = max((it.product.length for it in items), default=0)
    shipping_width = max((it.product.width for it in items), default=0)
    base_box_volume = shipping_length * shipping_width * max((it.product.height for it in items), default=0)
    if base_box_volume > 0:
        height_multiplier = max(1, (total_volume / base_box_volume))
    else:
        height_multiplier = 1
    shipping_height = int(max((it.product.height for it in items), default=0) * height_multiplier)

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
    

def get_rate_for_checkout(pincode, subtotal, cart_items, payment_method="Prepaid"):
    """
    Fetch cheapest rate using raw cart data for both COD and Prepaid.
    """
    url = f"{API_BASE_URL}/rate/check.json"

    if not cart_items.exists():
        return {"status": "error", "message": "Cart is empty."}
    
    # Aggregate cart items to compute total weight and dimensions
    items = [it for it in cart_items if it.product]
    if not items:
        return {"status": "error", "message": "Cart contains an invalid item."}

    total_weight = sum((it.product.weight * it.quantity) for it in items)
    volumetric_divisor = 5000.0
    total_volume = sum((it.product.length * it.product.width * it.product.height) * it.quantity for it in items)
    volumetric_weight = (total_volume / volumetric_divisor) if total_volume > 0 else 0
    shipping_weight = max(total_weight, volumetric_weight)

    shipping_length = max((it.product.length for it in items), default=0)
    shipping_width = max((it.product.width for it in items), default=0)
    base_box_volume = shipping_length * shipping_width * max((it.product.height for it in items), default=0)
    if base_box_volume > 0:
        height_multiplier = max(1, (total_volume / base_box_volume))
    else:
        height_multiplier = 1
    shipping_height = int(max((it.product.height for it in items), default=0) * height_multiplier)
    
    payload_data = {
        "from_pincode": FROM_PINCODE,
        "to_pincode": pincode,
        "shipping_weight_kg": safe_amount(shipping_weight),
        # Use the variable instead of the hardcoded "COD"
        "payment_method": payment_method, 
        "product_mrp": safe_amount(subtotal),
        "access_token": ACCESS_TOKEN,
        "secret_key": SECRET_KEY,
        "shipping_length_cms": str(shipping_length),
        "shipping_width_cms": str(shipping_width),
        "shipping_height_cms": str(shipping_height),
        "order_type": "forward",
    }

    try:
        # Debug: print payload and computed weights
        print('\n[iThink-debug] get_rate_for_checkout payload:', json.dumps(payload_data))
        print('[iThink-debug] computed total_volume(cm3)=', total_volume, 'volumetric_weight(kg)=', round(volumetric_weight,3), 'final_shipping_weight(kg)=', round(float(safe_amount(shipping_weight)),3))

        response = requests.post(url, json={"data": payload_data})
        response.raise_for_status()
        api_response = response.json()

        if api_response.get("status") == "success" and api_response.get("data"):
            # iThink returns a list of courier options in 'data'
            valid_options = [opt for opt in api_response["data"] if Decimal(opt.get('rate', '0')) > 0]
            if not valid_options:
                return {"status": "error", "message": f"No courier services found for {payment_method} to this pincode."}

            cheapest_option = min(valid_options, key=lambda x: Decimal(x['rate']))
            return {
                "status": "success",
                "service_name": cheapest_option['logistic_name'],
                "total_charges": cheapest_option['rate']
            }
        else:
            return {"status": "error", "message": api_response.get("message") or "Could not get rates."}

    except requests.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}