import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# Add invoice number
c.execute("ALTER TABLE sales ADD COLUMN invoice_no TEXT")

# Add custom date
c.execute("ALTER TABLE sales ADD COLUMN invoice_date TEXT")

conn.commit()
conn.close()

print("✅ Invoice fields added")
