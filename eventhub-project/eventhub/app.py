"""EventHub – simple Flask + SQLite backend.  Run: python app.py  ->  http://localhost:5000"""
import json, os, random, re, secrets, sqlite3
from datetime import date
from functools import wraps
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

DB = os.environ.get("EVENTHUB_DB", "eventhub.db")
app = Flask(__name__, static_folder="static", static_url_path="/static")
EMAIL, PHONE = re.compile(r"^\S+@\S+\.\S+$"), re.compile(r"^[6-9]\d{9}$")

SCHEMA = """
create table if not exists users(id integer primary key, name text, email text unique, pw text, role text default 'Participant', active int default 1, created text default current_timestamp);
create table if not exists sessions(token text primary key, uid integer);
create table if not exists events(id integer primary key, t text, c text, tg text, l text, v text, d text, tm text, p int, s int, cap int, o text, ty text, e text, g text, m int, ds text, status text default 'approved', owner int);
create table if not exists registrations(id text primary key, event_id int, user_id int, name text, email text, mob text, org text, tk text, total int, status text default 'Confirmed', pay text, checkin text, created text default current_timestamp);
create table if not exists saved(uid int, event_id int, primary key(uid,event_id));
"""
SEED = [
 (1,'AI & Data Science Summit 2026','Technology',['AI & Data Science','Conferences','Technology'],'Coimbatore','Codissia Trade Fair Complex','2026-10-25','9:00 AM – 5:00 PM',299,342,500,'Tech Innovations Forum','Offline','🤖','#4338ca,#06b6d4',95,'A full-day summit on applied AI, data engineering and responsible ML with keynotes and a hands-on lab.'),
 (2,'Generative AI Workshop','Workshop',['AI & Data Science','Workshops'],'Chennai','IIT Madras Research Park','2026-10-18','10:00 AM – 4:00 PM',199,58,120,'PromptCraft Labs','Hybrid','✨','#7c3aed,#ec4899',91,'Build LLM-powered apps, learn prompt design and ship a working prototype in one day.'),
 (3,'Tamil Cultural Festival 2026','Cultural',['Cultural'],'Madurai','Thamukkam Grounds','2026-11-08','4:00 PM – 10:00 PM',0,1200,2000,'Madurai Arts Council','Offline','🎭','#ea580c,#facc15',64,'Folk music, silambam, literature talks and street food celebrating Tamil heritage.'),
 (4,'Startup & Entrepreneurship Meetup','Business',['Business','Networking'],'Chennai','T-Hub Chennai','2026-10-31','5:00 PM – 8:00 PM',149,73,150,'Founders Circle','Offline','🚀','#0f766e,#22c55e',70,'Pitch, network and learn from founders who have raised their first round.'),
 (5,'National College Hackathon','Competition',['Hackathons','Competitions','College Events'],'Coimbatore','PSG Tech Campus','2026-11-14','9:00 AM – 9:00 PM',99,0,300,'CodeSprint India','Offline','⚡','#1d4ed8,#a855f7',87,'12 hours, teams of four, real problem statements from industry mentors.'),
 (6,'Machine Learning Career Workshop','Career',['AI & Data Science','Career','Workshops'],'Madurai','Online (Zoom)','2026-10-12','6:00 PM – 8:00 PM',0,210,400,'DataPath Mentors','Online','🎯','#0369a1,#38bdf8',82,'Resume reviews, portfolio tips and interview prep for ML and data roles.')]

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    if not c.execute("select 1 from events").fetchone():
        for r in SEED:
            c.execute("insert into events(id,t,c,tg,l,v,d,tm,p,s,cap,o,ty,e,g,m,ds) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*r[:3], json.dumps(r[3]), *r[4:]))
        for n, e, r in [("Admin","admin@eventhub.in","Admin"),("Demo Organizer","organizer@eventhub.in","Organizer"),("Demo User","user@eventhub.in","Participant")]:
            c.execute("insert into users(name,email,pw,role) values(?,?,?,?)", (n, e, generate_password_hash("eventhub123"), r))
    c.commit(); c.close()

def today(): return os.environ.get("EVENTHUB_TODAY") or date.today().isoformat()
def err(m, code=400): return jsonify(error=m), code
def ev(r): d = dict(r); d["tg"] = json.loads(d["tg"]); return d
def me():
    t = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return db().execute("select u.* from sessions s join users u on u.id=s.uid where s.token=? and u.active=1", (t,)).fetchone()

def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = me()
            if not u: return err("Login required", 401)
            if roles and u["role"] not in roles: return err("Not allowed", 403)
            g.user = u; return f(*a, **k)
        return w
    return deco

@app.get("/")
def home(): return send_from_directory("static", "index.html")

# ---------- auth ----------
def session(uid):
    t = secrets.token_urlsafe(24); db().execute("insert into sessions values(?,?)", (t, uid)); db().commit(); return t

@app.post("/api/auth/signup")
def signup():
    j = request.get_json(force=True, silent=True) or {}
    name, email, pw = (j.get("name") or "").strip(), (j.get("email") or "").strip().lower(), j.get("password") or ""
    role = j.get("role") if j.get("role") in ("Participant", "Organizer") else "Participant"
    if not name: return err("Name is required.")
    if not EMAIL.match(email): return err("Enter a valid email.")
    if len(pw) < 8: return err("Password must be at least 8 characters.")
    if db().execute("select 1 from users where email=?", (email,)).fetchone(): return err("Email already registered.", 409)
    uid = db().execute("insert into users(name,email,pw,role) values(?,?,?,?)", (name, email, generate_password_hash(pw), role)).lastrowid
    return jsonify(token=session(uid), user=dict(name=name, email=email, role=role)), 201

@app.post("/api/auth/login")
def login():
    j = request.get_json(force=True, silent=True) or {}
    u = db().execute("select * from users where email=?", ((j.get("email") or "").lower(),)).fetchone()
    if not u or not check_password_hash(u["pw"], j.get("password") or ""): return err("Wrong email or password.", 401)
    if not u["active"]: return err("Account suspended.", 403)
    return jsonify(token=session(u["id"]), user=dict(name=u["name"], email=u["email"], role=u["role"]))

# ---------- events ----------
@app.get("/api/events")
def events():
    a = request.args; q = (a.get("q") or "").lower()
    rows = [ev(r) for r in db().execute("select * from events where status='approved'")]
    f = lambda e: ((not q or q in (e["t"] + e["c"] + e["o"] + e["ds"]).lower())
        and (not a.get("category") or a["category"] == e["c"] or a["category"] in e["tg"])
        and (not a.get("city") or a["city"].lower() == e["l"].lower())
        and (not a.get("type") or a["type"] == e["ty"])
        and (not a.get("price") or (a["price"] == "Free") == (e["p"] == 0))
        and (not a.get("available") or e["s"] > 0))
    key = {"new": lambda e: -e["id"], "popular": lambda e: e["s"] - e["cap"], "date": lambda e: e["d"], "price": lambda e: e["p"]}.get(a.get("sort"), lambda e: -e["m"])
    return jsonify(sorted(filter(f, rows), key=key))

@app.get("/api/events/<int:i>")
def event(i):
    r = db().execute("select * from events where id=?", (i,)).fetchone()
    return jsonify(ev(r)) if r else err("Event not found", 404)

@app.post("/api/events")
@need("Organizer", "Admin")
def create_event():
    j = request.get_json(force=True, silent=True) or {}
    if not j.get("t") or not j.get("d") or not j.get("l"): return err("Name, date and city are required.")
    cap = int(j.get("cap") or 100)
    i = db().execute("insert into events(t,c,tg,l,v,d,tm,p,s,cap,o,ty,e,g,m,ds,status,owner) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (j["t"], j.get("c", "Technology"), json.dumps([j.get("c", "Technology")]), j["l"], j.get("v", j["l"]), j["d"], j.get("tm", "10:00 AM – 4:00 PM"),
         int(j.get("p") or 0), cap, cap, g.user["name"], j.get("ty", "Offline"), "🎪", "#4338ca,#0ea5e9", 60, j.get("ds", ""), "pending", g.user["id"])).lastrowid
    db().commit(); return jsonify(id=i, status="pending"), 201

