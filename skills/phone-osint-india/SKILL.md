---
name: phone-osint-india
description: Primary goal is to execute automated phone intelligence scripts and public search indexing for any provided phone number (+91 India), determining carrier series, telecom circle, zero-login WhatsApp status, and public search footprints.
---

# Phone OSINT India (+91)

Automated execution skill for analyzing Indian telephone numbers, mapping telecom circles, performing unauthenticated WhatsApp presence audits, and evaluating public search index exposure.

## Execution Goal

Whenever a target phone number is provided:
1. **Execute Analyzer & Dispatcher**:
   ```bash
   python3 skills/osint_scanner.py <PHONE_NUMBER> --type phone
   ```
2. **Execute Public Search Index Checks**:
   - Query search engines using the auto-generated dorks:
     - `"+91XXXXXXXXXX" OR "XXXXXXXXXX" OR "0XXXXXXXXXX"`
     - `"XXXXXXXXXX" (pdf OR xlsx OR doc)`
     - `site:justdial.com "XXXXXXXXXX"`
     - `site:indiamart.com "XXXXXXXXXX"`
     - `site:facebook.com "XXXXXXXXXX"`
3. **Compile Structured Triage Report**:
   - Deliver carrier classification, circle jurisdiction, WhatsApp status, and public indexing findings.
