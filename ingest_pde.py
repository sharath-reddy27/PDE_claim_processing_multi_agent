import csv
import sqlite3

DB = "db/rx_claims.db"

CSV_FILE = "data/pde_flat_file.csv"

conn = sqlite3.connect(DB)

cur = conn.cursor()

with open(CSV_FILE, newline="",
encoding= "utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute("""
        INSERT or REPLACE INTO claims
        (claim_id, error_code,provider_id, adjudication_ts, status)
        VALUES(?,?,?,?,?)""",(
                row["Claim_ID"],
                row["Error_Code"],
                row["Provider_ID"],
                row["Adjudication_Timestamp"],
                "NEW"

        ))
conn.commit()
conn.close()

print("PDE flat file ingested into SQLite")
