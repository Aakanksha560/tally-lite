import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    cgst_rate REAL,
    sgst_rate REAL,
    default_gst REAL
)
''')

# Insert default (only once)
c.execute("INSERT OR IGNORE INTO settings (id, cgst_rate, sgst_rate, default_gst) VALUES (1, 9, 9, 18)")

conn.commit()
conn.close()

print("✅ Settings table ready")
