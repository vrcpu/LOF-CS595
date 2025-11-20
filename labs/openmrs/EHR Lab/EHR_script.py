# main_script_final.py
import sys
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from parsing import parse_pdf  # <-- use the attached parsing.py (must be in same dir)

# ------------------------------
# Config
# ------------------------------
BASE_URL = "http://localhost:8080/openmrs"
USERNAME = "admin"
PASSWORD = "Admin123"

# Global CONFIG will be populated dynamically by parsing.parse_pdf(...)
CONFIG = {}

# ------------------------------
# OpenMRS Integration Functions
# ------------------------------
session = requests.Session()
session.auth = HTTPBasicAuth(USERNAME, PASSWORD)


def get_uuid(entity, name):
    """Search entity by name and return its UUID (or None)."""
    if not name:
        return None
    url = f"{BASE_URL}/ws/rest/v1/{entity}?q={name}"
    resp = session.get(url)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0].get("uuid")
        else:
            print(f"❌ No {entity} found with name '{name}'")
    else:
        print(f"❌ Error fetching {entity}: {resp.status_code} - {resp.text}")
    return None


def get_patient_uuid(openmrs_id):
    url = f"{BASE_URL}/ws/rest/v1/patient?q={openmrs_id}"
    resp = session.get(url)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0].get("uuid")
    print("❌ Could not fetch patient UUID for ID:", openmrs_id)
    return None


def create_encounter(patient_uuid):
    encounter_type_uuid = get_uuid("encountertype", CONFIG.get("encounter_type_name"))
    location_uuid = get_uuid("location", CONFIG.get("location_name"))
    provider_uuid = get_uuid("provider", CONFIG.get("provider_name"))
    encounter_role_uuid = get_uuid("encounterrole", CONFIG.get("encounter_role_name"))

    if None in [encounter_type_uuid, location_uuid, provider_uuid, encounter_role_uuid]:
        print("⚠️ Cannot create encounter due to missing UUIDs")
        return None

    url = f"{BASE_URL}/ws/rest/v1/encounter"
    headers = {"Content-Type": "application/json"}
    encounter_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    payload = {
        "encounterDatetime": encounter_datetime,
        "patient": patient_uuid,
        "encounterType": encounter_type_uuid,
        "location": location_uuid,
        "encounterProviders": [
            {"provider": provider_uuid, "encounterRole": encounter_role_uuid}
        ]
    }

    resp = session.post(url, json=payload, headers=headers)
    if resp.status_code == 201:
        encounter_uuid = resp.json()["uuid"]
        print("✅ Encounter created:", encounter_uuid)
        return encounter_uuid
    else:
        print("❌ Error creating encounter:", resp.status_code, resp.text)
        return None


# --- Allergies (now supports multiple) ---
def add_allergies(patient_uuid):
    allergies = CONFIG.get("allergies", [])
    if not allergies:
        print("ℹ️ No allergies to add.")
        return

    for allergy_conf in allergies:
        allergen_name = allergy_conf.get("allergen_name")
        severity_name = allergy_conf.get("severity_name")
        reaction_name = allergy_conf.get("reaction_name")
        comment = allergy_conf.get("comment")

        allergen_uuid = get_uuid("concept", allergen_name)
        severity_uuid = get_uuid("concept", severity_name)
        reaction_uuid = get_uuid("concept", reaction_name)

        if None in [allergen_uuid, severity_uuid, reaction_uuid]:
            print("⚠️ Cannot add allergy due to missing UUID(s) for:", allergen_name)
            continue

        # check duplicates
        url_check = f"{BASE_URL}/ws/rest/v1/patient/{patient_uuid}/allergy"
        resp_check = session.get(url_check)
        duplicate = False
        if resp_check.status_code == 200:
            existing_allergies = resp_check.json().get("results", [])
            for allergy in existing_allergies:
                existing_allergen = allergy.get("allergen", {}).get("codedAllergen", {}).get("uuid")
                if existing_allergen == allergen_uuid:
                    print(f"⚠️ Allergy '{allergen_name}' already exists for patient. Skipping.")
                    duplicate = True
                    break
        else:
            print(f"No Existing Allergies Found! : {resp_check.status_code}")

        if duplicate:
            continue

        payload = {
            "allergen": {"allergenType": "DRUG", "codedAllergen": {"uuid": allergen_uuid}},
            "severity": {"uuid": severity_uuid},
            "reactions": [{"reaction": {"uuid": reaction_uuid}}],
            "comment": comment or f"Patient reports {severity_name.lower()} {reaction_name.lower()} reaction to {allergen_name}."
        }

        url = f"{BASE_URL}/ws/rest/v1/patient/{patient_uuid}/allergy"
        resp = session.post(url, json=payload)
        print(f"Allergy '{allergen_name}':", "✅ Added" if resp.status_code in [200, 201] else f"❌ {resp.text}")


