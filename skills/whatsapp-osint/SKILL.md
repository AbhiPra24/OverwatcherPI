---
name: whatsapp-osint
description: Primary goal is to execute unauthenticated WhatsApp verification scripts for any provided phone number, extracting registered display name, account classification (Personal vs Business), and direct links with zero login.
---

# Zero-Login WhatsApp OSINT

Automated execution skill to inspect WhatsApp presence and public metadata without credentials, burner accounts, or session tokens.

## Execution Goal

Whenever a target phone number or handle is provided:
1. **Execute Unauthenticated Checker**:
   ```bash
   python3 skills/whatsapp-osint/scripts/wa_link_generator.py <PHONE_NUMBER>
   ```
2. **Inspect OpenGraph Metadata**:
   - Registered State: Boolean (`True`/`False`)
   - Account Type: Personal (`WhatsApp Messenger`) vs Business (`Business Account`)
   - Public Name: Extracted from `<meta property="og:title">` (if exposed)
   - Chat Dispatcher: Direct link (`https://wa.me/91XXXXXXXXXX`)
3. **Format Results**: Present immediate findings alongside privacy assessment.
