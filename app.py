"""
Backend API tier — Flask + PostgreSQL.

Reads all connection details from environment variables (set in
docker-compose.yml / .env) so the same image runs unmodified in any
environment (local, staging, prod) — only the env changes.
"""

import os
import time

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # frontend runs on a different origin/container

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("POSTGRES_DB", "taskflow"),
    "user": os.environ.get("POSTGRES_USER", "taskflow_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "changeme"),
}


def get_connection(retries=10, delay=2):
    """
    Retries connecting to the db service, since Compose starts containers
    in parallel and Postgres may not be accepting connections yet even
    after its container has started.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to database after {retries} attempts: {last_err}")


def init_db():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
    finally:
        conn.close()


@app.route("/api/health")
def health():
    """Used by docker-compose healthcheck / manual verification."""
    try:
        conn = get_connection(retries=1)
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"unreachable: {e}"
    return jsonify({"status": "ok", "database": db_status})


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, title, done, created_at FROM tasks ORDER BY id DESC;")
            rows = cur.fetchall()
        return jsonify(rows)
    finally:
        conn.close()


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    conn = get_connection()
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, done, created_at;",
                (title,),
            )
            row = cur.fetchone()
        return jsonify(row), 201
    finally:
        conn.close()


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    data = request.get_json(force=True) or {}
    conn = get_connection()
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE tasks SET done = %s WHERE id = %s RETURNING id, title, done, created_at;",
                (bool(data.get("done", False)), task_id),
            )
            row = cur.fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(row)
    finally:
        conn.close()


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s;", (task_id,))
            deleted = cur.rowcount
        if deleted == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"deleted": task_id})
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
