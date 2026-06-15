import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()


# 🛍️ Products
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price REAL,
    quantity INTEGER,
    gst_rate REAL,
    hsn_code TEXT
)
""")


# ⚙️ Settings (GST rates)
c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    cgst_rate REAL,
    sgst_rate REAL,
    default_gst REAL
)
""")

# Insert default settings if not exists
c.execute("SELECT * FROM settings WHERE id=1")
if not c.fetchone():
    c.execute("""
        INSERT INTO settings (id, cgst_rate, sgst_rate, default_gst)
        VALUES (1, 9, 9, 18)
    """)


# 🧾 Sales (Invoice header)
c.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    invoice_date TEXT,
    total REAL,
    customer_name TEXT,
    gstin TEXT
)
""")


# 📦 Sales Items (MULTI-PRODUCT SUPPORT)
c.execute("""
CREATE TABLE IF NOT EXISTS sales_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    price REAL,
    gst_rate REAL,
    cgst REAL,
    sgst REAL,
    total REAL
)
""")


# 🧾 Purchases
c.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    purchase_date TEXT,
    supplier_name TEXT,
    gstin TEXT,
    total REAL
)
""")



# 📦 Purchase Items
c.execute("""
CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    price REAL,
    gst_rate REAL,
    cgst REAL,
    sgst REAL,
    total REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    gstin TEXT,
    type TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY,
    name TEXT,
    address TEXT,
    gstin TEXT,
    phone TEXT
)
""")

c.execute("""
INSERT OR IGNORE INTO company
(id,name,address,gstin,phone)
VALUES
(
1,
'Your Company',
'Your Address',
'GSTIN HERE',
'9876543210'
)
""")

conn.commit()
conn.close()

print("✅ Database created successfully!")

