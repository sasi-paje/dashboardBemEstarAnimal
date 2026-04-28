# Contexto do Projeto: Dashboard Bem-Estar Animal

## Visão Geral
Dashboard BI para monitoramento de filas de atendimento de serviços veterinários usando Python + Dash + Plotly. O projeto conecta-se a um banco de dados Supabase/PostgreSQL para exibir informações sobre vagas, departamentos, status de atendimento e não-comparecimentos em tempo real.

## Stack Técnica
- **Dashboard:** Dash + Plotly + Dash Bootstrap Components
- **Backend/Python:** psycopg2 para conexão PostgreSQL
- **Banco de dados:** PostgreSQL (Supabase)
- **Gerenciamento de dependências:** pip com venv
- **Arquivos de configuração:** .env para credenciais

## Estrutura de Arquivos
```
dashboardBemEstarAnimal/
├── app.py                    # Main Dash app com layout e callbacks
├── db.py                     # Conexão + queries + funções de dados
├── requirements.txt           # Dependências Python
├── views_bi.sql              # Views BI originais (vagas, fila, não-compareceram)
├── views_bi_temporal.sql     # Views BI temporais (histórico, resumo executivo)
├── assets/
│   └── style.css           # Estilos customizados (design branco)
├── components/
│   ├── __init__.py
│   ├── graphs.py           # Gráficos Plotly (ocupação, fila)
│   └── tables.py           # Tabelas Dash (detalhamento, não-compareceram)
└── .env                    # Credenciais do banco (não commitar)
```

## Views BI (criadas no banco)
- `vw_bi_counts_vagas` - Vagas totais/ocupadas/livres
- `vw_bi_details_nao_comparecerao` - Detalhes de não-comparecimentos
- `vw_bi_sk_quantity_departament_services` - Quantidade por dept/status

## Queries em db.py

### Funções Principais
- `get_kpis()` - Retorna todos os KPIs calculados
- `get_vagas()` - Vagas filtradas por local/serviço/departamento
- `get_fila()` - Fila filtrada
- `get_nao_compareream()` - Não-comparecimentos filtrados por período
- `get_filter_options()` - Opções para dropdowns de filtro
- `execute_query_dataframe()` - Executa query e retorna DataFrame

### Queries SQL
```sql
QUERY_VAGAS - Vagas por local/serviço/departamento
QUERY_FILA - Fila por departamento/status
QUERY_NAO_COMPARECERAM - Não-comparecimentos (usa createdat)
QUERY_MEDIA_HORA - Média de atendimentos por hora (usa call_time)
QUERY_LOCAIS - Locais únicos
QUERY_SERVICOS - Serviços únicos
QUERY_DEPARTAMENTOS - Departamentos únicos
```

## Layout do Dashboard

### Abas
- **Geral** - Visão geral do sistema (vagas, fila, não-comparecimentos)
- **Departamentos** - Andamento por departamento (fluxo, status)

### Filtros (Topo)
- **Local:** Dropdown com opções dos locais de serviço
- **Servico:** Dropdown com serviços ativos
- **Periodo:** DatePickerRange (data início e fim)
- **Botão:** ↻ Atualizar (atualização manual)

### Tab: Geral
**KPIs (6 cards):**
1. Total Vagas
2. Ocupadas (blue)
3. Livres (green)
4. Taxa Ocupacao (yellow)
5. Em Fila (purple)
6. Nao Comp. (red)

**Graficos:**
1. Ocupacao por Local - Barras empilhadas (ocupadas vs nao confirmadas)
2. Status da Fila - Pizza (waiting/calling/called/cancelled)
3. Evolucao Temporal - Linhas (total vagas, ocupadas, nao comp)
4. Atendimentos por Hora - Barras
5. Nao-Comparecimentos por Local - Barras agrupadas por mes

**Tabela:**
- Detalhes Nao-Comparecimentos (50 registros, paginado)

