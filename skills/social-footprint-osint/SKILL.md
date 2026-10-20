---
name: social-footprint-osint
description: Primary goal is to execute cross-platform username and handle reconnaissance across 400+ platforms using Sherlock, Blackbird, and WhatsMyName patterns with automated public indexing for any provided username or real name.
---

# Zero-Login Social Footprint OSINT

Automated execution skill to footprint usernames, aliases, and real names across 400+ online networks, forums, and developer platforms completely unauthenticated.

## Execution Goal

Whenever a username, alias, or real name is provided:
1. **Execute Unified Scanner**:
   ```bash
   # For usernames/handles:
   python3 skills/osint_scanner.py <USERNAME> --type username

   # For real names:
   python3 skills/osint_scanner.py "<REAL_NAME>" --type name --location "India"
   ```
2. **Execute Public Search Index Checks**:
   - Query search engines for handle presence across GitHub, X, LinkedIn, Telegram, and Reddit.
   - For names: Cross-reference corporate director records (`site:zaubacorp.com`), court records (`site:ecourts.gov.in`), and PDF lists.
3. **Trigger Zero-Login Multi-Site Scanners**:
   - Sherlock CLI: `sherlock <USERNAME> --print-found --timeout 10`
   - Direct web lookup: `https://whatsmyname.app/?q=<USERNAME>`
