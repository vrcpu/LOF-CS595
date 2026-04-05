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

        """
        TODO: Implement this function to retrieve patient documents from Abstractive Health API.
    
        Steps to follow:
        1. Define the API endpoint URL: 
        'https://api.abstractive.ai/retrieve-patient-docs'
        2. Build the JSON payload with the following keys:
        - user_api_email : load from environment variables
        - token : the token obtained from AbstractiveHealthTokenService
        - conversation_id : argument passed to function
        - patient_id : argument passed to function
        - test : argument passed to function
        3. Use requests.post() to send the POST request with the JSON payload.
        4. Check for HTTP errors using resp.raise_for_status().
        5. Return the JSON response from the API.
        """
        # TODO: Step 1 - Define the URL for the API endpoint
    
        # TODO: Step 2 - Create the payload dictionary
    
        # TODO: Step 3 - Send the POST request to the API
    
        # TODO: Step 4 - Handle any potential HTTP errors
    
        # TODO: Step 5 - Return the JSON response