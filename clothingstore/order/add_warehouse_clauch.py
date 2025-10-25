import requests
import json

url = "https://my.ithinklogistics.com/api_v3/warehouse/add.json"

# Define the payload as a Python dictionary with your updated data
payload_data = {
    "data": {
        # --- Updated Fields ---
        "company_name": "Clauch Clothing B2B",
        "mobile": "8857885379",
        "address1": "clauch clothing 1st floor near last choice & company , amina compound, Dhamankar Naka",
        "address2": "",
        "pincode": "421302",
        "city_name": "Bhiwandi",
        "state_name": "maharashtra",
        "country_name": "India",
        
        # --- Preserved Credentials ---
        "access_token": "51a908dc57d0246eb1a99926feccec20",
        "secret_key": "626c25081cbeeead0a6bbd1a395b0546"
    }
}

# Convert the dictionary into a JSON string
payload_string = json.dumps(payload_data)

headers = {
    'content-type': "application/json",
    'cache-control': "no-cache"
}

# Send the request with the updated payload string
response = requests.request("POST", url, data=payload_string, headers=headers)

print(response.text)