# --- Conditions (supports multiple) ---
def add_conditions(patient_uuid):
    conditions = CONFIG.get("conditions", [])
    if not conditions:
        print("ℹ️ No conditions to add.")
        return

    for cond_conf in conditions:
        condition_name = cond_conf.get("condition_name")
        condition_uuid = get_uuid("concept", condition_name)
        if not condition_uuid:
            print("⚠️ Cannot add condition due to missing UUID for:", condition_name)
            continue

        payload = {
            "patient": patient_uuid,
            "condition": {"coded": condition_uuid},
            "clinicalStatus": cond_conf.get("clinical_status"),
            "verificationStatus": cond_conf.get("verification_status"),
            "onsetDate": cond_conf.get("onset_date")
        }

        url = f"{BASE_URL}/ws/rest/v1/condition"
        resp = session.post(url, json=payload)
        print(f"Condition '{condition_name}':", "✅ Added" if resp.status_code in [200, 201] else f"❌ {resp.text}")


# --- Observations (works as before) ---
def add_observations(patient_uuid):
    obs_conf = CONFIG.get("observations", {})
    if not obs_conf:
        print("ℹ️ No observations to add.")
        return

    obs_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    for concept_name, value in obs_conf.items():
        concept_uuid = get_uuid("concept", concept_name)
        if not concept_uuid:
            print(f"⚠️ Cannot add observation for {concept_name}: UUID not found")
            continue

        payload = {
            "person": patient_uuid,
            "concept": concept_uuid,
            "obsDatetime": obs_datetime,
            "value": value
        }

        url = f"{BASE_URL}/ws/rest/v1/obs"
        resp = session.post(url, json=payload)
        print(f"Observation ({concept_name}):", "✅ Added" if resp.status_code in [200, 201] else f"❌ {resp.text}")


# --- Check existing medication orders for duplicates ---
def medication_exists_in_openmrs(patient_uuid, drug_name):
    url = f"{BASE_URL}/ws/rest/v1/order?patient={patient_uuid}"
    resp = session.get(url)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        for order in results:
            if drug_name.lower() in order.get("display", "").lower() and order.get("action") == "NEW":
                print(f"⚠️ Medication already active in OpenMRS: {order.get('display')}")
                return True
    else:
        print(f"❌ Failed to fetch existing orders: {resp.status_code} - {resp.text}")
    return False


