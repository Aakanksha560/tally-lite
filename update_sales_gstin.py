import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute("ALTER TABLE sales ADD COLUMN gstin TEXT")

conn.commit()
conn.close()

print("✅ GSTIN column added")
