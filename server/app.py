"""CareLedger - health expense & insurance manager (Flask + SQLite + JWT)."""
import os, sqlite3, csv, io, datetime as dt
from functools import wraps
import jwt
from flask import Flask, request, jsonify, g, Response
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash

SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.environ.get("DB_PATH", "careledger.db")
app = Flask(__name__, static_folder="static", static_url_path="")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL, category TEXT, amount REAL NOT NULL, date TEXT NOT NULL, status TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  bill_id INTEGER REFERENCES bills(id), insurer TEXT, claimed REAL NOT NULL, approved REAL, status TEXT, filed_on TEXT);
CREATE TABLE IF NOT EXISTS prescriptions(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL, dosage TEXT, frequency TEXT, cost REAL, refill_on TEXT);
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  doctor TEXT NOT NULL, kind TEXT, when_at TEXT NOT NULL, fee REAL, status TEXT);
CREATE TABLE IF NOT EXISTS budgets(user_id INTEGER PRIMARY KEY REFERENCES users(id), monthly_limit REAL NOT NULL);
"""
TABLES = {  # resource -> writable columns (generic CRUD is driven from this)
    "bills": ["provider", "category", "amount", "date", "status", "notes"],
    "claims": ["bill_id", "insurer", "claimed", "approved", "status", "filed_on"],
    "prescriptions": ["name", "dosage", "frequency", "cost", "refill_on"],
    "appointments": ["doctor", "kind", "when_at", "fee", "status"],
}
REQUIRED = {"bills": ["provider", "amount", "date"], "claims": ["bill_id", "claimed"],
            "prescriptions": ["name"], "appointments": ["doctor", "when_at"]}
DEFAULT_STATUS = {"bills": "unpaid", "claims": "submitted", "appointments": "scheduled"}
NUM = {"amount", "claimed", "approved", "cost", "fee", "bill_id"}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(SCHEMA)


# ---------- auth ----------
def make_token(user):
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
    return jwt.encode({"sub": str(user["id"]), "exp": exp}, SECRET, algorithm="HS256")


def auth(admin=False):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            h = request.headers.get("Authorization", "")
            try:
                uid = int(jwt.decode(h.replace("Bearer ", ""), SECRET, algorithms=["HS256"])["sub"])
            except Exception:
                return jsonify(error="Please sign in again"), 401
            g.user = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not g.user:
                return jsonify(error="Account not found"), 401
            if admin and g.user["role"] != "admin":
                return jsonify(error="Admins only"), 403
            return fn(*a, **kw)
        return wrapper
    return deco


def public(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]}


@app.post("/api/auth/register")
def register():
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if not name or "@" not in email:
        return jsonify(error="Enter your name and a valid email"), 400
    if len(pw) < 8:
        return jsonify(error="Password needs at least 8 characters"), 400
    try:
        cur = db().execute("INSERT INTO users(name,email,password) VALUES(?,?,?)", (name, email, generate_password_hash(pw)))
        db().commit()
    except sqlite3.IntegrityError:
        return jsonify(error="That email is already registered"), 409
    u = db().execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(token=make_token(u), user=public(u)), 201


@app.post("/api/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    u = db().execute("SELECT * FROM users WHERE email=?", ((d.get("email") or "").strip().lower(),)).fetchone()
    if not u or not check_password_hash(u["password"], d.get("password") or ""):
        return jsonify(error="Wrong email or password"), 401
    return jsonify(token=make_token(u), user=public(u))


@app.get("/api/auth/me")
@auth()
def me():
    return jsonify(user=public(g.user))


# ---------- generic CRUD ----------
def clean(res, d):
    out = {}
    for f in TABLES[res]:
        v = d.get(f)
        if v in (None, ""):
            if f in REQUIRED[res]:
                raise ValueError(f"{f.replace('_', ' ')} is required")
            v = DEFAULT_STATUS.get(res) if f == "status" else None
        elif f in NUM:
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"{f.replace('_', ' ')} must be a number")
            if v < 0:
                raise ValueError(f"{f.replace('_', ' ')} cannot be negative")
        out[f] = v
    if res == "claims":
        ok = db().execute("SELECT 1 FROM bills WHERE id=? AND user_id=?", (out["bill_id"], g.user["id"])).fetchone()
        if not ok:
            raise ValueError("Choose one of your bills")
    return out


def check(res):
    if res not in TABLES:
        return jsonify(error="Unknown resource"), 404


@app.get("/api/<res>")
@auth()
def list_items(res):
    if check(res): return check(res)
    sql = ("SELECT c.*, b.provider AS bill FROM claims c LEFT JOIN bills b ON b.id=c.bill_id WHERE c.user_id=? ORDER BY c.id DESC"
           if res == "claims" else f"SELECT * FROM {res} WHERE user_id=? ORDER BY id DESC")
    return jsonify([dict(r) for r in db().execute(sql, (g.user["id"],))])


@app.post("/api/<res>")
@auth()
def create_item(res):
    if check(res): return check(res)
    d = clean(res, request.get_json(silent=True) or {})
    cols = ",".join(d)
    cur = db().execute(f"INSERT INTO {res}(user_id,{cols}) VALUES(?,{','.join('?' * len(d))})", (g.user["id"], *d.values()))
    db().commit()
    return jsonify(id=cur.lastrowid, **d), 201


@app.put("/api/<res>/<int:rid>")
@auth()
def update_item(res, rid):
    if check(res): return check(res)
    d = clean(res, request.get_json(silent=True) or {})
    cur = db().execute(f"UPDATE {res} SET {','.join(k + '=?' for k in d)} WHERE id=? AND user_id=?", (*d.values(), rid, g.user["id"]))
    db().commit()
    return jsonify(id=rid, **d) if cur.rowcount else (jsonify(error="Not found"), 404)


@app.delete("/api/<res>/<int:rid>")
@auth()
def delete_item(res, rid):
    if check(res): return check(res)
    cur = db().execute(f"DELETE FROM {res} WHERE id=? AND user_id=?", (rid, g.user["id"]))
    db().commit()
    return ("", 204) if cur.rowcount else (jsonify(error="Not found"), 404)


@app.get("/api/bills/export.csv")
@auth()
def export_bills():
    rows = db().execute("SELECT date,provider,category,amount,status,notes FROM bills WHERE user_id=? ORDER BY date", (g.user["id"],)).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "provider", "category", "amount", "status", "notes"])
    w.writerows([tuple(r) for r in rows])
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=bills.csv"})


# ---------- budget & dashboard ----------
@app.route("/api/budget", methods=["GET", "PUT"])
@auth()
def budget():
    if request.method == "PUT":
        try:
            v = float((request.get_json(silent=True) or {}).get("monthly_limit"))
            assert v >= 0
        except Exception:
            return jsonify(error="Enter a monthly limit of 0 or more"), 400
        db().execute("INSERT INTO budgets VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET monthly_limit=excluded.monthly_limit", (g.user["id"], v))
        db().commit()
    r = db().execute("SELECT monthly_limit FROM budgets WHERE user_id=?", (g.user["id"],)).fetchone()
    return jsonify(monthly_limit=r[0] if r else 0)


@app.get("/api/dashboard")
@auth()
def dashboard():
    u = g.user["id"]
    q = lambda s, *a: db().execute(s, (u, *a)).fetchall()
    one = lambda s, *a: q(s, *a)[0][0] or 0
    today = dt.date.today()
    ym = today.strftime("%Y-%m")
    spend = one("SELECT SUM(amount) FROM bills WHERE user_id=? AND substr(date,1,7)=?", ym)
    limit = (q("SELECT monthly_limit FROM budgets WHERE user_id=?") or [[0]])[0][0]
    months = [(today.replace(day=1) - dt.timedelta(days=31 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    totals = {r[0]: r[1] for r in q("SELECT substr(date,1,7),SUM(amount) FROM bills WHERE user_id=? GROUP BY 1")}
    return jsonify(
        month_spend=spend, monthly_limit=limit,
        outstanding=one("SELECT SUM(amount) FROM bills WHERE user_id=? AND status='unpaid'"),
        recovered=one("SELECT SUM(approved) FROM claims WHERE user_id=? AND status IN ('approved','paid')"),
        pending_claims=one("SELECT COUNT(*) FROM claims WHERE user_id=? AND status='submitted'"),
        by_category=[dict(r) for r in q("SELECT COALESCE(category,'Other') AS category,SUM(amount) AS total FROM bills WHERE user_id=? AND substr(date,1,7)=? GROUP BY 1 ORDER BY 2 DESC", ym)],
        trend=[{"month": m, "total": totals.get(m, 0)} for m in months],
        appointments=[dict(r) for r in q("SELECT doctor,kind,when_at,fee FROM appointments WHERE user_id=? AND status='scheduled' AND when_at>=? ORDER BY when_at LIMIT 4", today.isoformat())],
        refills=[dict(r) for r in q("SELECT name,dosage,refill_on FROM prescriptions WHERE user_id=? AND refill_on<=? ORDER BY refill_on LIMIT 4", (today + dt.timedelta(days=7)).isoformat())],
    )


@app.get("/api/admin/stats")
@auth(admin=True)
def admin_stats():
    users = db().execute("""SELECT u.id,u.name,u.email,u.role,u.created_at,
        (SELECT COUNT(*) FROM bills WHERE user_id=u.id) AS bills,
        (SELECT COALESCE(SUM(amount),0) FROM bills WHERE user_id=u.id) AS spend FROM users u ORDER BY u.id""").fetchall()
    return jsonify(users=[dict(r) for r in users], total_spend=sum(r["spend"] for r in users))


@app.errorhandler(ValueError)
def bad(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(HTTPException)
def http_err(e):
    return jsonify(error=e.description), e.code


@app.get("/")
def index():
    return app.send_static_file("index.html")


# ---------- demo data ----------
def seed():
    init_db()
    c = sqlite3.connect(DB_PATH)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return c.close()
    ins = lambda n, e, p, r: c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", (n, e, generate_password_hash(p), r)).lastrowid
    ins("Admin", "admin@careledger.dev", "admin1234", "admin")
    u = ins("Demo Patient", "demo@careledger.dev", "demo1234", "user")
    t = dt.date.today()
    d = lambda n: (t - dt.timedelta(days=n)).isoformat()
    bills = [("Apollo Clinic", "Consultation", 1500, d(3), "paid"), ("MedPlus Pharmacy", "Pharmacy", 2350, d(9), "paid"),
             ("Thyrocare Labs", "Lab", 4200, d(14), "unpaid"), ("Smile Dental", "Dental", 8000, d(26), "paid"),
             ("Fortis Hospital", "Hospital", 36000, d(41), "paid"), ("Apollo Clinic", "Consultation", 1500, d(58), "paid"),
             ("Netmeds", "Pharmacy", 1890, d(74), "paid"), ("Lilavati Hospital", "Hospital", 12500, d(95), "disputed")]
    ids = [c.execute("INSERT INTO bills(user_id,provider,category,amount,date,status) VALUES(?,?,?,?,?,?)", (u, *b)).lastrowid for b in bills]
    for bid, ins_, cl, ap, st in [(ids[4], "Star Health", 36000, 28000, "approved"), (ids[2], "Star Health", 4200, None, "submitted"), (ids[7], "Star Health", 12500, 0, "rejected")]:
        c.execute("INSERT INTO claims(user_id,bill_id,insurer,claimed,approved,status,filed_on) VALUES(?,?,?,?,?,?,?)", (u, bid, ins_, cl, ap, st, d(10)))
    for r in [("Metformin", "500 mg", "Twice daily", 320, (t + dt.timedelta(days=4)).isoformat()), ("Vitamin D3", "60000 IU", "Weekly", 150, (t + dt.timedelta(days=20)).isoformat())]:
        c.execute("INSERT INTO prescriptions(user_id,name,dosage,frequency,cost,refill_on) VALUES(?,?,?,?,?,?)", (u, *r))
    for a in [("Dr. Mehta", "Check-up", (t + dt.timedelta(days=2)).isoformat() + "T10:30", 800, "scheduled"), ("Dr. Rao", "Dental", (t + dt.timedelta(days=12)).isoformat() + "T16:00", 600, "scheduled")]:
        c.execute("INSERT INTO appointments(user_id,doctor,kind,when_at,fee,status) VALUES(?,?,?,?,?,?)", (u, *a))
    c.execute("INSERT INTO budgets VALUES(?,?)", (u, 20000))
    c.commit(); c.close()


if __name__ == "__main__":
    seed()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
