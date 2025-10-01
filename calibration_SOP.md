# AV-SAFE Calibration SOP (Sound & Light)

**Objective:** Ensure measurement agreement with Class-1 SLM (IEC 61672) and reference flicker meter.

## Before You Start
- Device clock synced (UTC), firmware & config versions noted.
- Reference instruments: Class-1 SLM (IEC 61672) + flicker meter (make/model/serial).
- Quiet test room; stable light source for reference flicker.

## Audio Steps
1. Attach reference acoustic calibrator (e.g., 1 kHz @ 94 dB).  
2. Record device reading (precheck) → compute delta vs reference; must be within tolerance (e.g., ±0.3 dB).  
3. Verify A/C/Z weighting responses where applicable.  
4. Repeat after session (postcheck).  
5. Note environmental conditions (temp/humidity/pressure).

## Light Steps
1. Set reference flicker source (known f & %mod) using the flicker meter.  
2. Measure with device; ensure frequency match ±0.5 Hz and %mod within agreed tolerance.  
3. Repeat postcheck.

## Record & Sign
- Create a **Calibration Record** JSON (schema v1) with: device_id, operator, firmware/config, pre/post checks, references, environment.
- Compute `content_hash` and **sign** payload (Ed25519). Store `calibration_id` and signature with the record.
- Attach `calibration_id` in every minute summary.

## Schedule
- Recalibrate **every 6–12 months** or after hardware service.  
- Set reminders in CI / calendar.
