from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import logging

app = FastAPI()

# ---- Logger ayarı ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("myapp")

# ---- Veri modelleri ----
class Category(BaseModel):
    name: str

class Block(BaseModel):
    category_id: int   # önce category
    title: str
    content: str

# ---- DB yardımcı fonksiyon ----
def get_db():
    conn = sqlite3.connect("mydb.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---- Log DB fonksiyonu ----
def log_to_db(level: str, message: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (level, message) VALUES (?, ?)",
            (level, message)
        )
        conn.commit()

def app_log(level: str, message: str):
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.debug(message)

    log_to_db(level, message)

# ---- Tabloları oluştur ----
with get_db() as conn:
    # Category tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    # Blocks tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT,
            content TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    """)
    # Logs tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# ==========================
# CATEGORY CRUD
# ==========================

@app.get("/categories")
def get_categories():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories")
        rows = cursor.fetchall()
    app_log("info", "Tüm kategoriler getirildi")
    return [dict(row) for row in rows]

@app.get("/categories/{category_id}")
def get_category(category_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories WHERE id = ?", (category_id,))
        row = cursor.fetchone()
    if row:
        app_log("info", f"Kategori getirildi: id={category_id}")
        return dict(row)
    app_log("warning", f"Kategori bulunamadı: id={category_id}")
    return {"error": f"Category {category_id} not found"}

@app.post("/categories")
def add_category(category: Category):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (category.name,))
            conn.commit()
            new_id = cursor.lastrowid
            app_log("info", f"Kategori eklendi: {category.name} (id={new_id})")
            return {"id": new_id, "name": category.name}
        except sqlite3.IntegrityError:
            app_log("warning", f"Kategori zaten mevcut: {category.name}")
            return {"error": "Bu kategori zaten mevcut"}

@app.put("/categories/{category_id}")
def update_category(category_id: int, category: Category):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET name = ? WHERE id = ?", (category.name, category_id))
        conn.commit()
        if cursor.rowcount == 0:
            app_log("warning", f"Güncellenmek istenen kategori bulunamadı: id={category_id}")
            return {"error": f"Category {category_id} not found"}
    app_log("info", f"Kategori güncellendi: id={category_id}, yeni ad={category.name}")
    return {"id": category_id, "name": category.name}

@app.delete("/categories/{category_id}")
def delete_category(category_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        if cursor.rowcount == 0:
            app_log("warning", f"Silinmek istenen kategori bulunamadı: id={category_id}")
            return {"error": f"Category {category_id} not found"}
    app_log("info", f"Kategori silindi: id={category_id}")
    return {"message": f"Category {category_id} deleted"}


# ==========================
# BLOCK CRUD
# ==========================

@app.get("/blocks")
def get_blocks():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.category_id, b.title, b.content, c.name as category_name
            FROM blocks b
            JOIN categories c ON b.category_id = c.id
        """)
        rows = cursor.fetchall()
    app_log("info", "Tüm bloklar getirildi")
    return [dict(row) for row in rows]

@app.post("/blocks")
def add_block(block: Block):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE id = ?", (block.category_id,))
        category = cursor.fetchone()
        if not category:
            app_log("warning", f"Geçersiz kategori id ile blok ekleme denemesi: {block.category_id}")
            return {"error": "Geçersiz kategori id"}

        cursor.execute(
            "INSERT INTO blocks (category_id, title, content) VALUES (?, ?, ?)", 
            (block.category_id, block.title, block.content)
        )
        conn.commit()
        new_id = cursor.lastrowid
    app_log("info", f"Blok eklendi: id={new_id}, kategori={block.category_id}, başlık={block.title}, içerik={block.content}")
    return {
        "id": new_id,
        "category_id": block.category_id,
        "title": block.title,
        "content": block.content
    }

@app.put("/blocks/{block_id}")
def update_block(block_id: int, block: Block):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blocks SET category_id = ?, title = ?, content = ? WHERE id = ?", 
            (block.category_id, block.title, block.content, block_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            app_log("warning", f"Güncellenmek istenen blok bulunamadı: id={block_id}")
            return {"error": f"Block {block_id} not found"}
    app_log("info", f"Blok güncellendi: id={block_id}, kategori={block.category_id}, başlık={block.title}, içerik={block.content}")
    return {
        "id": block_id,
        "category_id": block.category_id,
        "title": block.title,
        "content": block.content
    }

@app.delete("/blocks/{block_id}")
def delete_block(block_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
        conn.commit()
        if cursor.rowcount == 0:
            app_log("warning", f"Silinmek istenen blok bulunamadı: id={block_id}")
            return {"error": f"Block {block_id} not found"}
    app_log("info", f"Blok silindi: id={block_id}")
    return {"message": f"Block {block_id} deleted"}


# ==========================
# LOGS
# ==========================
@app.get("/logs")
def get_logs():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, level, message, created_at FROM logs ORDER BY created_at DESC")
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
