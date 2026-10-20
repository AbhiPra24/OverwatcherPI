---
name: osint
description: Unified multi-vector OSINT framework for investigating phone numbers (+91 India), email addresses, usernames/social handles, real names, and vehicle registration plates. Automates CLI script execution, unauthenticated API queries, public search indexing, UPI VPA identity checks, professional profiling, and academic/corporate record retrieval without credentials.
---

# Unified Zero-Login OSINT Skill & Tool Reference

An all-in-one Open-Source Intelligence (OSINT) workflow, execution engine, and tool reference index designed to investigate indicators across India and global platforms with **zero logins, zero session cookies, and zero API credentials**.

---

## 1. Best-in-Class OSINT Tools & Reference Catalog

A curated guide to the industry's gold-standard open-source intelligence tools categorized by investigation vector:

### A. Master Frameworks & Curated Toolkits
* **[OSINT Framework](https://osintframework.com)**: The industry-standard hierarchical directory of OSINT resources categorized by indicator.
* **[Awesome-OSINT (`jivoi/awesome-osint`)](https://github.com/jivoi/awesome-osint)**: The most comprehensive curated GitHub repository for open-source intelligence tools.
* **[Bellingcat Investigation Toolkit](https://www.bellingcat.com/resources/)**: Battle-tested methodologies and tools curated by investigative researchers.

### B. Username, Social Identity & Discussion Reconnaissance
* **[Sherlock (`sherlock-project/sherlock`)](https://github.com/sherlock-project/sherlock)**: The industry benchmark CLI tool for hunting usernames across 400+ platforms without login.
* **[Maigret (`soxoj/maigret`)](https://github.com/soxoj/maigret)**: Advanced fork of Sherlock that extracts bio data, links, avatars, and outputs structured intelligence dossiers.
* **[Blackbird (`p1ngul1n0/blackbird`)](https://github.com/p1ngul1n0/blackbird)**: Ultra-fast asynchronous username finder covering 570+ platforms.
* **[WhatsMyName (`WebBreacher/WhatsMyName`)](https://whatsmyname.app)**: Detection rule signatures maintained by the intelligence community; runs zero-login in browser or CLI.
* **[Social-Analyzer (`qeeqbox/social-analyzer`)](https://github.com/qeeqbox/social-analyzer)**: Full-featured API and dashboard to analyze profiles across 1000+ networks.

### C. Phone Number, Telecom & Financial/UPI Intelligence
* **[PhoneInfoga (`sundowndev/phoneinfoga`)](https://github.com/sundowndev/phoneinfoga)**: Python/Go tool for scanning international numbers using public footprinting and unauthenticated APIs.
* **[Google libphonenumber (`google/libphonenumber`)](https://github.com/google/libphonenumber)**: Google's authoritative library for offline parsing, validating, formatting, and carrier classification.
* **[UPI VPA Reverse Name Resolution Protocol](https://www.npci.org.in)**: Leveraging NPCI beneficiary name validation on deterministic Virtual Payment Addresses (PhonePe `@ybl`/`@ibl`/`@axl`, Google Pay `@okhdfcbank`/`@oksbi`/`@okaxis`/`@okicici`, Paytm `@paytm`, BHIM `@upi`, Amazon Pay `@apl`) to unmask bank-verified legal KYC names without transactions.
* **[Sanchar Saathi (CEIR / DoT)](https://sancharsaathi.gov.in)**: Government of India portal for verifying device IMEI legitimacy (`KYM`), lost/stolen blocking, and TAF-COP SIM registrations.
* **[TruecallerJS (`sumithemmadi/truecallerjs`)](https://github.com/sumithemmadi/truecallerjs)**: CLI and Node.js client for caller-ID data lookup.

### D. Professional, Career & Academic Footprinting
* **Professional Trajectory Analysis**: Extraction of career timelines, company tenures, promotions, specialized functional skills (B2B/B2C sales, engineering, finance), corporate tooling (CRM, LMS), and professional network circles.
* **Academic & University Registries**: University placement rosters, convocation gazettes, academic committee records, research project documentation, and alumni associations.

### E. Email & Domain Intelligence
* **[Holehe (`megadose/holehe`)](https://github.com/megadose/holehe)**: Checks if an email is registered across 120+ platforms (Instagram, Google, Twitter, Amazon) without notifying the target.
* **[theHarvester (`laramies/theHarvester`)](https://github.com/laramies/theHarvester)**: Reconnaissance tool for gathering emails, subdomains, names, and virtual hosts from public search engines.
* **[Epieos (`epieos.com`)](https://epieos.com)**: Zero-login reverse email search uncovering associated Google services, reviews, Maps activity, and avatars.

### F. Instagram Reconnaissance (Zero-Login)
* **[Instaloader (`instaloader/instaloader`)](https://github.com/instaloader/instaloader)**: Download public photos, captions, and metadata via `--no-login` mode.
* **[Toutatis (`megadose/toutatis`)](https://github.com/megadose/toutatis)**: Extracts public profile details, user IDs, and metadata.
* **[Picuki](https://www.picuki.com)** / **[Imginn](https://imginn.com)**: Public web mirrors for browsing and extracting Instagram posts and media without hitting login walls.

### G. Indian Public Corporate, Legal & Transport Registries
* **[Parivahan Sewa (MoRTH)](https://parivahan.gov.in)** & **[eChallan Portal](https://echallan.parivahan.gov.in)**: Central national vehicle and traffic violation registries.
* **[Zauba Corp](https://www.zaubacorp.com)** & **[Tofler](https://www.tofler.in)**: Public MCA corporate director and business registry intelligence (Director Identification Numbers - DIN, company charges, filings).
* **[eCourts India (`ecourts.gov.in`)](https://ecourts.gov.in)**: National public registry for searching district and high court cases by party name or filing details.

---

## 2. Master CLI Orchestrator

The skill is powered by the unified orchestrator script: [`skills/osint_scanner.py`](file:///data/Work/OverwatcherPI/skills/osint_scanner.py).

### Commands
```bash
# Auto-detects indicator type and runs all checks:
python3 skills/osint_scanner.py <TARGET>

# Explicit vector execution:
python3 skills/osint_scanner.py <PHONE_NUMBER> --type phone
python3 skills/osint_scanner.py <EMAIL_ADDRESS> --type email
python3 skills/osint_scanner.py <USERNAME> --type username
python3 skills/osint_scanner.py "<REAL_NAME>" --type name --location "India"
python3 skills/osint_scanner.py <VEHICLE_PLATE> --type plate

# Output structured JSON for automated pipelines:
python3 skills/osint_scanner.py <TARGET> --json
```

---

## 3. Supported Indicators & Capabilities

| Indicator Type | Synthetic Examples | Automated Actions |
| :--- | :--- | :--- |
| **Phone (+91 India)** | `+919876543210`, `9876543210` | E.164 formatting, TRAI telecom circle & carrier allocation, deterministic UPI VPA generation (GPay, PhonePe, Paytm, BHIM, Amazon Pay), zero-login WhatsApp presence & name check, public directory dorks. |
| **Email Address** | `user@example.com` | MX DNS verification, disposable domain check, breach/pastebin/document public dorks. |
| **Username / Handle** | `target_user`, `@target` | 400+ platform enumeration (Sherlock / WhatsMyName), zero-login Instagram mirrors (Picuki, Imginn), tagged post/reel dorks, indexed comment queries. |
| **Real Name** | `"John Doe"`, `"Alex Smith"` | Professional career trajectory, university/academic document dorks, Indian corporate director checks (MCA / Zauba Corp), eCourts case registry dorks. |
| **Vehicle Plate (India)** | `DL10AB1234`, `MH02CL0555` | Offline RTO district parsing across all 36 Indian states/UTs, unauthenticated eChallan and Parivahan URL dispatch. |

---

## 4. Public Search Indexing Protocol

Whenever an investigation is triggered, execute targeted search engine dorks based on the target type:

### For Phone Numbers & UPI VPAs:
```text
"+91XXXXXXXXXX" OR "XXXXXXXXXX" OR "0XXXXXXXXXX"
"XXXXXXXXXX" (filetype:pdf OR filetype:xlsx OR filetype:docx)
"XXXXXXXXXX@paytm" OR "XXXXXXXXXX@ybl" OR "XXXXXXXXXX@okhdfcbank"
site:justdial.com "XXXXXXXXXX"
site:indiamart.com "XXXXXXXXXX"
site:facebook.com "XXXXXXXXXX"
```

### For Emails:
```text
"<EMAIL>"
site:pastebin.com "<EMAIL>"
site:github.com "<EMAIL>"
"<EMAIL>" (filetype:pdf OR filetype:txt)
```

### For Usernames & Handles (Profiles, Comments & Tagged Posts):
```text
# Basic presence & URL
site:instagram.com inurl:<USERNAME>
site:instagram.com "@<USERNAME>"

# Tagged posts, video reels & photo credits
site:instagram.com/p/ "@<USERNAME>"
site:instagram.com/reel/ "@<USERNAME>"
site:instagram.com "with @<USERNAME>" OR "pc: @<USERNAME>" OR "cr: @<USERNAME>"

# Publicly indexed comments & community discussions
site:instagram.com/p/ "<USERNAME>"
site:instagram.com/reel/ "<USERNAME>"
site:reddit.com/user "<USERNAME>" OR site:reddit.com "<USERNAME>"

# Cross-platform links
"<USERNAME>" (site:twitter.com OR site:x.com OR site:linkedin.com OR site:github.com)
site:t.me "<USERNAME>"
```

### For Real Names (Professional, Academic & Corporate):
```text
"<NAME>" "<LOCATION>"
"<NAME>" ("BBA" OR "MBA" OR "B.Tech" OR "University" OR "Vidyapith" OR "College")
"<NAME>" site:linkedin.com/in/
site:zaubacorp.com/company/ "<NAME>" OR site:tofler.in "<NAME>"
site:ecourts.gov.in "<NAME>"
"<NAME>" (filetype:pdf OR filetype:xlsx)
```

### For Vehicle Plates:
```text
"<PLATE>" (echallan OR parivahan)
"<PLATE_WITH_SPACES>"
```

---

## 5. Autonomous Multi-Agent Fan-Out Protocol

When any target identifier is received, the agent operates completely autonomously without asking for confirmation:
1. **Parallel Execution**:
   - Immediately execute the technical scanner: `python3 skills/osint_scanner.py "<TARGET>"`.
   - Concurrently fan out research tasks (using subagents or parallel search tooling) to probe public search engine dorks across global and Indian web indexes.
   - Run zero-login unauthenticated platform checks (WhatsApp OpenGraph, UPI VPA derivation, Instagram mirrors, MX records, RTO jurisdiction).
2. **Consolidation**:
   - Synthesize all findings from technical scripts, APIs, and web indexing into a unified Intelligence Dossier:
     1. **Target Identification & Technical Resolution** (Carrier/LSA, MX host, RTO jurisdiction, or profile links)
     2. **Platform & Financial/Identity Presence** (WhatsApp status, deterministic UPI VPAs, social mirror availability)
     3. **Deep Public Search Indexing Findings**:
        - Professional career trajectory & employment records
        - Academic credentials, university lists, research projects
        - Publicly indexed comments & community discussions
        - Tagged posts, video reels, and media credits (`pc: @...`, `with @...`)
        - Tagged accounts, collaborators, venues, and clustered sub-accounts
        - Leaks, document rosters, or directory entries
     4. **Direct Action & Verification Links** (UPI payment verification apps, eChallan, Parivahan, archive snapshots, or direct profile links)
