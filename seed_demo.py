"""Optional: load demo products so screenshots look good. Run: python seed_demo.py"""
import sqlite3
from datetime import date, timedelta
from app import DB_PATH, init_db

init_db()
d = lambda n: (date.today() + timedelta(days=n)).isoformat()
rows = [
    ("Tata Salt 1kg", 28, 40, 10, d(300)), ("Aashirvaad Atta 5kg", 245, 12, 5, d(120)),
    ("Amul Butter 100g", 56, 4, 5, d(12)), ("Britannia Bread", 40, 15, 5, d(3)),
    ("Maggi Noodles", 14, 60, 10, d(200)), ("Parle-G Biscuit", 10, 80, 15, d(150)),
    ("Amul Milk 500ml", 30, 3, 10, d(2)), ("Fortune Oil 1L", 150, 20, 5, d(250)),
    ("Old Curd Pack", 25, 6, 5, d(-2)), ("Surf Excel 1kg", 130, 18, 5, None),
]
db = sqlite3.connect(DB_PATH)
if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
    db.executemany("INSERT INTO products (name, price, quantity, low_stock_threshold, expiry_date) "
                   "VALUES (?,?,?,?,?)", rows)
    db.commit()
    print("Demo products added.")
else:
    print("Products already exist, skipped.")
