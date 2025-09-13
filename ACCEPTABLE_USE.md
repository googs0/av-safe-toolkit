# Acceptable Use (Anti-Surveillance)

Do not use the AV-SAFE-Toolkit to surveil, target, discipline, or coerce people; do not capture or store raw speech, images, or video; do no harm. Deploy transparently and with consent. There are **no exceptions** to the prohibitions below.

---

## Purpose
This policy sets the ethical and operational boundaries for use of the **AV-SAFE Toolkit**, any reference hardware, and the **HF-AVC corpus**. It complements—but does not replace—the software license. By using the Project, you agree to abide by this policy **in addition to** the LICENSE, the [Code of Conduct](CODE_OF_CONDUCT.md), and the [Security](SECURITY.md) and [Privacy](PRIVACY.md) policies.

---

## Core Principles
- **Descriptors, not recordings.** No raw intelligible content (speech, images, video).
- **Do no harm.** No exposures, reenactments, or protocols that could harm people.
- **Privacy by design.** Minimize data, add integrity (hash/sign), enable audit.
- **Transparency.** Clear signage/notices and meaningful opt-out where applicable.

---

## Prohibited Uses (no exceptions)
You **may not** use the Project to:
- **Surveil, target, or discipline** individuals (e.g., workplace monitoring, tenant/student discipline, algorithmic management).
- Support **detention, interrogation, intelligence, military, or policing** operations, including in carceral or siege contexts.
- **Coerce or harm**, including inducing sleep loss, distress, or hazardous flicker/repetition; or **recreate harmful exposures**.
- **Capture, transmit, or store raw intelligible content** (speech, images, video) using this software or derivative hardware.
- **Identify, fingerprint, or track** individuals using acoustic/photometric signatures or any derived biometric proxy.
- **Bypass consent, signage, or transparency** requirements; or **violate privacy/data-protection laws**.

> **There are no exceptions** to the above.

---

## Sensitive Settings (expressly disallowed unless you have written ethics approval *and* legal authorization)
- Detention/prison, immigration/border facilities, police stations, military/intelligence sites.
- Workplaces if used for **performance/discipline** or employee behavioral surveillance.
- Dormitories, residential institutions, shelters when used for **control or discipline**.
- Clinical/medical contexts for **non-consensual** monitoring.

---

## Permitted Use (examples)
- **Research & education** under IRB/REC (or equivalent) approval, using **descriptors-only** pipelines.
- **Architectural, occupational, and public-health audits** of rooms/buildings for WHO noise and IEEE-1789 flicker guidance.
- **Rights-oriented inspections** by ombuds/independent monitors where deployments meet the requirements below and avoid prohibited contexts.

---

## Deployment Requirements
- **Descriptors only:** Store minute-level descriptors and integrity hashes/signatures—**never** raw A/V content.
- **Transparency:** Visible signage plus a plain-language notice (what is measured, why, retention, contact).
- **Consent:** Obtain consent where required; provide a **meaningful opt-out**.
- **Data minimization & retention:** Collect the minimum necessary; define retention periods and delete on schedule.
- **Security:** Protect keys; use TLS; restrict access; keep audit logs; **never commit private keys** to source control.
- **Calibration & uncertainty:** Maintain calibration logs; note uncertainty; verify material results with reference instruments.
- **Chain of custody:** Preserve per-minute hash-chain continuity and timestamps in reports.

---

## Human-Subjects & Safety
- **No harmful exposures** (e.g., sleep-deprivation protocols, hazardous flicker) under **any** circumstances.
- Any study involving people requires **prior ethics approval** and trauma-informed procedures.

---

## Legal
You are solely responsible for complying with local, national, and international law (e.g., privacy, labor, housing, education, and health regulations).

---

## Reporting & Misuse
- Contact: **av-safe-info@proton.me**
- Include: context, links, dates, and any relevant artifacts (no PII, no raw A/V).
- We will acknowledge receipt and may publish anonymized transparency notes when appropriate.

---

## Enforcement & Governance
- The maintainers may **refuse support**, **close issues/PRs**, **revoke contributor status**, and **ban accounts** involved in violations.
- Documented misuse may be added to a public advisory in the repository’s Security or Discussions sections.
- This policy is maintained under project governance (see [GOVERNANCE.md](GOVERNANCE.md)) and may be updated to address new risks.

---

See also: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SECURITY.md](SECURITY.md) · [PRIVACY.md](PRIVACY.md) · [DISCLAIMER.md](DISCLAIMER.md)
