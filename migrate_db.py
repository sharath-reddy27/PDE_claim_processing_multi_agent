"""
DB Migration: Add received_date column to claims and seed test data.
Run once: python migrate_db.py
"""
import sqlite3

DB_PATH = "db/rx_claims.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add received_date column (safe – skips if already exists)
try:
    cur.execute("ALTER TABLE claims ADD COLUMN received_date TEXT")
    print("✅ Column 'received_date' added to claims table.")
except sqlite3.OperationalError:
    print("ℹ️  Column 'received_date' already exists.")

# Seed received_date values:
#   equal to adjudication_ts (2025-01-02) → will trigger REPROCESS
#   older than adjudication_ts            → will trigger ALREADY_PROCESSED
updates = [
    ("2025-01-02", "C0002"),   # equal  → REPROCESS
    ("2025-01-02", "C0004"),   # equal  → REPROCESS
    ("2024-12-15", "C0006"),   # older  → ALREADY_PROCESSED
    ("2024-11-20", "C0008"),   # older  → ALREADY_PROCESSED
    ("2025-01-02", "C0010"),   # equal  → REPROCESS
    ("2024-12-01", "C0012"),   # older  → ALREADY_PROCESSED
    ("2025-01-02", "C0014"),   # equal  → REPROCESS
    ("2024-10-05", "C0016"),   # older  → ALREADY_PROCESSED
    ("2025-01-02", "C0018"),   # equal  → REPROCESS
    ("2024-09-10", "C0020"),   # older  → ALREADY_PROCESSED
    ("2026-01-15", "TEST002"), # equal  → REPROCESS
]
for rd, cid in updates:
    cur.execute("UPDATE claims SET received_date=? WHERE claim_id=?", (rd, cid))

# All remaining 935 claims get an older received_date → ALREADY_PROCESSED
cur.execute(
    "UPDATE claims SET received_date='2024-12-01' WHERE error_code='935' AND (received_date IS NULL OR received_date='')"
)

conn.commit()

# Verify
print("\n📋 Sample 935 claims after migration:")
print(f"  {'claim_id':<10} {'received_date':<15} {'adjudication_ts':<20} {'status'}")
for row in cur.execute(
    "SELECT claim_id, received_date, adjudication_ts, status FROM claims WHERE error_code='935' LIMIT 10"
).fetchall():
    print(f"  {row[0]:<10} {str(row[1]):<15} {str(row[2]):<20} {row[3]}")

conn.close()
print("\n✅ Migration complete.")
