import requests
import json

url = "https://my.ithinklogistics.com/api_v3/warehouse/get.json"

# Your API credentials
# Using the same credentials from the previous script for consistency
payload_data = {
    "access_token": "840004f98101e32cdf1dd35b76de9b29",      # <-- Replace with your Access Token
    "secret_key": "aa676f2223360056ad5e78253de68130",          # <-- Replace with your Secret Key
    "store_id": "24543" }


# The API requires the payload to be nested under a "data" key
payload = json.dumps({"data": payload_data})

headers = {
    'Content-Type': "application/json"
}

try:
    print("Fetching warehouse details...")
    response = requests.request("POST", url, data=payload, headers=headers)
    response.raise_for_status()  # This will raise an exception for HTTP errors
    
    # Pretty print the JSON response
    print("✅ Success! API Response:")
    print(json.dumps(response.json(), indent=4))

except requests.exceptions.HTTPError as errh:
    print(f"Http Error: {errh}")
    print(f"Response Body: {response.text}") # Print error response from server
except requests.exceptions.RequestException as err:
    print(f"An error occurred: {err}")
except json.JSONDecodeError:
    print("Failed to decode JSON from response:")
    print(response.text)