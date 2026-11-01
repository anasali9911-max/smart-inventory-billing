# 🛒 Smart Inventory & Billing System

A lightweight web app for **small retailers (kirana / general stores)** to manage stock, generate bills, and avoid losses from stock-outs and expired products.

## The Problem
Small shopkeepers still track stock and sales in notebooks. This causes:
- Surprise **stock-outs** of fast-moving items
- Losses from **expired products** nobody noticed
- **Billing mistakes** and no reliable sales record

## The Solution
This app automates stock tracking, billing and alerts with a simple, easy-to-use interface.

## Features
- 🔐 Secure login with **Admin / Staff** roles (hashed passwords)
- 📦 Product management: add, edit, delete, search
- 🧾 Billing: select items, auto-calculated totals, **stock auto-reduced**, printable invoice
- ⚠️ **Low-stock**, **near-expiry** and **expired** alerts on the dashboard
- 🚫 Expired or out-of-stock items cannot be billed
- 📊 Daily and monthly sales reports with chart and top-selling products
- 👥 Admin can create staff accounts

## Tech Stack
Python, Flask, SQLite, Jinja2, Bootstrap 5, Chart.js

## Setup
```bash
git clone https://github.com/<your-username>/smart-inventory-billing.git
cd smart-inventory-billing
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed_demo.py          # optional: demo data
python app.py
```
Open http://127.0.0.1:5000

**Default login:** `admin` / `admin123` — change it after first login (Staff page → create a new admin).

## Project Structure
```
app.py            # routes, database logic, auth
seed_demo.py      # optional demo data
templates/        # Jinja2 HTML templates
requirements.txt
```

## Screenshots
Add your screenshots in a `screenshots/` folder and link them here:
`![Dashboard](screenshots/dashboard.png)`

## Future Improvements
- Barcode scanning, GST invoices, PDF export
- Supplier & purchase-order management
- WhatsApp low-stock alerts

## Author
Anas Ali
