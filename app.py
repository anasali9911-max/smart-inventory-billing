"""Smart Inventory & Billing System for small retail shops.
Flask + SQLite. Run: python app.py
"""
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, g, render_template, request, redirect,
                   url_for, session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "shop.db"))
NEAR_EXPIRY_DAYS = 30

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','staff'))
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 5,
    expiry_date TEXT
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    customer TEXT,
    total REAL NOT NULL,
    user_id INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER REFERENCES products(id),
    name TEXT NOT NULL,
    price REAL NOT NULL,
    qty INTEGER NOT NULL
);
"""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                   ("admin", generate_password_hash("admin123"), "admin"))
    db.commit()
    db.close()


# ---------- auth ----------
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if session.get("role") != "admin":
            flash("Only admin can access that page.", "danger")
            return redirect(url_for("dashboard"))
        return view(*a, **kw)
    return login_required(wrapped)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE username = ?",
                                (request.form["username"].strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=user["id"], username=user["username"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- dashboard ----------
def stock_alerts(db):
    today = date.today()
    limit = (today + timedelta(days=NEAR_EXPIRY_DAYS)).isoformat()
    low = db.execute("SELECT * FROM products WHERE quantity <= low_stock_threshold "
                     "ORDER BY quantity").fetchall()
    expired = db.execute("SELECT * FROM products WHERE expiry_date IS NOT NULL "
                         "AND expiry_date < ? ORDER BY expiry_date", (today.isoformat(),)).fetchall()
    near = db.execute("SELECT * FROM products WHERE expiry_date IS NOT NULL "
                      "AND expiry_date >= ? AND expiry_date <= ? ORDER BY expiry_date",
                      (today.isoformat(), limit)).fetchall()
    return low, expired, near


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    low, expired, near = stock_alerts(db)
    today = date.today().isoformat()
    row = db.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) c FROM sales "
                     "WHERE date(created_at) = ?", (today,)).fetchone()
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    return render_template("dashboard.html", low=low, expired=expired, near=near,
                           today_total=row["t"], today_count=row["c"],
                           total_products=total_products, days=NEAR_EXPIRY_DAYS)


# ---------- products ----------
def parse_product_form(form):
    name = form.get("name", "").strip()
    if not name:
        raise ValueError("Product name is required.")
    try:
        price = float(form["price"])
        quantity = int(form["quantity"])
        threshold = int(form.get("low_stock_threshold") or 5)
    except (ValueError, KeyError):
        raise ValueError("Price, quantity and threshold must be valid numbers.")
    if price < 0 or quantity < 0 or threshold < 0:
        raise ValueError("Values cannot be negative.")
    expiry = form.get("expiry_date") or None
    if expiry:
        try:
            datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid expiry date.")
    return name, price, quantity, threshold, expiry


@app.route("/products")
@login_required
def products():
    q = request.args.get("q", "").strip()
    db = get_db()
    rows = db.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY name",
                      (f"%{q}%",)).fetchall()
    limit = (date.today() + timedelta(days=NEAR_EXPIRY_DAYS)).isoformat()
    return render_template("products.html", products=rows, q=q,
                           today=date.today().isoformat(), limit=limit)


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def product_add():
    if request.method == "POST":
        try:
            data = parse_product_form(request.form)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("product_form.html", product=request.form, mode="Add")
        get_db().execute("INSERT INTO products (name, price, quantity, low_stock_threshold, "
                         "expiry_date) VALUES (?,?,?,?,?)", data)
        get_db().commit()
        flash("Product added.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product={}, mode="Add")


@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if product is None:
        abort(404)
    if request.method == "POST":
        try:
            data = parse_product_form(request.form)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("product_form.html", product=request.form, mode="Edit")
        db.execute("UPDATE products SET name=?, price=?, quantity=?, low_stock_threshold=?, "
                   "expiry_date=? WHERE id=?", (*data, pid))
        db.commit()
        flash("Product updated.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product=dict(product), mode="Edit")

@app.route("/products/<int:pid>/delete", methods=["POST"])
@admin_required
def product_delete(pid):
    db = get_db()
    # keep sales history intact: sale_items store name/price snapshots
    db.execute("UPDATE sale_items SET product_id = NULL WHERE product_id = ?", (pid,))
    db.execute("DELETE FROM products WHERE id = ?", (pid,))
    db.commit()
    flash("Product deleted.", "info")
    return redirect(url_for("products"))


# ---------- billing ----------
@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    db = get_db()
    if request.method == "POST":
        ids = request.form.getlist("product_id")
        qtys = request.form.getlist("qty")
        wanted = {}
        try:
            for pid, qty in zip(ids, qtys):
                if not pid:
                    continue
                qty = int(qty)
                if qty <= 0:
                    raise ValueError
                wanted[int(pid)] = wanted.get(int(pid), 0) + qty
        except ValueError:
            flash("Enter valid quantities.", "danger")
            return redirect(url_for("billing"))
        if not wanted:
            flash("Add at least one item to the bill.", "warning")
            return redirect(url_for("billing"))

        today = date.today().isoformat()
        lines, total = [], 0.0
        for pid, qty in wanted.items():
            p = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
            if p is None:
                flash("A selected product no longer exists.", "danger")
                return redirect(url_for("billing"))
            if p["expiry_date"] and p["expiry_date"] < today:
                flash(f"'{p['name']}' is expired and cannot be sold.", "danger")
                return redirect(url_for("billing"))
            if qty > p["quantity"]:
                flash(f"Not enough stock for '{p['name']}' (available: {p['quantity']}).", "danger")
                return redirect(url_for("billing"))
            lines.append((p, qty))
            total += p["price"] * qty

        try:
            cur = db.execute("INSERT INTO sales (created_at, customer, total, user_id) "
                             "VALUES (?,?,?,?)",
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              request.form.get("customer", "").strip() or "Walk-in",
                              round(total, 2), session["user_id"]))
            sale_id = cur.lastrowid
            for p, qty in lines:
                db.execute("INSERT INTO sale_items (sale_id, product_id, name, price, qty) "
                           "VALUES (?,?,?,?,?)", (sale_id, p["id"], p["name"], p["price"], qty))
                db.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                           (qty, p["id"]))
            db.commit()
        except sqlite3.Error:
            db.rollback()
            flash("Could not save the bill. Please try again.", "danger")
            return redirect(url_for("billing"))
        flash("Bill generated and stock updated.", "success")
        return redirect(url_for("invoice", sale_id=sale_id))

    today = date.today().isoformat()
    items = db.execute("SELECT id, name, price, quantity FROM products WHERE quantity > 0 "
                       "AND (expiry_date IS NULL OR expiry_date >= ?) ORDER BY name",
                       (today,)).fetchall()
    return render_template("billing.html", products=[dict(r) for r in items])


@app.route("/sales")
@login_required
def sales():
    rows = get_db().execute(
        "SELECT s.*, u.username FROM sales s LEFT JOIN users u ON u.id = s.user_id "
        "ORDER BY s.id DESC LIMIT 200").fetchall()
    return render_template("sales.html", sales=rows)


@app.route("/sales/<int:sale_id>")
@login_required
def invoice(sale_id):
    db = get_db()
    sale = db.execute("SELECT s.*, u.username FROM sales s LEFT JOIN users u "
                      "ON u.id = s.user_id WHERE s.id = ?", (sale_id,)).fetchone()
    if sale is None:
        abort(404)
    items = db.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
    return render_template("invoice.html", sale=sale, items=items)


# ---------- reports ----------
@app.route("/reports")
@login_required
def reports():
    db = get_db()
    since = (date.today() - timedelta(days=29)).isoformat()
    daily = db.execute("SELECT date(created_at) d, SUM(total) t, COUNT(*) c FROM sales "
                       "WHERE date(created_at) >= ? GROUP BY d ORDER BY d", (since,)).fetchall()
    monthly = db.execute("SELECT strftime('%Y-%m', created_at) m, SUM(total) t, COUNT(*) c "
                         "FROM sales GROUP BY m ORDER BY m DESC LIMIT 12").fetchall()
    top = db.execute("SELECT name, SUM(qty) q, SUM(qty*price) r FROM sale_items "
                     "GROUP BY name ORDER BY q DESC LIMIT 5").fetchall()
    return render_template("reports.html", daily=[dict(r) for r in daily],
                           monthly=[dict(r) for r in monthly], top=top)


# ---------- staff management ----------
@app.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    db = get_db()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")
        if not username or len(password) < 6 or role not in ("admin", "staff"):
            flash("Username required and password must be at least 6 characters.", "danger")
        else:
            try:
                db.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                           (username, generate_password_hash(password), role))
                db.commit()
                flash("User created.", "success")
            except sqlite3.IntegrityError:
                flash("Username already exists.", "danger")
        return redirect(url_for("users"))
    return render_template("users.html",
                           users=db.execute("SELECT id, username, role FROM users").fetchall())


init_db()

if __name__ == "__main__":
    app.run(debug=True)
