import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from .settings import ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class Store:
    def __init__(self, path=None):
        path = path or ROOT / 'data' / 'records.sqlite3'
        if str(path) != ':memory:':
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, status TEXT, stamp TEXT, payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS relations (item_id TEXT, doc_id TEXT, reason TEXT, PRIMARY KEY(item_id,doc_id))')
        self.db.execute('CREATE TABLE IF NOT EXISTS periods (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def put_period(self, period):
        self.db.execute('INSERT OR REPLACE INTO periods VALUES (?,?)', (period['id'], json.dumps(period, ensure_ascii=False)))
        self.db.commit()

    def periods(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM periods ORDER BY id')]

    def put(self, article):
        self.db.execute('INSERT OR REPLACE INTO articles VALUES (?,?)', (article['id'], json.dumps(article, ensure_ascii=False)))
        self.db.commit()

    def get(self, article_id):
        row = self.db.execute('SELECT payload FROM articles WHERE id=?', (article_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def articles(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM articles ORDER BY id')]

    def cache_get(self, key, success_seconds, failure_seconds=600):
        row = self.db.execute('SELECT status,stamp,payload FROM cache WHERE key=?', (key,)).fetchone()
        if not row:
            return None
        ttl = success_seconds if row[0] == 'ok' else failure_seconds
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(row[1])).total_seconds()
        return {'status': row[0], 'data': json.loads(row[2])} if age < ttl else None

    def cache_put(self, key, status, payload):
        self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?)', (key, status, now(), json.dumps(payload, ensure_ascii=False)))
        self.db.commit()

    def link(self, item_id, doc_id, reason):
        self.db.execute('INSERT OR REPLACE INTO relations VALUES (?,?,?)', (item_id, doc_id, reason))
        self.db.commit()

    def related(self, item_id):
        return [r[0] for r in self.db.execute('SELECT doc_id FROM relations WHERE item_id=?', (item_id,))]

    def counts(self):
        articles = self.articles()
        return {'metadata': len(articles), 'bodies': sum(bool(a.get('text')) for a in articles),
                'validated': sum(a.get('validation') == 'valid' for a in articles),
                'failed_or_pending': sum(a.get('validation') != 'valid' for a in articles)}
