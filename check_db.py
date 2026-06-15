import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

for t in tables:
    print(f"\nTable: {t[0]}")
    cols = c.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for col in cols:
        print(col)

conn.close()