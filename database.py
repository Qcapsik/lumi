# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
"""SQLite-хранилище для бота Луми: шаблоны, логи, настройки гильдий."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "lumi.db"


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                theme TEXT DEFAULT 'default',
                accent_color TEXT DEFAULT '#FFD700',
                auto_log INTEGER DEFAULT 1,
                language TEXT DEFAULT 'ru',
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS server_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                payload TEXT NOT NULL,
                created_at TEXT,
                UNIQUE(guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                tool_name TEXT,
                arguments TEXT,
                result TEXT,
                success INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ticket_config (
                guild_id INTEGER PRIMARY KEY,
                category_id INTEGER,
                panel_channel_id INTEGER,
                support_role_name TEXT,
                ticket_counter INTEGER DEFAULT 0,
                embed_title TEXT DEFAULT '🎫 Поддержка',
                embed_description TEXT,
                embed_color TEXT DEFAULT '#5865F2',
                button_label TEXT DEFAULT 'Открыть тикет',
                button_emoji TEXT DEFAULT '🎫',
                welcome_message TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS open_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS component_panels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                panel_type TEXT,
                payload TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS member_stats (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                last_xp REAL DEFAULT 0,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS economy (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                credits INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                UNIQUE(guild_id, role_name)
            );

            CREATE TABLE IF NOT EXISTS warns (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                count INTEGER DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                channel_id INTEGER,
                when_ts INTEGER NOT NULL,
                text TEXT,
                done INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                when_ts INTEGER NOT NULL,
                channel_id INTEGER,
                reminded INTEGER DEFAULT 0,
                remind_before INTEGER DEFAULT 3600
            );

            CREATE TABLE IF NOT EXISTS polls (
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER,
                title TEXT,
                options_json TEXT,
                votes_json TEXT,
                ended INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, message_id)
            );

            CREATE TABLE IF NOT EXISTS automod_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                bad_words_json TEXT DEFAULT '[]',
                min_interval REAL DEFAULT 5.0,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                name TEXT,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                year INTEGER,
                created_at TEXT,
                UNIQUE(guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS welcome_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                rules_text TEXT,
                guest_role_id INTEGER,
                enabled INTEGER DEFAULT 1,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS achievements (
                user_id INTEGER NOT NULL,
                ach_id TEXT NOT NULL,
                ts INTEGER,
                PRIMARY KEY (user_id, ach_id)
            );

            CREATE TABLE IF NOT EXISTS voice_minutes (
                guild_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                minutes INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, member_id)
            );

            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                started_ts INTEGER NOT NULL,
                minutes INTEGER NOT NULL,
                done INTEGER DEFAULT 0,
                channel_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS daily_streak (
                user_id INTEGER PRIMARY KEY,
                last_date TEXT,
                streak INTEGER DEFAULT 0,
                best INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS favorite_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                duration INTEGER DEFAULT 0,
                thumb TEXT,
                webpage_url TEXT,
                added_at TEXT,
                UNIQUE(user_id, url)
            );

            CREATE TABLE IF NOT EXISTS pets (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT DEFAULT '🐱',
                xp INTEGER DEFAULT 0,
                hunger INTEGER DEFAULT 80,
                happiness INTEGER DEFAULT 80,
                last_feed INTEGER DEFAULT 0,
                created_at TEXT
            );
            """
        )


def _now() -> str:
    return datetime.utcnow().isoformat()


def get_guild_settings(guild_id: int) -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        if not row:
            con.execute(
                "INSERT INTO guild_settings (guild_id, updated_at) VALUES (?, ?)",
                (guild_id, _now()),
            )
            return {
                "guild_id": guild_id,
                "theme": "default",
                "accent_color": "#FFD700",
                "auto_log": True,
                "language": "ru",
            }
        return dict(row)


