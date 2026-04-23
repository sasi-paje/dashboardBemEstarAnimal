-- Views BI para Dashboard - Análise Completa
-- Base: sk_booking, sk_call_queue, JSONBs

-- ============================================
-- VW_BI_VAGAS_TEMPORAL
-- Vagas por dia/local/serviço com evolução temporal
-- ============================================
DROP VIEW IF EXISTS vw_bi_vagas_temporal CASCADE;

CREATE VIEW vw_bi_vagas_temporal AS
SELECT
    sk.service_date AS data,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.service_name AS servico,
    COUNT(*) AS total_vagas,
    COUNT(*) FILTER (WHERE sk.status = 'scheduled') AS vagas_scheduled,
    COUNT(*) FILTER (WHERE sk.status = 'checked_in') AS vagas_checked_in,
    COUNT(*) FILTER (WHERE sk.status IS NULL) AS vagas_nao_confirmadas,
    COUNT(*) FILTER (WHERE sk.status IS NOT NULL) AS vagas_ocupadas,
    COUNT(*) FILTER (WHERE sk.status IS NULL) AS vagas_livres
FROM sk_booking sk
JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
WHERE sk.service_date IS NOT NULL
GROUP BY sk.service_date, ss.id, ss.name, svc.service_name
ORDER BY sk.service_date DESC, ss.name;

-- ============================================
-- VW_BI_FILA_TEMPORAL
-- Estado da fila em tempo real por dia/local/status
-- ============================================
DROP VIEW IF EXISTS vw_bi_fila_temporal CASCADE;

CREATE VIEW vw_bi_fila_temporal AS
SELECT
    cq.service_date AS data,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.service_name AS servico,
    cq.status::text AS status_fila,
    ds.name AS status_departamento,
    d.name AS departamento,
    COUNT(*) AS quantidade
FROM sk_call_queue cq
JOIN sk_sites_services ss ON cq.id_site_service = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
LEFT JOIN cfg_service_department_status cds ON cq.id_service_department_status = cds.id
LEFT JOIN cfg_departaments_status ds ON cds.id_department_status = ds.id
LEFT JOIN ref_departments d ON ds.id_department = d.id
WHERE cq.service_date IS NOT NULL
GROUP BY cq.service_date, ss.id, ss.name, svc.service_name, cq.status, ds.name, d.name
ORDER BY cq.service_date DESC, ss.name, d.name;

-- ============================================
-- VW_BI_TEMPO_MEDIO_ATENDIMENTO
-- Tempo médio de espera e atendimento
-- ============================================
DROP VIEW IF EXISTS vw_bi_tempo_medio CASCADE;

CREATE VIEW vw_bi_tempo_medio AS
WITH call_data AS (
    SELECT
        cq.service_date AS data,
        ss.id AS site_service_id,
        ss.name AS local_servico,
        svc.service_name AS servico,
        cq.call_time,
        cq.attended_time,
        cq.call_count,
        cq.board_count,
        cq.status::text,
        CASE
            WHEN cq.attended_time IS NOT NULL AND cq.call_time IS NOT NULL
            THEN EXTRACT(EPOCH FROM (cq.attended_time - cq.call_time)) / 60
            ELSE NULL
        END AS tempo_espera_minutos
    FROM sk_call_queue cq
    JOIN sk_sites_services ss ON cq.id_site_service = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    WHERE cq.call_time IS NOT NULL
)
SELECT
    data,
    site_service_id,
    local_servico,
    servico,
    status,
    COUNT(*) FILTER (WHERE tempo_espera_minutos IS NOT NULL) AS total_chamados_com_tempo,
    AVG(tempo_espera_minutos) FILTER (WHERE tempo_espera_minutos IS NOT NULL) AS tempo_medio_espera_minutos,
    MAX(tempo_espera_minutos) FILTER (WHERE tempo_espera_minutos IS NOT NULL) AS tempo_max_espera_minutos,
    MIN(tempo_espera_minutos) FILTER (WHERE tempo_espera_minutos IS NOT NULL) AS tempo_min_espera_minutos,
    AVG(call_count) AS avg_call_count,
    AVG(board_count) AS avg_board_count
