import json
import random
import os
import requests
import re
from requests.auth import HTTPBasicAuth
from datetime import datetime

# ---------------- CONFIG ----------------
OPENMRS_BASE_URL = "http://localhost:8080/openmrs/ws/rest/v1"
OPENMRS_USERNAME = "admin"
OPENMRS_PASSWORD = "Admin123"
JSON_DIR = "Patient_data"

ENCOUNTER_TYPE_UUID = "67a71486-1a54-468f-ac3e-7091a9a79584"  # Adult Initial
LOCATION_UUID = "8d6c993e-c2cc-11de-8d13-0010c6dffd0f"
DRUG_ORDER_TYPE_UUID = "131168f4-15f5-102d-96e4-000c29c2a5d7"  # Drug Order Type
# ----------------------------------------

session = requests.Session()
session.auth = HTTPBasicAuth(OPENMRS_USERNAME, OPENMRS_PASSWORD)
session.headers.update({"Content-Type": "application/json"})

# ---------- Generate OpenMRS Patient Identifier ----------
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

# ---------- Create Patient ----------
def create_openmrs_patient(patient_json):
    name = patient_json.get("name", "")
    gender = patient_json.get("gender", "")
    birthdate = patient_json.get("birthDate", "")
    openmrs_identifier = generate_openmrs_id(random.randint(10000, 99999))

    payload = {
        "person": {
            "names": [{"givenName": name.split(" ")[0], "familyName": " ".join(name.split(" ")[1:])}],
            "gender": gender[0].upper() if gender else "",
            "birthdate": birthdate,
        },
        "identifiers": [{
            "identifier": openmrs_identifier,
            "identifierType": "05a29f94-c0ed-11e2-94be-8c13b969e334",
            "location": LOCATION_UUID,
            "preferred": True
        }]
    }

    resp = session.post(f"{OPENMRS_BASE_URL}/patient", json=payload)
    if resp.status_code in [200, 201]:
        uuid = resp.json()["uuid"]
        print(f"✅ Patient '{name}' created (UUID: {uuid})")
        return uuid
    else:
        print(f"❌ Failed to create patient '{name}': {resp.text}")
        return None

