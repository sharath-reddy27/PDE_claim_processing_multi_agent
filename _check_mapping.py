import sqlite3
conn = sqlite3.connect("db/rx_claims.db")
cur = conn.cursor()

print("=== Provider Mapping Table ===")
cur.execute("SELECT * FROM provider_mapping")
for r in cur.fetchall():
    print(" ", r)

print()
print("=== 781 claims with non-empty provider_id (REJECT candidates) ===")
cur.execute("SELECT claim_id, provider_id, status FROM claims WHERE error_code='781' AND provider_id != '' AND status='NEW' LIMIT 10")
for r in cur.fetchall():
    print(" ", r)

conn.close()
