"""
db.py -- Conexão central com o banco SQLite do projeto.

Usa modo WAL (Write-Ahead Logging), que permite MÚLTIPLOS AGENTES lendo
o banco ao mesmo tempo sem travar uns aos outros, mesmo enquanto uma
escrita (ex: registro de nova leitura de foto) está acontecendo.

Substitui os arquivos JSON soltos (pacientes.json, historico.json) por
duas tabelas, eliminando o risco de corrupção por escrita simultânea que
existia antes.
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "dados_contador_mdt.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            peso REAL NOT NULL,
            data_inicio_tratamento TEXT NOT NULL,
            esquema_manutencao TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id TEXT NOT NULL,
            data TEXT NOT NULL,
            leituras TEXT NOT NULL,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_historico_paciente
        ON historico(paciente_id)
    """)
    conn.commit()
    conn.close()