"""
SQLite 数据库初始化和连接管理。
管理知识库和文档的元数据表。
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 数据库文件路径（项目根目录）
DB_DIR = Path(__file__).parents[2] / "data"
DB_PATH = DB_DIR / "paper_rag.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，自动创建目录。"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构。"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL DEFAULT 'work',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            kb_id INTEGER,
            kb_name TEXT DEFAULT '',
            model_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            estimated_cost REAL DEFAULT 0.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'uploaded',
            page_count INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS thesis_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            kb_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            literature_notes TEXT NOT NULL DEFAULT '[]',
            outline TEXT DEFAULT NULL,
            outline_status TEXT NOT NULL DEFAULT 'none',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
        )
    """)

    # 迁移：为已存在的数据库添加 sections_content 列
    try:
        cursor.execute("ALTER TABLE thesis_projects ADD COLUMN sections_content TEXT NOT NULL DEFAULT '{}'")
    except Exception:
        pass  # 列已存在

    # 迁移：多知识库（JSON 数组）+ 研究方法/专家角色（创建必填）
    try:
        cursor.execute("ALTER TABLE thesis_projects ADD COLUMN kb_ids TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass  # 列已存在
    try:
        cursor.execute("ALTER TABLE thesis_projects ADD COLUMN methodology TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass  # 列已存在

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            tool_name TEXT DEFAULT NULL,
            latency_ms INTEGER DEFAULT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES thesis_projects(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER,
            project_id INTEGER,
            scope TEXT NOT NULL DEFAULT 'kb',
            category TEXT NOT NULL DEFAULT 'preference',
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            source TEXT NOT NULL DEFAULT 'chat',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES thesis_projects(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER,
            project_id INTEGER,
            conversation_id INTEGER,
            category TEXT NOT NULL DEFAULT 'preference',
            content TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            source_user_message TEXT NOT NULL DEFAULT '',
            source_assistant_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES thesis_projects(id) ON DELETE CASCADE,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER,
            project_id INTEGER,
            conversation_id INTEGER,
            question TEXT NOT NULL DEFAULT '',
            memory_ids TEXT NOT NULL DEFAULT '[]',
            memories TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES thesis_projects(id) ON DELETE CASCADE,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
    """)

    conn.commit()
    conn.close()


def now_iso() -> str:
    """返回当前北京时间 ISO 格式字符串。"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat()


# 模块加载时自动初始化
init_db()