### Tab: Departamentos
**Graficos:**
1. Fila por Departamento - Barras empilhadas (status)
2. Status por Departamento - Sunburst
3. Fluxo de Atendimento - Barras por departamento

**Tabela:**
- Detalhamento do Fluxo (departamento, status, quantidades por status)

### Auto-Refresh
- Intervalo: 30 minutos (1800000 ms)
- Indicador visual de última atualização

### Views BI Utilizadas
| View | Uso |
|------|-----|
| `vw_bi_fact_resumo` | KPIs principais, grafico temporal |
| `vw_bi_vagas_temporal` | Grafico ocupacao por local |
| `vw_bi_fila_temporal` | Status fila, fila por departamento |
| `vw_bi_fluxo_departamentos` | Fluxo e status por departamento |
| `vw_bi_nao_compareceram_detalhado` | Tabela de nao-comparecimentos |
| `vw_bi_atendimentos_por_hora` | Grafico de distribuicao horaria |
| `vw_bi_dim_local` | Join para filtros de local/servico |

### Funcoes db.py para BI
- `get_kpis_fact_resumo()` - KPIs agregados
- `get_fact_resumo()` - Dados fact table
- `get_vagas_temporal()` - Vagas com evolucao temporal
- `get_fila_temporal()` - Fila por local/status/departamento
- `get_fluxo_departamentos()` - Fluxo detalhado por departamento
- `get_departamentos_flow()` - Agregacao por departamento/status
- `get_nao_compareceram_detalhado()` - Detalhes nao-comp.
- `get_atendimentos_por_hora()` - Distribuicao horaria

## Tabelas do Banco Utilizadas

| Tabela | Purpose |
|--------|---------|
| `sk_booking` | Registros de agendamento (vagas) |
| `sk_sites_services` | Relação site-serviço (local de serviço) |
| `sk_service` | Catálogo de serviços |
| `sk_call_queue` | Fila de atendimento em tempo real |
| `person` | Pessoas/tutores (client_id para join) |
| `pet` | Animais (join via details->>'pet_id') |
| `ref_departments` | Departamentos do fluxo |
| `cfg_service_departments` | Relação serviço-departamento |
| `cfg_departaments_status` | Status possíveis por departamento |
| `cfg_service_department_status` | Status por serviço-departamento |

## Conexão com Banco

```python
# Em db.py
def get_connection():
    return connect(
        host=os.getenv("HOST_DEV"),
        port=os.getenv("PORT_DEV"),
        dbname=os.getenv("DB_NAME_DEV"),
        user=os.getenv("DB_USER_DEV"),
        password=os.getenv("DB_PASSWORD_DEV"),
    )
```

**CREDENCIAIS DEV (.env):**
- HOST: aws-1-sa-east-1.pooler.supabase.com
- PORT: 5432
- DB_NAME: postgres
- DB_USER: bi_user.eibebxjtmwmegaqileqn
- DB_PASSWORD: 75979640

## Dependências (requirements.txt)
```
dash>=2.14.0
plotly>=5.18.0
dash-bootstrap-components>=1.5.0
pandas>=2.1.0
psycopg2-binary
python-dotenv
```

## Decisões Arquiteturais

- [15/Abr/2026] — BI Dashboard criado com Dash + Plotly + Bootstrap
- [15/Abr/2026] — Design em tons de branco para visual limpo
- [15/Abr/2026] — Filtros no topo da página
- [15/Abr/2026] — Auto-refresh a cada 30 minutos + botão manual
- [15/Abr/2026] — Média/Hora calculada usando `call_time` de `sk_call_queue`
- [15/Abr/2026] — Não-comparecimentos filtrados por `service_date`
- [28/Abr/2026] — Connection pooling com psycopg2.ThreadedConnectionPool (minconn=3, maxconn=10)
- [28/Abr/2026] — Locking thread-safe para acesso ao pool de conexões
- [28/Abr/2026] — Filtro de data padrão = hoje (não mais 30 dias atrás)
- [28/Abr/2026] — get_kpis_fact_resumo com agregação SQL (SUM/AVG no banco)
- [28/Abr/2026] — get_nao_compareceram_por_local() com date_from/date_to e LIMIT 100
- [28/Abr/2026] — get_atendimentos_por_hora() LIMIT 24
- [28/Abr/2026] — get_dim_local() com WHERE active=true e LIMIT 1000
- [28/Abr/2026] — LIMIT 500 em todas as queries principais (get_fact_resumo, get_vagas_temporal, get_fila_temporal, get_fluxo_departamentos, get_dim_date, get_tempo_medio)