FROM call_data
GROUP BY data, site_service_id, local_servico, servico, status
ORDER BY data DESC, local_servico;

-- ============================================
-- VW_BI_HISTORICO_DEPARTAMENTO
-- Expande o JSONB call_queue_department_history em linhas
-- ============================================
DROP VIEW IF EXISTS vw_bi_historico_departamento CASCADE;

CREATE VIEW vw_bi_historico_departamento AS
SELECT
    cq.id AS queue_id,
    cq.service_date AS data,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.service_name AS servico,
    hist->>'moved_at' AS data_movimentacao,
    (hist->>'old_department_code')::text AS department_code,
    (hist->>'old_department_name')::text AS department_name,
    (hist->>'old_queue_status')::text AS status_anterior,
    (hist->>'old_department_status_name')::text AS status_departamento_anterior,
    (hist->>'old_call_time')::time AS hora_chamada_anterior,
    (hist->>'old_attended_time')::time AS hora_atendimento_anterior,
    (hist->>'old_call_count')::int AS call_count_anterior,
    (hist->>'old_board_count')::int AS board_count_anterior,
    (hist->>'old_is_priority')::boolean AS era_prioridade,
    (hist->>'old_result_type')::text AS result_type_anterior,
    (hist->>'old_id_attendant')::bigint AS attendant_id_anterior
FROM sk_call_queue cq
JOIN sk_sites_services ss ON cq.id_site_service = ss.id
JOIN sk_service svc ON ss.id_service = svc.id,
    jsonb_array_elements(cq.details->'call_queue_department_history') AS hist
WHERE cq.details IS NOT NULL
  AND cq.details->'call_queue_department_history' IS NOT NULL
ORDER BY cq.service_date DESC, cq.id, (hist->>'moved_at')::timestamp;

-- ============================================
-- VW_BI_NAO_COMPARECERAM_DETALHADO
-- Não-comparecimentos com detalhes completos
-- ============================================
DROP VIEW IF EXISTS vw_bi_nao_compareceram_detalhado CASCADE;

CREATE VIEW vw_bi_nao_compareceram_detalhado AS
SELECT DISTINCT ON (sk.id)
    sk.service_date AS data_agendamento,
    TO_CHAR(sk.service_date, 'YYYY-MM') AS ano_mes,
    TO_CHAR(sk.service_date, 'Day') AS dia_semana,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.service_name AS servico,
    sk.id AS booking_id,
    sk.init_interval_hour AS hora_vaga,
    p.person_id AS tutor_id,
    p.name AS nome_tutor,
    p.cpf,
    p.phone AS telefone,
    (sk.details->>'pet_id')::text::integer AS pet_id,
    pet.name AS nome_animal,
    pet.size AS porte,
    pet.gender AS sexo,
    br.breed AS raca,
    CASE
        WHEN (sk.details->>'priority') = 'true' THEN 'Sim'
        ELSE 'Não'
    END AS era_prioridade,
    (sk.details->>'priority_type')::text::integer AS priority_type,
    sk.createdat AS data_criacao_agendamento
FROM sk_booking sk
JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
JOIN person p ON sk.client_id = p.client_id
LEFT JOIN pet ON (sk.details->>'pet_id')::text::integer = pet.id
LEFT JOIN breed br ON pet.breed_id = br.id
WHERE sk.status IS NULL
  AND sk.service_date IS NOT NULL
ORDER BY sk.id;

-- ============================================
-- VW_BI_RESUMO_EXECUTIVO
-- Resumo executivo combinando todos os KPIs
-- ============================================
DROP VIEW IF EXISTS vw_bi_resumo_executivo CASCADE;

