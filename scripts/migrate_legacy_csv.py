from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CSV_FILE = DATA_DIR / "diagnosticos.csv"
DB_FILE = DATA_DIR / "jurisflow.db"


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            nome TEXT NOT NULL,
            escritorio TEXT NOT NULL,
            cargo TEXT,
            email TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            cidade_estado TEXT,
            area TEXT,
            porte TEXT,
            volume TEXT,
            objetivo TEXT,
            prioridade TEXT,
            sistemas TEXT,
            principal_gargalo TEXT NOT NULL,
            observacoes TEXT,
            consentimento TEXT NOT NULL
        )
        """
    )
    conn.commit()


def main() -> None:
    if not CSV_FILE.exists():
        print("legacy_csv_missing")
        return

    with sqlite3.connect(DB_FILE) as conn:
        ensure_table(conn)
        existing = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        if existing:
            print(f"skipped_existing_rows={existing}")
            return

        with CSV_FILE.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            rows = list(reader)

        for row in rows:
            conn.execute(
                """
                INSERT INTO leads (
                    timestamp,
                    nome,
                    escritorio,
                    cargo,
                    email,
                    whatsapp,
                    cidade_estado,
                    area,
                    porte,
                    volume,
                    objetivo,
                    prioridade,
                    sistemas,
                    principal_gargalo,
                    observacoes,
                    consentimento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row.get("timestamp", ""),
                    row.get("nome", ""),
                    row.get("escritorio", ""),
                    row.get("cargo", ""),
                    row.get("email", ""),
                    row.get("whatsapp", ""),
                    row.get("cidade_estado", ""),
                    row.get("area", ""),
                    row.get("porte", ""),
                    row.get("volume", ""),
                    row.get("objetivo", ""),
                    row.get("prioridade", ""),
                    row.get("sistemas", ""),
                    row.get("principal_gargalo", ""),
                    row.get("observacoes", ""),
                    row.get("consentimento", "sim"),
                ],
            )
        conn.commit()
        print(f"imported_rows={len(rows)}")


if __name__ == "__main__":
    main()
