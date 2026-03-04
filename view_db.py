import sqlite3

print("\n========== rx_claims.db ==========")
conn = sqlite3.connect("db/rx_claims.db")
cur = conn.cursor()
print("\n--- CLAIMS TABLE ---")
cur.execute("SELECT * FROM claims")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("  (no records)")

print("\n--- PROVIDER MAPPING TABLE ---")
cur.execute("SELECT * FROM provider_mapping")
rows = cur.fetchall()
if rows:
    print(f"  {'ID':<5} {'OLD_PROVIDER_ID':<16} {'NEW_PROVIDER_ID':<16} {'PROVIDER_NAME':<25} {'NPI':<14} {'ACTIVE'}")
    print(f"  {'-'*5} {'-'*16} {'-'*16} {'-'*25} {'-'*14} {'-'*6}")
    for row in rows:
        print(f"  {str(row[0]):<5} {str(row[1]):<16} {str(row[2]):<16} {str(row[3]):<25} {str(row[4]):<14} {row[5]}")
else:
    print("  (no records)")
conn.close()

print("\n========== reports.db ==========")
conn2 = sqlite3.connect("db/reports.db")
cur2 = conn2.cursor()
print("\n--- REPORTS TABLE ---")
cur2.execute("SELECT * FROM reports")
rows2 = cur2.fetchall()
if rows2:
    for row in rows2:
        print(row)
else:
    print("  (no records)")
conn2.close()