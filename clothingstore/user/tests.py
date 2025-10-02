import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load .env
load_dotenv()

# Initialize Twilio client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_FROM")

def send_test_message(to_number):
    try:
        message = client.messages.create(
            from_=TWILIO_NUMBER,
            to=f"whatsapp:+91{to_number}",
            body="Greetings from Clauch Factory"
        )
        print("Message sent successfully! SID:", message.sid)
        return True
    except Exception as e:
        print("Error sending message:", e)
        return False

send_test_message("7028885969")
