import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute("ALTER TABLE purchase_items ADD COLUMN gst_rate REAL")
c.execute("ALTER TABLE purchase_items ADD COLUMN cgst REAL")
c.execute("ALTER TABLE purchase_items ADD COLUMN sgst REAL")
c.execute("ALTER TABLE purchase_items ADD COLUMN total REAL")

conn.commit()
conn.close()

print("✅ purchase_items updated")
