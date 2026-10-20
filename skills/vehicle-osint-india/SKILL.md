---
name: vehicle-osint-india
description: Primary goal is to execute automated Indian vehicle plate parsing, extract RTO district jurisdiction, generate unauthenticated eChallan verification links, and run public indexing for any provided vehicle number.
---

# Vehicle OSINT India

Automated execution skill to analyze Indian motor vehicle registration numbers (RC) and traffic violations without requiring logins or subscriptions.

## Execution Goal

Whenever an Indian vehicle plate number is provided:
1. **Execute Plate Parser Script**:
   ```bash
   python3 skills/vehicle-osint-india/scripts/rto_lookup.py <PLATE_NUMBER>
   # or
   python3 skills/osint_scanner.py <PLATE_NUMBER> --type plate
   ```
2. **Execute Public Search Index Checks**:
   - Query search engines:
     - `"<PLATE_NUMBER>" echallan OR parivahan`
     - `"<PLATE_NUMBER_SPACED>"`
3. **Dispatch Unauthenticated Check URLs**:
   - National eChallan: `https://echallan.parivahan.gov.in/index/accused-challan`
   - Parivahan Portal: `https://parivahan.gov.in/rcdlstatus/`
   - State traffic police notice portals (BTP, Delhi Traffic, MTP).
