"""Convert Function Health biomarker data into a FHIR R4 collection Bundle and NDJSON.

Usage: python3 build_fhir.py INPUT.json [--out-dir DIR]

INPUT.json: {"requisitions": {date: requisition_id}, "biomarkers": [
  {"id", "name", "categories", "date", "value", "unit", "low", "high",
   "range", "status", "past": [{"date", "value", "in_range"}]}]}
status is one of above | below | in_range | neutral | text (as reported by Function Health).
"""
import json, uuid, re, argparse, os
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("--out-dir", default=".")
args = ap.parse_args()
_src = json.load(open(args.input))
REQ = _src.get("requisitions", {})
D = [(b["id"], b["name"], b.get("categories", []), b["date"], b["value"], b.get("unit"),
      b.get("low"), b.get("high"), b.get("range", ""), b["status"],
      [(p["date"], p["value"], p["in_range"]) for p in b.get("past", [])]) for b in _src["biomarkers"]]

NS = uuid.UUID("6f1c3a8e-2b4d-4e5f-9a7b-0c1d2e3f4a5b")
FH_SYS = "https://www.functionhealth.com/fhir/biomarker-id"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
V2_INT = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"

def uid(*parts):
    return str(uuid.uuid5(NS, "|".join(parts)))

# LOINC codes only where the analyte/specimen/method match is unambiguous.
LOINC_MAP = {
 "LDL-Cholesterol": ("13457-7", "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation"),
 "Total Cholesterol / HDL Ratio": ("9830-1", "Cholesterol.total/Cholesterol in HDL [Mass Ratio] in Serum or Plasma"),
 "Non-HDL Cholesterol": ("43396-1", "Cholesterol non HDL [Mass/volume] in Serum or Plasma"),
 "Total Cholesterol": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
 "HDL-Cholesterol": ("2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),
 "Triglycerides": ("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
 "Apolipoprotein B (ApoB)": ("1884-6", "Apolipoprotein B [Mass/volume] in Serum or Plasma"),
 "Lipoprotein (a)": ("43583-4", "Lipoprotein a [Moles/volume] in Serum or Plasma"),
 "Insulin": ("20448-7", "Insulin [Units/volume] in Serum or Plasma"),
 "Glucose": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
 "Hemoglobin A1c (HbA1c)": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
 "Uric Acid": ("3084-1", "Urate [Mass/volume] in Serum or Plasma"),
 "Blood Urea Nitrogen (BUN)": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
 "Creatinine": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
 "Creatinine-Based Estimated Glomerular Filtration Rate (eGFR)": ("98979-8", "Glomerular filtration rate/1.73 sq M.predicted [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (CKD-EPI 2021)"),
 "Blood Urea Nitrogen (BUN) / Creatinine Ratio": ("3097-3", "Urea nitrogen/Creatinine [Mass Ratio] in Serum or Plasma"),
 "Sodium": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),
 "Potassium": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
 "Chloride": ("2075-0", "Chloride [Moles/volume] in Serum or Plasma"),
 "Carbon Dioxide": ("2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma"),
 "Calcium": ("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),
 "Total Protein": ("2885-2", "Protein [Mass/volume] in Serum or Plasma"),
 "Albumin": ("1751-7", "Albumin [Mass/volume] in Serum or Plasma"),
 "Globulin": ("10834-0", "Globulin [Mass/volume] in Serum by calculation"),
 "Albumin / Globulin Ratio": ("1759-0", "Albumin/Globulin [Mass Ratio] in Serum or Plasma"),
 "Total Bilirubin": ("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
 "Alkaline Phosphatase (ALP)": ("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),
 "Aspartate Aminotransferase (AST)": ("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
 "Alanine Aminotransferase (ALT)": ("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
 "White Blood Cell (WBC) Count": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
 "Red Blood Cell (RBC) Count": ("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
 "Hemoglobin": ("718-7", "Hemoglobin [Mass/volume] in Blood"),
 "Hematocrit": ("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
 "Mean Corpuscular Volume (MCV)": ("787-2", "MCV [Entitic volume] by Automated count"),
 "Mean Corpuscular Hemoglobin (MCH)": ("785-6", "MCH [Entitic mass] by Automated count"),
 "Mean Corpuscular Hemoglobin Concentration (MCHC)": ("786-4", "MCHC [Mass/volume] by Automated count"),
 "Red Cell Distribution Width (RDW)": ("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
 "Platelet Count": ("777-3", "Platelets [#/volume] in Blood by Automated count"),
 "Mean Platelet Volume (MPV)": ("32623-1", "Platelet mean volume [Entitic volume] in Blood by Automated count"),
 "Neutrophils": ("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
 "Lymphocytes": ("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
 "Monocytes": ("742-7", "Monocytes [#/volume] in Blood by Automated count"),
 "Eosinophils": ("711-2", "Eosinophils [#/volume] in Blood by Automated count"),
 "Basophils": ("704-7", "Basophils [#/volume] in Blood by Automated count"),
 "Neutrophils %": ("770-8", "Neutrophils/100 leukocytes in Blood by Automated count"),
 "Lymphocytes %": ("736-9", "Lymphocytes/100 leukocytes in Blood by Automated count"),
 "Monocytes %": ("5905-5", "Monocytes/100 leukocytes in Blood by Automated count"),
 "Eosinophils %": ("713-8", "Eosinophils/100 leukocytes in Blood by Automated count"),
 "Basophils %": ("706-2", "Basophils/100 leukocytes in Blood by Automated count"),
 "Color - Urine": ("5778-6", "Color of Urine"),
 "Appearance - Urine": ("5767-9", "Appearance of Urine"),
 "Specific Gravity - Urine": ("5811-5", "Specific gravity of Urine by Test strip"),
 "pH - Urine": ("5803-2", "pH of Urine by Test strip"),
 "Iron": ("2498-4", "Iron [Mass/volume] in Serum or Plasma"),
 "Iron Binding Capacity": ("2500-7", "Iron binding capacity [Mass/volume] in Serum or Plasma"),
 "Iron % Saturation": ("2502-3", "Iron saturation [Mass Fraction] in Serum or Plasma"),
 "Ferritin": ("2276-4", "Ferritin [Mass/volume] in Serum or Plasma"),
 "Thyroid-Stimulating Hormone (TSH)": ("3016-3", "Thyrotropin [Units/volume] in Serum or Plasma"),
 "Thyroxine (T4) Free": ("3024-7", "Thyroxine (T4) free [Mass/volume] in Serum or Plasma"),
 "Triiodothyronine (T3) Free": ("3051-0", "Triiodothyronine (T3) Free [Mass/volume] in Serum or Plasma"),
 "Vitamin D": ("1989-3", "25-Hydroxyvitamin D3+25-Hydroxyvitamin D2 [Mass/volume] in Serum or Plasma"),
 "High-Sensitivity C-Reactive Protein (hs-CRP)": ("30522-7", "C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method"),
 "Cortisol": ("2143-6", "Cortisol [Mass/volume] in Serum or Plasma"),
 "DHEA Sulfate": ("2191-5", "Dehydroepiandrosterone sulfate (DHEA-S) [Mass/volume] in Serum or Plasma"),
 "Follicle Stimulating Hormone (FSH)": ("15067-2", "Follitropin [Units/volume] in Serum or Plasma"),
 "Insulin-like Growth Factor (IGF-1)": ("2484-4", "Insulin-like growth factor-I [Mass/volume] in Serum or Plasma"),
 "Mercury": ("5685-3", "Mercury [Mass/volume] in Blood"),
 "ABO Group": ("883-9", "ABO group [Type] in Blood"),
 "Rhesus (Rh) Factor": ("10331-7", "Rh [Type] in Blood"),
 "Hepatitis C Antibody": ("16128-1", "Hepatitis C virus Ab [Presence] in Serum"),
 "Hepatitis B Surface Antigen": ("5196-1", "Hepatitis B virus surface Ag [Presence] in Serum"),
 "Hepatitis B Surface Antibody, Qualitative": ("22322-2", "Hepatitis B virus surface Ab [Presence] in Serum"),
 "Hepatitis B Core Antibody, Total": ("16933-4", "Hepatitis B virus core Ab [Presence] in Serum"),
 "Albumin, Random Urine without Creatinine": ("14957-5", "Microalbumin [Mass/volume] in Urine"),
}

UCUM_MAP = {
 "mg/dL": "mg/dL", "mg/dL (calc)": "mg/dL", "g/dL": "g/dL", "g/dL (calc)": "g/dL",
 "%": "%", "% (calc)": "%", "fL": "fL", "pg": "pg",
 "Thousand/uL": "10*3/uL", "Million/uL": "10*6/uL", "cells/uL": "/uL",
 "mmol/L": "mmol/L", "U/L": "U/L", "ng/mL": "ng/mL", "ng/dL": "ng/dL",
 "mcg/dL": "ug/dL", "mcg/dL (calc)": "ug/dL", "mcg/L": "ug/L", "uIU/mL": "u[IU]/mL",
 "mIU/L": "m[IU]/L", "pg/mL": "pg/mL", "nmol/L": "nmol/L", "mL/min/1.73m2": "mL/min/{1.73_m2}",
 "U/mL": "U/mL", "(calc)": "{ratio}", "SD": "{SD}", "Angstrom": "Ao", "mg/L": "mg/L",
}

CAT_LAB = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                       "code": "laboratory", "display": "Laboratory"}]}

def num(v):
    try:
        f = float(v)
        return int(f) if re.fullmatch(r"-?\d+", v) else f
    except ValueError:
        return None

def interp(code):
    disp = {"H": "High", "L": "Low", "N": "Normal", "A": "Abnormal"}[code]
    return [{"coding": [{"system": V2_INT, "code": code, "display": disp}]}]

def flag(status, value, low, high, in_range):
    """status: current-result status string, or None for historical results (use in_range)."""
    if status == "above": return "H"
    if status == "below": return "L"
    if status in ("in_range", "error"): return "N"
    if status == "text": return "A"
    if status == "neutral": return None
    # historical
    if in_range: return "N"
    n = num(value)
    if n is not None and high is not None and n > high: return "H"
    if n is not None and low is not None and n < low: return "L"
    return "A"

PATIENT_ID = uid("patient")
ORG_ID = uid("org", "function-health")
patient = {"resourceType": "Patient", "id": PATIENT_ID,
           "identifier": [{"system": "https://www.functionhealth.com/fhir/member", "value": "function-health-member"}],
           "active": True,
           "text": {"status": "generated", "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\">Function Health member (demographics not provided by source)</div>"}}
org = {"resourceType": "Organization", "id": ORG_ID, "name": "Function Health",
       "identifier": [{"system": "urn:ietf:rfc:3986", "value": "https://www.functionhealth.com"}]}

observations, by_date = [], defaultdict(list)

def make_obs(b, date, value, status, in_range):
    bid, name, cats, _, _, unit, low, high, rstr, _, _ = b
    oid = uid("obs", bid, date)
    code = {"text": name, "coding": [{"system": FH_SYS, "code": bid, "display": name}]}
    if name in LOINC_MAP:
        lc, ld = LOINC_MAP[name]
        code["coding"].insert(0, {"system": LOINC, "code": lc, "display": ld})
    o = {"resourceType": "Observation", "id": oid,
         "identifier": [{"system": "https://www.functionhealth.com/fhir/result", "value": f"{bid}:{date}"}],
         "status": "final", "category": [CAT_LAB], "code": code,
         "subject": {"reference": f"Patient/{PATIENT_ID}"},
         "effectiveDateTime": date,
         "performer": [{"reference": f"Organization/{ORG_ID}"}]}
    n = num(value)
    if n is not None:
        q = {"value": n}
        if unit:
            q["unit"] = unit
            if unit in UCUM_MAP:
                q["system"] = UCUM; q["code"] = UCUM_MAP[unit]
        o["valueQuantity"] = q
    else:
        o["valueString"] = value
    f = flag(status, value, low, high, in_range)
    if f: o["interpretation"] = interp(f)
    if low is not None or high is not None or rstr:
        rr = {}
        uc = UCUM_MAP.get(unit) if unit else None
        def qty(x):
            d = {"value": x}
            if unit:
                d["unit"] = unit
                if uc: d["system"] = UCUM; d["code"] = uc
            return d
        if low is not None: rr["low"] = qty(low)
        if high is not None: rr["high"] = qty(high)
        if rstr: rr["text"] = rstr
        o["referenceRange"] = [rr]
    o["extension"] = [{"url": "https://www.functionhealth.com/fhir/StructureDefinition/biomarker-category",
                       "valueString": c} for c in cats]
    observations.append(o)
    by_date[date].append(oid)

for b in D:
    bid, name, cats, date, value, unit, low, high, rstr, status, past = b
    make_obs(b, date, value, status, None)
    for (pd, pv, pin) in past:
        make_obs(b, pd, pv, None, pin)

reports = []
for date in sorted(by_date):
    r = {"resourceType": "DiagnosticReport", "id": uid("report", date),
         "status": "final", "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB", "display": "Laboratory"}]}],
         "code": {"coding": [{"system": LOINC, "code": "11502-2", "display": "Laboratory report"}], "text": f"Function Health lab panel {date}"},
         "subject": {"reference": f"Patient/{PATIENT_ID}"},
         "effectiveDateTime": date, "issued": f"{date}T00:00:00Z",
         "performer": [{"reference": f"Organization/{ORG_ID}"}],
         "result": [{"reference": f"Observation/{i}"} for i in by_date[date]]}
    if date in REQ:
        r["identifier"] = [{"system": "https://www.functionhealth.com/fhir/requisition", "value": REQ[date]}]
    reports.append(r)

resources = [patient, org] + reports + observations
bundle = {"resourceType": "Bundle", "id": uid("bundle"), "type": "collection",
          "timestamp": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
          "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in resources]}
# Use urn:uuid references so the bundle resolves internally
s = json.dumps(bundle, indent=2)
for r in resources:
    s = s.replace(f'"{r["resourceType"]}/{r["id"]}"', f'"urn:uuid:{r["id"]}"')
open(os.path.join(args.out_dir, "function_health_fhir_bundle.json"), "w").write(s)

with open(os.path.join(args.out_dir, "function_health_fhir.ndjson"), "w") as fh:
    for r in resources:  # relative references (Patient/<id>) for server import
        fh.write(json.dumps(r) + "\n")

print(len(D), "biomarkers;", len(observations), "observations;", len(reports), "reports:", {d: len(v) for d, v in sorted(by_date.items())})
print("LOINC-coded:", sum(1 for b in D if b[1] in LOINC_MAP), "of", len(D))