# --- Add medications (supports multiple) ---
def add_medications(patient_uuid, encounter_uuid):
    meds = CONFIG.get("medications", [])
    if not meds:
        print("ℹ️ No medications to add.")
        return

    for med_conf in meds:
        drug_name = med_conf.get("drug_name")
        if not drug_name:
            print("⚠️ Skipping medication with no drug_name.")
            continue

        # skip if already present
        if medication_exists_in_openmrs(patient_uuid, drug_name):
            continue

        # Step 1: Get drug UUID
        drug_uuid = get_uuid("drug", drug_name)
        if not drug_uuid:
            print(f"⚠️ Cannot add medication '{drug_name}': drug not found")
            continue

        # Step 2: Fetch full drug details to get concept UUID
        url = f"{BASE_URL}/ws/rest/v1/drug/{drug_uuid}"
        resp = session.get(url)
        if resp.status_code == 200:
            concept_uuid = resp.json().get("concept", {}).get("uuid")
        else:
            concept_uuid = None

        if not concept_uuid:
            print(f"⚠️ Cannot add medication '{drug_name}': drug concept not found")
            continue

        # Other required UUIDs (permit missing and skip if any not found)
        dose_units_uuid = get_uuid("concept", med_conf.get("dose_units_name"))
        route_uuid = get_uuid("concept", med_conf.get("route_name"))
        frequency_uuid = get_uuid("concept", med_conf.get("frequency_name"))
        duration_units_uuid = get_uuid("concept", med_conf.get("duration_units_name"))
        quantity_units_uuid = get_uuid("concept", med_conf.get("quantity_units_name"))
        care_setting_uuid = get_uuid("caresetting", med_conf.get("care_setting_name"))
        orderer_uuid = get_uuid("provider", med_conf.get("orderer_name"))

        checks = {
            "drug_uuid": drug_uuid,
            "concept_uuid": concept_uuid,
            "dose_units_uuid": dose_units_uuid,
            "route_uuid": route_uuid,
            "frequency_uuid": frequency_uuid,
            "duration_units_uuid": duration_units_uuid,
            "quantity_units_uuid": quantity_units_uuid,
            "care_setting_uuid": care_setting_uuid,
            "orderer_uuid": orderer_uuid,
        }
        missing = [k for k, v in checks.items() if v is None]
        if missing:
            print(f"⚠️ Cannot add medication '{drug_name}' due to missing UUIDs:", missing)
            continue

        payload = {
            "type": "drugorder",
            "patient": patient_uuid,
            "careSetting": care_setting_uuid,
            "encounter": encounter_uuid,
            "orderer": orderer_uuid,
            "drug": drug_uuid,
            "concept": concept_uuid,
            "dose": med_conf.get("dose"),
            "doseUnits": dose_units_uuid,
            "route": route_uuid,
            "frequency": frequency_uuid,
            "duration": med_conf.get("duration"),
            "durationUnits": duration_units_uuid,
            "quantity": med_conf.get("quantity"),
            "quantityUnits": quantity_units_uuid,
            "numRefills": med_conf.get("num_refills", 0)
        }

        url = f"{BASE_URL}/ws/rest/v1/order"
        resp = session.post(url, json=payload)
        if resp.status_code in [200, 201]:
            print(f"Medication '{drug_name}': ✅ Added")
        else:
            try:
                err_msg = resp.json().get("error", {}).get("message", "")
                if "[Order.cannot.have.more.than.one]" in err_msg:
                    print(f"⚠️ Medication '{drug_name}' already exists for patient. Skipping.")
                else:
                    print(f"❌ {resp.text}")
            except Exception:
                print(f"❌ {resp.text}")


# ------------------------------
# Workflow
# ------------------------------
def process_patient(openmrs_id):
    patient_uuid = get_patient_uuid(openmrs_id)
    if not patient_uuid:
        print("⚠️ Cannot proceed without a valid patient UUID.")
        return

    print("✅ Patient UUID:", patient_uuid)

    encounter_uuid = create_encounter(patient_uuid)
    if not encounter_uuid:
        print("⚠️ Encounter creation failed.")
        return

    print("🎯 Encounter creation successful.")

    add_allergies(patient_uuid)
    add_conditions(patient_uuid)
    add_observations(patient_uuid)
    add_medications(patient_uuid, encounter_uuid)


# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    # Example PDF path (replace with actual path)
    pdf_path = "patient_record_updated.pdf" # <-- replace with actual PDF path

    # parse the PDF (from attached parsing.py)
    parsed_config = parse_pdf(pdf_path)
    CONFIG.update(parsed_config)
    # Add openmrs_id for testing here
    openmrs_id = "10001YY"   # <-- replace with actual OpenMRS patient ID
    CONFIG["_openmrs_id"] = openmrs_id

    print("✅ CONFIG prepared from PDF (keys):", list(CONFIG.keys()))
    process_patient(openmrs_id)
