import os
import json
import threading
import pandas as pd
from psycopg2 import connect
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    _pool = ThreadedConnectionPool(
                        minconn=1,
                        maxconn=5,
                        host=os.getenv("HOST_DEV"),
                        port=os.getenv("PORT_DEV"),
                        dbname=os.getenv("DB_NAME_DEV"),
                        user=os.getenv("DB_USER_DEV"),
                        password=os.getenv("DB_PASSWORD_DEV"),
                    )
                except Exception as e:
                    print(f"Pool creation failed: {e}")
                    _pool = None
                    raise
    return _pool

_connection_lock = threading.Lock()

def get_connection():
    with _connection_lock:
        pool = _get_pool()
        try:
            conn = pool.getconn()
            return conn
        except Exception as e:
            print(f"Error getting connection: {e}")
            raise

def get_connection_simple():
    return connect(
        host=os.getenv("HOST_DEV"),
        port=os.getenv("PORT_DEV"),
        dbname=os.getenv("DB_NAME_DEV"),
        user=os.getenv("DB_USER_DEV"),
        password=os.getenv("DB_PASSWORD_DEV"),
    )

def _return_connection(conn):
    with _connection_lock:
        pool = _get_pool()
        pool.putconn(conn)

def execute_query(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
    finally:
        _return_connection(conn)

def execute_query_simple(query, params=None):
    conn = get_connection_simple()
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
        _return_connection(conn)

def execute_query_dataframe_simple(query, params=None):
    conn = get_connection_simple()
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
        _return_connection(conn)

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
    p.cpf,
    sk.protocol AS protocolo
FROM sk_booking sk
JOIN person p ON sk.client_id = p.client_id AND p.person_type_id = 1
JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
WHERE sk.status = 'scheduled'
  AND sk.service_date < CURRENT_DATE
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

QUERY_ESPECIES = """
SELECT DISTINCT especie FROM vw_bi_nao_compareceram_detalhado WHERE especie IS NOT NULL ORDER BY especie
"""

QUERY_RACAS = """
SELECT DISTINCT raca FROM vw_bi_nao_compareceram_detalhado WHERE raca IS NOT NULL ORDER BY raca
"""

QUERY_GENEROS = """
SELECT DISTINCT sexo AS genero FROM vw_bi_nao_compareceram_detalhado WHERE sexo IS NOT NULL ORDER BY sexo
"""

QUERY_MUNICIPIOS = """
SELECT DISTINCT municipio FROM vw_bi_nao_compareceram_detalhado WHERE municipio IS NOT NULL ORDER BY municipio
"""

QUERY_BAIRROS = """
SELECT DISTINCT bairro FROM vw_bi_nao_compareceram_detalhado WHERE bairro IS NOT NULL ORDER BY bairro
"""

QUERY_TELEFONES = """
SELECT DISTINCT telefone FROM vw_bi_nao_compareceram_detalhado WHERE telefone IS NOT NULL ORDER BY telefone
"""

QUERY_CPFS = """
SELECT DISTINCT cpf FROM vw_bi_nao_compareceram_detalhado WHERE cpf IS NOT NULL ORDER BY cpf
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
    try:
        conn = get_connection_simple()
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
    except Exception as e:
        print(f"Error in get_filter_options: {e}")
        return [], [], []

def get_especies():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_ESPECIES)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_especies: {e}")
        return []

def get_racas():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_RACAS)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_racas: {e}")
        return []

def get_generos():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_GENEROS)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_generos: {e}")
        return []

def get_municipios():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_MUNICIPIOS)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_municipios: {e}")
        return []

def get_bairros():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_BAIRROS)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_bairros: {e}")
        return []

def get_telefones():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_TELEFONES)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_telefones: {e}")
        return []

def get_cpfs():
    try:
        conn = get_connection_simple()
        try:
            with conn.cursor() as cur:
                cur.execute(QUERY_CPFS)
                return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_cpfs: {e}")
        return []

def get_data(date_from=None, date_to=None, local=None, servico=None):
    return get_fact_resumo(date_from, date_to, local, servico)

def get_campanhas_ativas(date_from=None, date_to=None, local=None, servico=None):
    return get_vagas_temporal(date_from, date_to, local, servico)

def get_guinnes_atendimentos():
    return pd.DataFrame(columns=['horario', 'total'])

def get_solicitacoes():
    return pd.DataFrame(columns=['id', 'status', 'servico_campanha', 'municipio', 'bairro', 'telefone', 'cpf', 'genero', 'especie'])

def get_check_in_count():
    return 0

def get_nao_comparecimento_count(date_from=None, date_to=None, local=None, servico=None):
    kpis = get_kpis_fact_resumo(date_from, date_to, local, servico)
    return kpis.get('nao_compareceram', 0)

def get_kpis_fact_resumo(date_from=None, date_to=None, local=None, servico=None, weekend_only=False):
    query = """
    SELECT
        COALESCE(SUM(f.total_vagas), 0) AS total_vagas,
        COALESCE(SUM(f.vagas_ocupadas), 0) AS vagas_ocupadas,
        COALESCE(SUM(f.total_vagas), 0) - COALESCE(SUM(f.vagas_ocupadas), 0) AS vagas_livres,
        ROUND(COALESCE(SUM(f.vagas_ocupadas), 0)::numeric / NULLIF(COALESCE(SUM(f.total_vagas), 0), 0) * 100, 1) AS taxa_ocupacao,
        COALESCE(SUM(f.waiting), 0) + COALESCE(SUM(f.calling), 0) AS em_fila,
        COALESCE(SUM(f.waiting), 0) AS waiting,
        COALESCE(SUM(f.calling), 0) AS calling,
        COALESCE(SUM(f.called), 0) AS called,
        COALESCE(SUM(f.nao_compareceram), 0) AS nao_compareceram,
        COALESCE(SUM(f.vagas_scheduled), 0) AS vagas_scheduled,
        COALESCE(SUM(f.vagas_checked_in), 0) AS vagas_checked_in
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
    if weekend_only:
        query += " AND EXTRACT(DOW FROM f.data) IN (0, 6)"

    try:
        df = execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_kpis_fact_resumo, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params) if params else None)

    if df.empty or df.iloc[0]['total_vagas'] is None or df.iloc[0]['taxa_ocupacao'] is None:
        return {
            'total_vagas': 0,
            'vagas_ocupadas': 0,
            'vagas_livres': 0,
            'taxa_ocupacao': 0,
            'em_fila': 0,
            'waiting': 0,
            'calling': 0,
            'called': 0,
            'nao_compareceram': 0,
            'vagas_scheduled': 0,
            'vagas_checked_in': 0
        }

    return {
        'total_vagas': int(df.iloc[0]['total_vagas']),
        'vagas_ocupadas': int(df.iloc[0]['vagas_ocupadas']),
        'vagas_livres': int(df.iloc[0]['vagas_livres']),
        'taxa_ocupacao': round(float(df.iloc[0]['taxa_ocupacao']), 1),
        'em_fila': int(df.iloc[0]['em_fila']),
        'waiting': int(df.iloc[0]['waiting']),
        'calling': int(df.iloc[0]['calling']),
        'called': int(df.iloc[0]['called']),
        'nao_compareceram': int(df.iloc[0]['nao_compareceram']),
        'vagas_scheduled': int(df.iloc[0]['vagas_scheduled']),
        'vagas_checked_in': int(df.iloc[0]['vagas_checked_in'])
    }

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
    query += " ORDER BY f.data DESC, dl.local_servico LIMIT 500"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_fact_resumo, falling back to pool: {e}")
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
    query += " ORDER BY data DESC, local_servico LIMIT 500"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_vagas_temporal, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_campanhas_encerradas():
    """Retorna campanhas encerradas com total de vagas e atendimentos"""
    query = """
    SELECT
        c.id,
        c.name AS campanha,
        c.end_date AS data_encerramento,
        COUNT(b.id) AS total_vagas,
        COUNT(b.status) AS vagas_com_status,
        COUNT(b.pet_id) AS total_atendidas
    FROM sk_campaign c
    LEFT JOIN sk_booking b ON b.id_campaign = c.id
    WHERE c.active = false
    GROUP BY c.id, c.name, c.end_date
    ORDER BY c.end_date DESC
    """
    try:
        return execute_query_dataframe_simple(query, None)
    except Exception as e:
        print(f"Error in get_campanhas_encerradas, falling back to pool: {e}")
        return execute_query_dataframe(query, None)

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
    query += " ORDER BY data DESC, local_servico, departamento LIMIT 500"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_fila_temporal, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_fluxo_departamentos(date_from=None, date_to=None, local=None, servico=None, weekend_only=False):
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
    if weekend_only:
        query += " AND EXTRACT(DOW FROM data) IN (0, 6)"
    query += " ORDER BY data DESC, local_servico, ordem_fluxo, ordem_status LIMIT 500"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_fluxo_departamentos, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_fluxo_historico_departamentos(date_from=None, date_to=None, local=None, servico=None, weekend_only=False):
    """
    Quantas vezes cada status de cada departamento foi de fato atingido, usando o
    LOG de movimentação (log_call_queue_department) — não o snapshot atual da fila.
    Isso importa porque sk_call_queue guarda só o status ATUAL de cada item: quando
    um animal avança de "Recepção" para "Assinatura de Termo", o registro de que ele
    passou pela Recepção desaparece do snapshot (some da fila, não do histórico).
    Sem essa fonte, uma etapa "de passagem" como Recepção aparenta erroneamente 0.
    """
    query = """
    SELECT d.name AS departamento, d.flow_order AS ordem_fluxo,
           cds.name AS status, cds.flow_order AS ordem_status,
           COUNT(*) AS quantidade
    FROM log_call_queue_department lcqd
    JOIN sk_call_queue cq ON lcqd.id_call_queue = cq.id
    JOIN sk_sites_services ss ON cq.id_site_service = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN cfg_service_department_status csds ON lcqd.id_service_department_status = csds.id
    JOIN cfg_departaments_status cds ON csds.id_department_status = cds.id
    JOIN ref_departments d ON cds.id_department = d.id
    WHERE cq.service_date IS NOT NULL
    """
    params = []
    if date_from:
        query += " AND cq.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND cq.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if servico:
        query += " AND svc.service_name = %s"
        params.append(servico)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM cq.service_date) IN (0, 6)"
    query += " GROUP BY d.name, d.flow_order, cds.name, cds.flow_order"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_fluxo_historico_departamentos, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_departamentos_configurados(servico):
    """
    Departamentos cadastrados para o serviço (cfg_service_departments), independente
    de já existir movimentação na fila. Usado para exibir a etapa mesmo com 0 registros
    (ex: "Recepção" configurada mas ainda sem nenhum atendimento no fluxo) em vez de a
    etapa simplesmente desaparecer do card "Etapas de..." por causa do INNER JOIN da view.
    """
    query = """
    SELECT d.id AS department_id, d.name AS departamento, d.flow_order AS ordem_fluxo
    FROM cfg_service_departments sd
    JOIN ref_departments d ON sd.id_department = d.id
    JOIN sk_service svc ON sd.id_service = svc.id
    WHERE svc.service_name = %s
    ORDER BY d.flow_order
    """
    try:
        return execute_query_dataframe_simple(query, (servico,))
    except Exception as e:
        print(f"Error in get_departamentos_configurados, falling back to pool: {e}")
        return execute_query_dataframe(query, (servico,))

