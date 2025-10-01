# Data Protection Impact Assessment (DPIA) — AV-SAFE

**Purpose**  
Audit audio/light environments using *content-safe descriptors only* (no recordings). Outputs are per-minute JSON objects validated against strict schemas and standards-aligned rules.

**Processing Summary**  
- **Inputs (on-device only):** audio level descriptors (LAeq/LCpeak, 1/3-octave), light flicker descriptors (f_flicker, %mod, Flicker Index), optional coarse location code = room/site label.
- **No raw content captured or stored.** No speech, faces, or frames leave device memory.  
- **Outputs:** minute JSONL with descriptors, hash-chain, optional signatures, flags from WHO/IEEE profiles; HTML report.
- **Recipients:** audit team / authorized reviewers only. No commercial reuse.

**Lawful Basis (EU GDPR—choose per deployment)**  
- Public interest; legitimate interest; research (Art. 89) with safeguards; or OH&S compliance.  
- No special category data processed (unless optional biometrics are explicitly enabled on-device and minimized).

**Data Minimization & Privacy Controls**  
- **No raw AV**, descriptors only.  
- **Coarse location policy:** use location code or geohash truncated to 5–7 chars; no precise addresses.  
- **Retention:** default `retention_days = 365` (override per project); reports kept per legal requirement.  
- **Schema fences:** `additionalProperties: false`; validation on ingest.  
- **Integrity:** hash-chain + optional Ed25519 signatures; device & calibration IDs in every record.

**Risks & Mitigations**  
- *Risk:* re-identification from unusual descriptor patterns → **Mitigation:** band/time aggregation; no per-event raw logs.  
- *Risk:* unauthorized access → **Mitigation:** JWT/OAuth, least privilege storage, versioned buckets, CI validation.  
- *Risk:* calibration drift → **Mitigation:** signed calibration records, pre/post checks, scheduled recalibration.

**Data Subject Rights**  
- Right of access, rectification, deletion (where applicable). Provide contact and project ID for queries.

**Contacts**  
av-safe-info@proton.me

**Review**  
- DPIA owner:
