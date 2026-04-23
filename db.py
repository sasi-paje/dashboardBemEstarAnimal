import os
import json
import pandas as pd
from psycopg2 import connect
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return connect(
        host=os.getenv("HOST_DEV"),
        port=os.getenv("PORT_DEV"),
        dbname=os.getenv("DB_NAME_DEV"),
        user=os.getenv("DB_USER_DEV"),
        password=os.getenv("DB_PASSWORD_DEV"),
    )

def execute_query(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
    finally:
        conn.close()

def execute_query_dataframe(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return pd.DataFrame(rows, columns=columns)
            conn.commit()
    finally:
        conn.close()

def get_bookings_overview(local=None, servico=None, departamento=None, date_from=None, date_to=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT get_bookings_overview(%s, %s, %s, %s, NULL, NULL, NULL, NULL, NULL, %s, NULL, NULL, NULL, NULL, NULL)",
                (departamento, None, date_from, date_to, local)
            )
            result = cur.fetchone()
            if result and result[0]:
                data = json.loads(result[0])
                if isinstance(data, list) and len(data) > 0:
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    return pd.DataFrame([data])
            return pd.DataFrame()
    finally:
        conn.close()

QUERY_VAGAS = """
SELECT
    v.id_site_service,
    v.name_service AS servico,
    v.total_vagas_ocupadas,
    v.total_vagas_livres,
    v.total_de_vagas AS total_vagas
FROM vw_bi_counts_vagas v
WHERE (%s IS NULL OR v.id_site_service = %s)
ORDER BY v.name_service
"""

QUERY_FILA = """
SELECT
    ss.name AS local_servico,
    svc.service_name AS servico,
    cq.status,
    COUNT(cq.id) AS quantidade
FROM sk_call_queue cq
JOIN sk_sites_services ss ON cq.id_site_service = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
WHERE (%s IS NULL OR ss.name = %s)
  AND (%s IS NULL OR svc.service_name = %s)
GROUP BY ss.name, svc.service_name, cq.status
ORDER BY ss.name, svc.service_name, cq.status
"""

QUERY_NAO_COMPARECERAM = """
SELECT
    sk.id AS booking_id,
    sk.service_date AS data_agendamento,
    sk.init_interval_hour AS hora_agendamento,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    p.name AS nome,
    p.cpf
FROM sk_booking sk
JOIN person p ON sk.client_id = p.client_id AND p.person_type_id = 1
JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
WHERE sk.status IS NULL
  AND (%s IS NULL OR ss.name = %s)
  AND (%s IS NULL OR sk.service_date >= %s)
  AND (%s IS NULL OR sk.service_date <= %s)
ORDER BY sk.service_date DESC, sk.init_interval_hour DESC
"""

QUERY_MEDIA_HORA = """
SELECT
    EXTRACT(HOUR FROM call_time) AS hora,
    COUNT(*) AS total
FROM sk_call_queue
WHERE call_time IS NOT NULL
  AND (%s IS NULL OR service_date >= %s)
  AND (%s IS NULL OR service_date <= %s)
GROUP BY EXTRACT(HOUR FROM call_time)
ORDER BY hora
"""

QUERY_LOCAIS = """
SELECT DISTINCT name AS local_servico
FROM sk_sites_services
ORDER BY name
"""

QUERY_SERVICOS = """
SELECT DISTINCT service_name AS servico
FROM sk_service
WHERE active = true
ORDER BY service_name
"""

QUERY_DEPARTAMENTOS = """
SELECT DISTINCT name AS department
FROM ref_departments
WHERE is_active = true
ORDER BY name
"""

def get_vagas(local=None, servico=None, departamento=None):
    return execute_query_dataframe(
        QUERY_VAGAS,
        (local, local)
    )

def get_fila(local=None, servico=None, departamento=None):
    return execute_query_dataframe(
        QUERY_FILA,
        (local, local, servico, servico)
    )

def get_nao_compareream(local=None, date_from=None, date_to=None):
    return execute_query_dataframe(
        QUERY_NAO_COMPARECERAM,
        (local, local, date_from, date_from, date_to, date_to)
    )

def get_media_hora(date_from=None, date_to=None):
    df = execute_query_dataframe(
        QUERY_MEDIA_HORA,
        (date_from, date_from, date_to, date_to)
    )
    if df.empty:
        return 0
    total_atendimentos = df['total'].sum()
    horas_com_atendimento = len(df)
    if horas_com_atendimento == 0:
        return 0
    return round(total_atendimentos / horas_com_atendimento, 1)

def get_kpis(local=None, servico=None, departamento=None, date_from=None, date_to=None):
    df_overview = get_bookings_overview(local, servico, departamento, date_from, date_to)

    if not df_overview.empty:
        total_vagas = int(df_overview['total_de_vagas'].iloc[0])
        vagas_ocupadas = int(df_overview['total_vagas_ocupadas'].iloc[0])
        vagas_livres = int(df_overview['total_vagas_livres'].iloc[0])
    else:
        total_vagas = vagas_ocupadas = vagas_livres = 0

    df_fila = get_fila(local, servico, departamento)
    em_fila = int(df_fila['quantidade'].sum()) if not df_fila.empty else 0

    df_nao_compareceam = get_nao_compareream(local, date_from, date_to)
    nao_compareceam = len(df_nao_compareceam)

    media_hora = get_media_hora(date_from, date_to)

    taxa_ocupacao = round((vagas_ocupadas / total_vagas * 100), 1) if total_vagas > 0 else 0

    return {
        'total_vagas': total_vagas,
        'vagas_ocupadas': vagas_ocupadas,
        'vagas_livres': vagas_livres,
        'taxa_ocupacao': taxa_ocupacao,
        'em_fila': em_fila,
        'nao_compareceam': nao_compareceam,
        'media_hora': media_hora
    }

def get_filter_options():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(QUERY_LOCAIS)
            locais = [r[0] for r in cur.fetchall()]

            cur.execute(QUERY_SERVICOS)
            servicos = [r[0] for r in cur.fetchall()]

            cur.execute(QUERY_DEPARTAMENTOS)
            departamentos = [r[0] for r in cur.fetchall()]

            return locais, servicos, departamentos
    finally:
        conn.close()

# ============================================
# Novas funções para Views BI temporais
# ============================================

def get_fact_resumo(date_from=None, date_to=None, local=None, servico=None):
    query = """
    SELECT 
        f.data,
        f.site_service_id,
        dl.local_servico,
        dl.servico,
        f.total_vagas,
        f.vagas_scheduled,
        f.vagas_checked_in,
        f.vagas_nao_confirmadas,
        f.vagas_ocupadas,
        f.em_fila,
        f.waiting,
        f.calling,
        f.called,
        f.cancelled,
        f.nao_compareceram,
        f.taxa_ocupacao_pct
    FROM vw_bi_fact_resumo f
    JOIN vw_bi_dim_local dl ON f.site_service_id = dl.site_service_id
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND f.data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND f.data <= %s"
        params.append(date_to)
    if local:
        query += " AND dl.local_servico = %s"
        params.append(local)
    if servico:
        query += " AND dl.servico = %s"
        params.append(servico)
    query += " ORDER BY f.data DESC, dl.local_servico"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_vagas_temporal(date_from=None, date_to=None, local=None, servico=None):
    query = """
    SELECT 
        data,
        site_service_id,
        local_servico,
        servico,
        total_vagas,
        vagas_scheduled,
        vagas_checked_in,
        vagas_nao_confirmadas,
        vagas_ocupadas,
        vagas_livres
    FROM vw_bi_vagas_temporal
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    if local:
        query += " AND local_servico = %s"
        params.append(local)
    if servico:
        query += " AND servico = %s"
        params.append(servico)
    query += " ORDER BY data DESC, local_servico"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_fila_temporal(date_from=None, date_to=None, local=None, servico=None, departamento=None):
    query = """
    SELECT 
        data,
        site_service_id,
        local_servico,
        servico,
        status_fila,
        status_departamento,
        departamento,
        quantidade
    FROM vw_bi_fila_temporal
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    if local:
        query += " AND local_servico = %s"
        params.append(local)
    if servico:
        query += " AND servico = %s"
        params.append(servico)
    if departamento:
        query += " AND departamento = %s"
        params.append(departamento)
    query += " ORDER BY data DESC, local_servico, departamento"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_fluxo_departamentos(date_from=None, date_to=None, local=None, servico=None):
    query = """
    SELECT 
        data,
        site_service_id,
        local_servico,
        servico,
        department_id,
        departamento,
        ordem_fluxo,
        status_id,
        status,
        ordem_status,
        is_initial,
        is_final,
        is_cancelled,
        quantidade,
        qtd_waiting,
        qtd_calling,
        qtd_called,
        qtd_cancelled
    FROM vw_bi_fluxo_departamentos
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    if local:
        query += " AND local_servico = %s"
        params.append(local)
    if servico:
        query += " AND servico = %s"
        params.append(servico)
    query += " ORDER BY data DESC, local_servico, ordem_fluxo, ordem_status"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_nao_compareceram_por_local():
    query = """
    SELECT
        local_servico,
        ano_mes,
        COUNT(*) AS total
    FROM vw_bi_nao_compareceram_detalhado
    WHERE ano_mes >= TO_CHAR(CURRENT_DATE - INTERVAL '2 months', 'YYYY-MM')
    GROUP BY local_servico, ano_mes
    ORDER BY local_servico, ano_mes
    """
    return execute_query_dataframe(query)

def get_nao_compareceram_detalhado(date_from=None, date_to=None, local=None, servico=None, limit=1000):
    query = """
    SELECT 
        data_agendamento,
        ano_mes,
        dia_semana,
        site_service_id,
        local_servico,
        servico,
        booking_id,
        hora_vaga,
        tutor_id,
        nome_tutor,
        cpf,
        telefone,
        pet_id,
        nome_animal,
        porte,
        sexo,
        raca,
        era_prioridade,
        priority_type,
        data_criacao_agendamento
    FROM vw_bi_nao_compareceram_detalhado
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND data_agendamento >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data_agendamento <= %s"
        params.append(date_to)
    if local:
        query += " AND local_servico = %s"
        params.append(local)
    if servico:
        query += " AND servico = %s"
        params.append(servico)
    query += " ORDER BY data_agendamento DESC, local_servico LIMIT %s"
    params.append(limit)
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_dim_local():
    return execute_query_dataframe("SELECT * FROM vw_bi_dim_local ORDER BY local_servico")

def get_dim_date(date_from=None, date_to=None):
    query = "SELECT * FROM vw_bi_dim_date WHERE 1=1"
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    query += " ORDER BY data DESC"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_atendimentos_por_hora():
    return execute_query_dataframe("SELECT * FROM vw_bi_atendimentos_por_hora ORDER BY hora")

def get_tempo_medio(date_from=None, date_to=None):
    query = """
    SELECT 
        data,
        site_service_id,
        local_servico,
        servico,
        status,
        total_chamados_com_tempo,
        tempo_medio_espera_minutos,
        tempo_max_espera_minutos,
        tempo_min_espera_minutos,
        avg_call_count,
        avg_board_count
    FROM vw_bi_tempo_medio
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    query += " ORDER BY data DESC, local_servico"
    return execute_query_dataframe(query, tuple(params) if params else None)

def get_kpis_fact_resumo(date_from=None, date_to=None, local=None, servico=None):
    df = get_fact_resumo(date_from, date_to, local, servico)
    if df.empty:
        return {
            'total_vagas': 0,
            'vagas_ocupadas': 0,
            'vagas_livres': 0,
            'taxa_ocupacao': 0,
            'em_fila': 0,
            'waiting': 0,
            'calling': 0,
            'called': 0,
            'nao_compareceram': 0
        }
    
    return {
        'total_vagas': int(df['total_vagas'].sum()),
        'vagas_ocupadas': int(df['vagas_ocupadas'].sum()),
        'vagas_livres': int(df['vagas_nao_confirmadas'].sum()),
        'taxa_ocupacao': round(df['taxa_ocupacao_pct'].mean(), 1) if len(df) > 0 else 0,
        'em_fila': int(df['em_fila'].sum()),
        'waiting': int(df['waiting'].sum()),
        'calling': int(df['calling'].sum()),
        'called': int(df['called'].sum()),
        'nao_compareceram': int(df['nao_compareceram'].sum())
    }

def get_departamentos_flow(date_from=None, date_to=None, local=None):
    df = get_fluxo_departamentos(date_from, date_to, local)
    if df.empty:
        return pd.DataFrame()
    
    agg_df = df.groupby(['departamento', 'ordem_fluxo', 'status']).agg({
        'quantidade': 'sum',
        'qtd_waiting': 'sum',
        'qtd_calling': 'sum',
        'qtd_called': 'sum',
        'qtd_cancelled': 'sum'
    }).reset_index()
    
    return agg_df.sort_values(['ordem_fluxo', 'status'])