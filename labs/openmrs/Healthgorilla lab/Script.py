import csv
import json
import random
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth
from services import HealthGorillaTokenService

# ---------------- CONFIG ----------------
HG_BASE_URL = "https://sandbox.healthgorilla.com/fhir"
OPENMRS_BASE_URL = "http://localhost:8080/openmrs/ws/rest/v1"
OPENMRS_USERNAME = "admin"
OPENMRS_PASSWORD = "Admin123"
CSV_FILE = "patients.csv"
# ----------------------------------------

session = requests.Session()
session.auth = HTTPBasicAuth(OPENMRS_USERNAME, OPENMRS_PASSWORD)
session.headers.update({"Content-Type": "application/json"})


# ---------- Utility: CSV + ID ----------
def load_patients_from_csv(csv_file):
    patients = []
    with open(csv_file, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patients.append(row)
    return patients


def generate_openmrs_id(base_number: int):
    valid_chars = '0123456789ACDEFGHJKLMNPRTUVWXY'
    base_str = str(base_number)
    total, factor = 0, 2
    for char in reversed(base_str):
        code_point = valid_chars.index(char)
        addend = factor * code_point
        factor = 1 if factor == 2 else 2
        addend = (addend // len(valid_chars)) + (addend % len(valid_chars))
        total += addend
    remainder = total % len(valid_chars)
    check_code_point = (len(valid_chars) - remainder) % len(valid_chars)
    return f"{base_str}{valid_chars[check_code_point]}"


# ---------- Health Gorilla Retrieval ----------
def retrieve_patient_from_hg(patient):
   """
    TODO: Implement this function.
    Purpose:
        Retrieve a FHIR Patient from Health Gorilla based on the 
        patient's first name, last name, and birthdate.
    Steps:
        1. Construct the Health Gorilla API URL and parameters.
        2. Use the bearer token from HealthGorillaTokenService for authentication.
        3. Send a GET request to /Patient endpoint.
        4. Parse the response JSON and return the first matching patient entry.
        5. Handle cases where no patient is found or any error occurs.
    """


# ---------- Fetch Conditions from Health Gorilla ----------
def fetch_conditions_from_hg(patients_data, output_file="retrieved_conditions.json"):
    """Fetch all conditions for each HG patient and save to JSON."""
    token_service = HealthGorillaTokenService()
    headers = {"Authorization": f"Bearer {token_service.get_bearer_token()}"}

    all_conditions = {}

    print("\n📥 Fetching conditions for each Health Gorilla patient...")
    for patient_key, patient_info in patients_data.items():
        resource = patient_info.get("resource", {})
        patient_id = resource.get("id")
        if not patient_id:
            print(f"⚠️ Skipping {patient_key} (missing HG ID)")
            continue

        url = f"{HG_BASE_URL}/Condition"
        params = {"patient": patient_id}
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            cond_data = resp.json()
            entries = cond_data.get("entry", [])
            all_conditions[patient_key] = {"conditions": entries}
            print(f"✅ Retrieved {len(entries)} total conditions for {patient_key}")
        except Exception as e:
            print(f"❌ Error retrieving conditions for {patient_key}: {e}")
            all_conditions[patient_key] = {"error": str(e)}

    with open(output_file, "w") as f:
        json.dump(all_conditions, f, indent=4)
    print(f"\n✅ Saved all retrieved conditions → {output_file}")
    return all_conditions


# ---------- Create Patient in OpenMRS ----------
def create_openmrs_patient(fhir_patient):
    """Transform and post FHIR Patient to OpenMRS."""
    resource = fhir_patient.get("resource", {})
    name_data = resource.get("name", [{}])[0]
    address_data = resource.get("address", [{}])[0]

    openmrs_identifier = generate_openmrs_id(random.randint(10000, 99999))
    payload = {
        "person": {
            "names": [{"givenName": name_data.get("given", [""])[0], "familyName": name_data.get("family", "")}],
            "gender": resource.get("gender", "")[0].upper() if resource.get("gender") else "",
            "birthdate": resource.get("birthDate", ""),
            "addresses": [{
                "address1": address_data.get("line", [""])[0],
                "cityVillage": address_data.get("city", ""),
                "country": address_data.get("country", "")
            }]
        },
        "identifiers": [{
            "identifier": openmrs_identifier,
            "identifierType": "05a29f94-c0ed-11e2-94be-8c13b969e334",
            "location": "8d6c993e-c2cc-11de-8d13-0010c6dffd0f",
            "preferred": True
        }]
    }

    resp = session.post(f"{OPENMRS_BASE_URL}/patient", json=payload)
    if resp.status_code in [200, 201]:
        uuid = resp.json()["uuid"]
        print(f"✅ Patient {name_data.get('family', '')} created in OpenMRS (UUID: {uuid})")
        return uuid
    else:
        print(f"❌ Failed to create patient: {resp.status_code} {resp.text}")
        return None


# ---------- Helper: Normalize Date ----------
def normalize_date(onset_date):
    """Ensure date is in ISO8601 format acceptable by OpenMRS."""
    if not onset_date:
        return None
    try:
        # Case: YYYY-MM-DD
        if len(onset_date) == 10 and "-" in onset_date:
            return onset_date + "T00:00:00.000+0000"
        # Case: Only year or year-month
        elif len(onset_date) in [4, 7]:
            dt = datetime.strptime(onset_date + "-01"*(len(onset_date)==4), "%Y-%m-%d")
            return dt.strftime("%Y-%m-%dT00:00:00.000+0000")
        # Already ISO
        elif "T" in onset_date:
            return onset_date
    except Exception:
        pass
    return None


# ---------- Ensure Concept ----------
def get_uuid(entity, name):
    if not name:
        return None
    url = f"{OPENMRS_BASE_URL}/{entity}?q={name}"
    resp = session.get(url)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0].get("uuid")
    return None


def ensure_concept_exists(condition_name):
    uuid = get_uuid("concept", condition_name)
    if uuid:
        return uuid

    print(f"🆕 Creating new concept for '{condition_name}'...")
    concept_payload = {
        "names": [{"name": condition_name, "locale": "en", "conceptNameType": "FULLY_SPECIFIED", "localePreferred": True}],
        "datatype": "N/A",
        "conceptClass": "Diagnosis",
        "descriptions": [{"description": "Imported from Health Gorilla (non-coded condition)", "locale": "en"}]
    }

    resp = session.post(f"{OPENMRS_BASE_URL}/concept", json=concept_payload)
    if resp.status_code == 201:
        uuid = resp.json()["uuid"]
        print(f"✅ Created concept '{condition_name}' (UUID: {uuid})")
        return uuid
    else:
        print(f"❌ Failed to create concept '{condition_name}': {resp.status_code}")
        return None


# ---------- Add Conditions ----------
def add_conditions(patient_uuid, conditions):
    for cond in conditions:
        name = cond["condition_name"]
        concept_uuid = ensure_concept_exists(name)
        if not concept_uuid:
            continue

        iso_date = normalize_date(cond.get("onset_date"))
        payload = {
            "patient": patient_uuid,
            "condition": {"coded": concept_uuid},
            "clinicalStatus": cond.get("clinical_status", "ACTIVE"),
            "verificationStatus": cond.get("verification_status", "CONFIRMED")
        }
        if iso_date:
            payload["onsetDate"] = iso_date

        resp = session.post(f"{OPENMRS_BASE_URL}/condition", json=payload)
        if resp.status_code in [200, 201]:
            print(f"✅ Condition '{name}' added.")
        else:
            print(f"❌ Failed to add '{name}': {resp.status_code} → {resp.text[:150]}")


# ---------- Upload Conditions ----------
"""
# TODO: Implement upload_conditions(patient_uuid, hg_conditions, max_conditions=20)
# This function should:
# 1. Loop through up to `max_conditions` entries in `hg_conditions`.
# 2. Extract the condition name (from resource → code → coding → display) and onset date.
# 3. Skip any condition without a valid name.
# 4. Prepare a list of dictionaries containing:
#       - condition_name
#       - clinical_status
#       - verification_status
#       - onset_date
# 5. Finally, call the add_conditions() function to upload these prepared conditions to OpenMRS.
"""

def upload_conditions(patient_uuid, hg_conditions, max_conditions=20):
   # TODO: Write your code here to prepare the `prepared` list based on HG conditions
    add_conditions(patient_uuid, prepared)


# ---------- Main ----------
def main():
    print("\n📥 Reading patients from CSV...")
    patients = load_patients_from_csv(CSV_FILE)

    retrieved_patients = {}
    for patient in patients:
        #result = retrieve_patient_from_hg(patient)
        if result:
            key = f"{patient['First Name']}_{patient['Last Name']}"
            retrieved_patients[key] = result

    with open("retrieved_patients.json", "w") as f:
        json.dump(retrieved_patients, f, indent=4)
    print("✅ Retrieved Health Gorilla patients saved to retrieved_patients.json")

    all_conditions = fetch_conditions_from_hg(retrieved_patients)

    print("\n📤 Creating patients in OpenMRS and uploading conditions...")
    for key, data in retrieved_patients.items():
        uuid = create_openmrs_patient(data)
        if not uuid:
            continue
        conds = all_conditions.get(key, {}).get("conditions", [])
        #upload_conditions(uuid, conds)

    print("\n✅ Pipeline complete — Patients and Conditions synced successfully ")


if __name__ == "__main__":
    main()
