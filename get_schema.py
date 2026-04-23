import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_connection

TABLES = [
    "ref_departments",
    "cfg_service_department_status",
    "sk_call_queue",
    "cfg_service_departments",
    "cfg_departaments_status",
]

def get_table_data(table_name):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT * FROM {table_name} LIMIT 100')
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return columns, rows
    finally:
        conn.close()

for table in TABLES:
    print(f"\n{'='*60}")
    print(f"TABELA: {table}")
    print(f"{'='*60}")
    try:
        columns, rows = get_table_data(table)
        print(f"Colunas: {columns}")
        print(f"Linhas: {len(rows)}")
        for row in rows[:20]:
            print(row)
    except Exception as e:
        print(f"Erro: {e}")