# ---------- Create Encounter ----------
def create_encounter(patient_uuid):
    payload = {
        "patient": patient_uuid,
        "encounterType": ENCOUNTER_TYPE_UUID,
        "location": LOCATION_UUID,
        "encounterDatetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    }

    r = session.post(f"{OPENMRS_BASE_URL}/encounter", json=payload)
    if r.status_code in [200, 201]:
        return r.json()["uuid"]
    else:
        print(f"❌ Failed to create encounter: {r.text}")
        return None

# ---------- Get Concept UUID ----------
def get_concept_uuid(name):
    url = f"{OPENMRS_BASE_URL}/concept?q={name}"
    r = session.get(url)
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            return results[0]["uuid"]
    return None

# ---------- Create Concept ----------
def create_concept(name):
    payload = {
        "names": [{
            "name": name,
            "locale": "en",
            "conceptNameType": "FULLY_SPECIFIED",
            "localePreferred": True
        }],
        "datatype": "N/A",
        "conceptClass": "Drug"
    }

    r = session.post(f"{OPENMRS_BASE_URL}/concept", json=payload)
    if r.status_code == 201:
        print(f"🆕 Created concept '{name}'")
        return r.json()["uuid"]
    else:
        print(f"❌ Failed to create concept '{name}': {r.text}")
        return None

# ---------- Add Conditions ----------

def add_conditions(patient_uuid, conditions):
    seen_concepts = set()

    for cond in conditions:
        concept_uuid = get_concept_uuid(cond)
        if not concept_uuid:
            concept_uuid = create_concept(cond)

        if concept_uuid in seen_concepts:
            print(f"⚠️ Skipping duplicate condition: {cond}")
            continue

        seen_concepts.add(concept_uuid)

        payload = {
            "patient": patient_uuid,
            "condition": {"coded": concept_uuid},
            "clinicalStatus": "ACTIVE",
            "verificationStatus": "CONFIRMED"
        }

        r = session.post(f"{OPENMRS_BASE_URL}/condition", json=payload)
        if r.status_code in [200, 201]:
            print(f"✅ Condition '{cond}' added")
        else:
            print(f"❌ Failed to add condition '{cond}': {r.text}")
            

# ---------- Add Medications ----------

## --- Helper Functions ---
# ---------- Drug Helpers ----------

def get_drug_uuid_by_name(name):
    r = session.get(f"{OPENMRS_BASE_URL}/drug?q={requests.utils.quote(name)}&v=default")
    if r.status_code == 200:
        for d in r.json().get("results", []):
            if d["display"].lower() == name.lower():
                return d["uuid"]
    return None


def create_drug(name, concept_uuid):
    payload = {
        "name": name,
        "concept": concept_uuid,
        "combination": False   # ⭐ REQUIRED by OpenMRS
    }

    r = session.post(f"{OPENMRS_BASE_URL}/drug", json=payload)
    if r.status_code in [200, 201]:
        print(f"🆕 Created drug '{name}'")
        return r.json()["uuid"]
    else:
        print(f"❌ Failed to create drug '{name}': {r.text}")
        return None
    
def get_first_provider_uuid():
    # Try to find any provider; best is to search by "admin" or "Super User"
    r = session.get(f"{OPENMRS_BASE_URL}/provider?q=admin&v=default")
    if r.status_code == 200 and r.json().get("results"):
        return r.json()["results"][0]["uuid"]

    r = session.get(f"{OPENMRS_BASE_URL}/provider?v=default")
    if r.status_code == 200 and r.json().get("results"):
        return r.json()["results"][0]["uuid"]

    return None

def find_concept_by_exact_name(name):
    r = session.get(f"{OPENMRS_BASE_URL}/concept?q={name}&v=default")
    if r.status_code == 200:
        for c in r.json().get("results", []):
            if c["display"].lower() == name.lower():
                return c["uuid"]
    return None

def get_frequency_uuid_by_name(name):
    url = f"{OPENMRS_BASE_URL}/orderfrequency?v=default"
    r = session.get(url)

    if r.status_code != 200:
        print("❌ Unable to fetch order frequencies:", r.text)
        return None

    for freq in r.json().get("results", []):
        if freq.get("display", "").lower() == name.lower():
            return freq.get("uuid")

    print(f"❌ Frequency '{name}' not found in OpenMRS")
    return None

def add_medications(patient_uuid, encounter_uuid, medications):
    orderer_uuid = get_first_provider_uuid()
    dose_units_uuid = get_concept_uuid("Tablet")
    route_uuid = get_concept_uuid("Oral")
    frequency_uuid = get_concept_uuid("Once Daily")

    for med in medications:
        parts = med.split(":")
        drug_name = parts[0].strip()
        start_date_raw = parts[1].strip() if len(parts) > 1 else "01/01/1981"
        start_date = datetime.strptime(start_date_raw, "%m/%d/%Y").strftime("%Y-%m-%dT%H:%M:%S.000+0000")

        print("Drug Name:", drug_name)

        # 1️⃣ Get or create concept
        concept_uuid = get_concept_uuid(drug_name)
        if not concept_uuid:
            concept_uuid = create_concept(drug_name)

        # 2️⃣ Get or create drug
        drug_uuid = get_drug_uuid_by_name(drug_name)
        if not drug_uuid:
            drug_uuid = create_drug(drug_name, concept_uuid)

        print(f"Concept UUID: {concept_uuid}")
        print(f"Drug UUID: {drug_uuid}")
        print("Start Date:", start_date)

        payload = {
            "type": "drugorder",
            "action": "NEW",
            "careSetting": "OUTPATIENT",
            "patient": patient_uuid,
            "encounter": encounter_uuid,
            "concept": concept_uuid,
            "drug": drug_uuid,   # ⭐ THIS is the key fix
            "orderType": DRUG_ORDER_TYPE_UUID,
            "orderer": orderer_uuid,
            "dose": 1,
            "doseUnits": dose_units_uuid,
            "route": route_uuid,
            "frequency": frequency_uuid,
            "quantity": 30,
            "numRefills": 0,
            "quantityUnits": dose_units_uuid,
        }

        r = session.post(f"{OPENMRS_BASE_URL}/order", json=payload)
        if r.status_code in [200, 201]:
            print(f"✅ Medication '{drug_name}' added")
        else:
            print(f"❌ Failed to add medication '{drug_name}': {r.text[:700]}")



# -------------------- Vitals --------------------

VITAL_CONCEPT_QUERY = {
    "temperature": ("Temperature", "Numeric"),
    "weight": ("Weight", "Numeric"),
    "height": ("Height", "Numeric"),
    "bmi": ("Body mass index", "Numeric"),
    "blood_pressure": ("Blood Pressure", "Text"),  
}

def parse_vital_line(line: str):
    """
    Parses lines like:
      temperature: 98[degF] at 12/12/2023
      blood pressure systolic: 120mm[Hg] at 12/12/2023
      bmi: 26.44kg/m2 at 12/12/2023

    Returns dict: {name, value, unit, date}
    """
    line = line.strip()

    # Split " at "
    if " at " not in line:
        return None

    left, date_str = line.rsplit(" at ", 1)
    date_str = date_str.strip()

    # Split "name: rest"
    if ":" not in left:
        return None

    name, rest = left.split(":", 1)
    name = name.strip().lower()
    rest = rest.strip()

    # Extract numeric at the beginning (int or float)
    m = re.match(r"^([-+]?\d+(?:\.\d+)?)\s*(.*)$", rest)
    if not m:
        return None

    value = float(m.group(1))
    unit = (m.group(2) or "").strip()

    # Normalize unit a bit:
    # If it's like "[degF]" keep "degF"
    if unit.startswith("[") and unit.endswith("]"):
        unit = unit[1:-1].strip()

    # If it's like "mm[Hg]" keep as "mm[Hg]" (that's fine)
    # If empty unit, keep ""

    return {
        "name": name,
        "value": value,
        "unit": unit,
        "date": date_str
    }

# -- Unit conversion --
def f_to_c(f): 
    return (f - 32) * 5.0 / 9.0

def lb_to_kg(lb):
    return lb * 0.45359237

def in_to_cm(inches):
    return inches * 2.54

def create_obs(patient_uuid, encounter_uuid, concept_uuid, obs_datetime, value_numeric=None, value_text=None):
    payload = {
        "person": patient_uuid,
        "encounter": encounter_uuid,
        "concept": concept_uuid,
        "obsDatetime": obs_datetime
    }
    if value_numeric is not None:
        payload["value"] = value_numeric
    elif value_text is not None:
        payload["value"] = value_text
    else:
        raise ValueError("Need value_numeric or value_text")

    r = session.post(f"{OPENMRS_BASE_URL}/obs", json=payload)
    if r.status_code in [200, 201]:
        return True
    print("❌ Obs failed:", r.text)
    return False


def get_concept_uuid_by_name_and_datatype(q, desired_datatype):
    """
    desired_datatype examples: 'Numeric', 'Text', 'Coded'
    """
    r = session.get(f"{OPENMRS_BASE_URL}/concept?q={requests.utils.quote(q)}&v=full")
    if r.status_code != 200:
        return None

    results = r.json().get("results", [])
    desired_datatype = desired_datatype.lower()

    # Prefer exact-ish matches AND correct datatype
    for c in results:
        dt = (c.get("datatype", {}) or {}).get("display", "")
        if dt.lower() == desired_datatype:
            return c.get("uuid")

    # If nothing matches datatype, return None
    return None

def add_vitals(patient_uuid, encounter_uuid, vitals_lines):
    # Resolve the correct concepts once (datatype-safe)
    temp_uuid = get_concept_uuid_by_name_and_datatype("Temperature", "Numeric")
    wt_uuid   = get_concept_uuid_by_name_and_datatype("Weight", "Numeric")
    ht_uuid   = get_concept_uuid_by_name_and_datatype("Height", "Numeric")
    bmi_uuid  = get_concept_uuid_by_name_and_datatype("Body mass index", "Numeric")

    # For BP, simplest approach = store "120/80" as TEXT.
    # If your "Blood Pressure" concept is Numeric in your dictionary, this will return None.
    #bp_uuid   = get_concept_uuid_by_name_and_datatype("Blood Pressure", "Text")

    sbp_uuid  = get_concept_uuid_by_name_and_datatype("Systolic blood pressure", "Numeric")
    dbp_uuid  = get_concept_uuid_by_name_and_datatype("Diastolic blood pressure", "Numeric")

    # If BP Text concept not found, fall back to just searching and using it as Text anyway
    # (some OpenMRS configs use "Blood pressure" casing)
    # if not bp_uuid:
    #     bp_uuid = get_concept_uuid_by_name_and_datatype("Blood pressure", "Numeric")

    if not sbp_uuid:
        sbp_uuid = get_concept_uuid_by_name_and_datatype("Systolic BP", "Numeric")
    if not dbp_uuid:
        dbp_uuid = get_concept_uuid_by_name_and_datatype("Diastolic BP", "Numeric")
        
    # Basic safety warnings (do not crash lab)
    if not temp_uuid: print("⚠️ Temperature concept (Numeric) not found")
    if not wt_uuid:   print("⚠️ Weight concept (Numeric) not found")
    if not ht_uuid:   print("⚠️ Height concept (Numeric) not found")
    if not bmi_uuid:  print("⚠️ Body mass index concept (Numeric) not found")
    # if not bp_uuid:   print("⚠️ Blood Pressure concept (Text) not found (BP will be skipped)")
    if not sbp_uuid:  print("⚠️ Systolic blood pressure (Numeric) concept not found; skipping SBP")
    if not dbp_uuid:  print("⚠️ Diastolic blood pressure (Numeric) concept not found; skipping DBP")

    # Capture BP to combine
    bp_sys = None
    bp_dia = None
    bp_date = None

    for line in vitals_lines:
        parsed = parse_vital_line(line)
        if not parsed:
            print("⚠️ Could not parse vital:", line)
            continue

        name = parsed["name"]          
        value = parsed["value"]
        unit = (parsed["unit"] or "").strip()
        dt = datetime.strptime(parsed["date"], "%m/%d/%Y").strftime("%Y-%m-%d %H:%M:%S")

        # BP capture
        if name == "blood pressure systolic":
            bp_sys, bp_date = int(value), dt
            continue
        if name == "blood pressure diastolic":
            bp_dia, bp_date = int(value), dt
            continue

        # Temperature
        if name == "temperature":
            if not temp_uuid:
                continue
            # Handle degF -> C
            c = f_to_c(value) if unit.lower() in ("degf", "[degf]") else value
            create_obs(patient_uuid, encounter_uuid, temp_uuid, dt, value_numeric=round(c, 2))
            continue

        # Weight
        if name == "weight":
            if not wt_uuid:
                continue
            kg = lb_to_kg(value) if unit.lower() in ("lb_av", "[lb_av]") else value
            create_obs(patient_uuid, encounter_uuid, wt_uuid, dt, value_numeric=round(kg, 2))
            continue

        # Height
        if name == "height":
            if not ht_uuid:
                continue
            cm = in_to_cm(value) if unit.lower() in ("in_i", "[in_i]") else value
            create_obs(patient_uuid, encounter_uuid, ht_uuid, dt, value_numeric=round(cm, 2))
            continue

        # BMI
        if name == "bmi":
            if not bmi_uuid:
                continue
            create_obs(patient_uuid, encounter_uuid, bmi_uuid, dt, value_numeric=round(value, 2))
            continue

        print("⚠️ Unhandled vital type:", name)

    # --- Post BP as TWO numeric obs (SBP + DBP) ---
    if bp_sys is not None and bp_dia is not None:
        obs_dt = bp_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if sbp_uuid:
            create_obs(patient_uuid, encounter_uuid, sbp_uuid, obs_dt, value_numeric=round(bp_sys, 0))

        if dbp_uuid:
            create_obs(patient_uuid, encounter_uuid, dbp_uuid, obs_dt, value_numeric=round(bp_dia, 0))

    elif bp_sys is not None or bp_dia is not None:
        print("⚠️ Only one BP component found; skipping BP obs.")

# ---------- Main ----------
def main():
    for file_name in os.listdir(JSON_DIR):
        if not file_name.endswith(".json"):
            continue

        with open(os.path.join(JSON_DIR, file_name)) as f:
            patient_data = json.load(f)

        patient_uuid = create_openmrs_patient(patient_data)

        if patient_uuid:
            encounter_uuid = create_encounter(patient_uuid)
            add_conditions(patient_uuid, patient_data.get("conditions", []))

            if encounter_uuid:
                add_medications(patient_uuid, encounter_uuid, patient_data.get("medications", []))
                add_vitals(patient_uuid, encounter_uuid, patient_data.get("vitals", []))

    print("\n✅ All patients imported successfully!")

if __name__ == "__main__":
    main()