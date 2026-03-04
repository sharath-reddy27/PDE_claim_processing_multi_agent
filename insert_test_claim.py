import sqlite3

conn = sqlite3.connect("db/rx_claims.db")
cur = conn.cursor()

cur.execute("""
INSERT OR REPLACE INTO claims
(claim_id,error_code,provider_id,
adjudication_ts,status)
VALUES (?,?,?,?,?)
""",("TEST001","781",None,None,"NEW"))

cur.execute("""
INSERT OR REPLACE INTO claims
(claim_id,error_code,provider_id,
adjudication_ts,status)
VALUES (?,?,?,?,?)
""",("TEST002","935","P999","2026-01-15 10:00:00","ADJUDICATED"))

conn.commit()
conn.close()

print("TEST claims inserted")