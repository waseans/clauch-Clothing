import requests
import json

url = "https://my.ithinklogistics.com/api_v3/rate/check.json"

# Your shipment details (using your provided credentials for the example)
payload_data = {
    "from_pincode": "421302",
    "to_pincode": "440016",
    "shipping_length_cms": "20",
    "shipping_width_cms": "15",
    "shipping_height_cms": "10",
    "shipping_weight_kg": "2",
    "order_type": "forward",
    "payment_method": "COD",
    "product_mrp": "500.00",
    "access_token": "840004f98101e32cdf1dd35b76de9b29",
    "secret_key": "aa676f2223360056ad5e78253de68130"
}

# The API requires the payload to be nested under a "data" key
payload = json.dumps({"data": payload_data})

headers = {
    'Content-Type': "application/json"
}

try:
    response = requests.request("POST", url, data=payload, headers=headers)
    response.raise_for_status()
    
    # --- MODIFIED PART ---
    # Parse the JSON response
    api_response = response.json()
    
    # Check if the API call was successful and data exists
    if api_response.get("status") == "success" and api_response.get("data"):
        courier_options = api_response["data"]
        
        # Find the dictionary with the minimum 'rate'
        cheapest_option = min(courier_options, key=lambda x: x['rate'])
        
        print("✅ Cheapest Shipping Option Found:")
        print("---------------------------------")
        print(f"   Courier: {cheapest_option['logistic_name']}")
        print(f"   Rate: ₹{cheapest_option['rate']}")
        print(f"   Delivery Estimate: {api_response.get('expected_delivery_date', 'N/A')}")
        print("---------------------------------")
        # You can print the full dictionary for the cheapest option if you need more details
        # print("\nFull details:")
        # print(json.dumps(cheapest_option, indent=4))

    else:
        # Handle cases where status is not 'success' or data is missing
        print("API call was not successful or returned no data.")
        print(json.dumps(api_response, indent=4))

except requests.exceptions.RequestException as err:
    print(f"An error occurred: {err}")
except json.JSONDecodeError:
    print("Failed to decode JSON from response:")
    print(response.text)