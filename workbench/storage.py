"""Tenant-scoped persistence. SQL identifiers are application constants."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS resources (
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS scope ON resources(tenant,kind);
            CREATE TABLE IF NOT EXISTS approvals (
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, tool TEXT NOT NULL,
              arguments TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL,
              run_id TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts (
              channel_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, reply TEXT);
            ''')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def add(self, tenant, kind, payload):
        key = uuid.uuid4().hex
        with self.connect() as c:
            c.execute("INSERT INTO resources VALUES (?,?,?,?,?)", (key, tenant, kind, json.dumps(payload), time.time()))
        return {"id": key, **payload}

    def list(self, tenant, kind):
        with self.connect() as c:
            rows = c.execute("SELECT id,payload FROM resources WHERE tenant=? AND kind=? ORDER BY created LIMIT 200", (tenant, kind)).fetchall()
        return [{**json.loads(r['payload']), "id": r['id']} for r in rows]

    def get(self, tenant, kind, key):
        with self.connect() as c:
            r = c.execute("SELECT payload FROM resources WHERE tenant=? AND kind=? AND id=?", (tenant, kind, key)).fetchone()
        return {**json.loads(r[0]), "id": key} if r else None

    def delete(self, tenant, kind, key):
        with self.connect() as c:
            return bool(c.execute("DELETE FROM resources WHERE tenant=? AND kind=? AND id=?", (tenant, kind, key)).rowcount)

    def update(self, tenant, kind, key, payload):
        with self.connect() as c:
            changed = c.execute("UPDATE resources SET payload=? WHERE tenant=? AND kind=? AND id=?", (json.dumps(payload), tenant, kind, key)).rowcount
        return bool(changed)

    def event(self, tenant, run_id, payload):
        with self.connect() as c:
            c.execute("INSERT INTO events(tenant,run_id,payload) VALUES (?,?,?)", (tenant, run_id, json.dumps({"time": time.time(), **payload})))

    def events(self, tenant, run_id):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT payload FROM events WHERE tenant=? AND run_id=? ORDER BY seq", (tenant, run_id))]

    def propose(self, tenant, tool, arguments):
        key = uuid.uuid4().hex
        with self.connect() as c:
            c.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?)", (key, tenant, tool, json.dumps(arguments, sort_keys=True), time.time()+600, "pending"))
        return key

    def consume(self, tenant, key, approve):
        # Serialize competing approvals; the action can be claimed only once.
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM approvals WHERE id=? AND tenant=?", (key, tenant)).fetchone()
            if not r or r['state'] != 'pending' or r['expires'] < time.time():
                return None
            c.execute("UPDATE approvals SET state=? WHERE id=?", ('claimed' if approve else 'rejected', key))
            return dict(r)

    def finish_approval(self, tenant, key, state):
        with self.connect() as c:
            c.execute("UPDATE approvals SET state=? WHERE id=? AND tenant=?", (state, key, tenant))

    def pending(self, tenant):
        with self.connect() as c:
            rows = c.execute("SELECT id,tool,arguments,expires FROM approvals WHERE tenant=? AND state='pending' AND expires>?", (tenant,time.time())).fetchall()
        return [{**dict(r), "arguments": json.loads(r['arguments'])} for r in rows]

    def message(self, tenant, role, text):
        with self.connect() as c:
            c.execute("INSERT INTO messages(tenant,role,text) VALUES (?,?,?)", (tenant,role,text))

    def history(self, tenant):
        with self.connect() as c:
            rows = c.execute("SELECT role,text FROM messages WHERE tenant=? ORDER BY id DESC LIMIT 12", (tenant,)).fetchall()
        return [{"role": r['role'], "content": r['text'][:12000]} for r in reversed(rows)]

    def claim_delivery(self, tenant, channel_id):
        with self.connect() as c:
            return bool(c.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,NULL)", (channel_id,tenant)).rowcount)

    def complete_delivery(self, tenant, channel_id, reply):
        with self.connect() as c:
            c.execute("UPDATE receipts SET reply=? WHERE channel_id=? AND tenant=?", (reply, channel_id, tenant))

    def delivery_reply(self, tenant, channel_id):
        with self.connect() as c:
            r=c.execute("SELECT reply FROM receipts WHERE channel_id=? AND tenant=?", (channel_id,tenant)).fetchone()
        return r[0] if r else None

    def deliver_due(self):
        # Real local effect: a durable inbox item, atomically with removal.
        count = 0
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT * FROM resources WHERE kind='reminder'").fetchall()
            for r in rows:
                p = json.loads(r['payload'])
                if p['due_at'] <= time.time():
                    c.execute("INSERT INTO resources VALUES (?,?,?,?,?)", (uuid.uuid4().hex,r['tenant'],'inbox',json.dumps({"text":p['text'],"reminder_id":r['id']}),time.time()))
                    c.execute("DELETE FROM resources WHERE id=?", (r['id'],))
                    count += 1
        return count
