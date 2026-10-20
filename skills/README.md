# PraLabs Zero-Login OSINT Skills & Execution Suite

A unified, multi-vector Open-Source Intelligence suite engineered to **automatically execute scripts, commands, and public search indexing** for any provided **phone number, email address, username/handle, real name, or vehicle plate**—operating 100% without logins, API keys, or accounts.

---

## Unified Execution Architecture

The suite includes an automated orchestrator: [`osint_scanner.py`](./osint_scanner.py). It automatically detects the indicator type and executes the relevant toolchain, metadata checkers, and public dork generators.

```text
Target Input (Phone / Email / Username / Name / Plate)
   │
   ├── [Auto-Detection Engine]
   │
   ├── Phone (+91) ───► BSNL/Airtel/Jio Series ──► Zero-Login WhatsApp Check ──► Public Dorks
   ├── Email ────────► DNS / MX Records Check ─► Disposable Domain Filter ────► Public Dorks
   ├── Username ─────► Direct Profile Maps ────► Zero-Login IG Mirrors ──────► Sherlock / Dorks
   ├── Real Name ────► MCA / Zauba Corp Dorks ──► eCourts Registries ──────────► Social Dorks
   └── Vehicle Plate ─► Offline RTO / State ────► Parivahan / eChallan URLs ───► Public Dorks
```

---

## Quick Execution

### 1. Unified Automated Scanner
```bash
# Auto-detects input type and executes all relevant checks:
python3 skills/osint_scanner.py 9457548199
python3 skills/osint_scanner.py user@example.com
python3 skills/osint_scanner.py target_handle
python3 skills/osint_scanner.py "Rahul Sharma"
python3 skills/osint_scanner.py MH02CL0555

# Output in JSON format for pipelines:
python3 skills/osint_scanner.py 9457548199 --json
```

---

## Skills Catalog & Goals

| Skill | Directory | Primary Goal & Execution |
| :--- | :--- | :--- |
| **Phone OSINT** | [`phone-osint-india/`](./phone-osint-india/SKILL.md) | Auto-extract carrier series, telecom circle, run zero-login WhatsApp presence checks, and test public web indexing. |
| **WhatsApp OSINT** | [`whatsapp-osint/`](./whatsapp-osint/SKILL.md) | Check WhatsApp presence, personal vs business classification, and public display names without authentication. |
| **Instagram OSINT** | [`instagram-osint/`](./instagram-osint/SKILL.md) | Generate unauthenticated mirror links (Picuki, Imginn, Dumpor), run public dorks, and prepare Instaloader commands. |
| **Social Footprint** | [`social-footprint-osint/`](./social-footprint-osint/SKILL.md) | Cross-platform handle reconnaissance across 400+ platforms via Sherlock, Blackbird, and WhatsMyName patterns. |
| **Vehicle OSINT** | [`vehicle-osint-india/`](./vehicle-osint-india/SKILL.md) | Offline Indian RTO district parsing, unauthenticated eChallan portal link generation, and violation dorking. |

---

## Directory Layout

```
skills/
├── README.md
├── osint_scanner.py                        # Unified multi-indicator orchestrator
├── whatsapp-osint/
│   ├── SKILL.md
│   └── scripts/wa_link_generator.py        # Live zero-login WhatsApp inspector
├── instagram-osint/
│   ├── SKILL.md
│   └── scripts/ig_profile_inspector.py     # Unauthenticated mirror link & dork generator
├── social-footprint-osint/
│   └── SKILL.md                            # Cross-platform username reconnaissance
├── phone-osint-india/
│   ├── SKILL.md
│   └── scripts/phone_analyzer.py           # Indian telecom analyzer & dork constructor
└── vehicle-osint-india/
    ├── SKILL.md
    └── scripts/rto_lookup.py               # Offline Indian RTO district & plate parser
```