CREATE VIEW vw_bi_resumo_executivo AS
WITH vagas AS (
    SELECT
        service_date,
        COUNT(*) AS total_vagas,
        COUNT(*) FILTER (WHERE status IS NOT NULL) AS vagas_ocupadas,
        COUNT(*) FILTER (WHERE status IS NULL) AS nao_confirmados
    FROM sk_booking
    WHERE service_date IS NOT NULL
    GROUP BY service_date
),
fila AS (
    SELECT
        service_date,
        COUNT(*) AS em_fila,
        COUNT(*) FILTER (WHERE status = 'waiting') AS waiting,
        COUNT(*) FILTER (WHERE status = 'calling') AS calling,
        COUNT(*) FILTER (WHERE status = 'called') AS called
    FROM sk_call_queue
    WHERE service_date IS NOT NULL
    GROUP BY service_date
),
nao_compareceram AS (
    SELECT
        service_date,
        COUNT(*) AS total_nao_compareceram
    FROM sk_booking
    WHERE status IS NULL AND service_date IS NOT NULL
    GROUP BY service_date
)
SELECT
    COALESCE(v.service_date, COALESCE(f.service_date, nc.service_date)) AS data,
    COALESCE(v.total_vagas, 0) AS total_vagas,
    COALESCE(v.vagas_ocupadas, 0) AS vagas_ocupadas,
    COALESCE(v.nao_confirmados, 0) AS nao_confirmados,
    COALESCE(f.em_fila, 0) AS em_fila,
    COALESCE(f.waiting, 0) AS waiting,
    COALESCE(f.calling, 0) AS calling,
    COALESCE(f.called, 0) AS called,
    COALESCE(nc.total_nao_compareceram, 0) AS nao_compareceram,
    CASE WHEN COALESCE(v.total_vagas, 0) > 0
         THEN ROUND(COALESCE(v.vagas_ocupadas, 0)::numeric / v.total_vagas * 100, 1)
         ELSE 0
    END AS taxa_ocupacao_pct
FROM vagas v
FULL OUTER JOIN fila f ON v.service_date = f.service_date
FULL OUTER JOIN nao_compareceram nc ON COALESCE(v.service_date, f.service_date) = nc.service_date
ORDER BY data DESC;

-- ============================================
-- VW_BI_FLUXO_DEPARTAMENTOS
-- Análise do fluxo por departamento
-- ============================================
DROP VIEW IF EXISTS vw_bi_fluxo_departamentos CASCADE;

CREATE VIEW vw_bi_fluxo_departamentos AS
SELECT
    cq.service_date AS data,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.service_name AS servico,
    d.id AS department_id,
    d.name AS departamento,
    d.flow_order AS ordem_fluxo,
    ds.id AS status_id,
    ds.name AS status,
    ds.flow_order AS ordem_status,
    ds.is_initial,
    ds.is_final,
    ds.is_cancelled,
    COUNT(*) AS quantidade,
    COUNT(*) FILTER (WHERE cq.status = 'waiting') AS qtd_waiting,
    COUNT(*) FILTER (WHERE cq.status = 'calling') AS qtd_calling,
    COUNT(*) FILTER (WHERE cq.status = 'called') AS qtd_called,
    COUNT(*) FILTER (WHERE cq.status = 'cancelled') AS qtd_cancelled
FROM sk_call_queue cq
JOIN sk_sites_services ss ON cq.id_site_service = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
JOIN cfg_service_department_status cds ON cq.id_service_department_status = cds.id
JOIN cfg_service_departments sd ON cds.id_service_department = sd.id
JOIN ref_departments d ON sd.id_department = d.id
JOIN cfg_departaments_status ds ON cds.id_department_status = ds.id
WHERE cq.service_date IS NOT NULL
GROUP BY cq.service_date, ss.id, ss.name, svc.service_name, d.id, d.name, d.flow_order,
         ds.id, ds.name, ds.flow_order, ds.is_initial, ds.is_final, ds.is_cancelled