## Problemas Conhecidos
- Tabela `cfg_service_department_status` usa colunas com prefixo `id_` (ex: `id_service_department`)
- Não há vínculo direto entre `sk_booking.status = NULL` e o pet específico - pet_id está no campo JSON `details`
- Dados de `call_time` em `sk_call_queue` são escassos (apenas 4 registros)
- View `vw_bi_counts_vagas` tem colunas diferentes: `id_site_service`, `name_service`, `total_vagas_ocupadas`, `total_vagas_livres`, `total_de_vagas`

## Como Rodar
```bash
# Ativar venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Rodar dashboard
python app.py
# Acessar http://localhost:8050
```

## Notas Importantes
- Não commitar .env com credenciais reais
- O Dashboard é responsivo (mobile/tablet/desktop)
- Todas as views BI devem ser criadas no banco antes de usar o dashboard

## Análise Completa do Banco de Dados

### Visão Geral da Arquitetura

O banco é um sistema de gerenciamento de filas de atendimento veterinário com fluxo bem definido:

```
AGENDAMENTO (sk_booking) → FILA (sk_call_queue) → FLUXO DE ATENDIMENTO (departamentos)
```

### Entidades Principais

#### 1. `sk_booking` (22.708 registros)
**Purpose:** Gerencia agendamentos/vagas de serviço
**Key Columns:**
- `id` - PK bigint
- `id_site_sevice` - FK para local de serviço
- `client_id` - FK para pessoa (tutor)
- `service_date` - Data do agendamento
- `init_interval_hour` / `end_interval_hour` - Hora da vaga
- `status` - Enum (NULL=não confirmado, 'scheduled', 'checked_in')
- `checkin_status` - Sempre 0 (legacy)
- `details` - JSONB com histórico de re-agendamento
- `attendance_data` - JSONB com tipo de fila
- `call_time` - Hora que foi chamado (raro)
- `pet_id` - ID direto do pet (alguns registros)

**JSONB `details` estrutura:**
```json
{
  "extra": "null",
  "pet_id": 17,
  "reason": null,
  "priority": true,
  "tutor_id": 19,
  "client_id": 1,
  "priority_type": 60,
  "reschedule_at": null,
  "rescheduled_from": null,
  "reschedule_reason": null,
  "reschedule_by_person_id": null
}
```

**JSONB `attendance_data` estrutura:**
```json
{
  "type_queue": 1,
  "reception_appointment_id": "4"
}
```

**Distribuição de status:**
- NULL (não confirmado/não compareceu): 22.668
- 'scheduled': 22
- 'checked_in': 18

**Interpretação:** `status IS NULL` indica que o agendamento NÃO foi cumprido (não-comparecimento).

#### 2. `sk_call_queue` (11 registros)
**Purpose:** Fila de atendimento em tempo real (chamados ativos)
**Key Columns:**
- `id` - PK
- `id_site_service` - Local de serviço
- `service_date` - Data do atendimento
- `status` - Enum ('called', 'calling', 'cancelled', 'waiting')
- `call_time` - Hora que foi chamado
- `call_count` - Quantas vezes chamou
- `board_count` - Contagem em quadro
- `id_attendant` - Atendente que chamou
- `id_pet` / `id_person` - Links direto para pet/pessoa
- `client_id` - Tutor
- `id_service_department_status` - Status no fluxo do departamento
- `details` - JSONB com histórico de movimentações

