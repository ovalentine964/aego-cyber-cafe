#!/usr/bin/env python3
"""
SQLite Database Manager for Aego Cyber Cafe
Manages transactions, customer sessions, and usage statistics.

Usage:
    python3 database.py init                    # Initialize database
    python3 database.py stats                   # Show usage statistics
    python3 database.py transactions --limit 20 # Show recent transactions
    python3 database.py sessions                # Show active sessions
    python3 database.py export --output /path/  # Export data as JSON
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DB_PATH = Path("/opt/aego/data/aego.db")
LOG_DIR = Path("/opt/aego/logs")

# Ensure directories
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "database.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("aego-db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrency
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database() -> None:
    """Initialize all database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    logger.info("Initializing database...")

    # ── Transactions Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_ref TEXT UNIQUE,
            checkout_request_id TEXT,
            phone TEXT NOT NULL,
            amount INTEGER NOT NULL,
            service TEXT NOT NULL,
            account_ref TEXT,
            mpesa_receipt TEXT,
            status TEXT DEFAULT 'initiated' CHECK(status IN (
                'initiated', 'pending', 'success', 'failed',
                'cancelled', 'timeout', 'refunded', 'b2c_initiated',
                'b2c_success', 'b2c_failed'
            )),
            raw_response TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_checkout ON transactions(checkout_request_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_phone ON transactions(phone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_service ON transactions(service)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_created ON transactions(created_at)")

    # ── Sessions Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            customer_phone TEXT,
            customer_name TEXT,
            language TEXT DEFAULT 'en' CHECK(language IN ('en', 'sw', 'luo', 'ki')),
            current_service TEXT,
            current_step TEXT,
            session_data TEXT DEFAULT '{}',
            state TEXT DEFAULT 'active' CHECK(state IN (
                'active', 'waiting_payment', 'payment_confirmed',
                'in_progress', 'completed', 'abandoned', 'escalated'
            )),
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_phone ON sessions(customer_phone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_state ON sessions(state)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_service ON sessions(current_service)")

    # ── Usage Stats Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            service TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            avg_completion_time_seconds REAL DEFAULT 0,
            UNIQUE(date, service)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_date ON usage_stats(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_service ON usage_stats(service)")

    # ── Customers Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            name TEXT,
            preferred_language TEXT DEFAULT 'en',
            total_visits INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            first_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer_phone ON customers(phone)")

    # ── Audit Log ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            operator TEXT DEFAULT 'system',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


class TransactionDB:
    """Transaction database operations."""

    def __init__(self, conn: sqlite3.Connection = None):
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def create(
        self,
        phone: str,
        amount: int,
        service: str,
        account_ref: str = "",
        checkout_request_id: str = "",
        status: str = "initiated",
    ) -> int:
        """Create a new transaction record."""
        ref = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{phone[-4:]}"
        cursor = self.conn.execute(
            """
            INSERT INTO transactions (transaction_ref, checkout_request_id, phone, amount, service, account_ref, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ref, checkout_request_id, phone, amount, service, account_ref, status),
        )
        self.conn.commit()
        txn_id = cursor.lastrowid
        logger.info(f"Transaction created: id={txn_id}, ref={ref}, phone={phone}, amount={amount}")
        return txn_id

    def update_status(
        self,
        checkout_request_id: str,
        status: str,
        mpesa_receipt: str = "",
        raw_response: dict = None,
    ) -> bool:
        """Update transaction status by checkout_request_id."""
        cursor = self.conn.execute(
            """
            UPDATE transactions
            SET status = ?, mpesa_receipt = ?, raw_response = ?, updated_at = CURRENT_TIMESTAMP
            WHERE checkout_request_id = ?
            """,
            (status, mpesa_receipt, json.dumps(raw_response) if raw_response else None, checkout_request_id),
        )
        self.conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Transaction updated: {checkout_request_id} -> {status}")
        return updated

    def get_by_checkout_id(self, checkout_request_id: str) -> dict:
        """Get transaction by checkout_request_id."""
        row = self.conn.execute(
            "SELECT * FROM transactions WHERE checkout_request_id = ?",
            (checkout_request_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_by_phone(self, phone: str, limit: int = 10) -> list:
        """Get transactions for a phone number."""
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE phone = ? ORDER BY created_at DESC LIMIT ?",
            (phone, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent(self, limit: int = 20, status: str = None) -> list:
        """Get recent transactions."""
        if status:
            rows = self.conn.execute(
                "SELECT * FROM transactions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_revenue(self, date_from: str = None, date_to: str = None) -> dict:
        """Get revenue summary."""
        query = """
            SELECT
                COUNT(*) as total_transactions,
                SUM(CASE WHEN status = 'success' THEN amount ELSE 0 END) as total_revenue,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
            FROM transactions WHERE 1=1
        """
        params = []
        if date_from:
            query += " AND created_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND created_at <= ?"
            params.append(date_to)

        row = self.conn.execute(query, params).fetchone()
        return dict(row) if row else {}


class SessionDB:
    """Session database operations."""

    def __init__(self, conn: sqlite3.Connection = None):
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def create(
        self,
        session_id: str,
        customer_phone: str = "",
        customer_name: str = "",
        language: str = "en",
        current_service: str = "",
    ) -> int:
        """Create a new session."""
        cursor = self.conn.execute(
            """
            INSERT INTO sessions (session_id, customer_phone, customer_name, language, current_service)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, customer_phone, customer_name, language, current_service),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update(
        self,
        session_id: str,
        current_step: str = None,
        session_data: dict = None,
        state: str = None,
        current_service: str = None,
    ) -> bool:
        """Update session fields."""
        updates = ["last_activity = CURRENT_TIMESTAMP"]
        params = []

        if current_step is not None:
            updates.append("current_step = ?")
            params.append(current_step)
        if session_data is not None:
            updates.append("session_data = ?")
            params.append(json.dumps(session_data))
        if state is not None:
            updates.append("state = ?")
            params.append(state)
            if state == "completed":
                updates.append("completed_at = CURRENT_TIMESTAMP")
        if current_service is not None:
            updates.append("current_service = ?")
            params.append(current_service)

        params.append(session_id)
        query = f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?"

        cursor = self.conn.execute(query, params)
        self.conn.commit()
        return cursor.rowcount > 0

    def get(self, session_id: str) -> dict:
        """Get session by ID."""
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_active(self, limit: int = 50) -> list:
        """Get active sessions."""
        rows = self.conn.execute(
            """
            SELECT * FROM sessions
            WHERE state IN ('active', 'waiting_payment', 'in_progress')
            ORDER BY last_activity DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_phone(self, phone: str) -> list:
        """Get sessions for a phone number."""
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE customer_phone = ? ORDER BY created_at DESC",
            (phone,),
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup_stale(self, hours: int = 24) -> int:
        """Mark stale sessions as abandoned."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute(
            """
            UPDATE sessions SET state = 'abandoned'
            WHERE state IN ('active', 'waiting_payment', 'in_progress')
            AND last_activity < ?
            """,
            (cutoff,),
        )
        self.conn.commit()
        count = cursor.rowcount
        if count:
            logger.info(f"Cleaned up {count} stale sessions")
        return count


class StatsDB:
    """Usage statistics operations."""

    def __init__(self, conn: sqlite3.Connection = None):
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def update_daily_stats(self, date: str = None) -> None:
        """Aggregate and update daily stats from transactions."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get stats from transactions for the date
        rows = self.conn.execute(
            """
            SELECT
                service,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status IN ('failed', 'cancelled', 'timeout') THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'success' THEN amount ELSE 0 END) as revenue
            FROM transactions
            WHERE DATE(created_at) = ?
            GROUP BY service
            """,
            (date,),
        ).fetchall()

        for row in rows:
            self.conn.execute(
                """
                INSERT INTO usage_stats (date, service, total_requests, completed, failed, revenue)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, service) DO UPDATE SET
                    total_requests = excluded.total_requests,
                    completed = excluded.completed,
                    failed = excluded.failed,
                    revenue = excluded.revenue
                """,
                (date, row["service"], row["total"], row["completed"], row["failed"], row["revenue"]),
            )

        self.conn.commit()
        logger.info(f"Daily stats updated for {date}")

    def get_summary(self, days: int = 30) -> dict:
        """Get summary statistics for the last N days."""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        row = self.conn.execute(
            """
            SELECT
                SUM(total_requests) as total_requests,
                SUM(completed) as total_completed,
                SUM(failed) as total_failed,
                SUM(revenue) as total_revenue
            FROM usage_stats
            WHERE date >= ?
            """,
            (date_from,),
        ).fetchone()

        # Per-service breakdown
        services = self.conn.execute(
            """
            SELECT service,
                   SUM(total_requests) as requests,
                   SUM(completed) as completed,
                   SUM(revenue) as revenue
            FROM usage_stats
            WHERE date >= ?
            GROUP BY service
            ORDER BY revenue DESC
            """,
            (date_from,),
        ).fetchall()

        return {
            "period_days": days,
            "date_from": date_from,
            "totals": dict(row) if row else {},
            "by_service": [dict(s) for s in services],
        }

    def get_daily_trend(self, days: int = 7) -> list:
        """Get daily transaction trend."""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            """
            SELECT date,
                   SUM(total_requests) as requests,
                   SUM(completed) as completed,
                   SUM(revenue) as revenue
            FROM usage_stats
            WHERE date >= ?
            GROUP BY date
            ORDER BY date
            """,
            (date_from,),
        ).fetchall()
        return [dict(r) for r in rows]


class CustomerDB:
    """Customer database operations."""

    def __init__(self, conn: sqlite3.Connection = None):
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def upsert(
        self,
        phone: str,
        name: str = None,
        language: str = None,
        spent: float = 0,
    ) -> None:
        """Create or update customer record."""
        self.conn.execute(
            """
            INSERT INTO customers (phone, name, preferred_language, total_visits, total_spent, last_visit)
            VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone) DO UPDATE SET
                name = COALESCE(excluded.name, name),
                preferred_language = COALESCE(excluded.language, preferred_language),
                total_visits = total_visits + 1,
                total_spent = total_spent + excluded.total_spent,
                last_visit = CURRENT_TIMESTAMP
            """,
            (phone, name, language, spent),
        )
        self.conn.commit()

    def get(self, phone: str) -> dict:
        """Get customer by phone."""
        row = self.conn.execute(
            "SELECT * FROM customers WHERE phone = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None

    def get_top(self, limit: int = 10) -> list:
        """Get top customers by spending."""
        rows = self.conn.execute(
            "SELECT * FROM customers ORDER BY total_spent DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def audit_log(action: str, entity_type: str = "", entity_id: str = "", details: str = "", operator: str = "system") -> None:
    """Write an audit log entry."""
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO audit_log (action, entity_type, entity_id, details, operator)
            VALUES (?, ?, ?, ?, ?)
            """,
            (action, entity_type, entity_id, details, operator),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def show_stats() -> None:
    """Display usage statistics."""
    stats = StatsDB()
    summary = stats.get_summary(30)

    print("\n═══════════════════════════════════════════")
    print("  AEGO CYBER CAFE — Usage Statistics (30d)")
    print("═══════════════════════════════════════════\n")

    totals = summary.get("totals", {})
    print(f"  Total Requests:  {totals.get('total_requests', 0)}")
    print(f"  Completed:       {totals.get('total_completed', 0)}")
    print(f"  Failed:          {totals.get('total_failed', 0)}")
    print(f"  Revenue:         KES {totals.get('total_revenue', 0):,.0f}")

    services = summary.get("by_service", [])
    if services:
        print(f"\n  {'Service':<25} {'Requests':>10} {'Revenue':>12}")
        print(f"  {'─' * 47}")
        for s in services:
            print(f"  {s['service']:<25} {s['requests']:>10} {s['revenue']:>10,.0f}")

    print()


def show_transactions(limit: int = 20) -> None:
    """Display recent transactions."""
    txn_db = TransactionDB()
    txns = txn_db.get_recent(limit)

    print(f"\n═══ Recent Transactions (last {limit}) ═══\n")
    print(f"  {'ID':<6} {'Phone':<14} {'Amount':>8} {'Service':<20} {'Status':<12} {'Time'}")
    print(f"  {'─' * 80}")

    for t in txns:
        time_str = t.get("created_at", "")[:16]
        print(
            f"  {t['id']:<6} {t['phone']:<14} {t['amount']:>8} "
            f"{t['service']:<20} {t['status']:<12} {time_str}"
        )

    print()


def show_sessions() -> None:
    """Display active sessions."""
    sess_db = SessionDB()
    sessions = sess_db.get_active()

    print(f"\n═══ Active Sessions ({len(sessions)}) ═══\n")
    print(f"  {'Session ID':<30} {'Phone':<14} {'Service':<15} {'State':<15} {'Last Activity'}")
    print(f"  {'─' * 90}")

    for s in sessions:
        last = s.get("last_activity", "")[:16]
        print(
            f"  {s['session_id'][:28]:<30} {s.get('customer_phone', ''):<14} "
            f"{s.get('current_service', ''):<15} {s['state']:<15} {last}"
        )

    print()


def main():
    parser = argparse.ArgumentParser(description="Aego Cyber Cafe Database Manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize database")
    subparsers.add_parser("stats", help="Show usage statistics")

    txn_parser = subparsers.add_parser("transactions", help="Show recent transactions")
    txn_parser.add_argument("--limit", type=int, default=20)

    subparsers.add_parser("sessions", help="Show active sessions")

    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up stale sessions")
    cleanup_parser.add_argument("--hours", type=int, default=24)

    export_parser = subparsers.add_parser("export", help="Export data as JSON")
    export_parser.add_argument("--output", required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "init":
        init_database()
        print("✅ Database initialized successfully")

    elif args.command == "stats":
        stats = StatsDB()
        stats.update_daily_stats()
        show_stats()

    elif args.command == "transactions":
        show_transactions(args.limit)

    elif args.command == "sessions":
        show_sessions()

    elif args.command == "cleanup":
        sess_db = SessionDB()
        count = sess_db.cleanup_stale(args.hours)
        print(f"✅ Cleaned up {count} stale sessions")

    elif args.command == "export":
        conn = get_connection()
        data = {}

        for table in ["transactions", "sessions", "usage_stats", "customers"]:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]

        conn.close()

        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        export_file = output_path / f"aego_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(export_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"✅ Data exported to {export_file}")


if __name__ == "__main__":
    main()
