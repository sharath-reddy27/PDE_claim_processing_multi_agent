"""
Seed a REJECT test claim — Error 781 with an unmappable provider ID (P999).
The RX agent will try to resolve P999 → no mapping found → REJECT.
"""
import sqlite3

conn = sqlite3.connect("db/rx_claims.db")
cur = conn.cursor()

# Remove existing REJECT test claim if re-running
cur.execute("DELETE FROM claims WHERE claim_id = 'TEST-REJECT-001'")

cur.execute("""
    INSERT INTO claims (claim_id, error_code, provider_id, adjudication_ts, status, received_date)
    VALUES ('TEST-REJECT-001', '781', 'P999', NULL, 'NEW', NULL)
""")
conn.commit()
conn.close()
print("✅ Seeded TEST-REJECT-001 (error=781, provider=P999, no mapping → will REJECT)")
