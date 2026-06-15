from flask import Flask, render_template, request, send_file, redirect
import sqlite3
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

def get_db():
    return sqlite3.connect("database.db")


# 🏠 HOME
@app.route('/')
def index():
    db = get_db()

    products = db.execute(
        "SELECT * FROM products"
    ).fetchall()

    total_products = db.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    low_stock = db.execute(
        "SELECT COUNT(*) FROM products WHERE quantity <= 5"
    ).fetchone()[0]

    today_sales = db.execute("""
        SELECT SUM(total)
        FROM sales
        WHERE invoice_date = date('now')
    """).fetchone()[0] or 0

    today_purchase = db.execute("""
        SELECT SUM(total)
        FROM purchases
        WHERE purchase_date = date('now')
    """).fetchone()[0] or 0

    gst = db.execute("""
        SELECT
            SUM(cgst),
            SUM(sgst)
        FROM sales_items
    """).fetchone()

    gst_payable = (gst[0] or 0) + (gst[1] or 0)

    db.close()

    return render_template(
        "index.html",
        products=products,
        total_products=total_products,
        low_stock=low_stock,
        today_sales=today_sales,
        today_purchase=today_purchase,
        gst_payable=gst_payable
    )


# ⚙️ SETTINGS
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        cgst = float(request.form['cgst'])
        sgst = float(request.form['sgst'])
        total = cgst + sgst

        cursor.execute("""
            UPDATE settings
            SET cgst_rate=?, sgst_rate=?, default_gst=?
            WHERE id=1
        """, (cgst, sgst, total))

        db.commit()
        db.close()
        return "✅ Settings Updated"

    settings = cursor.execute("SELECT * FROM settings WHERE id=1").fetchone()
    db.close()
    return render_template("settings.html", settings=settings)


