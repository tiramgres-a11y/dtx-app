"""
CardioNutri Family — Dummy data seeder.
Inserts 5 ingredients and 3 DASH/Portfolio-aligned recipes for testing.
Safe to re-run (INSERT OR IGNORE).
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "cardionutri.db"

# (name, category, cal/100g, sodium_mg, sat_fat_g, cholesterol_mg, fiber_g, protein_g, carbs_g, fat_g)
INGREDIENTS = [
    ("Rolled Oats",     "grain",     389, 2,   0.7, 0,  10.6, 16.9, 66.3, 6.9),
    ("Canned Chickpeas","legume",    164, 240, 0.1, 0,  7.6,  8.9,  27.4, 2.6),
    ("Spinach",         "vegetable", 23,  79,  0.1, 0,  2.2,  2.9,  3.6,  0.4),
    ("Salmon Fillet",   "protein",   208, 59,  1.2, 63, 0.0,  20.4, 0.0,  13.4),
    ("Olive Oil",       "fat",       884, 2,   13.8,0,  0.0,  0.0,  0.0,  100.0),
]

# (name, description, base_servings, meal_type, diet_tags, prep_min, cook_min)
RECIPES = [
    (
        "DASH Oatmeal Bowl",
        "Hearty oat bowl with berries — low sodium, high fiber breakfast.",
        2, "breakfast", json.dumps(["DASH", "Portfolio", "vegan"]), 5, 10,
    ),
    (
        "Chickpea Spinach Stew",
        "Protein-rich legume stew with wilted spinach. DASH and Portfolio friendly.",
        4, "dinner", json.dumps(["DASH", "Portfolio", "vegan"]), 10, 25,
    ),
    (
        "Baked Salmon with Spinach",
        "Omega-3 rich salmon over sautéed spinach with olive oil.",
        2, "dinner", json.dumps(["DASH", "Portfolio"]), 10, 20,
    ),
]

# (recipe_name, ingredient_name, quantity_g, notes)
RECIPE_INGREDIENTS = [
    ("DASH Oatmeal Bowl",          "Rolled Oats",     80,  "dry"),
    ("Chickpea Spinach Stew",      "Canned Chickpeas",400, "drained and rinsed"),
    ("Chickpea Spinach Stew",      "Spinach",         200, "fresh, roughly chopped"),
    ("Chickpea Spinach Stew",      "Olive Oil",       15,  "for sautéing"),
    ("Baked Salmon with Spinach",  "Salmon Fillet",   300, "skin-on"),
    ("Baked Salmon with Spinach",  "Spinach",         150, "wilted"),
    ("Baked Salmon with Spinach",  "Olive Oil",       10,  "drizzled"),
]

# (ingredient_name, quantity_g)
PANTRY_STOCK = [
    ("Rolled Oats",     500),
    ("Canned Chickpeas",800),
    ("Spinach",         300),
    ("Salmon Fillet",   600),
    ("Olive Oil",       250),
]


def seed(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # Ingredients
        conn.executemany(
            """INSERT OR IGNORE INTO ingredients
               (name, category, calories_per_100g, sodium_mg, sat_fat_g,
                cholesterol_mg, fiber_g, protein_g, carbs_g, fat_g)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            INGREDIENTS,
        )
        print(f"Ingredients seeded: {len(INGREDIENTS)}")

        # Recipes
        conn.executemany(
            """INSERT OR IGNORE INTO recipes
               (name, description, base_servings, meal_type, diet_tags,
                prep_minutes, cook_minutes)
               VALUES (?,?,?,?,?,?,?)""",
            RECIPES,
        )
        print(f"Recipes seeded: {len(RECIPES)}")

        # Recipe ingredients (resolve names → IDs)
        for rec_name, ing_name, qty, notes in RECIPE_INGREDIENTS:
            recipe_id = conn.execute(
                "SELECT id FROM recipes WHERE name = ?", (rec_name,)
            ).fetchone()[0]
            ingredient_id = conn.execute(
                "SELECT id FROM ingredients WHERE name = ?", (ing_name,)
            ).fetchone()[0]
            conn.execute(
                """INSERT OR IGNORE INTO recipe_ingredients
                   (recipe_id, ingredient_id, quantity_g, notes)
                   VALUES (?,?,?,?)""",
                (recipe_id, ingredient_id, qty, notes),
            )
        print(f"Recipe-ingredient links seeded: {len(RECIPE_INGREDIENTS)}")

        # Pantry
        for ing_name, qty in PANTRY_STOCK:
            ingredient_id = conn.execute(
                "SELECT id FROM ingredients WHERE name = ?", (ing_name,)
            ).fetchone()[0]
            conn.execute(
                """INSERT OR IGNORE INTO pantry (ingredient_id, quantity_g)
                   VALUES (?,?)""",
                (ingredient_id, qty),
            )
        print(f"Pantry entries seeded: {len(PANTRY_STOCK)}")

        conn.commit()

        # Quick verification query
        rows = conn.execute(
            """SELECT r.name, i.name, ri.quantity_g
               FROM recipe_ingredients ri
               JOIN recipes r ON r.id = ri.recipe_id
               JOIN ingredients i ON i.id = ri.ingredient_id
               ORDER BY r.name, i.name"""
        ).fetchall()
        print("\nVerification — recipe contents:")
        for row in rows:
            print(f"  [{row[0]}]  {row[1]}: {row[2]} g")

        print("\nSeed complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