**JSONB `details` estrutura (com histórico de movimentação):**
```json
{
  "room_name": "10",
  "type_queue": "1",
  "reception_appointment_id": "10",
  "call_queue_department_history": [
    {
      "moved_at": "2026-04-13T00:40:10.343094+00:00",
      "old_call_time": "20:21:07",
      "old_call_count": 2,
      "old_board_count": 2,
      "old_is_priority": false,
      "old_result_type": "pending",
      "old_id_attendant": 10,
      "old_queue_status": "called",
      "old_department_id": 2,
      "old_department_code": "TERM",
      "old_department_name": "Assinatura de Termo",
      "old_department_status_id": 17,
      "old_department_status_code": "IN_PROGRESS",
      "old_department_status_name": "Em Atendimento"
    }
  ]
}
```

**Importante:** `call_queue_department_history` é um ARRAY que mantém todo o histórico de movimentações entre departamentos.

#### 3. `sk_sites_services` (16 registros)
**Purpose:** Locais de serviço (cada local tem horários, configs de almoço, etc.)
**Key Columns:**
- `id` - PK
- `id_site` - Site físico
- `id_service` - Serviço oferecido
- `name` - Nome do local ("Meu Pet BV - Vacina", "Parque Anaua", etc.)
- `active` - Se está ativo
- `init_time` / `end_time` - Horário funcionamento
- `init_lunch_time` / `end_lunch_time` - Horário almoço
- `available_resource_total` - Recursos disponíveis (vagas)
- `service_time` - Tempo estimado por atendimento

#### 4. `sk_service` (2 registros)
**Purpose:** Catálogo de serviços
- ID:3 | Castração | distinction_species:True
- ID:4 | Vacinação | distinction_species:True

#### 5. `person` (344 registros)
**Purpose:** Pessoas/tutores
- `person_id` - PK
- `client_id` - ID do cliente
- `name` - Nome
- `cpf` - CPF
- `person_type_id` - Tipo (1=Tutor, 7=?)
- `phone`, `email`, `data_nascimento`
- Endereço completo (rua, numero, cep, bairro, cidade, uf)
- `uuid` - UUID único

#### 6. `pet` (577 registros)
**Purpose:** Animais
- `id` - PK
- `tutor_id` - FK para person
- `name` - Nome do animal
- `gender` - M/F
- `size` - P/M/G/XG
- `breed_id` - Raça
- `birth_date` - Data nascimento
- `color` - Cor
- `is_pcd` - Se é PCD
- `chip_code` - Código chip
- `is_castrated` - Se é castrado

#### 7. `ref_departments` (5 registros)
**Purpose:** Departamentos do fluxo de atendimento

| ID | Code | Name | Flow Order |
|----|------|------|------------|
| 1 | RECEPTION | Recepção | 1 |
| 2 | TERM | Assinatura de Termo | 2 |
| 3 | Vacinação | Vacinação | 3 |
| 5 | POST_ATTENDANT | Pós-atendimento | 4 |
| 6 | DISCHARGE | Alta / Finalização | 5 |

#### 8. `cfg_departaments_status` (12 registros)
**Purpose:** Status possíveis por departamento (矩阵 departamento × status)

| Dept | Status | Name | Initial | Final | Cancelled |
|------|--------|------|---------|-------|-----------|
| 1 RECEPTION | CANCELLED | Agendada | true | false | true |
| 1 RECEPTION | CHECKED_IN | Presente | false | true | false |
| 2 TERM | WAITING | Aguardando | true | false | false |
| 2 TERM | APPROVED | Aprovado | false | true | false |
| 2 TERM | REJECTED | Reprovado | false | true | true |
| 2 TERM | CALLING | Chamando | false | false | false |
| 2 TERM | IN_PROGRESS | Em Atendimento | false | false | false |
| 3 Vacinação | WAITING | Aguardando | true | false | false |
| 3 Vacinação | CALLING | Chamando | false | false | false |
| 3 Vacinação | IN_PROGRESS | Em Atendimento | false | false | false |
| 3 Vacinação | COMPLETED | Finalizado | false | true | false |
| 3 Vacinação | NOT_COMPLETED | Não Finalizado | false | true | true |

