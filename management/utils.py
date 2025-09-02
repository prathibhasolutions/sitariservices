import random
import requests

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_whatsapp(mobile_number, otp):
    url = 'https://api.interakt.ai/v1/public/message/'
    headers = {
        'Authorization': 'Basic UDhqYURhVmhYbEkyd0I5MUxfeDNxSUlDdmFJa3VIV0RBM2hxdW1tWEtlbzo=',
        'Content-Type': 'application/json'
    }
    payload = {
        "countryCode": "+91",
        "phoneNumber": mobile_number,
        "type": "Template",
        "template": {
            "name": "otp_login",
            "languageCode": "en",
            "bodyValues": [otp],
            "buttonValues": {
                "0": [otp]
            }
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    print("INTERAKT API RESPONSE STATUS:", response.status_code)
    print("INTERAKT API RESPONSE BODY:", response.text)
    return response.status_code == 200
