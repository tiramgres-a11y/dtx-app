"""
CardioNutri Family — SQLite schema initializer.
Run once (or re-run safely) to create cardionutri.db with all tables.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "cardionutri.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ingredients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    category        TEXT    NOT NULL DEFAULT '',
    calories_per_100g REAL  NOT NULL DEFAULT 0,
    sodium_mg       REAL    NOT NULL DEFAULT 0,
    sat_fat_g       REAL    NOT NULL DEFAULT 0,
    cholesterol_mg  REAL    NOT NULL DEFAULT 0,
    fiber_g         REAL    NOT NULL DEFAULT 0,
    protein_g       REAL    NOT NULL DEFAULT 0,
    carbs_g         REAL    NOT NULL DEFAULT 0,
    fat_g           REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    description     TEXT    NOT NULL DEFAULT '',
    base_servings   INTEGER NOT NULL DEFAULT 4,
    meal_type       TEXT    NOT NULL DEFAULT 'dinner',
    diet_tags       TEXT    NOT NULL DEFAULT '[]',
    prep_minutes    INTEGER NOT NULL DEFAULT 0,
    cook_minutes    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id       INTEGER NOT NULL REFERENCES recipes(id)     ON DELETE CASCADE,
    ingredient_id   INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    quantity_g      REAL    NOT NULL,
    notes           TEXT    NOT NULL DEFAULT '',
    UNIQUE (recipe_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS pantry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id   INTEGER NOT NULL UNIQUE REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity_g      REAL    NOT NULL DEFAULT 0,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weekly_plan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date       TEXT    NOT NULL,
    meal_type       TEXT    NOT NULL,
    recipe_id       INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    servings        INTEGER NOT NULL DEFAULT 4,
    notes           TEXT    NOT NULL DEFAULT '',
    UNIQUE (plan_date, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe ON recipe_ingredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_weekly_plan_date          ON weekly_plan(plan_date);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    print(f"Initializing database at: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        # Verify tables were created
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables created: {tables}")
        print("Schema initialization complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
