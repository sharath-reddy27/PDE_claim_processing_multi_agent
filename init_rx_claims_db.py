import sqlite3
import os

DB_PATH = "db/rx_claims.db"
os.makedirs("db", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ── Claims table ──────────────────────────────────────────────
cur.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id        TEXT PRIMARY KEY,
        error_code      TEXT,
        provider_id     TEXT,
        adjudication_ts TEXT,
        status          TEXT
    )
""")

# ── Provider mapping table ────────────────────────────────────
# old_provider_id : the stale / invalid / missing provider reference
# new_provider_id : the corrected CMS-validated provider ID
# provider_name   : human-readable name for demo output
# npi             : National Provider Identifier
# is_active       : 1 = valid & active in CMS master file
cur.execute("""
    CREATE TABLE IF NOT EXISTS provider_mapping (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        old_provider_id TEXT,
        new_provider_id TEXT NOT NULL,
        provider_name   TEXT,
        npi             TEXT,
        is_active       INTEGER DEFAULT 1
    )
""")

# ── Seed provider mapping data ────────────────────────────────
# old_provider_id matches actual values in claims table (P002, P004, etc.)
# new_provider_id is the CMS-validated corrected ID
# Empty string '' means provider_id was missing — resolved to a default active provider
# Clear existing seed data to avoid duplicates on re-run
cur.execute("DELETE FROM provider_mapping")

sample_providers = [
    # old_provider_id,  new_provider_id,  provider_name,                npi,           is_active
    ("",      "P002",  "Sunrise Pharmacy",          "1234567890", 1),  # missing → default
    ("P002",  "P002",  "Sunrise Pharmacy",          "1234567890", 1),
    ("P004",  "P004",  "MedPlus Pharmacy",          "2345678901", 1),
    ("P006",  "P006",  "HealthFirst Dispensary",    "3456789012", 1),
    ("P008",  "P008",  "CityMed Pharmacy",          "4567890123", 1),
    ("P010",  "P010",  "National Rx Center",        "5678901234", 1),
    ("P012",  "P012",  "Riverside Pharmacy",        "6789012345", 1),
    ("P014",  "P014",  "PharmaPlus",                "7890123456", 1),
    ("P016",  "P016",  "QuickRx Dispensary",        "8901234567", 1),
    ("P018",  "P018",  "WellCare Pharmacy",         "9012345678", 1),
    ("P020",  "P020",  "MediServe Rx",              "0123456789", 1),
    # Retired / inactive providers — mapped to active replacements
    ("P022",  "P002",  "Sunrise Pharmacy (merged)",  "1234567890", 0),
    ("P024",  "P004",  "MedPlus Pharmacy (merged)",  "2345678901", 0),
]

cur.executemany("""
    INSERT INTO provider_mapping
        (old_provider_id, new_provider_id, provider_name, npi, is_active)
    VALUES (?, ?, ?, ?, ?)
""", sample_providers)

conn.commit()
conn.close()

print("rx_claims.db initialized ✅")
print(f"  → {len(sample_providers)} provider mappings seeded into provider_mapping table.")
