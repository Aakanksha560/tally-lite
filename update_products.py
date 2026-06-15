import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# Add GST column
c.execute("ALTER TABLE products ADD COLUMN gst_rate REAL DEFAULT 0")

# Add HSN code column
c.execute("ALTER TABLE products ADD COLUMN hsn_code TEXT")

conn.commit()
conn.close()

print("✅ Products table updated!")
