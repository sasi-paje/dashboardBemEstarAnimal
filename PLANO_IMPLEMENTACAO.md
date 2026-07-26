# Plano de Implementação — Transformar dashboardBemEstarAnimal no padrão dashsepet

## 1. Objetivo
Deixar o projeto `dashboardBemEstarAnimal` com a **mesma aparência visual** e **mesmas informações** do projeto `dashsepet`, migrando seu design system, estrutura de abas, filtros, KPIs, gráficos, tabelas e funcionalidades.

---

## 2. Análise Atual

### 2.1 Estrutura do dashboardBemEstarAnimal (origem)
- **2 tabs**: Visão Geral, Departamentos
- **Filtros**: Local, Serviço, Departamento, Período
- **KPIs**: Total Vagas, Ocupadas, Livres, Taxa Ocup., Em Fila, Não Comp.
- **Gráficos**: Ocupação por Local, Status da Fila, Evolução Temporal, Atendimentos por Hora, Não-Comparecimentos por Local, Fila por Depto, Status por Depto
- **Tabelas**: Detalhes Não-Comparecimentos, Detalhamento do Fluxo
- **db.py**: Usa `ThreadedConnectionPool`, views BI específicas (`vw_bi_fact_resumo`, `vw_bi_vagas_temporal`, etc.)
- **app.py**: ~797 linhas, estrutura limpa por tabs
- **style.css**: ~507 linhas, tema verde/cinza, header branco

### 2.2 Estrutura do dashsepet (referência)
- **5 tabs**: Geral, Campanhas Ativas, Guinness Book, Downloads, Solicitações
- **Filtros**: Local de Serviço, Espécie, Raça, Gênero, Período, Município, Bairro, Telefone, CPF
- **KPIs**: Variam por aba (Total Vagas, Total Agendamentos, Termos Assinados, Vagas Ocupadas, Vagas Disponíveis, Ocupação, Total Solicitações, Total Castrados, Meta, Total Downloads, Usuários Ativos, Usuários Inativos)
- **Gráficos**: Atendimentos por Período, Vagas Ações Ativas, Top 10 Campanhas, Top 10 Raças, Espécie, Gênero, Vagas por Local (com paginação), Donut de Vagas, Gauge de Progresso, Status das Solicitações
- **Tabelas**: Dados Detalhados (grande, com paginação), Campanhas Ativas, Solicitações
- **db.py**: Conexão simples (sem pool), múltiplas views (`vw_bi_sepete`, `vw_bi_campanhas_ativas`, `vw_bi_guinnes_atendimentos`, `vw_bi_solicitacoes`)
- **app.py**: ~1821 linhas, callback monolítico com controle de visibilidade por aba
- **style.css**: ~438 linhas, design system completo navy/azul, header escuro

---

## 3. Estratégia de Migração

A migração será feita em **5 fases**:

### FASE 1 — Design System e Layout Base
**Arquivos alterados**: `assets/style.css`, `app.py` (layout base)

**Ações**:
1. Substituir `assets/style.css` completo pelo design system do dashsepet
   - Tokens CSS (`:root`) com cores navy/azul
   - Fontes Sora + DM Sans
   - Reset/base, layout wrapper, header escuro (`#1c2c51`)
   - Painel de filtros, cards KPI, charts rows, tabelas, dividers
2. Atualizar `app.py` para usar o novo layout:
   - Importar `PALETTE` e constantes de estilo
   - Substituir header por header escuro com logo, título, subtítulo e botão Atualizar
   - Adotar `.dash-main`, `.filter-panel`, `.kpi-grid`, `.chart-row`, `.section-block`, `.table-card`
   - Manter `dcc.Store` e `dcc.Interval` para estado e atualização

### FASE 2 — Filtros Expandidos
**Arquivos alterados**: `app.py` (layout), `db.py` (novas funções)

**Ações**:
1. Aumentar filtros de 4 para 9, seguindo dashsepet:
   - Local de Serviço (`filtro-servico`)
   - Espécie (`filtro-especie`)
   - Raça (`filtro-raça`)
   - Gênero (`filtro-genero`)
   - Período (`filtro-data`)
   - Município (`filtro-municipio`)
   - Bairro (`filtro-bairro`)
   - Telefone (`filtro-telefone`)
   - CPF (`filtro-cpf`)
2. Atualizar `db.py`:
   - Remover `ThreadedConnectionPool`
   - Adotar conexão simples como dashsepet
   - Criar funções `get_especies()`, `get_racas()`, `get_generos()`, `get_municipios()`, `get_bairros()`, `get_telefones()`, `get_cpfs()`
   - Manter compatibilidade com views existentes

