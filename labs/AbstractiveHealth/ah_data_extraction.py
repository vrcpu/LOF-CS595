# Script.py
import os
import sys
from dotenv import load_dotenv
import time
import zipfile
import io
import requests
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from labs.AbstractiveHealth.services import ah_services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), './../..')))
from lof.services import AbstractiveHealthTokenService

load_dotenv()  # Load AH credentials from .env
AH_services = ah_services.AH_Services

def main():
    # Step 1: Get AH token
    try:
        token = AbstractiveHealthTokenService().get_bearer_token()
        print("✅ Token obtained:", token[:10] + "...")  # partial token
    except Exception as e:
        print("❌ Failed to get token:", e)
        return

    # Step 2: Define a test patient
    patient = {
        "First Name": "Nwhinone",
        "Last Name": "Nwhinzzztestpatient",
        "Gender": "M",
        "Birth Date": "1981-01-01",
        "Phone": "205-111-1111",
        "Email": "test@example.com",
        "Address": "1100 Test Street",
        "City": "Helena",
        "State": "AL",
        "ZIP": "35080",
        "Country": "USA"
    }

    # Step 3: Search patient
    try:
        search_resp = AH_services.search_patient(token, patient, test=True)
        print("✅ Patient search response:", search_resp)
    except Exception as e:
        print("❌ Failed to search patient:", e)
        return

    # Extract patient_id & conversation_id
    try:
        conversation_id = search_resp['conversation_id']
        patient_id = search_resp['results'][0]['patient_id']
        print(f"Patient ID: {patient_id}, Conversation ID: {conversation_id}")
    except Exception as e:
        print("❌ Failed to parse search results:", e)
        return

    # Step 4: Retrieve patient documents with polling
    try:
        timeout = 300  # max wait 5 minutes
        interval = 20  # check every 20 seconds
        start_time = time.time()
        docs_resp = AH_services.retrieve_patient_docs(token, conversation_id, patient_id, test=True)

        while docs_resp.get("processing", True):
            print("⏳ Documents still processing... waiting 20 seconds")
            time.sleep(interval)
            docs_resp = AH_services.retrieve_patient_docs(token, conversation_id, patient_id, test=True)

            if time.time() - start_time > timeout:
                print("❌ Timeout waiting for documents")
                break

        if docs_resp.get("status") == "success" and "results" in docs_resp:
            result = docs_resp["results"][0]
            if "url" in result:
                print("✅ Documents ready for download:", result["url"])
                process_documents(docs_resp)  # <-- Only this now
            else:
                print("⚠️ Documents processed but URL not available yet")
        else:
            print("❌ Failed to retrieve documents:", docs_resp)

    except Exception as e:
        print("❌ Failed to retrieve documents:", e)


# Step 5: Process retrieved docs and prepare OpenMRS JSON
def process_documents(docs_resp):
    results = docs_resp.get("results", [])
    if not results:
        print("❌ No document URLs found")
        return

    for res in results:
        if res.get("status") != "success":
            print(f"⚠️ Skipping patient {res.get('patient_id')}, status: {res.get('status')}")
            continue

        url = res.get("url")
        if not url:
            print(f"⚠️ No URL found for patient {res.get('patient_id')}")
            continue

        print(f"⬇️ Downloading ZIP for patient {res.get('patient_id')}")
        try:
            r = requests.get(url)
            r.raise_for_status()
        except Exception as e:
            print(f"❌ Failed to download ZIP: {e}")
            continue

        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # Extract cleaned_text_notes JSON files
                # note_files = [
                #     f for f in z.namelist() 
                #     if "cleaned_text_notes/" in f and f.endswith(".json") and not f.split("/")[-1].startswith("._")
                # ]

                note_files = [
                    f for f in z.namelist()
                    if (
                        "cleaned_text_notes/" in f
                        and f.endswith(".json")
                        and "Progress note_" in os.path.basename(f)
                        and not os.path.basename(f).startswith("._")
                    )
                ]
                print(f"📄 Found {len(note_files)} notes")

                os.makedirs("Patient_data", exist_ok=True)

                for nf in note_files:
                    try:
                        with z.open(nf) as f:
                            # Try UTF-8 first, fallback to latin-1 if decoding fails
                            try:
                                note = json.load(f)
                            except UnicodeDecodeError:
                                note_content = f.read().decode('latin-1')
                                note = json.loads(note_content)

                            section = note.get("section_content", {})
                            patient_info = section.get("Patient", {})

                            # Print patient info for quick verification
                            print("---- Patient Info ----")
                            print(f"Name: {patient_info.get('First Name', 'N/A')} {patient_info.get('Last Name', 'N/A')}")
                            print(f"DOB: {patient_info.get('Birth Date', 'N/A')}, Gender: {patient_info.get('Gender', 'N/A')}")
                            print(f"Phone: {patient_info.get('Phone', 'N/A')}, Email: {patient_info.get('Email', 'N/A')}")

                            # Map into OpenMRS-ready JSON
                            omrs_json = {
                                "patient_id": res.get("patient_id", ""),
                                "name": f"{patient_info.get('First Name','') or patient_info.get('given_name','')} "
                                        f"{patient_info.get('Last Name','') or patient_info.get('family_name','')}",
                                "gender": patient_info.get("Gender","") or patient_info.get('administrative_gender_code',''),
                                "birthDate": patient_info.get("Birth Date","") or patient_info.get('birth_time',''),
                                "conditions": section.get("Medical History", []) or section.get("Conditions", []),
                                "medications": section.get("Medications", []),
                                "labs": section.get("Labs", []),
                                "vitals": section.get("Vitals", [])
                            }

                            # Save to OpenMRS_ready folder
                            file_name = os.path.join("Patient_data", nf.split("/")[-1])
                            with open(file_name, "w", encoding="utf-8") as f_out:
                                json.dump(omrs_json, f_out, indent=2)
                            print(f"✅ OpenMRS JSON saved: {file_name}")
                            print("----------------------\n")
                    except Exception as e:
                        print(f"❌ Error reading note {nf}: {e}")

        except Exception as e:
            print(f"❌ Failed to process ZIP: {e}")


if __name__ == "__main__":
    main()