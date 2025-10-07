import requests
import json
from datetime import datetime, timedelta

# Using Staging URL for getting order details
url = "https://pre-alpha.ithinklogistics.com/api_v3/order/get_details.json"

# --- 1. CONFIGURE YOUR DETAILS HERE ---

# Staging/Test API credentials
access_token = "5a7b40197cd919337501dd6e9a3aad9a"
secret_key = "2b54c373427be180d1899400eeb21aab"

# --- 2. CHOOSE YOUR QUERY METHOD ---

# METHOD 1: Get details for specific AWB numbers (default)
awb_numbers_to_get = ["1333110035967"] # Pre-filled with the AWB from your successful test
payload_data = {
    "awb_number_list": ",".join(awb_numbers_to_get),
    "start_date": "", # Leave blank when querying by AWB
    "end_date": "",   # Leave blank when querying by AWB
    "access_token": access_token,
    "secret_key": secret_key
}

# # METHOD 2: Get all orders in a date range (uncomment to use)
# today = datetime.now()
# seven_days_ago = today - timedelta(days=7)
# payload_data = {
#     "awb_number_list": "", # Leave blank when querying by date
#     "start_date": seven_days_ago.strftime("%Y-%m-%d"),
#     "end_date": today.strftime("%Y-%m-%d"),
#     "access_token": access_token,
#     "secret_key": secret_key
# }

# --- 3. ASSEMBLE AND MAKE THE API CALL ---

payload = json.dumps({"data": payload_data})
headers = {'Content-Type': "application/json"}

try:
    print(f"Fetching order details...")
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