def get_nao_compareceram_por_local(date_from=None, date_to=None):
    query = """
    SELECT
        local_servico,
        ano_mes,
        COUNT(*) AS total
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
    query += " GROUP BY local_servico, ano_mes ORDER BY local_servico, ano_mes LIMIT 100"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_nao_compareceram_por_local, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

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
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_nao_compareceram_detalhado, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_dim_local():
    try:
        return execute_query_dataframe_simple("SELECT * FROM vw_bi_dim_local WHERE active = true ORDER BY local_servico LIMIT 1000")
    except Exception as e:
        print(f"Error in get_dim_local, falling back to pool: {e}")
        return execute_query_dataframe("SELECT * FROM vw_bi_dim_local WHERE active = true ORDER BY local_servico LIMIT 1000")

def get_dim_date(date_from=None, date_to=None):
    query = "SELECT * FROM vw_bi_dim_date WHERE 1=1"
    params = []
    if date_from:
        query += " AND data >= %s"
        params.append(date_from)
    if date_to:
        query += " AND data <= %s"
        params.append(date_to)
    query += " ORDER BY data DESC LIMIT 1000"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_dim_date, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

def get_atendimentos_por_hora(date_from=None, date_to=None):
    try:
        return execute_query_dataframe_simple("SELECT * FROM vw_bi_atendimentos_por_hora ORDER BY hora")
    except Exception as e:
        print(f"Error in get_atendimentos_por_hora, falling back to pool: {e}")
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
    query += " ORDER BY data DESC, local_servico LIMIT 500"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_tempo_medio, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)

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


# ─── Tela "Dashboard" (redesign estilo SEMMA) ──────────────────────────────

def get_totais_acumulados(local=None):
    """Vagas ocupadas acumuladas por serviço, sem filtro de período (para os widgets do hero)."""
    query = """
    SELECT dl.servico, COALESCE(SUM(f.vagas_ocupadas), 0) AS total_ocupadas
    FROM vw_bi_fact_resumo f
    JOIN vw_bi_dim_local dl ON f.site_service_id = dl.site_service_id
    WHERE 1=1
    """
    params = []
    if local:
        query += " AND dl.local_servico = %s"
        params.append(local)
    query += " GROUP BY dl.servico"
    try:
        df = execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_totais_acumulados, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params) if params else None)

    result = {'Castração': 0, 'Vacinação': 0}
    for _, row in df.iterrows():
        if row['servico'] in result:
            result[row['servico']] = int(row['total_ocupadas'])
    return result


def get_atendimentos_por_mes(date_from=None, date_to=None, local=None, weekend_only=False):
    """Vagas ocupadas por mês/serviço, para o gráfico 'Volume do período'."""
    query = """
    SELECT
        TO_CHAR(f.data, 'YYYY-MM') AS ano_mes,
        dl.servico,
        COALESCE(SUM(f.vagas_ocupadas), 0) AS total_ocupadas
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
    if weekend_only:
        query += " AND EXTRACT(DOW FROM f.data) IN (0, 6)"
    query += " GROUP BY TO_CHAR(f.data, 'YYYY-MM'), dl.servico ORDER BY 1"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_atendimentos_por_mes, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)


