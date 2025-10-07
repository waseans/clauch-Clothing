import requests
import json
from datetime import datetime

# Using Staging URL as requested for testing
url = "https://pre-alpha.ithinklogistics.com/api_v3/order/add.json"

# --- 1. CONFIGURE YOUR DETAILS HERE ---

# --- 1. CONFIGURE YOUR DETAILS HERE ---

# Staging/Test API credentials
access_token = "5a7b40197cd919337501dd6e9a3aad9a"
secret_key = "2b54c373427be180d1899400eeb21aab"

# Your specific IDs from previous API calls
pickup_address_id = "1293"       # Your Warehouse ID
return_address_id = "1293"       # Your Return Address ID
store_id = "24543"               # <-- Your Store ID we found earlier

# Staging server only allows "Delhivery"
logistics_partner = "Delhivery"

# --- 2. DEFINE THE ORDER PAYLOAD ---

unique_order_id = f"SDK-FINAL-{int(datetime.now().timestamp())}"
current_date = datetime.now().strftime("%d-%m-%Y")

products_list = [
    {"product_name": "Test Product - Blue Shirt", "product_sku": "TS-BLUE-01", "product_quantity": "1", "product_price": "500.00", "product_tax_rate": "5", "product_hsn_code": "610910"}
]

shipments_list = [
    {
        # Core Order Details
        "order": unique_order_id, "order_date": current_date, "total_amount": "500.00", "payment_mode": "COD", "cod_amount": "500.00",
        
        # --- Customer Details (Now with all address lines) ---
        "name": "Test Customer", "company_name": "", "add": "123, Test Society, Main Road", "add2": "", "add3": "", "pin": "411045", "city": "Pune", "state": "Maharashtra", "country": "India", "phone": "9988776655", "alt_phone": "", "email": "test@example.com",
        
        # Package & Product Details
        "weight": "0.5", "shipment_length": "15", "shipment_width": "10", "shipment_height": "5", "products": products_list,
        
        # Address & Billing
        "return_address_id": return_address_id, "is_billing_same_as_shipping": "yes",
        
        # All Optional Fields Required by Validator
        "waybill": "", "sub_order": "", "gst_number": "", "eway_bill_number": "", "reseller_name": "", "what3words": "",
        "shipping_charges": "0", "giftwrap_charges": "0", "transaction_charges": "0", "total_discount": "0", "first_attemp_discount": "0", "cod_charges": "0", "advance_amount": "0",
        "store_id": store_id, "api_source": "1"
    }
]

# --- 3. ASSEMBLE THE FINAL API REQUEST DATA ---

payload_data = {
    "shipments": shipments_list,
    "pickup_address_id": pickup_address_id,
    "logistics": logistics_partner,
    "s_type": "",
    "access_token": access_token,
    "secret_key": secret_key
}

payload = json.dumps({"data": payload_data})
headers = {'Content-Type': "application/json"}

# --- 4. MAKE THE API CALL ---

try:
    print(f"Attempting to create order: {unique_order_id}...")
    response = requests.request("POST", url, data=payload, headers=headers)
    response.raise_for_status()
    
    print("✅ Success! API Response:")
    print(json.dumps(response.json(), indent=4))

except requests.exceptions.HTTPError as errh:
    print(f"Http Error: {errh}")
    print(f"Response Body: {response.text}")
except requests.exceptions.RequestException as err:
    print(f"An error occurred: {err}")
except json.JSONDecodeError:
    print("Failed to decode JSON from response:")
    print(response.text)
