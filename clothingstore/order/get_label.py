import requests
import json

# Using Staging URL for the label
url = "https://pre-alpha.ithinklogistics.com/api_v3/shipping/label.json"

# --- 1. CONFIGURE YOUR DETAILS HERE ---

# Staging/Test API credentials
access_token = "5a7b40197cd919337501dd6e9a3aad9a"
secret_key = "2b54c373427be180d1899400eeb21aab"

# AWB number from the test order we created successfully
awb_numbers = ["1333110035967"]

# Desired page size for the label
page_size = "A4" # Options: "A4", "A5", "A6"

# Name of the file to save the label as
output_filename = "shipping_label.pdf"

# --- 2. ASSEMBLE THE API REQUEST ---

payload_data = {
    "awb_numbers": ",".join(awb_numbers),
    "page_size": page_size,
    "access_token": access_token,
    "secret_key": secret_key,
    "display_cod_prepaid": "",  # Using default settings
    "display_shipper_mobile": "", # Using default settings
    "display_shipper_address": ""# Using default settings
}

payload = json.dumps({"data": payload_data})
headers = {'Content-Type': "application/json"}

# --- 3. MAKE THE API CALL & SAVE THE FILE ---

try:
    print(f"Requesting shipping label for AWB: {', '.join(awb_numbers)}...")
    response = requests.request("POST", url, data=payload, headers=headers)
    response.raise_for_status() # Check for HTTP errors like 404, 500

    # Check if the response is a PDF file
    if 'application/pdf' in response.headers.get('Content-Type', ''):
        # Open a file in binary write mode and save the content
        with open(output_filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Success! Label saved as '{output_filename}'")
    else:
        # If the response is not a PDF, it's likely an error message
        print("❌ API did not return a PDF. It returned an error:")
        # Try to print the JSON error, or the raw text if it's not JSON
        try:
            print(json.dumps(response.json(), indent=4))
        except json.JSONDecodeError:
            print(response.text)

except requests.exceptions.HTTPError as errh:
    print(f"Http Error: {errh}")
    print(f"Response Body: {response.text}")
except requests.exceptions.RequestException as err:
    print(f"An error occurred: {err}")