def update_guild_settings(guild_id: int, **kwargs) -> dict:
    allowed = {"theme", "accent_color", "auto_log", "language"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_guild_settings(guild_id)
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as con:
        con.execute(
            f"INSERT OR IGNORE INTO guild_settings (guild_id, updated_at) VALUES (?, ?)",
            (guild_id, _now()),
        )
        con.execute(
            f"UPDATE guild_settings SET {cols} WHERE guild_id = ?",
            (*fields.values(), guild_id),
        )
    return get_guild_settings(guild_id)


def save_template(guild_id: int, name: str, payload: dict, description: str = "") -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO server_templates (guild_id, name, description, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, name) DO UPDATE SET
                description = excluded.description,
                payload = excluded.payload,
                created_at = excluded.created_at
            """,
            (guild_id, name, description, json.dumps(payload, ensure_ascii=False), _now()),
        )
        return cur.lastrowid


def get_template(guild_id: int, name: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM server_templates WHERE guild_id = ? AND name = ?",
            (guild_id, name),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return data


def list_templates(guild_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, description, created_at FROM server_templates WHERE guild_id = ? ORDER BY created_at DESC",
            (guild_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def log_action(
    guild_id: int,
    user_id: int,
    tool_name: str,
    arguments: dict,
    result: str,
    success: bool,
):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO action_log (guild_id, user_id, tool_name, arguments, result, success, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                tool_name,
                json.dumps(arguments, ensure_ascii=False),
                result[:4000],
                int(success),
                _now(),
            ),
        )


def get_recent_actions(guild_id: int, limit: int = 20) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT tool_name, arguments, result, success, created_at
            FROM action_log WHERE guild_id = ? ORDER BY id DESC LIMIT ?
            """,
            (guild_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def add_chat_message(guild_id: int, user_id: int, role: str, content: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO chat_history (guild_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, role, content[:8000], _now()),
        )


def get_chat_history(guild_id: int, user_id: int, limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT role, content FROM chat_history
            WHERE guild_id = ? AND user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (guild_id, user_id, limit),
        ).fetchall()
        return list(reversed([dict(r) for r in rows]))


def save_ticket_config(guild_id: int, **kwargs) -> dict:
    allowed = {
        "category_id", "panel_channel_id", "support_role_name", "embed_title",
        "embed_description", "embed_color", "button_label", "button_emoji", "welcome_message",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    fields["updated_at"] = _now()
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO ticket_config (guild_id) VALUES (?)", (guild_id,))
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            con.execute(f"UPDATE ticket_config SET {cols} WHERE guild_id = ?", (*fields.values(), guild_id))
        row = con.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (guild_id,)).fetchone()
        return dict(row) if row else {}


def get_ticket_config(guild_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (guild_id,)).fetchone()
        return dict(row) if row else None


def next_ticket_number(guild_id: int) -> int:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO ticket_config (guild_id, ticket_counter) VALUES (?, 0)",
            (guild_id,),
        )
        con.execute(
            "UPDATE ticket_config SET ticket_counter = ticket_counter + 1 WHERE guild_id = ?",
            (guild_id,),
        )
        row = con.execute(
            "SELECT ticket_counter FROM ticket_config WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        return row["ticket_counter"] if row else 1


def add_open_ticket(guild_id: int, channel_id: int, user_id: int) -> bool:
    with _conn() as con:
        try:
            con.execute(
                "INSERT INTO open_tickets (guild_id, channel_id, user_id, created_at) VALUES (?, ?, ?, ?)",
                (guild_id, channel_id, user_id, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def remove_open_ticket(guild_id: int, channel_id: int = None, user_id: int = None):
    with _conn() as con:
        if channel_id:
            con.execute(
                "DELETE FROM open_tickets WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id),
            )
        elif user_id:
            con.execute(
                "DELETE FROM open_tickets WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )


def get_user_open_ticket(guild_id: int, user_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM open_tickets WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def get_ticket_by_channel(guild_id: int, channel_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM open_tickets WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        ).fetchone()
        return dict(row) if row else None


def get_panel_by_message(guild_id: int, message_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM component_panels WHERE guild_id = ? AND message_id = ? ORDER BY id DESC LIMIT 1",
            (guild_id, message_id),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return data


def save_component_panel(guild_id: int, channel_id: int, message_id: int, panel_type: str, payload: dict):
    with _conn() as con:
        con.execute("DELETE FROM component_panels WHERE guild_id = ? AND message_id = ?", (guild_id, message_id))
        con.execute(
            """
            INSERT INTO component_panels (guild_id, channel_id, message_id, panel_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, message_id, panel_type, json.dumps(payload, ensure_ascii=False), _now()),
        )


# ── Уровни и статистика ─────────────────────────────────────────────────

def add_member_message(guild_id: int, member_id: int, xp: int) -> tuple:
    """Прибавляет XP и счётчик сообщений. Возвращает (new_xp, level, level_up)."""
    with _conn() as con:
        con.execute(
            """
            INSERT INTO member_stats (guild_id, member_id, xp, messages, last_xp)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET
                xp = xp + excluded.xp,
                messages = messages + 1,
                last_xp = excluded.last_xp
            """,
            (guild_id, member_id, xp, _now_as_ts()),
        )
        row = con.execute(
            "SELECT xp FROM member_stats WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        xp_total = row["xp"]
        level = int((xp_total / 50) ** 0.5)
        # level_up определяется через проверку предыдущего уровня
        old_row = con.execute(
            "SELECT xp - ? AS prev FROM member_stats WHERE guild_id = ? AND member_id = ?",
            (xp, guild_id, member_id),
        ).fetchone()
        prev_xp = (old_row["prev"] or 0)
        prev_level = int((prev_xp / 50) ** 0.5)
        return xp_total, level, level > prev_level


def get_member_stats(guild_id: int, member_id: int) -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM member_stats WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        if not row:
            return {"xp": 0, "messages": 0, "level": 0}
        data = dict(row)
        data["level"] = int((data["xp"] / 50) ** 0.5)
        return data


def leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT member_id, xp, messages FROM member_stats WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["level"] = int((d["xp"] / 50) ** 0.5)
            out.append(d)
        return out


def get_last_xp_ts(guild_id: int, member_id: int) -> float:
    with _conn() as con:
        row = con.execute(
            "SELECT last_xp FROM member_stats WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return row["last_xp"] if row and row["last_xp"] else 0.0


# ── Экономика ────────────────────────────────────────────────────────────

def add_credits(guild_id: int, member_id: int, amount: int) -> int:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO economy (guild_id, member_id, credits) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET credits = credits + excluded.credits
            """,
            (guild_id, member_id, amount),
        )
        row = con.execute(
            "SELECT credits FROM economy WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return row["credits"] if row else 0


def get_credits(guild_id: int, member_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT credits FROM economy WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return row["credits"] if row else 0


def transfer_credits(guild_id: int, from_id: int, to_id: int, amount: int) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT credits FROM economy WHERE guild_id = ? AND member_id = ?", (guild_id, from_id)
        ).fetchone()
        if not row or row["credits"] < amount:
            return False
        con.execute(
            "UPDATE economy SET credits = credits - ? WHERE guild_id = ? AND member_id = ?",
            (amount, guild_id, from_id),
        )
        con.execute(
            """
            INSERT INTO economy (guild_id, member_id, credits) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET credits = credits + excluded.credits
            """,
            (guild_id, to_id, amount),
        )
        return True


def add_shop_item(guild_id: int, role_name: str, price: int) -> bool:
    with _conn() as con:
        try:
            con.execute(
                "INSERT INTO shop_items (guild_id, role_name, price) VALUES (?, ?, ?)",
                (guild_id, role_name, price),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def remove_shop_item(guild_id: int, role_name: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM shop_items WHERE guild_id = ? AND role_name = ?", (guild_id, role_name)
        )
        return cur.rowcount > 0


def list_shop_items(guild_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role_name, price FROM shop_items WHERE guild_id = ? ORDER BY price ASC", (guild_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Варны ────────────────────────────────────────────────────────────────

def add_warn(guild_id: int, member_id: int) -> int:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO warns (guild_id, member_id, count, updated_at) VALUES (?, ?, 1, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET count = count + 1, updated_at = excluded.updated_at
            """,
            (guild_id, member_id, _now()),
        )
        row = con.execute(
            "SELECT count FROM warns WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return row["count"] if row else 1


def get_warns(guild_id: int, member_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT count FROM warns WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return row["count"] if row else 0


def clear_warns(guild_id: int, member_id: int) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM warns WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        )
        return cur.rowcount > 0


# ── Напоминания ──────────────────────────────────────────────────────────

def add_reminder(guild_id: int, user_id: int, channel_id: int, when_ts: int, text: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO reminders (guild_id, user_id, channel_id, when_ts, text) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, channel_id, when_ts, text),
        )
        return cur.lastrowid


def due_reminders(now_ts: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM reminders WHERE done = 0 AND when_ts <= ? ORDER BY when_ts ASC LIMIT 100",
            (now_ts,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_reminder_done(rid: int):
    with _conn() as con:
        con.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))


def upcoming_reminders(user_id: int, limit: int = 5) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, text, when_ts FROM reminders WHERE user_id = ? AND done = 0 ORDER BY when_ts ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Ивенты / рейды ───────────────────────────────────────────────────────

def add_event(guild_id: int, name: str, when_ts: int, channel_id: int, remind_before: int = 3600) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO events (guild_id, name, when_ts, channel_id, remind_before) VALUES (?, ?, ?, ?, ?)",
            (guild_id, name, when_ts, channel_id, remind_before),
        )
        return cur.lastrowid


def due_event_reminders(now_ts: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM events WHERE reminded = 0 AND when_ts - remind_before <= ?
            """,
            (now_ts,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_event_reminded(eid: int):
    with _conn() as con:
        con.execute("UPDATE events SET reminded = 1 WHERE id = ?", (eid,))


def list_events(guild_id: int, limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, when_ts, channel_id FROM events WHERE guild_id = ? AND when_ts > ? ORDER BY when_ts ASC LIMIT ?",
            (guild_id, _now_as_ts(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Голосования ──────────────────────────────────────────────────────────

def save_poll(guild_id: int, message_id: int, channel_id: int, title: str, options: list):
    votes = {str(i): 0 for i in range(len(options))}
    with _conn() as con:
        con.execute(
            """
            INSERT INTO polls (guild_id, message_id, channel_id, title, options_json, votes_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, message_id) DO UPDATE SET
                options_json = excluded.options_json, votes_json = excluded.votes_json, ended = 0
            """,
            (guild_id, message_id, channel_id, title, json.dumps(options, ensure_ascii=False),
             json.dumps(votes)),
        )


def get_poll(guild_id: int, message_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM polls WHERE guild_id = ? AND message_id = ?", (guild_id, message_id)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["options"] = json.loads(data.pop("options_json"))
        data["votes"] = json.loads(data.pop("votes_json"))
        return data


def vote_poll(guild_id: int, message_id: int, index: int) -> bool:
    poll = get_poll(guild_id, message_id)
    if not poll or poll.get("ended"):
        return False
    votes = poll["votes"]
    idx = str(index)
    if idx not in votes:
        return False
    with _conn() as con:
        con.execute(
            "UPDATE polls SET votes_json = ? WHERE guild_id = ? AND message_id = ?",
            (json.dumps(votes), guild_id, message_id),
        )
    return True


# ── Авто-модерация ───────────────────────────────────────────────────────

def get_automod(guild_id: int) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,)).fetchone()
        if not row:
            return {"enabled": False, "bad_words": [], "min_interval": 5.0}
        data = dict(row)
        data["bad_words"] = json.loads(data.pop("bad_words_json") or "[]")
        return data


def save_automod(guild_id: int, enabled: bool = True, bad_words: list = None, min_interval: float = None) -> dict:
    cfg = get_automod(guild_id)
    if enabled is not None:
        cfg["enabled"] = bool(enabled)
    if bad_words is not None:
        cfg["bad_words"] = [str(w).lower() for w in bad_words]
    if min_interval is not None:
        cfg["min_interval"] = float(min_interval)
    with _conn() as con:
        con.execute(
            """
            INSERT INTO automod_settings (guild_id, enabled, bad_words_json, min_interval, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                enabled = excluded.enabled,
                bad_words_json = excluded.bad_words_json,
                min_interval = excluded.min_interval,
                updated_at = excluded.updated_at
            """,
            (guild_id, int(cfg["enabled"]), json.dumps(cfg["bad_words"]), cfg["min_interval"], _now()),
        )
    return cfg


# ── Дни рождения ─────────────────────────────────────────────────────────

def register_birthday_db(guild_id: int, member_id: int, name: str, month: int, day: int, year: int = None):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO birthdays (guild_id, member_id, name, month, day, year, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET
                name = excluded.name, month = excluded.month,
                day = excluded.day, year = excluded.year, created_at = excluded.created_at
            """,
            (guild_id, member_id, name or "", month, day, year, _now()),
        )


def get_birthday(guild_id: int, member_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM birthdays WHERE guild_id = ? AND member_id = ?", (guild_id, member_id)
        ).fetchone()
        return dict(row) if row else None


def list_birthdays_db(guild_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM birthdays WHERE guild_id = ? ORDER BY month ASC, day ASC", (guild_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def birthdays_on_day(guild_id: int, month: int, day: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM birthdays WHERE guild_id = ? AND month = ? AND day = ?",
            (guild_id, month, day),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Приветствие ──────────────────────────────────────────────────────────

def save_welcome_config(
    guild_id: int, channel_id: int = None, rules_text: str = None,
    guest_role_id: int = None, enabled: bool = None,
) -> dict:
    cfg = get_welcome_config(guild_id)
    if channel_id is not None:
        cfg["channel_id"] = channel_id
    if rules_text is not None:
        cfg["rules_text"] = rules_text
    if guest_role_id is not None:
        cfg["guest_role_id"] = guest_role_id
    if enabled is not None:
        cfg["enabled"] = int(enabled)
    with _conn() as con:
        con.execute(
            """
            INSERT INTO welcome_config (guild_id, channel_id, rules_text, guest_role_id, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id, rules_text = excluded.rules_text,
                guest_role_id = excluded.guest_role_id, enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (guild_id, cfg.get("channel_id"), cfg.get("rules_text"), cfg.get("guest_role_id"),
             cfg.get("enabled", 1), _now()),
        )
    return cfg


def get_welcome_config(guild_id: int) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM welcome_config WHERE guild_id = ?", (guild_id,)).fetchone()
        if not row:
            return {"channel_id": None, "rules_text": None, "guest_role_id": None, "enabled": 1}
        return dict(row)


# ── Каналы по назначению (birthday и т.п.) ────────────────────────────────

def set_guild_channel(guild_id: int, purpose: str, channel_id: int):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO guild_channels (guild_id, purpose, channel_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, purpose) DO UPDATE SET channel_id = excluded.channel_id
            """,
            (guild_id, purpose, channel_id),
        )


# ── Ачивки ─────────────────────────────────────────────────────────────────

def add_achievement(user_id: int, ach_id: str) -> bool:
    """Открывает ачивку. Возвращает True, если открыта впервые."""
    import time as _t
    with _conn() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO achievements (user_id, ach_id, ts) VALUES (?, ?, ?)",
            (user_id, ach_id, int(_t.time())),
        )
        return cur.rowcount > 0


def has_achievement(user_id: int, ach_id: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM achievements WHERE user_id = ? AND ach_id = ?", (user_id, ach_id)
        ).fetchone()
        return row is not None


def get_achievements(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT ach_id, ts FROM achievements WHERE user_id = ? ORDER BY ts ASC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def last_achievements(user_id: int, limit: int = 3) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT ach_id, ts FROM achievements WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Статистика голосовых ───────────────────────────────────────────────────

def add_voice_minutes(guild_id: int, member_id: int, minutes: int) -> int:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO voice_minutes (guild_id, member_id, minutes) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, member_id) DO UPDATE SET minutes = minutes + excluded.minutes
            """,
            (guild_id, member_id, minutes),
        )
        row = con.execute(
            "SELECT minutes FROM voice_minutes WHERE guild_id = ? AND member_id = ?",
            (guild_id, member_id),
        ).fetchone()
        return row["minutes"] if row else 0


def get_voice_minutes(guild_id: int, member_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT minutes FROM voice_minutes WHERE guild_id = ? AND member_id = ?",
            (guild_id, member_id),
        ).fetchone()
        return row["minutes"] if row else 0


def top_voice_minutes(guild_id: int, limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT member_id, minutes FROM voice_minutes WHERE guild_id = ? ORDER BY minutes DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Фокус-сессии ───────────────────────────────────────────────────────────

def add_focus_session(user_id: int, minutes: int, channel_id: int) -> int:
    import time as _t
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO focus_sessions (user_id, started_ts, minutes, channel_id) VALUES (?, ?, ?, ?)",
            (user_id, int(_t.time()), minutes, channel_id),
        )
        return cur.lastrowid


def get_active_focus(user_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM focus_sessions WHERE user_id = ? AND done = 0 ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def due_focus_sessions(now_ts: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM focus_sessions WHERE done = 0 AND started_ts + minutes * 60 <= ?",
            (now_ts,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_focus_done(fid: int):
    with _conn() as con:
        con.execute("UPDATE focus_sessions SET done = 1 WHERE id = ?", (fid,))


def week_focus_stats(user_id: int) -> tuple[int, int]:
    """Возвращает (количество сессий, суммарные минуты) за последние 7 дней."""
    import time as _t
    week_ago = int(_t.time()) - 7 * 86400
    with _conn() as con:
        rows = con.execute(
            "SELECT minutes FROM focus_sessions WHERE user_id = ? AND started_ts >= ?",
            (user_id, week_ago),
        ).fetchall()
        return len(rows), sum(r["minutes"] for r in rows)


# ── Клановая лотерея ───────────────────────────────────────────────────────

def recent_speakers(guild_id: int, hours: int = 24) -> list[int]:
    """Возвращает user_id, которые писали на сервере за последние N часов."""
    import time as _t
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT user_id FROM chat_history WHERE guild_id = ? AND created_at >= ?",
            (guild_id, since),
        ).fetchall()
        return [r["user_id"] for r in rows]


def top_messages_last_days(guild_id: int, days: int = 7, limit: int = 5) -> list[dict]:
    """Топ участников по числу сообщений за последние N дней."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT user_id, COUNT(*) AS cnt FROM chat_history
            WHERE guild_id = ? AND created_at >= ?
            GROUP BY user_id ORDER BY cnt DESC LIMIT ?
            """,
            (guild_id, since, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def messages_count_last_days(guild_id: int, days: int = 7) -> int:
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) AS c FROM chat_history WHERE guild_id = ? AND created_at >= ?",
            (guild_id, since),
        ).fetchone()
        return row["c"] if row else 0


# ── Питомцы ─────────────────────────────────────────────────────────────────

def get_pet(user_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_pet(user_id: int, name: str, kind: str) -> dict:
    import time as _t
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO pets (user_id, name, kind, xp, hunger, happiness, last_feed, created_at)
            VALUES (?, ?, ?, 0, 80, 80, ?, ?)
            """,
            (user_id, name, kind, int(_t.time()), _now()),
        )
        row = con.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)


def feed_pet(user_id: int, xp: int = 7) -> dict:
    import time as _t
    with _conn() as con:
        con.execute(
            "UPDATE pets SET hunger = 100, happiness = MIN(100, happiness + 5), xp = xp + ?, last_feed = ? WHERE user_id = ?",
            (xp, int(_t.time()), user_id),
        )
        row = con.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)


def pat_pet(user_id: int, xp: int = 2) -> dict:
    import time as _t
    with _conn() as con:
        con.execute(
            "UPDATE pets SET happiness = 100, xp = xp + ?, last_feed = ? WHERE user_id = ?",
            (xp, int(_t.time()), user_id),
        )
        row = con.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)


# ── Дневной бонус и серия ───────────────────────────────────────────────────

def claim_daily(user_id: int, today: str, yesterday: str) -> dict:
    """Начисляет дневной бонус и обновляет серию. Возвращает {reward, streak, best, first}."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM daily_streak WHERE user_id = ?", (user_id,)
        ).fetchone()
        cur_streak = row["streak"] if row else 0
        last_date = row["last_date"] if row else None
        if last_date == today:
            return {"reward": 0, "streak": cur_streak, "best": row["best"] if row else 0, "first": False}
        if last_date == yesterday:
            cur_streak += 1
        else:
            cur_streak = 1
        best = max(cur_streak, row["best"] if row else 0)
        con.execute(
            """
            INSERT INTO daily_streak (user_id, last_date, streak, best) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_date = excluded.last_date, streak = excluded.streak, best = excluded.best
            """,
            (user_id, today, cur_streak, best),
        )
        reward = min(150, 50 + 10 * (cur_streak - 1))
        return {"reward": reward, "streak": cur_streak, "best": best, "first": True}


def get_daily_streak(user_id: int) -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM daily_streak WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return {"streak": 0, "best": 0, "last_date": None}
        return dict(row)


# ── Избранные треки ─────────────────────────────────────────────────────────

def add_favorite(user_id: int, track: dict):
    """Добавляет трек в избранное. Максимум 20. Возвращает "ok", "exists", "limit" или False."""
    with _conn() as con:
        count = con.execute(
            "SELECT COUNT(*) AS c FROM favorite_tracks WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
        if count >= 20:
            return "limit"
        try:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO favorite_tracks
                (user_id, title, url, duration, thumb, webpage_url, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, track["title"], track["url"], int(track.get("duration") or 0),
                 track.get("thumbnail"), track.get("webpage_url") or "", _now()),
            )
            return "ok" if cur.rowcount > 0 else "exists"
        except Exception:
            return False


def list_favorites(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM favorite_tracks WHERE user_id = ? ORDER BY id ASC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def remove_favorite(user_id: int, index: int) -> bool:
    with _conn() as con:
        rows = con.execute(
            "SELECT id FROM favorite_tracks WHERE user_id = ? ORDER BY id ASC", (user_id,)
        ).fetchall()
        if not 0 <= index < len(rows):
            return False
        con.execute("DELETE FROM favorite_tracks WHERE id = ?", (rows[index]["id"],))
        return True


def get_guild_channel(guild_id: int, purpose: str) -> int | None:
    with _conn() as con:
        row = con.execute(
            "SELECT channel_id FROM guild_channels WHERE guild_id = ? AND purpose = ?",
            (guild_id, purpose),
        ).fetchone()
        return row["channel_id"] if row else None


def _now_as_ts() -> float:
    import time
    return time.time()

