import requests
import json

# Using Staging URL for tracking
url = "https://pre-alpha.ithinklogistics.com/api_v3/order/track.json"

# --- 1. CONFIGURE YOUR DETAILS HERE ---

# Staging/Test API credentials
access_token = "5a7b40197cd919337501dd6e9a3aad9a"
secret_key = "2b54c373427be180d1899400eeb21aab"

# List of Air Waybill (AWB) numbers you want to track.
# I've pre-filled it with the one from your successful order.
awb_numbers_to_track = [
    "1333110035967"
    # To track multiple orders, just add more AWB numbers to this list:
    # "AWB_NUMBER_2",
    # "AWB_NUMBER_3"
]

# --- 2. ASSEMBLE THE API REQUEST ---

# The API expects a single string of comma-separated AWB numbers.
# This line converts our Python list into that format.
awb_string = ",".join(awb_numbers_to_track)

payload_data = {
    "awb_number_list": awb_string,
    "access_token": access_token,
    "secret_key": secret_key
}

payload = json.dumps({"data": payload_data})
headers = {'Content-Type': "application/json"}

# --- 3. MAKE THE API CALL ---

try:
    print(f"Tracking AWB number(s): {awb_string}...")
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