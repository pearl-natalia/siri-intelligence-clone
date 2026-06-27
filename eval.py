import sqlite3, os, time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "eval.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            input       TEXT,
            tool        TEXT,
            success     INTEGER,
            latency_ms  INTEGER,
            error       TEXT
        )
    """)
    conn.commit()
    return conn


def log(input: str, tool: str, success: bool, latency_ms: int, error: str = None):
    conn = _connect()
    conn.execute(
        "INSERT INTO runs (timestamp, input, tool, success, latency_ms, error) VALUES (?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), input, tool, int(success), latency_ms, error)
    )
    conn.commit()
    conn.close()


def report():
    conn = _connect()
    rows = conn.execute("SELECT tool, success, latency_ms FROM runs").fetchall()
    conn.close()

    if not rows:
        print("No runs logged yet.")
        return

    total = len(rows)
    passed = sum(1 for _, s, _ in rows if s)
    avg_latency = sum(l for _, _, l in rows) / total

    print(f"\n{'='*40}")
    print(f"Total runs:   {total}")
    print(f"Pass rate:    {passed}/{total} ({100*passed//total}%)")
    print(f"Avg latency:  {avg_latency:.0f}ms")

    # Per-tool breakdown
    tools = {}
    for tool, success, latency in rows:
        t = tool or "llm"
        if t not in tools:
            tools[t] = {"pass": 0, "fail": 0, "latency": []}
        tools[t]["pass" if success else "fail"] += 1
        tools[t]["latency"].append(latency)

    print(f"\n{'Tool':<25} {'Pass':<6} {'Fail':<6} {'Avg ms'}")
    print("-" * 50)
    for tool, stats in sorted(tools.items()):
        avg = sum(stats["latency"]) / len(stats["latency"])
        print(f"{tool:<25} {stats['pass']:<6} {stats['fail']:<6} {avg:.0f}")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    report()