# 📦 PURCHASE
@app.route('/purchase', methods=['GET', 'POST'])
def purchase():

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':

        invoice_no = request.form['invoice_no']
        purchase_date = request.form['purchase_date']
        party_id = request.form['party_id']

        name = request.form['name']
        qty = int(request.form['qty'])
        price = float(request.form['price'])
        gst_rate = float(request.form['gst_rate'])
        hsn = request.form['hsn_code']

        # Get Supplier Details
        party = cursor.execute(
            "SELECT * FROM parties WHERE id=?",
            (party_id,)
        ).fetchone()

        if not party:
            db.close()
            return "❌ Invalid supplier selected"

        supplier = party[1]
        gstin = party[2]

        # Check if product already exists
        product = cursor.execute(
            "SELECT * FROM products WHERE name=?",
            (name,)
        ).fetchone()

        if product:

            product_id = product[0]
            new_stock = product[3] + qty

            cursor.execute("""
                UPDATE products
                SET quantity=?,
                    price=?,
                    gst_rate=?,
                    hsn_code=?
                WHERE id=?
            """, (
                new_stock,
                price,
                gst_rate,
                hsn,
                product_id
            ))

        else:

            cursor.execute("""
                INSERT INTO products
                (
                    name,
                    price,
                    quantity,
                    gst_rate,
                    hsn_code
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                price,
                qty,
                gst_rate,
                hsn
            ))

            product_id = cursor.lastrowid

        # GST Calculation
        taxable = price * qty
        gst = taxable * (gst_rate / 100)

        cgst = gst / 2
        sgst = gst / 2

        total = taxable + gst

        # Purchase Header
        cursor.execute("""
            INSERT INTO purchases
            (
                invoice_no,
                purchase_date,
                supplier_name,
                gstin,
                total
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            invoice_no,
            purchase_date,
            supplier,
            gstin,
            total
        ))

        purchase_id = cursor.lastrowid

        # Purchase Item
        cursor.execute("""
            INSERT INTO purchase_items
            (
                purchase_id,
                product_id,
                quantity,
                price,
                gst_rate,
                cgst,
                sgst,
                total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            purchase_id,
            product_id,
            qty,
            price,
            gst_rate,
            cgst,
            sgst,
            total
        ))

        db.commit()
        db.close()

        return f"""
        ✅ Purchase Saved Successfully

        <br><br>

        Purchase Invoice:
        {invoice_no}

        <br><br>

        Supplier:
        {supplier}

        <br><br>

        Total:
        ₹{total:.2f}

        <br><br>

        <a href="/purchase">
            Add Another Purchase
        </a>
        """

    parties = cursor.execute("""
        SELECT *
        FROM parties
    """).fetchall()

    db.close()

    return render_template(
        "purchase.html",
        parties=parties
    )


# 🧾 SALES (MULTI PRODUCT + AUTO INVOICE NUMBER)
@app.route('/sale', methods=['GET', 'POST'])
def sale():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':

        invoice_date = request.form['invoice_date']

        party_id = request.form['party_id']

        party = cursor.execute(
            "SELECT * FROM parties WHERE id=?",
            (party_id,)
        ).fetchone()

        if not party:
            db.close()
            return "❌ Invalid customer selected"

        customer = party[1]
        gstin = party[2]

        # Auto Invoice Number
        last_sale = cursor.execute("""
            SELECT id
            FROM sales
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if last_sale:
            invoice_no = f"INV-{last_sale[0] + 1:04d}"
        else:
            invoice_no = "INV-0001"

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('qty[]')

        settings = cursor.execute(
            "SELECT * FROM settings WHERE id=1"
        ).fetchone()

        total_invoice = 0

        cursor.execute("""
            INSERT INTO sales
            (
                invoice_no,
                invoice_date,
                total,
                customer_name,
                gstin
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            invoice_no,
            invoice_date,
            0,
            customer,
            gstin
        ))

        sale_id = cursor.lastrowid

        for i in range(len(product_ids)):

            product_id = product_ids[i]
            qty = int(quantities[i])

            product = cursor.execute(
                "SELECT * FROM products WHERE id=?",
                (product_id,)
            ).fetchone()

            if not product:
                continue

            price = product[2]
            stock = product[3]

            if qty > stock:
                db.close()
                return f"❌ Not enough stock for {product[1]}"

            taxable = price * qty

            cgst = taxable * (settings[1] / 100)
            sgst = taxable * (settings[2] / 100)

            total = taxable + cgst + sgst

            total_invoice += total

            cursor.execute("""
                INSERT INTO sales_items
                (
                    sale_id,
                    product_id,
                    quantity,
                    price,
                    gst_rate,
                    cgst,
                    sgst,
                    total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id,
                product_id,
                qty,
                price,
                settings[3],
                cgst,
                sgst,
                total
            ))

            cursor.execute("""
                UPDATE products
                SET quantity=?
                WHERE id=?
            """, (
                stock - qty,
                product_id
            ))

        cursor.execute("""
            UPDATE sales
            SET total=?
            WHERE id=?
        """, (
            total_invoice,
            sale_id
        ))

        db.commit()
        db.close()

        return f"""
        ✅ Invoice Created Successfully

        <br><br>

        Invoice Number: {invoice_no}

        <br><br>

        Invoice Total: ₹{total_invoice:.2f}

        <br><br>

        <a href="/invoice/{sale_id}">
            Download Invoice PDF
        </a>
        """

    products = cursor.execute(
        "SELECT * FROM products"
    ).fetchall()

    parties = cursor.execute(
        "SELECT * FROM parties"
    ).fetchall()

    db.close()

    return render_template(
        "sales.html",
        products=products,
        parties=parties
    )

# 🧾 PARTIES
@app.route('/party', methods=['GET', 'POST'])
def party():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        name = request.form['name']
        gstin = request.form['gstin']
        ptype = request.form['type']

        cursor.execute(
            "INSERT INTO parties (name, gstin, type) VALUES (?, ?, ?)",
            (name, gstin, ptype)
        )

        db.commit()
        db.close()
        return "✅ Party Added"

    parties = cursor.execute("SELECT * FROM parties").fetchall()
    db.close()

    return render_template("party.html", parties=parties)

# 📊 MONTHLY REPORT
@app.route('/monthly')
def monthly():
    db = get_db()
    month = request.args.get('month')

    query = """
        SELECT 
            si.gst_rate,
            SUM(si.quantity * si.price),
            SUM(si.cgst),
            SUM(si.sgst),
            SUM(si.total)
        FROM sales_items si
        JOIN sales s ON si.sale_id = s.id
    """

    params = []

    if month:
        query += " WHERE strftime('%Y-%m', s.invoice_date)=?"
        params.append(month)

    query += " GROUP BY si.gst_rate"

    rows = db.execute(query, params).fetchall()
    db.close()

    return render_template("monthly.html", rows=rows, month=month)


# 📊 GSTR-1
@app.route('/gstr1')
def gstr1():
    db = get_db()

    b2b = db.execute("""
        SELECT 
            si.gst_rate,
            SUM(si.quantity * si.price),
            SUM(si.cgst),
            SUM(si.sgst),
            SUM(si.total)
        FROM sales_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.gstin IS NOT NULL AND s.gstin != ''
        GROUP BY si.gst_rate
    """).fetchall()

    b2c = db.execute("""
        SELECT 
            si.gst_rate,
            SUM(si.quantity * si.price),
            SUM(si.cgst),
            SUM(si.sgst),
            SUM(si.total)
        FROM sales_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.gstin IS NULL OR s.gstin = ''
        GROUP BY si.gst_rate
    """).fetchall()

    db.close()
    return render_template("gstr1.html", b2b=b2b, b2c=b2c)


# 📄 GSTR-3B
@app.route('/gstr3b')
def gstr3b():
    db = get_db()

    sales = db.execute("SELECT SUM(cgst), SUM(sgst) FROM sales_items").fetchone()
    purchase = db.execute("SELECT SUM(cgst), SUM(sgst) FROM purchase_items").fetchone()

    db.close()

    output_cgst = sales[0] or 0
    output_sgst = sales[1] or 0

    input_cgst = purchase[0] or 0
    input_sgst = purchase[1] or 0

    net_cgst = output_cgst - input_cgst
    net_sgst = output_sgst - input_sgst

    total = net_cgst + net_sgst

    return render_template("gstr3b.html",
        output_cgst=output_cgst,
        output_sgst=output_sgst,
        input_cgst=input_cgst,
        input_sgst=input_sgst,
        net_cgst=net_cgst,
        net_sgst=net_sgst,
        total_payable=total
    )


# 📥 EXPORT GSTR-1
@app.route('/export/gstr1')
def export_gstr1():
    db = get_db()

    wb = Workbook()
    ws = wb.active
    ws.title = "GSTR-1"

    ws.append(["Type", "GST%", "Taxable", "CGST", "SGST", "Total"])

    rows = db.execute("""
        SELECT 
            CASE 
                WHEN s.gstin IS NOT NULL AND s.gstin != '' THEN 'B2B'
                ELSE 'B2C'
            END,
            si.gst_rate,
            SUM(si.quantity * si.price),
            SUM(si.cgst),
            SUM(si.sgst),
            SUM(si.total)
        FROM sales_items si
        JOIN sales s ON si.sale_id = s.id
        GROUP BY 1, si.gst_rate
    """).fetchall()

    for r in rows:
        ws.append(r)

    db.close()

    file = "gstr1.xlsx"
    wb.save(file)
    return send_file(file, as_attachment=True)


# 🧾 PROFESSIONAL GST INVOICE PDF
@app.route('/invoice/<int:sale_id>')
def invoice(sale_id):

    db = get_db()

    company = db.execute("""
        SELECT * FROM company
        WHERE id=1
    """).fetchone()

    sale = db.execute("""
        SELECT *
        FROM sales
        WHERE id=?
    """, (sale_id,)).fetchone()

    items = db.execute("""
        SELECT
            p.name,
            p.hsn_code,
            si.quantity,
            si.price,
            si.gst_rate,
            si.cgst,
            si.sgst,
            si.total
        FROM sales_items si
        JOIN products p
        ON si.product_id = p.id
        WHERE si.sale_id=?
    """, (sale_id,)).fetchall()

    db.close()

    filename = f"invoice_{sale_id}.pdf"

    doc = SimpleDocTemplate(filename)

    styles = getSampleStyleSheet()

    elements = []

    # Company Header

    elements.append(
        Paragraph(
            f"<b>{company[1]}</b>",
            styles['Title']
        )
    )

    elements.append(
        Paragraph(company[2], styles['Normal'])
    )

    elements.append(
        Paragraph(
            f"GSTIN: {company[3]}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Phone: {company[4]}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph("<br/>", styles['Normal'])
    )

    elements.append(
        Paragraph(
            "<b>GST TAX INVOICE</b>",
            styles['Heading1']
        )
    )

    # Invoice Details

    elements.append(
        Paragraph(
            f"Invoice No: {sale[1]}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Date: {sale[2]}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Customer: {sale[4]}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Customer GSTIN: {sale[5] or 'B2C'}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph("<br/>", styles['Normal'])
    )

    # Table

    table_data = [[
        "Product",
        "HSN",
        "Qty",
        "Rate",
        "GST %",
        "CGST",
        "SGST",
        "Total"
    ]]

    total_cgst = 0
    total_sgst = 0
    grand_total = 0

    for item in items:

        table_data.append([
            item[0],
            item[1] or "",
            item[2],
            f"₹{item[3]:.2f}",
            f"{item[4]}%",
            f"₹{item[5]:.2f}",
            f"₹{item[6]:.2f}",
            f"₹{item[7]:.2f}"
        ])

        total_cgst += item[5]
        total_sgst += item[6]
        grand_total += item[7]

    table = Table(table_data)

    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))

    elements.append(table)

    elements.append(
        Paragraph("<br/>", styles['Normal'])
    )

    # GST Summary

    elements.append(
        Paragraph(
            f"Total CGST: ₹{total_cgst:.2f}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Total SGST: ₹{total_sgst:.2f}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"<b>Grand Total: ₹{grand_total:.2f}</b>",
            styles['Heading2']
        )
    )

    elements.append(
        Paragraph("<br/><br/>", styles['Normal'])
    )

    elements.append(
        Paragraph(
            "Authorized Signatory",
            styles['Normal']
        )
    )

    doc.build(elements)

    return send_file(
        filename,
        as_attachment=True
    )


@app.route('/company', methods=['GET', 'POST'])
def company():

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':

        cursor.execute("""
        UPDATE company
        SET name=?,
            address=?,
            gstin=?,
            phone=?
        WHERE id=1
        """,
        (
            request.form['name'],
            request.form['address'],
            request.form['gstin'],
            request.form['phone']
        ))

        db.commit()

    company = cursor.execute(
        "SELECT * FROM company WHERE id=1"
    ).fetchone()

    db.close()

    return render_template(
        "company.html",
        company=company
    )

# ➕ ADD PRODUCT
@app.route('/add', methods=['POST'])
def add_product():

    db = get_db()
    cursor = db.cursor()

    name = request.form['name']
    price = float(request.form['price'])
    qty = int(request.form['qty'])

    cursor.execute("""
        INSERT INTO products
        (name, price, quantity, gst_rate, hsn_code)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        price,
        qty,
        18,
        ''
    ))

    db.commit()
    db.close()

    return redirect('/')

# 🗑 DELETE PRODUCT
@app.route('/delete/<int:id>')
def delete_product(id):

    db = get_db()

    db.execute(
        "DELETE FROM products WHERE id=?",
        (id,)
    )

    db.commit()
    db.close()

    return redirect('/')

@app.route('/ledger/<int:party_id>')
def ledger(party_id):

    db = get_db()

    party = db.execute("""
        SELECT *
        FROM parties
        WHERE id=?
    """, (party_id,)).fetchone()

    sales = db.execute("""
        SELECT
            invoice_no,
            invoice_date,
            total
        FROM sales
        WHERE customer_name=?
        ORDER BY id DESC
    """, (party[1],)).fetchall()

    total_sales = sum(row[2] for row in sales)

    db.close()

    return render_template(
        "ledger.html",
        party=party,
        sales=sales,
        total_sales=total_sales
    )

@app.route('/purchase-summary')
def purchase_summary():

    db = get_db()

    rows = db.execute("""
        SELECT
            gst_rate,
            SUM(quantity * price),
            SUM(cgst),
            SUM(sgst),
            SUM(total)
        FROM purchase_items
        GROUP BY gst_rate
        ORDER BY gst_rate
    """).fetchall()

    db.close()

    return render_template(
        "purchase_summary.html",
        rows=rows
    )

# 📒 SUPPLIER LEDGER
@app.route('/supplier-ledger/<int:party_id>')
def supplier_ledger(party_id):

    db = get_db()

    party = db.execute("""
        SELECT *
        FROM parties
        WHERE id=?
    """, (party_id,)).fetchone()

    if not party:
        db.close()
        return "❌ Supplier not found"

    purchases = db.execute("""
        SELECT
            invoice_no,
            purchase_date,
            total
        FROM purchases
        WHERE supplier_name=?
        ORDER BY id DESC
    """, (party[1],)).fetchall()

    total_purchase = sum(
        row[2] for row in purchases
    )

    db.close()

    return render_template(
        "supplier_ledger.html",
        party=party,
        purchases=purchases,
        total_purchase=total_purchase
    )

# 📈 FINANCIAL YEAR REPORT
@app.route('/financial-year')
def financial_year():

    db = get_db()

    fy = request.args.get('fy')

    sales = []
    total_sales = 0

    if fy:

        start_year = int(fy[:4])
        end_year = start_year + 1

        start_date = f"{start_year}-04-01"
        end_date = f"{end_year}-03-31"

        sales = db.execute("""
            SELECT
                invoice_no,
                invoice_date,
                customer_name,
                total
            FROM sales
            WHERE invoice_date BETWEEN ? AND ?
            ORDER BY invoice_date
        """, (
            start_date,
            end_date
        )).fetchall()

        total_sales = sum(
            row[3] for row in sales
        )

    db.close()

    return render_template(
        "financial_year.html",
        sales=sales,
        total_sales=total_sales,
        fy=fy
    )


if __name__ == "__main__":
    app.run(debug=True)
    



