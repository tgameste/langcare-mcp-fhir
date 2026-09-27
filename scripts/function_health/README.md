# Function Health → FHIR R4

Converts Function Health biomarker results into FHIR R4 resources: one Patient, one Organization,
a DiagnosticReport per draw date, and an Observation per result (current value and history).

```sh
python3 build_fhir.py sample_input.json --out-dir out/
```

Writes two files:

- `function_health_fhir_bundle.json` — a `collection` Bundle with internal `urn:uuid:` references
- `function_health_fhir.ndjson` — one resource per line with relative references (`Patient/<id>`), for bulk import

## Mapping

- **Code**: LOINC where the analyte, specimen and method match unambiguously, plus the Function Health biomarker ID as a second coding.
- **Value**: numeric results become `valueQuantity` with UCUM codes; text results (`NEGATIVE`, `NONE SEEN`, blood type) become `valueString`.
- **Interpretation**: H / L / N / A from Function's range status. Neutral markers get none.
- **Reference range**: low/high where given, plus the lab's original range text.
- **IDs**: deterministic UUIDv5 from biomarker ID and date, so re-running updates rather than duplicates.

`sample_input.json` is synthetic. Keep real lab results out of the repository.
