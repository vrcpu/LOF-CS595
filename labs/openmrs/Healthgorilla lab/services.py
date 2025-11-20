import os

import requests

from dotenv import load_dotenv

# Load .env file
load_dotenv()

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


class HealthGorillaTokenService:

    def get_bearer_token(self):
        response = requests.post(BASE_URL + '/hg/token/', json={}, headers=lof_service_request_headers())
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            print(f"Failed to get Health Gorilla token: {response.status_code} : {response.json()['message']}")
            raise Exception(f"Failed to get Health Gorilla token: {response.status_code}")


class IMONLPService:

    def tokenize_text(self, text):
        response = requests.post(BASE_URL + '/imo/nlp', json={'text': text}, headers=lof_service_request_headers())
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to Retrieve IMO Tokens: {response.status_code} : {response.json()['message']}")
            raise Exception(f"Failed to get Retrieve IMO Tokens: {response.status_code}")


class IMONormalizeService:

    def normalize_text(self, entities, domain):
        json_data = {
            "entities": entities,
            "domain": domain,
            "match_field": "input_term",
            "input_code_system": "",
            "threshold": 0
        }
        response = requests.post(BASE_URL + '/imo/normalize', json=json_data, headers=lof_service_request_headers())
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to Normalize Text: {response.status_code} : {response.json()['message']}")
            raise Exception(f"Failed to Normalize Text: {response.status_code}")


class FDBService:

    def get_drug_info(self, drug_name):
        response = requests.get(BASE_URL + '/fdb/smart-search', params={'name': drug_name},
                                headers=lof_service_request_headers())

        response_json = response.json()
        id = response_json['data']['best_match']['id']
        response = requests.get(BASE_URL + f'/fdb/meducation/content', params={'code': id},
                                headers=lof_service_request_headers())

        if response.status_code == 200:
            response_json = response.json()
            name = response_json['title']
            uses = response_json['content']['uses']
            instructions = response_json['content']['instructions']
            cautions = response_json['content']['cautions']
            sideEffects = response_json['content']['sideEffects']
            extra = response_json['content']['extra']
            disclaimer = response_json['content']['disclaimer']

            return {
                'name': name,
                'uses': uses,
                'instructions': instructions,
                'caution': cautions,
                'side_effects': sideEffects,
                'extra': extra,
                'disclaimer': disclaimer
            }
        else:
            print(f"Failed to get FDB drug info: {response.status_code} : {response.json()['message']}")
            raise Exception(f"Failed to get FDB drug info: {response.status_code}")
        
if __name__ == '__main__':
    token = lof_service_request_headers()
    print('LoF Services verified successfully')

    # nlp_service = IMONLPService()
    # with open('sample_note.txt','r') as note:
    #     notes_text = '\n'.join(note.readlines())
    #     import json
    #     print(json.dumps(nlp_service.tokenize_text(text=notes_text)))