def get_especies_vacinacao(date_from=None, date_to=None, local=None, weekend_only=False):
    """Quebra Canino/Felino das doses de vacinação aplicadas (só cobre agendamentos com pet_id vinculado)."""
    query = """
    SELECT
        CASE b.id_specie WHEN 1 THEN 'Canino' WHEN 2 THEN 'Felino' ELSE 'Outro' END AS especie,
        COUNT(*) AS total
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN pet p ON sk.pet_id = p.id
    JOIN breed b ON p.breed_id = b.id
    WHERE svc.service_name = 'Vacinação'
      AND sk.status IS NOT NULL
    """
    params = []
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    query += " GROUP BY b.id_specie"
    try:
        df = execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_especies_vacinacao, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params) if params else None)

    result = {'Canino': 0, 'Felino': 0}
    for _, row in df.iterrows():
        if row['especie'] in result:
            result[row['especie']] = int(row['total'])
    return result


# ─── Tela de detalhe: Vacinação ──────────────────────────────────────────
# Só o que existe de verdade no sistema: agendamento (sk_booking.status
# 'scheduled'/'checked_in'), pet.gender, breed.id_specie e o catálogo real
# de vacinas aplicadas (trx_vaccine_application). Nada aqui é inventado —
# onde o design do cliente pedia uma categoria que não existe no banco
# (ex: "recusada pelo tutor"), a tela usa só as categorias reais.

