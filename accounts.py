import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

database_path = Path(os.environ.get("DATA_DIR", Path(__file__).parent)) / "accounts.db"

PLAN_PRICE = "£9.99"
BOOK_LIMIT = 5
CHAPTER_LIMIT = 30
FREE_BOOK_LIMIT = 1
FREE_CHAPTER_LIMIT = 8
RANGES = {
    "3-5": (3, 5),
    "6-8": (6, 8),
    "9-11": (9, 11),
    "12-15": (12, 15),
}


def connect():
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_until TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id TEXT NOT NULL,
                chapters INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                created_at TEXT NOT NULL,
                covers_until TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            UPDATE users SET paid_until = NULL
            WHERE NOT EXISTS (SELECT 1 FROM payments WHERE payments.user_id = users.id)
            """
        )


def now():
    return datetime.now(timezone.utc)


def iso(value: datetime):
    return value.isoformat()


def parse_time(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value)


def hash_password(password: str, salt: str):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return digest.hex()


def register(email: str, password: str):
    email = email.strip().lower()
    if "@" not in email or len(password) < 6:
        raise ValueError("Use a valid email and a password of at least 6 characters.")
    salt = secrets.token_hex(16)
    with connect() as connection:
        try:
            connection.execute(
                "INSERT INTO users (email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?)",
                (email, hash_password(password, salt), salt, iso(now())),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with that email already exists.") from error
    return login(email, password)


def login(email: str, password: str):
    email = email.strip().lower()
    with connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or hash_password(password, user["password_salt"]) != user["password_hash"]:
            raise ValueError("Email or password is incorrect.")
        token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user["id"], iso(now())),
        )
    return {"token": token, "account": account_summary(user["id"])}


def logout(token: str):
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))


def user_from_token(token: str | None):
    if not token:
        return None
    with connect() as connection:
        row = connection.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    return row


def period_start(paid_until: datetime):
    return paid_until - timedelta(days=30)


def current_plan(paid_until: str | None):
    paid = parse_time(paid_until)
    if paid is not None and paid > now():
        return {
            "name": "Plus",
            "price": PLAN_PRICE,
            "interval": "month",
            "audiobooks": BOOK_LIMIT,
            "chapters": CHAPTER_LIMIT,
            "subscription_active": True,
            "window_start": period_start(paid),
        }
    return {
        "name": "Free",
        "price": "£0",
        "interval": "month",
        "audiobooks": FREE_BOOK_LIMIT,
        "chapters": FREE_CHAPTER_LIMIT,
        "subscription_active": False,
        "window_start": now() - timedelta(days=30),
    }


def usage_since(user_id: int, start: datetime):
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS books_used, COALESCE(SUM(chapters), 0) AS chapters_used
            FROM usage
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, iso(start)),
        ).fetchone()
    return {"books_used": row["books_used"], "chapters_used": row["chapters_used"]}


def account_summary(user_id: int):
    with connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    plan = current_plan(user["paid_until"])
    usage = usage_since(user["id"], plan["window_start"])
    return {
        "email": user["email"],
        "plan": {
            "name": plan["name"],
            "price": plan["price"],
            "interval": plan["interval"],
            "audiobooks": plan["audiobooks"],
            "chapters": plan["chapters"],
        },
        "subscription_active": plan["subscription_active"],
        "paid_until": user["paid_until"],
        "books_used": usage["books_used"],
        "chapters_used": usage["chapters_used"],
        "books_remaining": max(plan["audiobooks"] - usage["books_used"], 0),
        "chapters_remaining": max(plan["chapters"] - usage["chapters_used"], 0),
    }


def subscribe(user_id: int):
    raise PermissionError("Plus costs £9.99 a month. The plan stays on Free until that payment is completed.")


def allowed_range(chapter_range: str, chapters_remaining: int):
    bounds = RANGES.get(chapter_range)
    if bounds is None:
        raise ValueError("Choose a chapter range of 3-5, 6-8, 9-11, or 12-15.")
    low, high = bounds
    if chapters_remaining < low:
        raise ValueError(
            f"This range needs at least {low} chapters, and this account has {chapters_remaining} left this month."
        )
    return f"{low}-{min(high, chapters_remaining)}"


def check_can_generate(user, chapter_range: str):
    summary = account_summary(user["id"])
    plan_name = summary["plan"]["name"]
    if summary["books_remaining"] < 1:
        if plan_name == "Free":
            raise PermissionError(
                "The free plan includes 1 audiobook a month. Upgrade to Plus for £9.99 to generate 5."
            )
        raise PermissionError("This Plus plan has already generated 5 audiobooks this month.")
    if summary["chapters_remaining"] < 1:
        raise PermissionError(
            f"The {plan_name} plan has used all {summary['plan']['chapters']} chapters for this month."
        )
    return allowed_range(chapter_range, summary["chapters_remaining"])


def record_usage(user_id: int, book_id: str, chapters: int):
    with connect() as connection:
        connection.execute(
            "INSERT INTO usage (user_id, book_id, chapters, created_at) VALUES (?, ?, ?, ?)",
            (user_id, book_id, chapters, iso(now())),
        )


init_db()