### FASE 3 — Sistema de Abas e KPIs
**Arquivos alterados**: `app.py`

**Ações**:
1. Alterar tabs de 2 para 5:
   - **Geral** — Visão geral dos atendimentos
   - **Campanhas Ativas** — Foco em vagas e ações ativas
   - **Guinness Book** — Progresso de castrações
   - **Downloads** — Métricas de download/usuários
   - **Solicitações** — Status de solicitações
2. Implementar KPIs por aba igual dashsepet
3. Adicionar lógica de visibilidade dinâmica de elementos por aba (rows de gráfico, tabelas, botões)

### FASE 4 — Gráficos e Tabelas
**Arquivos alterados**: `app.py` (charts e callbacks), `components/graphs.py`, `components/tables.py`

**Ações**:
1. Criar funções de gráfico equivalentes ao dashsepet:
   - `create_chart_periodo()`
   - `create_chart_vagas_acao()`
   - `create_chart_top_campanhas()`
   - `create_chart_raca()`
   - `create_chart_especie()` (donut)
   - `create_chart_genero()` (donut)
   - `create_chart_vagas_local()` (com paginação)
   - `create_chart_vagas_donut()`
   - `create_gauge_chart()`
   - `create_chart_status_solicitacoes()`
2. Atualizar tabelas para estilo dashsepet:
   - Cabeçalho navy (`#1c2c51`)
   - Fonte Sora/DM Sans
   - Estilo condicional com azul claro
3. Adicionar paginação no gráfico Vagas por Local

### FASE 5 — Funcionalidades Extras
**Arquivos alterados**: `app.py`, `requirements.txt`

**Ações**:
1. Adicionar botão **Exportar** (Excel)
2. Adicionar link **Exportar Solicitações** (API externa)
3. Adicionar callback `exportar_dados()` com openpyxl
4. Adicionar atualização de dados via `botao-atualizar-dados`
5. Atualizar `requirements.txt`:
   - Remover `dash-bootstrap-components` (se não usado)
   - Garantir `openpyxl`, `requests`

---

## 4. Mapeamento de Arquivos

| Arquivo Origem | Arquivo Destino | Ação |
|----------------|-----------------|------|
| `dashsepet/assets/style.css` | `dashboardBemEstarAnimal/assets/style.css` | Substituição completa |
| `dashsepet/app.py` | `dashboardBemEstarAnimal/app.py` | Reescrita completa do layout e callbacks |
| `dashsepet/db.py` | `dashboardBemEstarAnimal/db.py` | Adaptar estrutura (remover pool, adicionar novas views) |
| `dashboardBemEstarAnimal/components/graphs.py` | Remover/Integrar em app.py | Funções serão reescritas no padrão dashsepet |
| `dashboardBemEstarAnimal/components/tables.py` | Remover/Integrar em app.py | Tabelas serão reescritas no padrão dashsepet |
| `dashboardBemEstarAnimal/views_bi.sql` | Manter | Views SQL já existem |
| `dashboardBemEstarAnimal/create_indexes.sql` | Manter | Índices já existem |

---

## 5. Ordem de Implementação Recomendada

1. **Backup** do projeto atual
2. **Fase 1**: CSS + Layout base
3. **Fase 2**: db.py + filtros
4. **Fase 3**: Tabs + KPIs
5. **Fase 4**: Gráficos + Tabelas
6. **Fase 5**: Funcionalidades extras
7. **Testes** de cada aba individualmente
8. **Validação** visual e funcional

---

## 6. Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Views SQL diferentes entre projetos | Manter `views_bi.sql` e `create_indexes.sql` intactos; adaptar apenas queries Python |
| Dados insuficientes em algumas views | Criar fallbacks (figuras vazias) como já existem |
| Performance com mais filtros | Como dashsepet já funciona, replicar mesma lógica de callback |
| Dependências faltando | Atualizar `requirements.txt` antes de executar |

---

## 7. Critérios de Aceitação

- [ ] Header escuro navy com logo e botão Atualizar
- [ ] 5 tabs funcionais: Geral, Campanhas Ativas, Guinness Book, Downloads, Solicitações
- [ ] 9 filtros funcionais com opções dinâmicas
- [ ] KPIs corretos por aba
- [ ] Todos os gráficos renderizam sem erros
- [ ] Tabela com estilo navy e paginação
- [ ] Botão Exportar funcional (Excel)
- [ ] Design responsivo igual dashsepet
- [ ] Sem erros de lint