def get_locais_atendidos(date_from=None, date_to=None, local=None, weekend_only=False, servico='Vacinação'):
    """Quantidade de locais (sites) distintos com pelo menos 1 agendamento no período."""
    query = """
    SELECT COUNT(DISTINCT s.id) AS locais_atendidos
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN sk_sites s ON ss.id_site = s.id
    WHERE svc.service_name = %s
      AND sk.status IS NOT NULL
    """
    params = [servico]
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    try:
        df = execute_query_dataframe_simple(query, tuple(params))
    except Exception as e:
        print(f"Error in get_locais_atendidos, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params))
    if df.empty or df.iloc[0]['locais_atendidos'] is None:
        return 0
    return int(df.iloc[0]['locais_atendidos'])


def get_desfechos_agendamento(date_from=None, date_to=None, local=None, weekend_only=False, servico='Vacinação'):
    """
    Desfecho real do agendamento: só existem 2 estados no sistema
    (scheduled = agendado, checked_in = compareceu). Categorias como
    "recusada"/"contraindicada" do mockup genérico não são rastreadas aqui.
    """
    query = """
    SELECT sk.status, COUNT(*) AS total
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    WHERE svc.service_name = %s
      AND sk.status IS NOT NULL
    """
    params = [servico]
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    query += " GROUP BY sk.status"
    try:
        df = execute_query_dataframe_simple(query, tuple(params))
    except Exception as e:
        print(f"Error in get_desfechos_agendamento, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params))

    result = {'checked_in': 0, 'scheduled': 0}
    for _, row in df.iterrows():
        if row['status'] in result:
            result[row['status']] = int(row['total'])
    return result


def get_perfil_animais(date_from=None, date_to=None, local=None, weekend_only=False, servico='Vacinação'):
    """Quebra Fêmeas/Machos por espécie (Canino/Felino) — pet.gender + breed.id_specie."""
    query = """
    SELECT
        CASE b.id_specie WHEN 1 THEN 'Canino' WHEN 2 THEN 'Felino' ELSE 'Outro' END AS especie,
        p.gender AS sexo,
        COUNT(*) AS total
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN pet p ON sk.pet_id = p.id
    JOIN breed b ON p.breed_id = b.id
    WHERE svc.service_name = %s
      AND sk.status IS NOT NULL
      AND p.gender IN ('F', 'M')
    """
    params = [servico]
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    query += " GROUP BY especie, p.gender"
    try:
        return execute_query_dataframe_simple(query, tuple(params))
    except Exception as e:
        print(f"Error in get_perfil_animais, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params))


def get_composicao_doses(date_from=None, date_to=None, local=None, weekend_only=False):
    """Doses aplicadas por tipo de vacina (trx_vaccine_application -> master_vaccine -> ref_vaccine_type)."""
    query = """
    SELECT COALESCE(rvt.name, 'Não classificado') AS tipo_vacina, COUNT(*) AS total
    FROM trx_vaccine_application tva
    LEFT JOIN master_vaccine mv ON tva.id_vaccine = mv.id
    LEFT JOIN ref_vaccine_type rvt ON mv.id_vaccine_type = rvt.id
    LEFT JOIN sk_booking bk ON tva.booking_id = bk.id
    LEFT JOIN sk_sites_services ss ON bk.id_site_sevice = ss.id
    LEFT JOIN sk_sites s ON ss.id_site = s.id
    WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND tva.application_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND tva.application_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM tva.application_date) IN (0, 6)"
    query += " GROUP BY rvt.name ORDER BY total DESC"
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_composicao_doses, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)


def get_distribuicao_territorial(date_from=None, date_to=None, local=None, weekend_only=False, servico='Vacinação'):
    """Agendamentos por local (site) — usado para o Top 5 + 'Outros' da Distribuição territorial."""
    query = """
    SELECT s.site_name AS local_nome, COUNT(*) AS total
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN sk_sites s ON ss.id_site = s.id
    WHERE svc.service_name = %s
      AND sk.status IS NOT NULL
    """
    params = [servico]
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    query += " GROUP BY s.site_name ORDER BY total DESC"
    try:
        return execute_query_dataframe_simple(query, tuple(params))
    except Exception as e:
        print(f"Error in get_distribuicao_territorial, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params))


# ─── Filtro avançado: Espécie ───────────────────────────────────────────────
# A view vw_bi_fact_resumo é agregada por (data, site_service) e não guarda o
# pet — não dá pra filtrar por espécie a partir dela. Por isso os números
# "por espécie" são recalculados aqui direto de sk_booking/sk_call_queue com
# join em pet/breed (mesmo padrão já usado em get_especies_vacinacao/
# get_perfil_animais). "Total de vagas"/"vagas livres"/"taxa de ocupação" não
# têm um recorte por espécie que faça sentido (a vaga em si não é de um
# animal até ser ocupada), por isso não entram aqui.
def get_kpis_por_especie(date_from=None, date_to=None, local=None, servico=None, weekend_only=False, especie_id=None):
    query = """
    SELECT
        COUNT(*) FILTER (WHERE sk.status IS NOT NULL) AS vagas_ocupadas,
        COUNT(*) FILTER (WHERE sk.status = 'scheduled') AS vagas_scheduled,
        COUNT(*) FILTER (WHERE sk.status = 'checked_in') AS vagas_checked_in
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN pet p ON sk.pet_id = p.id
    JOIN breed b ON p.breed_id = b.id
    WHERE 1=1
    """
    params = []
    if especie_id:
        query += " AND b.id_specie = %s"
        params.append(especie_id)
    if date_from:
        query += " AND sk.service_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sk.service_date <= %s"
        params.append(date_to)
    if local:
        query += " AND ss.name = %s"
        params.append(local)
    if servico:
        query += " AND svc.service_name = %s"
        params.append(servico)
    if weekend_only:
        query += " AND EXTRACT(DOW FROM sk.service_date) IN (0, 6)"
    try:
        df = execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_kpis_por_especie, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params) if params else None)

    if df.empty or df.iloc[0]['vagas_ocupadas'] is None:
        return {'vagas_ocupadas': 0, 'vagas_scheduled': 0, 'vagas_checked_in': 0, 'em_fila': 0}

    query_fila = """
    SELECT COUNT(*) AS em_fila
    FROM sk_call_queue cq
    JOIN sk_sites_services ss ON cq.id_site_service = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    JOIN pet p ON cq.id_pet = p.id
    JOIN breed b ON p.breed_id = b.id
    WHERE cq.status IN ('waiting', 'calling')
    """
    params_fila = []
    if especie_id:
        query_fila += " AND b.id_specie = %s"
        params_fila.append(especie_id)
    if date_from:
        query_fila += " AND cq.service_date >= %s"
        params_fila.append(date_from)
    if date_to:
        query_fila += " AND cq.service_date <= %s"
        params_fila.append(date_to)
    if local:
        query_fila += " AND ss.name = %s"
        params_fila.append(local)
    if servico:
        query_fila += " AND svc.service_name = %s"
        params_fila.append(servico)
    if weekend_only:
        query_fila += " AND EXTRACT(DOW FROM cq.service_date) IN (0, 6)"
    try:
        df_fila = execute_query_dataframe_simple(query_fila, tuple(params_fila) if params_fila else None)
    except Exception as e:
        print(f"Error in get_kpis_por_especie (fila), falling back to pool: {e}")
        df_fila = execute_query_dataframe(query_fila, tuple(params_fila) if params_fila else None)
    em_fila = int(df_fila.iloc[0]['em_fila']) if not df_fila.empty and df_fila.iloc[0]['em_fila'] is not None else 0

    return {
        'vagas_ocupadas': int(df.iloc[0]['vagas_ocupadas']),
        'vagas_scheduled': int(df.iloc[0]['vagas_scheduled']),
        'vagas_checked_in': int(df.iloc[0]['vagas_checked_in']),
        'em_fila': em_fila,
    }


# ─── Histórico (registros passados, fora do sistema) ───────────────────────
# bea_external_records reúne 3 origens importadas de fora do sistema
# (Castramóvel, Clínica PetGold, Programa Bem-Estar Animal) — todas só com
# atendimentos de castração, sem vacinação nem microchip registrados aqui.
# Por isso "vacinados" e "com microchip" só existem cruzando o CPF do tutor
# com o cadastro do sistema (person/pet/trx_vaccine_application).
def _historico_date_filter(date_from, date_to, weekend_only, params):
    """Mesmo padrão de filtro de data/fim-de-semana usado no resto do db.py,
    aplicado em cima de service_date (única data real dessa tabela)."""
    clause = ""
    if date_from:
        clause += " AND service_date >= %s"
        params.append(date_from)
    if date_to:
        clause += " AND service_date <= %s"
        params.append(date_to)
    if weekend_only:
        clause += " AND EXTRACT(DOW FROM service_date) IN (0, 6)"
    return clause


def get_historico_resumo(date_from=None, date_to=None, weekend_only=False):
    """Contagem rápida (só na própria tabela, sem cruzamento) para o card de
    entrada do panorama — não paga o custo do cruzamento com o sistema."""
    params = []
    query = """
    SELECT
        COUNT(*) AS total_registros,
        COUNT(DISTINCT cpf) AS total_tutores,
        COUNT(DISTINCT (cpf, pet_name)) AS total_pets
    FROM bea_external_records
    WHERE 1=1
    """
    query += _historico_date_filter(date_from, date_to, weekend_only, params)
    try:
        df = execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_historico_resumo, falling back to pool: {e}")
        df = execute_query_dataframe(query, tuple(params) if params else None)

    if df.empty:
        return {'total_registros': 0, 'total_tutores': 0, 'total_pets': 0}
    row = df.iloc[0]
    return {
        'total_registros': int(row['total_registros']),
        'total_tutores': int(row['total_tutores']),
        'total_pets': int(row['total_pets']),
    }


def get_historico_tutores(date_from=None, date_to=None, weekend_only=False):
    """Uma linha por tutor (CPF) do histórico (Castramóvel + Clínica PetGold +
    Programa Bem-Estar Animal), com a quantidade de pets/castrações levados
    e, para quem já existe cadastrado no sistema (cruzamento por CPF),
    quantos desses pets têm vacinação aplicada e quantos têm microchip."""
    params = []
    date_filter = _historico_date_filter(date_from, date_to, weekend_only, params)
    query = f"""
    WITH historico AS (
        SELECT
            regexp_replace(cpf, '\\D', '', 'g') AS cpf_clean,
            cpf, owner_name, phone, address, pet_name
        FROM bea_external_records
        WHERE 1=1 {date_filter}
    ),
    tutores AS (
        SELECT
            cpf_clean,
            MIN(cpf) AS cpf,
            MIN(owner_name) AS tutor,
            MIN(phone) AS telefone,
            MIN(address) AS endereco,
            COUNT(DISTINCT pet_name) AS qtd_pets,
            COUNT(*) AS qtd_castracoes
        FROM historico
        GROUP BY cpf_clean
    ),
    match_person AS (
        SELECT DISTINCT ON (regexp_replace(cpf, '\\D', '', 'g'))
            regexp_replace(cpf, '\\D', '', 'g') AS cpf_clean,
            person_id
        FROM person
        WHERE cpf IS NOT NULL
    ),
    agg_pets AS (
        SELECT
            mp.cpf_clean,
            COUNT(DISTINCT pt.id) FILTER (
                WHERE pt.chip_code IS NOT NULL AND btrim(pt.chip_code) <> ''
            ) AS pets_com_chip,
            COUNT(DISTINCT v.pet_id) AS pets_vacinados
        FROM match_person mp
        JOIN pet pt ON pt.tutor_id = mp.person_id
        LEFT JOIN trx_vaccine_application v ON v.pet_id = pt.id
        GROUP BY mp.cpf_clean
    )
    SELECT
        t.cpf, t.tutor, t.telefone, t.endereco, t.qtd_pets, t.qtd_castracoes,
        (mp.cpf_clean IS NOT NULL) AS cadastrado_sistema,
        COALESCE(ap.pets_vacinados, 0) AS pets_vacinados,
        COALESCE(ap.pets_com_chip, 0) AS pets_com_chip
    FROM tutores t
    LEFT JOIN match_person mp ON mp.cpf_clean = t.cpf_clean
    LEFT JOIN agg_pets ap ON ap.cpf_clean = t.cpf_clean
    ORDER BY t.tutor
    """
    try:
        return execute_query_dataframe_simple(query, tuple(params) if params else None)
    except Exception as e:
        print(f"Error in get_historico_tutores, falling back to pool: {e}")
        return execute_query_dataframe(query, tuple(params) if params else None)