@app.get("/api/admin/events")
@need("Admin")
def pending():
    return jsonify([ev(r) for r in db().execute("select * from events where status=?", (request.args.get("status", "pending"),))])

@app.patch("/api/admin/events/<int:i>")
@need("Admin")
def review(i):
    s = (request.get_json(force=True, silent=True) or {}).get("status")
    if s not in ("approved", "rejected", "changes_requested"): return err("Invalid status.")
    db().execute("update events set status=? where id=?", (s, i)); db().commit(); return jsonify(id=i, status=s)

# ---------- registration ----------
def tprice(p, tk): return p * 2 if tk == "VIP" else round(p * .67) if tk == "Student" else p

@app.post("/api/events/<int:i>/register")
def register(i):
    e = db().execute("select * from events where id=? and status='approved'", (i,)).fetchone()
    if not e: return err("Event not found", 404)
    j = request.get_json(force=True, silent=True) or {}
    email, mob, tk = (j.get("email") or "").strip().lower(), (j.get("mob") or "").strip(), j.get("tk", "General")
    if not (j.get("name") or "").strip(): return err("Full name is required.")
    if not EMAIL.match(email): return err("Enter a valid email.")
    if not PHONE.match(mob): return err("Enter a 10-digit mobile number.")
    if tk not in ("General", "Student", "VIP"): return err("Ticket unavailable.")
    if e["d"] < today(): return err("This event has ended.", 410)
    if db().execute("select 1 from registrations where event_id=? and email=? and status='Confirmed'", (i, email)).fetchone():
        return err("You are already registered for this event.", 409)
    price = tprice(e["p"], tk); total = price + round(price * .03)
    if total and not (j.get("payment") or {}).get("method"): return err("Payment required.", 402)
    if db().execute("update events set s=s-1 where id=? and s>0", (i,)).rowcount == 0:
        return err("Registration closed. This event has reached its maximum capacity.", 409)
    u = me(); rid = "EH-26-%05d" % random.randint(10000, 99999)
    db().execute("insert into registrations(id,event_id,user_id,name,email,mob,org,tk,total,pay) values(?,?,?,?,?,?,?,?,?,?)",
        (rid, i, u["id"] if u else None, j["name"].strip(), email, mob, j.get("org", ""), tk, total, "paid" if total else "free"))
    db().commit(); return jsonify(id=rid, event=e["t"], ticket=tk, total=total, status="Confirmed"), 201

