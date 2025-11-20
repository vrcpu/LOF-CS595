# parsing.py
import pdfplumber
import re
import json
from datetime import datetime


def make_iso_date(d_str):
    """Convert YYYY-MM-DD into ISO datetime string."""
    try:
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT00:00:00.000+0000")
    except Exception:
        return d_str


def parse_numeric_and_unit(s):
    """Split values like '500 Tablet' into (500, 'Tablet')."""
    s = s.strip()
    m = re.match(r'(\d+(?:\.\d+)?)\s*(.*)', s)
    if m:
        num = float(m.group(1))
        if num.is_integer():
            num = int(num)
        return num, m.group(2).strip() or None
    return None, s or None


def parse_pdf(path):
    parsed = {
        "encounter_type_name": None,
        "location_name": None,
        "provider_name": None,
        "encounter_role_name": None,
        "allergies": [],
        "conditions": [],
        "observations": {},
        "medications": [],
        "name": None,
        "age": None,
        "gender": None,
    }

    with pdfplumber.open(path) as pdf:
        text = "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )

    lines = [re.sub(r"\s+", " ", l.strip()) for l in text.splitlines() if l.strip()]

    current_section = None
    current_med = None
    last_med_key = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # section headers
        if line in ["Patient Demographics", "Problem List", "Vital Signs", "Allergies", "Medications"]:
            current_section = line
            if current_med:
                parsed["medications"].append(current_med)
                current_med = None
                last_med_key = None
            i += 1
            continue

        # ---------------- Patient Demographics ----------------
        if current_section == "Patient Demographics":
            if line.startswith("Encounter Type"):
                parsed["encounter_type_name"] = line.split("Encounter Type", 1)[1].strip()
            elif line.startswith("Location"):
                parsed["location_name"] = line.split("Location", 1)[1].strip()
            elif line.startswith("Provider"):
                parsed["provider_name"] = line.split("Provider", 1)[1].strip()
            elif line.startswith("Encounter Role"):
                parsed["encounter_role_name"] = line.split("Encounter Role", 1)[1].strip()
            elif line.startswith("Name"):
                parsed["name"] = line.split("Name", 1)[1].strip()
            elif line.startswith("Age"):
                parsed["age"] = line.split("Age", 1)[1].strip()
            elif line.startswith("Gender"):
                parsed["gender"] = line.split("Gender", 1)[1].strip()
            i += 1
            continue

        # ---------------- Problem List ----------------
        if current_section == "Problem List":
            if re.search(r"\d{4}-\d{2}-\d{2}", line):
                parts = line.split()
                onset = parts[-1]
                verif = parts[-2]
                clinical = parts[-3]
                cond = " ".join(parts[:-3])
                parsed["conditions"].append({
                    "condition_name": cond,
                    "clinical_status": clinical,
                    "verification_status": verif,
                    "onset_date": make_iso_date(onset)
                })
            i += 1
            continue

        # ---------------- Vital Signs ----------------
        if current_section == "Vital Signs":
            if re.match(r"Weight.*\d", line):
                parsed["observations"]["Weight (kg)"] = int(re.search(r"(\d+)", line).group(1))
            elif re.match(r"Height.*\d", line):
                parsed["observations"]["Height"] = int(re.search(r"(\d+)", line).group(1))
            elif line.startswith("Blood Pressure"):
                bp_val = line.split("Blood Pressure", 1)[1].strip()
                if "/" in bp_val:
                    try:
                        sys, dia = bp_val.split("/")
                        parsed["observations"]["Systolic blood pressure"] = int(sys.strip())
                        parsed["observations"]["Diastolic blood pressure"] = int(dia.strip())
                    except Exception:
                        parsed["observations"]["Blood Pressure (raw)"] = bp_val
                else:
                    parsed["observations"]["Blood Pressure (raw)"] = bp_val
            i += 1
            continue

        # ---------------- Allergies ----------------
        if current_section == "Allergies":
            if line.lower().startswith("allergen") and "severity" in line.lower():
                i += 1
                continue
            parts = line.split()
            if len(parts) >= 4:
                allergen = parts[0]
                severity = parts[1]
                reaction = parts[2]
                comment = " ".join(parts[3:])
                parsed["allergies"].append({
                    "allergen_name": allergen,
                    "severity_name": severity,
                    "reaction_name": reaction,
                    "comment": comment
                })
            else:
                # continuation of previous allergy comment
                if parsed["allergies"]:
                    parsed["allergies"][-1]["comment"] += " " + line
            i += 1
            continue

        # ---------------- Medications ----------------
        if current_section == "Medications":
            if line.startswith("Drug:"):
                if current_med:
                    parsed["medications"].append(current_med)
                current_med = {"drug_name": line.split(":", 1)[1].strip()}
                last_med_key = None
            elif current_med is not None:
                if ":" in line:
                    key, val = [s.strip() for s in line.split(":", 1)]
                    last_med_key = key
                    if key == "Concept":
                        current_med["concept_name"] = val
                    elif key == "Dose":
                        num, unit = parse_numeric_and_unit(val)
                        if num is not None: current_med["dose"] = num
                        if unit: current_med["dose_units_name"] = unit
                    elif key == "Route":
                        current_med["route_name"] = val
                    elif key == "Frequency":
                        current_med["frequency_name"] = val
                    elif key == "Duration":
                        num, unit = parse_numeric_and_unit(val)
                        if num is not None: current_med["duration"] = num
                        if unit: current_med["duration_units_name"] = unit
                    elif key == "Quantity":
                        num, unit = parse_numeric_and_unit(val)
                        if num is not None: current_med["quantity"] = num
                        if unit: current_med["quantity_units_name"] = unit
                    elif key == "Refills":
                        try:
                            current_med["num_refills"] = int(val)
                        except Exception:
                            current_med["num_refills"] = 0
                    elif key == "Care Setting":
                        current_med["care_setting_name"] = val
                    elif key == "Orderer":
                        current_med["orderer_name"] = val
                else:
                    # continuation line → append to last key
                    if last_med_key == "Frequency":
                        current_med["frequency_name"] += " " + line
                    elif last_med_key == "Duration":
                        current_med["duration_units_name"] += " " + line
                    elif last_med_key == "Quantity":
                        current_med["quantity_units_name"] += " " + line
                    elif last_med_key == "Dose":
                        if "dose_units_name" in current_med:
                            current_med["dose_units_name"] += " " + line
                    else:
                        # generic continuation
                        if last_med_key:
                            k = last_med_key.lower().replace(" ", "_") + "_name"
                            if k in current_med:
                                current_med[k] += " " + line
            i += 1
            continue

        i += 1

    if current_med:
        parsed["medications"].append(current_med)

    # normalize N/A → None
    for k in parsed.keys():
        if isinstance(parsed[k], str) and parsed[k].upper() == "N/A":
            parsed[k] = None

    return parsed


if __name__ == "__main__":
    result = parse_pdf("patient_record_filled_fixed.pdf")
    print(json.dumps(result, indent=4))