ORDER BY cq.service_date DESC, ss.name, d.flow_order, ds.flow_order;

-- ============================================
-- VW_BI_ATENDIMENTOS_POR_HORA
-- Distribuição de atendimentos por hora do dia
-- ============================================
DROP VIEW IF EXISTS vw_bi_atendimentos_por_hora CASCADE;

CREATE VIEW vw_bi_atendimentos_por_hora AS
SELECT
    EXTRACT(HOUR FROM cq.call_time) AS hora,
    COUNT(*) AS total_chamados,
    COUNT(*) FILTER (WHERE cq.status = 'called') AS chamados_atendidos,
    COUNT(*) FILTER (WHERE cq.status = 'cancelled') AS chamados_cancelados,
    AVG(EXTRACT(EPOCH FROM (cq.attended_time - cq.call_time)) / 60)
        FILTER (WHERE cq.attended_time IS NOT NULL AND cq.call_time IS NOT NULL)
        AS tempo_medio_minutos
FROM sk_call_queue cq
WHERE cq.call_time IS NOT NULL
GROUP BY EXTRACT(HOUR FROM cq.call_time)
ORDER BY hora;

-- ============================================
-- VW_BI_PRIORIDADE_ANALISE
-- Análise de chamadas prioritárias vs normais
-- ============================================
DROP VIEW IF EXISTS vw_bi_prioridade_analise CASCADE;

CREATE VIEW vw_bi_prioridade_analise AS
SELECT
    cq.service_date AS data,
    ss.name AS local_servico,
    svc.service_name AS servico,
    cq.is_priority AS eh_prioridade,
    COUNT(*) AS total_chamados,
    COUNT(*) FILTER (WHERE cq.status = 'called') AS atendidos,
    COUNT(*) FILTER (WHERE cq.status = 'cancelled') AS cancelados,
    AVG(cq.call_count) AS avg_chamadas_por_atendimento,
    AVG(EXTRACT(EPOCH FROM (cq.attended_time - cq.call_time)) / 60)
        FILTER (WHERE cq.attended_time IS NOT NULL)
        AS tempo_medio_espera_minutos
FROM sk_call_queue cq
JOIN sk_sites_services ss ON cq.id_site_service = ss.id
JOIN sk_service svc ON ss.id_service = svc.id
WHERE cq.service_date IS NOT NULL
GROUP BY cq.service_date, ss.name, svc.service_name, cq.is_priority
ORDER BY cq.service_date DESC, ss.name;
-- ============================================
-- DIM_DATE (Dimensão Tempo)
-- Lookup de datas para JOINs
-- ============================================
DROP VIEW IF EXISTS vw_bi_dim_date CASCADE;

CREATE VIEW vw_bi_dim_date AS
SELECT 
    DISTINCT service_date AS data,
    EXTRACT(YEAR FROM service_date) AS ano,
    EXTRACT(MONTH FROM service_date) AS mes,
    TO_CHAR(service_date, 'YYYY-MM') AS ano_mes,
    TO_CHAR(service_date, 'Month') AS nome_mes,
    EXTRACT(DAY FROM service_date) AS dia,
    TO_CHAR(service_date, 'Day') AS dia_semana,
    EXTRACT(DOW FROM service_date) AS dia_semana_num,
    EXTRACT(WEEK FROM service_date) AS semana_ano,
    CASE WHEN EXTRACT(DOW FROM service_date) IN (0, 6) THEN true ELSE false END AS fim_de_semana
FROM sk_booking
WHERE service_date IS NOT NULL
ORDER BY service_date DESC;

-- ============================================
-- DIM_LOCAL (Dimensão Local/Serviço)
-- Lookup de locais e serviços para JOINs
-- ============================================
DROP VIEW IF EXISTS vw_bi_dim_local CASCADE;