#### 9. `cfg_service_departments` (3 registros)
**Purpose:** Relação serviço → departamentos (mapeia quais departamentos um serviço atravessa)
- service:4 (Vacinação) → depts: 1, 2, 3 (Recepção → Termo → Vacinação)

#### 10. `cfg_service_department_status` (12 registros)
**Purpose:** Status disponíveis para cada combinação serviço-departamento

### Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────┐
│                     sk_booking (Agendamentos)                   │
│  22.708 registros                                               │
│  status: NULL = não confirmou/não compareceu                    │
│  status: 'scheduled' = agendado                                 │
│  status: 'checked_in' = presente                                │
│                                                                 │
│  details JSONB: pet_id, tutor_id, priority, reschedule info      │
│  attendance_data: type_queue, reception_appointment_id          │
└────────────────────────────┬────────────────────────────────────┘
                             │ check-in
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   sk_call_queue (Fila Ativa)                    │
│  ~11 registros (atendimentos em andamento)                      │
│  status: waiting → calling → called → (completed/cancelled)    │
│                                                                 │
│  details JSONB: room_name, call_queue_department_history[]      │
│  id_service_department_status: posiciona no fluxo               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FLUXO POR DEPARTAMENTOS                        │
│                                                                 │
│  Reception (Recepção) → Term (Termo) → Vacinação → Discharge   │
│                                                                 │
│  cfg_departaments_status define status por dept:                │
│  - Reception: CANCELLED, CHECKED_IN                            │
│  - Term: WAITING, APPROVED, REJECTED, CALLING, IN_PROGRESS     │
│  - Vacinação: WAITING, CALLING, IN_PROGRESS, COMPLETED         │
│                                                                 │
│  cfg_service_department_status mapeia cada status ao workflow   │
└─────────────────────────────────────────────────────────────────┘
```

### Campos JSONB e Seus Usos

| Tabela | Campo | Estrutura | Uso Principal |
|--------|-------|-----------|---------------|
| sk_booking | details | `{pet_id, tutor_id, priority, priority_type, reschedule_*, client_id}` | Histórico de re-agendamento, link para pet |
| sk_booking | attendance_data | `{type_queue, reception_appointment_id}` | Tipo de fila, link para recepção |
| sk_call_queue | details | `{room_name, type_queue, reception_appointment_id, call_queue_department_history[]}` | Sala, histórico de movimentações |

### Relacionamentos

```
sk_booking
  ├── client_id → person.person_id
  ├── id_site_sevice → sk_sites_services.id
  ├── details->>'pet_id' → pet.id
  └── (attendance_data->>'reception_appointment_id' → ?)

sk_call_queue
  ├── id_site_service → sk_sites_services.id
  ├── client_id → person.person_id
  ├── id_pet → pet.id
  ├── id_person → person.person_id
  ├── id_attendant → sk_attendants.id
  ├── id_service_department_status → cfg_service_department_status.id
  └── details->>'reception_appointment_id' → sk_booking.id (via attendance_data)

sk_sites_services
  ├── id_site → sk_sites.id
  └── id_service → sk_service.id

cfg_service_departments
  ├── id_service → sk_service.id
  └── id_department → ref_departments.id

cfg_service_department_status
  ├── id_service_department → cfg_service_departments.id
  └── id_department_status → cfg_departaments_status.id
