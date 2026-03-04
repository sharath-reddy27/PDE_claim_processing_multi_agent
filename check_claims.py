import sqlite3

conn = sqlite3.connect("db/rx_claims.db")
cur = conn.cursor()
cur.execute("SELECT claim_id, error_code, provider_id, adjudication_ts, status, received_date FROM claims")
rows = cur.fetchall()
conn.close()

print(f"Total claims: {len(rows)}")
print("-" * 80)
for r in rows:
    print(f"  claim_id={r[0]} | error={r[1]} | provider={r[2]} | adj_ts={r[3]} | status={r[4]} | received={r[5]}")