CREATE VIEW vw_bi_dim_local AS
SELECT DISTINCT
    ss.id AS site_service_id,
    ss.name AS local_servico,
    svc.id AS service_id,
    svc.service_name AS servico,
    ss.active,
    ss.init_time,
    ss.end_time,
    ss.available_resource_total
FROM sk_sites_services ss
JOIN sk_service svc ON ss.id_service = svc.id
ORDER BY ss.name;

-- ============================================
-- FACT_RESUMO (Tabela Fato Principal)
-- Unifica vagas, fila e não-comparecimentos por data + site_service_id
-- Útil para filtros do dashboard
-- ============================================
DROP VIEW IF EXISTS vw_bi_fact_resumo CASCADE;

CREATE VIEW vw_bi_fact_resumo AS
WITH bookings AS (
    SELECT 
        service_date,
        id_site_sevice,
        status,
        createdat
    FROM sk_booking
    WHERE service_date IS NOT NULL
),
vagas_agg AS (
    SELECT 
        service_date,
        id_site_sevice,
        COUNT(*) AS total_vagas,
        COUNT(*) FILTER (WHERE status = 'scheduled') AS vagas_scheduled,
        COUNT(*) FILTER (WHERE status = 'checked_in') AS vagas_checked_in,
        COUNT(*) FILTER (WHERE status IS NULL) AS vagas_nao_confirmadas,
        COUNT(*) FILTER (WHERE status IS NOT NULL) AS vagas_ocupadas
    FROM bookings
    GROUP BY service_date, id_site_sevice
),
fila_agg AS (
    SELECT 
        service_date,
        id_site_service,
        COUNT(*) AS em_fila,
        COUNT(*) FILTER (WHERE status = 'waiting') AS waiting,
        COUNT(*) FILTER (WHERE status = 'calling') AS calling,
        COUNT(*) FILTER (WHERE status = 'called') AS called,
        COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled
    FROM sk_call_queue
    WHERE service_date IS NOT NULL
    GROUP BY service_date, id_site_service
),
nao_comp_agg AS (
    SELECT 
        service_date,
        id_site_sevice,
        COUNT(*) AS nao_compareceram
    FROM sk_booking
    WHERE status IS NULL AND service_date IS NOT NULL
    GROUP BY service_date, id_site_sevice
)
SELECT 
    COALESCE(v.service_date, COALESCE(f.service_date, n.service_date)) AS data,
    COALESCE(v.id_site_sevice, COALESCE(f.id_site_service, n.id_site_sevice)) AS site_service_id,
    COALESCE(v.total_vagas, 0) AS total_vagas,
    COALESCE(v.vagas_scheduled, 0) AS vagas_scheduled,
    COALESCE(v.vagas_checked_in, 0) AS vagas_checked_in,
    COALESCE(v.vagas_nao_confirmadas, 0) AS vagas_nao_confirmadas,
    COALESCE(v.vagas_ocupadas, 0) AS vagas_ocupadas,
    COALESCE(f.em_fila, 0) AS em_fila,
    COALESCE(f.waiting, 0) AS waiting,
    COALESCE(f.calling, 0) AS calling,
    COALESCE(f.called, 0) AS called,
    COALESCE(f.cancelled, 0) AS cancelled,
    COALESCE(n.nao_compareceram, 0) AS nao_compareceram,
    CASE WHEN COALESCE(v.total_vagas, 0) > 0 
         THEN ROUND(COALESCE(v.vagas_ocupadas, 0)::numeric / v.total_vagas * 100, 1)
         ELSE 0
    END AS taxa_ocupacao_pct
FROM vagas_agg v
FULL OUTER JOIN fila_agg f ON v.service_date = f.service_date AND v.id_site_sevice = f.id_site_service
FULL OUTER JOIN nao_comp_agg n ON COALESCE(v.service_date, f.service_date) = n.service_date 
    AND COALESCE(v.id_site_sevice, f.id_site_service) = n.id_site_sevice
ORDER BY data DESC, site_service_id;