```

### Views BI Criadas

#### Views Originais (views_bi.sql)
1. **vw_bi_counts_vagas** - Conta vagas totais/ocupadas/livres por local-serviço-departamento
2. **vw_bi_details_nao_comparecerao** - Detalhes de não-comparecimentos (booking sem status)
3. **vw_bi_sk_quantity_departament_services** - Quantidade na fila por local-serviço-departamento-status
4. **vw_bi_resumo** - Sumário combinando vagas, fila e não-comparecimentos

#### Views Dimensionais (views_bi_temporal.sql)
- **vw_bi_dim_date** - Dimensão data (ano, mes, dia_semana, fim_semana)
- **vw_bi_dim_local** - Dimensão local/serviço (site_service_id, local, servico)

#### Views Fact (views_bi_temporal.sql)
- **vw_bi_fact_resumo** (114 rows) - Tabela fato principal com todos os KPIs por data + site_service_id

#### Views Temporais (views_bi_temporal.sql) - Criadas em 23/Abr/2026

| View | Rows | Descrição |
|------|------|-----------|
| `vw_bi_vagas_temporal` | 114 | Vagas por dia/local/serviço com evolução temporal |
| `vw_bi_fila_temporal` | 10 | Estado da fila por dia/local/status |
| `vw_bi_tempo_medio` | 4 | Tempo médio de espera (call_time → attended_time) |
| `vw_bi_historico_departamento` | 4 | Expande JSONB `call_queue_department_history[]` em linhas |
| `vw_bi_nao_compareceram_detalhado` | 22659 | Não-comparecimentos com tutor, animal, raça, prioridade |
| `vw_bi_resumo_executivo` | 47 | KPIs combinados por dia (vagas, fila, não-compareceram, taxa ocupacao) |
| `vw_bi_fluxo_departamentos` | 10 | Análise do fluxo por departamento com contagem por status |
| `vw_bi_atendimentos_por_hora` | 4 | Distribuição de atendimentos por hora do dia |
| `vw_bi_prioridade_analise` | 9 | Chamadas prioritárias vs normais com tempo médio |

#### Colunas das Novas Views

**vw_bi_vagas_temporal:** data, site_service_id, local_servico, servico, total_vagas, vagas_scheduled, vagas_checked_in, vagas_nao_confirmadas, vagas_ocupadas, vagas_livres

**vw_bi_historico_departamento:** queue_id, data, site_service_id, local_servico, servico, data_movimentacao, department_code, department_name, status_anterior, status_departamento_anterior, hora_chamada_anterior, hora_atendimento_anterior, call_count_anterior, board_count_anterior, era_prioridade, result_type_anterior, attendant_id_anterior

**vw_bi_nao_compareceram_detalhado:** data_agendamento, ano_mes, dia_semana, site_service_id, local_servico, servico, booking_id, hora_vaga, tutor_id, nome_tutor, cpf, telefone, pet_id, nome_animal, porte, sexo, raca, era_prioridade, priority_type, data_criacao_agendamento

**vw_bi_resumo_executivo:** data, total_vagas, vagas_ocupadas, nao_confirmados, em_fila, waiting, calling, called, nao_compareceram, taxa_ocupacao_pct

### Problemas/Dívidas Técnicas Identificadas

1. **sk_booking.pet_id** existe como coluna direta, mas na prática `details->>'pet_id'` é usado
2. **call_time em sk_booking** está sempre NULL (apenas 4 registros em sk_call_queue têm)
3. **Status enum é USER-DEFINED** - não mostra valores no pg_enum padrão
4. **CROSS JOIN nas views BI** - pode gerar produtos cartesianos se configs não forem consistentes
5. **history em JSONB** - array call_queue_department_history pode crescer indefinidamente
6. **JSONB casting** - usar `(details->>'pet_id')::text::integer` ao invés de `(details->>'pet_id')::bigint` diretamente
7. **priority JSONB** - comparar com string `'true'` ao invés de boolean `true`

### Correções Aplicadas (23/Abr/2026)

- JSONB `details->>'pet_id'` precisa castear para text primeiro: `(details->>'pet_id')::text::integer`
- `priority` em JSONB é texto 'true'/'false', não boolean: `(details->>'priority') = 'true'`
- Tabela `breed` usa coluna `breed` não `name`

### Dados para BI

Para criar dashboards BI eficazes, focar em:

1. **Vagas**: sk_booking.service_date + id_site_service + status
2. **Fila**: sk_call_queue.service_date + id_site_service + status + id_service_department_status
3. **Não-comparecimentos**: sk_booking.status IS NULL + service_date
4. **Tempo médio**: call_time em sk_call_queue (limitado)
5. **Histórico por departamento**: details->'call_queue_department_history' (array)

### Relacionamento entre Views BI

```
┌─────────────────────────────────────────────────────────────────┐
│                    DIMENSÕES (Views de Lookup)                  │
│                                                                 │
│  vw_bi_dim_date                                                 │
│    └── data, ano, mes, ano_mes, nome_mes, dia_semana           │
│                                                                 │
│  vw_bi_dim_local                                                │
│    └── site_service_id, local_servico, service_id, servico     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FACT TABLE PRINCIPAL                          │
│                                                                 │
│  vw_bi_fact_resumo (114 rows)                                   │
│    └── data, site_service_id                                    │
│        ├── total_vagas, vagas_scheduled, vagas_checked_in       │
│        ├── vagas_ocupadas, vagas_nao_confirmadas                │
│        ├── em_fila, waiting, calling, called, cancelled          │
│        ├── nao_compareceram                                     │
│        └── taxa_ocupacao_pct                                    │
└─────────────────────────────────────────────────────────────────┘
           │                        │                    │
           ▼                        ▼                    ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ vw_bi_vagas_     │    │ vw_bi_nao_       │    │ vw_bi_fila_      │
