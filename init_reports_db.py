import sqlite3
import os
DB_PATH = "db/reports.db"

os.makedirs("db",exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY
            AUTOINCREMENT,
            claim_id TEXT,
            error_code TEXT,
            provider_id TEXT,
            decision TEXT,
            reason TEXT,
            created_ts TEXT
            )
            """)
conn.commit()
conn.close()
print("reports.db initialized")
