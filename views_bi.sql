-- Views BI com site_service_id para JOINs

-- ============================================
-- VW_BI_COUNTS_VAGAS
-- ============================================
DROP VIEW IF EXISTS vw_bi_counts_vagas CASCADE;

CREATE VIEW vw_bi_counts_vagas AS
WITH vagas_por_site AS (
    SELECT
        ss.id AS site_service_id,
        ss.name AS local_servico,
        svc.service_name AS servico,
        COUNT(*) AS total_vagas,
        COUNT(*) FILTER (WHERE sk.status IS NOT NULL) AS vagas_ocupadas,
        COUNT(*) FILTER (WHERE sk.status IS NULL) AS vagas_livres
    FROM sk_booking sk
    JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
    JOIN sk_service svc ON ss.id_service = svc.id
    GROUP BY ss.id, ss.name, svc.service_name
),
departamentos AS (
    SELECT DISTINCT
        ss.id AS site_service_id,
        d.id AS department_id,
        d.name AS department
    FROM sk_sites_services ss
    CROSS JOIN cfg_service_departments sd
    CROSS JOIN ref_departments d
    CROSS JOIN sk_service svc
    WHERE sd.id_department = d.id
        AND sd.id_service = svc.id
)
SELECT
    v.site_service_id,
    v.local_servico,
    v.servico,
    d.department,
    v.total_vagas,
    v.vagas_ocupadas,
    v.vagas_livres
FROM vagas_por_site v
JOIN departamentos d ON v.site_service_id = d.site_service_id
ORDER BY v.local_servico, v.servico, d.department;

-- ============================================
-- VW_BI_DETAILS_NAO_COMPARECERAO
-- ============================================
DROP VIEW IF EXISTS vw_bi_details_nao_comparecerao CASCADE;

CREATE VIEW vw_bi_details_nao_comparecerao AS
SELECT DISTINCT ON (sk.id)
    sk.id AS booking_id,
    sk.service_date AS data_agendamento,
    sk.init_interval_hour AS hora_agendamento,
    ss.id AS site_service_id,
    ss.name AS local_servico,
    p.person_id AS pessoa_id,
    p.name AS nome,
    p.cpf,
    sk.details->>'pet_id' AS pet_id,
    pt.name AS animal
FROM sk_booking sk
JOIN person p ON sk.client_id = p.client_id AND p.person_type_id = 1
JOIN sk_sites_services ss ON sk.id_site_sevice = ss.id
LEFT JOIN pet pt ON sk.details->>'pet_id' = pt.id::text
WHERE sk.status IS NULL
ORDER BY sk.id, sk.service_date DESC, sk.init_interval_hour DESC;

-- ============================================
-- VW_BI_SK_QUANTITY_DEPARTAMENT_SERVICES
-- ============================================
DROP VIEW IF EXISTS vw_bi_sk_quantity_departament_services CASCADE;

CREATE VIEW vw_bi_sk_quantity_departament_services AS
WITH all_statuses AS (
    SELECT DISTINCT
        ss.id AS site_service_id,
        ss.name AS local_servico,
        svc.service_name AS servico,
        d.id AS department_id,
        d.name AS department,
        ds.id AS status_id,
        ds.name AS status,
        COALESCE(ds.flow_order, 999) AS flow_order
    FROM sk_sites_services ss
    CROSS JOIN cfg_service_departments sd
    CROSS JOIN ref_departments d
    CROSS JOIN cfg_departaments_status ds
    CROSS JOIN sk_service svc
    WHERE sd.id_department = d.id
        AND sd.id_service = svc.id
        AND ds.id_department = d.id
)
SELECT
    s.site_service_id,
    s.local_servico,
    s.servico,
    s.department,
    s.status,
    COUNT(cq.id) AS quantidade
FROM all_statuses s
LEFT JOIN sk_call_queue cq ON cq.id_site_service = s.site_service_id
    AND cq.id_service_department_status IN (
        SELECT id FROM cfg_service_department_status
        WHERE id_service_department = (
            SELECT id FROM cfg_service_departments
            WHERE id_department = s.department_id AND id_service = (
                SELECT id FROM sk_service WHERE service_name = s.servico
            )
        )
        AND id_department_status = s.status_id
    )
GROUP BY s.site_service_id, s.local_servico, s.servico, s.department, s.status, s.flow_order
ORDER BY s.local_servico, s.servico, s.department, s.flow_order;

-- ============================================
-- VIEW AUXILIAR: RESUMO BI (opcional)
-- ============================================
DROP VIEW IF EXISTS vw_bi_resumo CASCADE;

CREATE VIEW vw_bi_resumo AS
SELECT 
    v.site_service_id,
    v.local_servico,
    v.servico,
    v.department,
    v.total_vagas,
    v.vagas_ocupadas,
    v.vagas_livres,
    COALESCE(q.quantidade, 0) AS quantidade_fila,
    COALESCE(nc.total_nao_compareream, 0) AS total_nao_compareream
FROM vw_bi_counts_vagas v
LEFT JOIN vw_bi_sk_quantity_departament_services q 
    ON v.site_service_id = q.site_service_id 
    AND v.department = q.department
LEFT JOIN (
    SELECT site_service_id, COUNT(*) as total_nao_compareream
    FROM vw_bi_details_nao_comparecerao
    GROUP BY site_service_id
) nc ON v.site_service_id = nc.site_service_id
ORDER BY v.local_servico, v.department;
