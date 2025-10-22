# ospra_os/learning/rules.py
from __future__ import annotations
import re, sqlite3, datetime as dt
from dataclasses import dataclass
from typing import Iterable, Optional

@dataclass
class Rule:
    pattern: str         # a plain substring or safe regex
    scope: str           # 'sender_domain' | 'subject_contains' | 'regex_subject'
    action: str          # 'ignore' | 'support' | 'orders'
    weight: float        # confidence 0..1
    hits: int
    last_seen: str

class RuleStore:
    def __init__(self, db_path: str):
        self.path = db_path
        self._ensure()

    def _conn(self):
        return sqlite3.connect(self.path, check_same_thread=False)

    def _ensure(self):
        with self._conn() as c:
            c.execute("""
              CREATE TABLE IF NOT EXISTS learned_rules (
                pattern TEXT NOT NULL,
                scope TEXT NOT NULL,
                action TEXT NOT NULL,
                weight REAL NOT NULL,
                hits INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                PRIMARY KEY(pattern, scope, action)
              )""")

            c.execute("""
              CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                sender_domain TEXT,
                subject TEXT,
                final_action TEXT NOT NULL   -- 'ignored' | 'support' | 'orders'
              )""")

    # ---------- runtime application ----------
    def best_guess(self, sender_email: str, subject: str) -> Optional[str]:
        dom = sender_email.split("@")[-1].lower() if "@" in sender_email else ""
        s = (subject or "").lower()

        with self._conn() as c:
            # 1) domain exact match
            for row in c.execute("""SELECT action, weight FROM learned_rules
                                    WHERE scope='sender_domain' AND pattern=?""", (dom,)):
                if row[1] >= 0.75:
                    return row[0]

            # 2) subject contains tokens
            tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t and len(t) >= 4][:6]
            if tokens:
                q = ",".join("?" * len(tokens))
                rows = c.execute(f"""SELECT action, MAX(weight) FROM learned_rules
                                     WHERE scope='subject_contains' AND pattern IN ({q})
                                     GROUP BY action""", tokens).fetchall()
                if rows:
                    # pick the action with highest max weight
                    rows.sort(key=lambda r: r[1], reverse=True)
                    if rows[0][1] >= 0.8:
                        return rows[0][0]

            # 3) optional regex_subject (keep few, high-confidence)
            for row in c.execute("""SELECT pattern, action, weight FROM learned_rules
                                    WHERE scope='regex_subject' AND weight>=0.9"""):
                pat, action, w = row
                try:
                    if re.search(pat, subject or "", re.I):
                        return action
                except re.error:
                    # ignore bad regex safely
                    pass
        return None

    # ---------- learning ----------
    def record_outcome(self, sender_email: str, subject: str, action_final: str) -> None:
        dom = sender_email.split("@")[-1].lower() if "@" in sender_email else None
        with self._conn() as c:
            c.execute("""INSERT INTO learning_events (ts, sender_domain, subject, final_action)
                         VALUES (?, ?, ?, ?)""",
                      (dt.datetime.utcnow().isoformat(), dom, subject or "", action_final))

    def promote(self, min_support: int = 4, min_ignore_ratio: float = 0.85) -> int:
        """
        Periodically mine events -> rules.
        - Domains: if >= min_support and >= min_ignore_ratio of outcomes are 'ignored' -> add sender_domain ignore.
        - Subject tokens: similar heuristic.
        Returns count of rules inserted/updated.
        """
        inserted = 0
        with self._conn() as c:
            # Domains
            rows = c.execute("""
              SELECT sender_domain, COUNT(*),
                     SUM(CASE WHEN final_action='ignored' THEN 1 ELSE 0 END)
              FROM learning_events
              WHERE sender_domain IS NOT NULL AND sender_domain != ''
              GROUP BY sender_domain
            """).fetchall()
            for dom, total, ignored in rows:
                if total >= min_support and ignored / total >= min_ignore_ratio:
                    inserted += self._upsert_rule(c, dom, 'sender_domain', 'ignore', hits=total, pos=ignored)

            # Subject tokens
            # Extract simple 4+ char tokens and aggregate
            token_stats = {}
            events = c.execute("SELECT subject, final_action FROM learning_events").fetchall()
            for subj, act in events:
                tokens = [t for t in re.split(r"[^a-z0-9]+", (subj or "").lower()) if len(t) >= 6][:6]
                for t in set(tokens):
                    d = token_stats.setdefault(t, {"tot": 0, "ign": 0})
                    d["tot"] += 1
                    if act == "ignored":
                        d["ign"] += 1
            for tok, agg in token_stats.items():
                tot, ign = agg["tot"], agg["ign"]
                if tot >= min_support and ign / tot >= min_ignore_ratio:
                    inserted += self._upsert_rule(c, tok, 'subject_contains', 'ignore', hits=tot, pos=ign)
        return inserted

    def _upsert_rule(self, c, pattern, scope, action, hits, pos):
        weight = pos / hits if hits else 0.0
        now = dt.datetime.utcnow().isoformat()
        c.execute("""INSERT INTO learned_rules (pattern, scope, action, weight, hits, last_seen)
                     VALUES (?, ?, ?, ?, ?, ?)
                     ON CONFLICT(pattern, scope, action) DO UPDATE SET
                       weight=excluded.weight,
                       hits=learned_rules.hits + excluded.hits,
                       last_seen=excluded.last_seen
                  """, (pattern, scope, action, weight, hits, now))
        return 1
