# services.py
import os
import requests

# --------------------------
# Verify OpenMRS / LOF Services
# --------------------------
def verify_lof_services():
    # Dummy check; replace with your actual OpenMRS API verification if needed
    print("LoF / OpenMRS Services verified successfully")

BASE_URL = 'https://api.leapoffaith.com/api/service'
BASE_HEADERS = {
    "Content-Type": "application/json"
}

def get_lof_auth_token():
    lof_credentials = {
        "client_id": os.getenv('client_id'),
        "client_secret": os.getenv('client_secret')
    }
    response = requests.post(BASE_URL + '/generate-access-token/', json=lof_credentials, headers=BASE_HEADERS)
    if response.status_code == 200:
        return response.status_code, response.json()['access_token']
    return response.status_code, response.json()['error']


def lof_service_request_headers():
    status_code, lof_auth_token = get_lof_auth_token()
    if status_code == 200:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + lof_auth_token
        }
    else:
        print(f"Failed to get LoF auth token: {status_code} : {lof_auth_token}")
        raise Exception(f"Failed to get LoF auth token: {status_code}")


# --------------------------
# Get AH Token
# --------------------------
def get_ah_token():
    AH_EMAIL = os.getenv("AH_EMAIL")
    AH_USERNAME = os.getenv("AH_USERNAME")
    AH_PASSWORD = os.getenv("AH_PASSWORD")
    
    url = "https://api.abstractive.ai/get-token"
    payload = {
        "user_api_email": AH_EMAIL,
        "username_api": AH_USERNAME,
        "user_api_password": AH_PASSWORD
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("status") != "success":
        raise Exception(f"Failed to get token: {data}")
    return data['access_token']

# --------------------------
# Search Patient
# --------------------------
def search_patient(token, patient, test=True):
    url = "https://api.abstractive.ai/search-patient"
    payload = {
        "user_api_email": os.getenv("AH_EMAIL"),
        "token": token,
        "patient_metadata": [
            {
                "demographics": {
                    "given_name": patient['First Name'],
                    "family_name": patient['Last Name'],
                    "administrative_gender_code": patient['Gender'],
                    "birth_time": patient['Birth Date'].replace("-", ""),
                    "phone_number": patient.get('Phone', ''),
                    "email": patient.get('Email', '')
                },
                "addresses": [
                    {
                        "street_address_line": patient.get('Address', ''),
                        "city": patient.get('City', ''),
                        "state": patient.get('State', ''),
                        "postal_code": patient.get('ZIP', ''),
                        "country": patient.get('Country', 'USA')
                    }
                ]
            }
        ],
        "robustness": "20",
        "test": test
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

# --------------------------
# Retrieve Patient Documents
# --------------------------
def retrieve_patient_docs(token, conversation_id, patient_id, test=True):
    url = "https://api.abstractive.ai/retrieve-patient-docs"
    payload = {
        "user_api_email": os.getenv("AH_EMAIL"),
        "token": token,
        "conversation_id": conversation_id,
        "patient_id": patient_id,
        "test": test
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()