│ temporal         │    │ compareceram_    │    │ temporal         │
│ (114 rows)       │    │ detalhado        │    │ (10 rows)        │
│                  │    │ (22659 rows)     │    │                  │
│ JOIN: data +     │    │ JOIN: data +     │    │ JOIN: data +     │
│ site_service_id  │    │ site_service_id  │    │ site_service_id  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
           │                        │                    │
           ▼                        ▼                    ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ vw_bi_tempo_     │    │ vw_bi_fluxo_     │    │ vw_bi_historico_│
│ medio            │    │ departamentos    │    │ departamento     │
│ (4 rows)         │    │ (10 rows)        │    │ (4 rows)         │
│                  │    │                  │    │                  │
│ JOIN: data +     │    │ JOIN: data +     │    │ JOIN: data +     │
│ site_service_id  │    │ site_service_id  │    │ site_service_id  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

**Chaves de Relacionamento:**
- `data` (DATE) - todas as views exceto `vw_bi_atendimentos_por_hora`
- `site_service_id` (INT) - views que filtram por local
- `local_servico` (TEXT) - views que filtram por nome do local
- `servico` (TEXT) - views que filtram por tipo de serviço
- `departamento` (TEXT) - views de fluxo/historico

**Filtros do Dashboard → Queries:**

| Filtro | View Principal | Views Drill-down |
|--------|---------------|------------------|
| Período (date_from/to) | `vw_bi_fact_resumo` | vagas, fila, nao_compareceram, historico |
| Local | `vw_bi_dim_local` + `vw_bi_fact_resumo` | fila_temporal, fluxo_departamentos |
| Serviço | `vw_bi_dim_local` | tempo_medio, prioridade_analise |
| Departamento | - | fila_temporal, historico_departamento |

**Views para Drill-down/especializadas:**
- `vw_bi_atendimentos_por_hora` - só hora (sem data/site), para gráfico de barras
- `vw_bi_prioridade_analise` - comparativo prioridades
- `vw_bi_resumo_executivo` - resumo diário agregadol