@app.get("/api/registrations")
@need()
def my_regs():
    rows = db().execute("select r.*, e.t as event, e.d as date, e.l as city from registrations r join events e on e.id=r.event_id where r.user_id=? or r.email=?", (g.user["id"], g.user["email"]))
    return jsonify([dict(r) for r in rows])

@app.delete("/api/registrations/<rid>")
@need()
def cancel(rid):
    r = db().execute("select * from registrations where id=?", (rid,)).fetchone()
    if not r or (r["email"] != g.user["email"] and g.user["role"] == "Participant"): return err("Registration not found", 404)
    if r["status"] != "Confirmed": return err("Already cancelled.", 409)
    db().execute("update registrations set status='Cancelled' where id=?", (rid,)); db().execute("update events set s=s+1 where id=?", (r["event_id"],)); db().commit()
    return jsonify(id=rid, status="Cancelled")

# ---------- organizer ----------
@app.get("/api/events/<int:i>/participants")
@need("Organizer", "Admin")
def participants(i):
    return jsonify([dict(r) for r in db().execute("select id,name,email,org,tk,pay,status,checkin,created from registrations where event_id=?", (i,))])

@app.post("/api/checkin")
@need("Organizer", "Admin")
def checkin():
    rid = (request.get_json(force=True, silent=True) or {}).get("id", "")
    r = db().execute("select r.*, e.t as event from registrations r join events e on e.id=r.event_id where r.id=?", (rid,)).fetchone()
    if not r or r["status"] != "Confirmed": return jsonify(valid=False, message="Invalid ticket"), 404
    if r["checkin"]: return jsonify(valid=True, duplicate=True, message="Already checked in", checkin=r["checkin"]), 409
    db().execute("update registrations set checkin=datetime('now') where id=?", (rid,)); db().commit()
    return jsonify(valid=True, message="Check-in successful", name=r["name"], ticket=r["tk"], event=r["event"])

@app.get("/api/organizer/stats")
@need("Organizer", "Admin")
def stats():
    c = db().execute("select count(*) n, coalesce(sum(total),0) rev, count(checkin) ci from registrations where status='Confirmed'").fetchone()
    return jsonify(registrations=c["n"], revenue=c["rev"], attendance_rate=round(100 * c["ci"] / c["n"], 1) if c["n"] else 0,
                   events=db().execute("select count(*) from events").fetchone()[0])

# ---------- saved, recommendations, AI ----------
@app.route("/api/saved/<int:i>", methods=["POST", "DELETE"])
@need()
def saved(i):
    if request.method == "POST": db().execute("insert or ignore into saved values(?,?)", (g.user["id"], i))
    else: db().execute("delete from saved where uid=? and event_id=?", (g.user["id"], i))
    db().commit(); return jsonify(ok=True)

def score(e, words):
    hits = sum(w in (e["t"] + e["ds"] + " ".join(e["tg"])).lower() for w in words)
    return min(99, e["m"] + 4 * hits)

@app.get("/api/recommendations")
def recs():
    words = [w.strip().lower() for w in (request.args.get("interests") or "").split(",") if w.strip()]
    rows = [ev(r) for r in db().execute("select * from events where status='approved'")]
    for e in rows: e["m"] = score(e, words); e["why"] = "Matches your interests: " + ", ".join(words) if words else "Popular near you"
    return jsonify(sorted(rows, key=lambda e: -e["m"])[:4])

@app.post("/api/ai")
def ai():
    q = ((request.get_json(force=True, silent=True) or {}).get("question") or "").lower()
    rows = [ev(r) for r in db().execute("select * from events where status='approved'")]
    city = re.search("coimbatore|chennai|madurai", q)
    if "free" in q: r = [e for e in rows if not e["p"]]
    elif city: r = [e for e in rows if e["l"].lower() == city[0]]
    elif "weekend" in q: r = [e for e in rows if date.fromisoformat(e["d"]).weekday() >= 5]
    elif re.search("final|student|career", q): r = [e for e in rows if any(t in ("Hackathons", "Career") for t in e["tg"])]
    elif re.search(r"\bai\b|data|machine|ml", q): r = [e for e in rows if "AI & Data Science" in e["tg"]]
    else: r = rows
    r = sorted(r, key=lambda e: -e["m"])[:4]
    return jsonify(answer=f"I found {len(r)} events." if r else "No events match that yet.", events=[dict(id=e["id"], t=e["t"], m=e["m"]) for e in r])

init()
if __name__ == "__main__":
    app.run(debug=True, port=5000)
