# services.py
import os
import requests

# --------------------------
# Search Patient
# --------------------------
class AH_Services:
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