import dash
from dash import dcc, html, callback, ctx, Input, Output, State
from datetime import datetime
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor
import plotly.express as px
import plotly.graph_objects as go

from db import (
    get_kpis_fact_resumo,
    get_vagas_temporal,
    get_campanhas_encerradas,
    get_fila_temporal,
    get_fluxo_departamentos,
    get_fluxo_historico_departamentos,
    get_departamentos_flow,
    get_departamentos_configurados,
    get_filter_options,
    get_totais_acumulados,
    get_atendimentos_por_mes,
    get_especies_vacinacao,
    get_locais_atendidos,
    get_desfechos_agendamento,
    get_perfil_animais,
    get_composicao_doses,
    get_distribuicao_territorial,
    get_kpis_por_especie,
)

LOCAL_CENTRO_ZOONOSES = 'Unidade de Vigilância e Controle de Zoonoses-UVCZ'

# Registros anteriores a esta data são "legados" (migrados de antes do sistema
# atual entrar em produção). O aviso amarelo no Dashboard avisa quando esses
# registros estão sendo somados aos KPIs/gráficos; "Remover filtro" apenas
# aplica um filtro de data (oculta da visão), não apaga nada do banco.
DATA_CORTE_LEGADO = '2026-01-01'

# Opções reais do "Filtro avançado" — carregadas uma vez na inicialização
# (não mudam por requisição). Se a consulta falhar por qualquer motivo, os
# dropdowns simplesmente ficam só com "Todos" em vez de derrubar o app.
try:
    _LOCAIS_REAIS, _SERVICOS_REAIS, _ = get_filter_options()
except Exception as e:
    print(f"Aviso: não foi possível carregar opções do filtro avançado: {e}")
    _LOCAIS_REAIS, _SERVICOS_REAIS = [], []

MESES_PT = {
    '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr', '05': 'Mai', '06': 'Jun',
    '07': 'Jul', '08': 'Ago', '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
}

# ─── Paralelização de consultas ao banco ───────────────────────────────────
# Cada get_* do db.py abre sua PRÓPRIA conexão (execute_query_dataframe_simple)
# e o servidor real fica na Supabase (rede) — o tempo de resposta de cada tela
# é dominado por ESPERA de rede, não por CPU. Hoje essas consultas rodavam
# todas em série (uma espera atrás da outra), o que soma ~10 consultas x
# algumas centenas de ms cada = os 8-10s relatados ao abrir Vacinação/Castração.
# Rodando em threads, o tempo total passa a ser ~o da consulta mais lenta do
# grupo, não a soma — sem mudar nenhuma query nem o resultado de nenhuma.
_db_executor = ThreadPoolExecutor(max_workers=12)


def parallel(*fns):
    """Executa callables (sem argumento, ex: lambdas) em paralelo e devolve os
    resultados na mesma ordem em que foram passados."""
    futures = [_db_executor.submit(fn) for fn in fns]
    return [f.result() for f in futures]

app = dash.Dash(
    __name__,
    external_stylesheets=[
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
        '/assets/style.css',
    ],
    suppress_callback_exceptions=True
)

today = datetime.now().strftime('%Y-%m-%d')


def format_number(num):
    if num is None:
        return '--'
    if isinstance(num, float):
        return f'{num:,.1f}'.replace(',', '.')
    return f'{int(num):,}'.replace(',', '.')


def create_empty_figure():
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#9ca3af'),
        dragmode=False,
        xaxis=dict(showgrid=False, showticklabels=False, fixedrange=True),
        yaxis=dict(showgrid=False, showticklabels=False, fixedrange=True),
        height=280
    )
    fig.add_annotation(text='Sem dados disponíveis', showarrow=False, font=dict(size=14, color='#9ca3af'))
    return fig


# ─── Filtros (legado — ainda usados pelas telas de Departamentos/Campanhas/
#     Castrações/Solicitações, hoje sem navegação própria neste app) ─────────
FILTER_PANEL = html.Div([
    html.Div([
        html.Div([
            html.Label('Local', className='filter-label'),
            dcc.Dropdown(
                id='filtro-local',
                options=[],
                value=None,
                placeholder='Selecione',
                clearable=True,
                className='filter-dropdown'
            )
        ], className='filter-group'),

        html.Div([
            html.Label('Serviço', className='filter-label'),
            dcc.Dropdown(
                id='filtro-servico',
                options=[],
                value=None,
                placeholder='Selecione',
                clearable=True,
                className='filter-dropdown'
            )
        ], className='filter-group'),

        html.Div([
            html.Label('Departamento', className='filter-label'),
            dcc.Dropdown(
                id='filtro-departamento',
                options=[],
                value=None,
                placeholder='Selecione',
                clearable=True,
                className='filter-dropdown'
            )
        ], className='filter-group'),
    ], className='filter-row'),

    html.Div([
        html.Div([
            html.Label('Período', className='filter-label'),
            dcc.DatePickerRange(
                id='date-picker',
                start_date=datetime.now().replace(day=1).strftime('%Y-%m-%d'),
                end_date=((datetime.now().replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)).strftime('%Y-%m-%d'),
                display_format='DD/MM/YYYY',
                className='filter-datepicker'
            )
        ], className='filter-group'),

        html.Div([
            html.Label('', className='filter-label'),
            html.Button('Limpar Filtros', id='btn-clear', className='btn-clear')
        ], className='filter-group'),

        html.Div([
            html.Label('', className='filter-label'),
            html.Button('↻ Atualizar', id='btn-refresh', className='btn-refresh')
        ], className='filter-group'),
    ], className='filter-row'),
], className='filter-panel')


# ─── Filtros da tela Dashboard (estilo SEMMA) ───────────────────────────────
# Sem data padrão: "Todos" deve mostrar todo o histórico disponível, não só o mês atual.
DASHBOARD_FILTER_PANEL = html.Div([
    html.Div([
        html.Label('Data inicial', className='sv2-field-label'),
        dcc.DatePickerSingle(
            id='dash-date-start',
            date=None,
            placeholder='Todo o período',
            display_format='DD/MM/YYYY',
        )
    ], className='sv2-date-field'),

    html.Div([
        html.Label('Data final', className='sv2-field-label'),
        dcc.DatePickerSingle(
            id='dash-date-end',
            date=None,
            placeholder='Todo o período',
            display_format='DD/MM/YYYY',
        )
    ], className='sv2-date-field'),

    html.Button(
        html.Div(className='sv2-funnel-icon'),
        id='dash-filter-icon-btn',
        className='sv2-filter-icon-btn',
        title='Filtros'
    ),

    dcc.RadioItems(
        id='dash-quick-filter',
        options=[
            {'label': [html.I(className='fa-solid fa-table-cells'), html.Span('Todos')], 'value': 'todos'},
            {'label': [html.I(className='fa-solid fa-building'), html.Span('Centro de Zoonoses')], 'value': 'zoonoses'},
            {'label': [html.I(className='fa-regular fa-calendar'), html.Span('Fim de semana')], 'value': 'weekend'},
        ],
        value='todos',
        className='sv2-pill-group',
        inputClassName='sv2-pill-input',
        labelClassName='sv2-pill-label',
    ),

    html.Button('Limpar', id='dash-btn-limpar', className='sv2-btn-limpar'),
    html.Button('Filtrar', id='dash-btn-filtrar', className='sv2-btn-filtrar'),
], className='sv2-filter-panel')


# ─── Filtro avançado (painel do botão de funil) ────────────────────────────
# Mesma regra de sempre: precisa existir de forma ESTÁTICA no layout (visível
# ou não via 'style') — os dropdowns aqui dentro são Input do callback
# principal, então não podem ser recriados dentro do próprio conteúdo dinâmico.
ADV_FILTER_PANEL = html.Div([
    html.Div([
        html.Label('Local de serviço', className='sv2-field-label'),
        dcc.Dropdown(
            id='adv-local',
            options=[{'label': l, 'value': l} for l in _LOCAIS_REAIS],
            value=None,
            placeholder='Todos',
            clearable=True,
            className='sv2-adv-dropdown'
        ),
    ], className='sv2-adv-field'),

    html.Div([
        html.Label('Serviço', className='sv2-field-label'),
        dcc.Dropdown(
            id='adv-servico',
            options=[{'label': 'Todos', 'value': 'todos'}] +
                    [{'label': s, 'value': s} for s in _SERVICOS_REAIS],
            value='todos',
            clearable=False,
            className='sv2-adv-dropdown'
        ),
    ], className='sv2-adv-field'),

    html.Div([
        html.Label('Espécie', className='sv2-field-label'),
        dcc.Dropdown(
            id='adv-especie',
            options=[
                {'label': 'Todas', 'value': 'todas'},
                {'label': 'Cão', 'value': '1'},
                {'label': 'Gato', 'value': '2'},
            ],
            value='todas',
            clearable=False,
            className='sv2-adv-dropdown'
        ),
    ], className='sv2-adv-field'),

    html.Div([
        html.Label('Origem dos registros', className='sv2-field-label'),
        dcc.RadioItems(
            id='adv-origem',
            options=[
                {'label': 'Sistema', 'value': 'sistema'},
                {'label': 'Ambos', 'value': 'ambos'},
                {'label': 'Histórico', 'value': 'historico'},
            ],
            value='ambos',
            className='sv2-pill-group',
            inputClassName='sv2-pill-input',
            labelClassName='sv2-pill-label',
        ),
    ], className='sv2-adv-field'),
], id='adv-filter-panel', className='sv2-adv-panel', style={'display': 'none'})


# ─── Aviso de dados legados ─────────────────────────────────────────────────
# Precisa existir de forma ESTÁTICA no layout (não gerado dentro do próprio
# callback que o usa como Input) para o botão "Remover filtro" não criar uma
# dependência circular com 'dashboard-content'. A visibilidade é controlada
# via Output(..., 'style'), não recriando os children a cada render.
LEGACY_WARNING_BANNER = html.Div([
    html.Div([
        html.Span('⚠', className='sv2-warning__icon'),
        html.Span(
            'Registros anteriores ao sistema estão sendo contabilizados',
            className='sv2-warning__text'
        ),
    ], className='sv2-warning__left'),
    html.Button('Remover filtro', id='dash-btn-remover-legado', className='sv2-warning__btn'),
], id='legacy-warning-banner', className='sv2-warning-banner')


# ─── Link "Voltar ao panorama" ──────────────────────────────────────────────
# Mesmo motivo do aviso de dados legados: precisa existir de forma ESTÁTICA
# (sempre no layout) para o Dash conseguir registrar o clique. Se ele só
# existisse quando view-mode='vacinacao', o próprio callback de navegação
# (que o usa como Input) nunca dispararia — nem para abrir a tela pela
# primeira vez — porque o Dash exige que todo Input de um callback já
# exista em algum lugar do layout atual, mesmo que oculto.
VIEW_BACK_LINK = html.A(
    [html.Span('←'), html.Span(' Voltar ao panorama')],
    id='btn-voltar-panorama', n_clicks=0, className='sv2-back-link',
    style={'display': 'none'}
)


# ─── Layout Principal ───────────────────────────────────────────────────────
# Este app é responsável apenas pela tela de Dashboard — a navegação entre
# seções (Departamentos, Campanhas, etc.) já é feita pelo sistema principal.
app.layout = html.Div([
    dcc.Store(id='last-update', data=None),
    dcc.Store(id='view-mode', data='panorama'),

    html.Div([
        VIEW_BACK_LINK,
        html.Div([
            html.Div([
                html.Div(id='hero-container'),
                DASHBOARD_FILTER_PANEL,
            ], className='sv2-hero-filter-card'),
            ADV_FILTER_PANEL,
        ], className='sv2-hero-filter-anchor'),
        LEGACY_WARNING_BANNER,
        html.Div(id='kpi-row-container'),
        # "Portas de entrada" precisa existir SEMPRE no DOM — o botão que
        # abre a tela de Vacinação (btn-abrir-vacinacao) vive dentro dela.
        # Mesmo raciocínio do link "Voltar": some visualmente via 'style',
        # nunca sai da árvore de componentes.
        html.Div(id='entry-section-container'),
        html.Div(id='dashboard-content'),
    ], className='sv2-page-body'),

    dcc.Interval(
        id='interval-component',
        interval=1800000,
        n_intervals=0
    )
], className='app-container sv2-standalone')


# ─── Navegação Panorama ↔ telas de detalhe (Vacinação/Castração) ───────────
# Callback separado do render_dashboard: os botões "abrir" (↗) ficam dentro
# do conteúdo dinâmico (dashboard-content) e o link "Voltar" fica dentro de
# view-back-link — ambos gerados pelo PRÓPRIO render_dashboard. Se fossem
# Input desse mesmo callback, criaria uma dependência circular (o mesmo bug
# que já corrigimos no aviso de dados legados). Por isso a troca de view-mode
# vive num callback à parte.
@callback(
    Output('view-mode', 'data'),
    [Input('btn-abrir-vacinacao', 'n_clicks'),
     Input('btn-abrir-castracao', 'n_clicks'),
     Input('btn-voltar-panorama', 'n_clicks')],
    prevent_initial_call=True
)
def toggle_view_mode(n_abrir_vacinacao, n_abrir_castracao, n_voltar):
    if ctx.triggered_id == 'btn-abrir-vacinacao':
        return 'vacinacao'
    if ctx.triggered_id == 'btn-abrir-castracao':
        return 'castracao'
    return 'panorama'


# ─── Abrir/fechar o painel "Filtro avançado" ───────────────────────────────
@callback(
    Output('adv-filter-panel', 'style'),
    Input('dash-filter-icon-btn', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_adv_filter_panel(n_clicks):
    return {} if (n_clicks or 0) % 2 == 1 else {'display': 'none'}


# ─── Callback da tela de Dashboard ──────────────────────────────────────────
# Datas e pill são Input (não State): a tela reage na hora, sem precisar
# clicar em "Filtrar" — o botão fica só como atalho/confirmação visual.
@callback(
    [Output('hero-container', 'children'),
     Output('kpi-row-container', 'children'),
     Output('entry-section-container', 'children'),
     Output('entry-section-container', 'style'),
     Output('dashboard-content', 'children'),
     Output('legacy-warning-banner', 'style'),
     Output('btn-voltar-panorama', 'style'),
     Output('dash-date-start', 'date'),
     Output('dash-date-end', 'date'),
     Output('dash-quick-filter', 'value')],
    [Input('dash-date-start', 'date'),
     Input('dash-date-end', 'date'),
     Input('dash-quick-filter', 'value'),
     Input('dash-btn-filtrar', 'n_clicks'),
     Input('dash-btn-limpar', 'n_clicks'),
     Input('dash-btn-remover-legado', 'n_clicks'),
     Input('view-mode', 'data'),
     Input('adv-local', 'value'),
     Input('adv-servico', 'value'),
     Input('adv-especie', 'value'),
     Input('adv-origem', 'value'),
     Input('interval-component', 'n_intervals')]
)
def render_dashboard(date_start, date_end, quick_filter, n_filtrar, n_limpar, n_remover_legado, view_mode,
                      adv_local, adv_servico, adv_especie, adv_origem, n_intervals):
    if ctx.triggered_id == 'dash-btn-limpar':
        date_start, date_end, quick_filter = None, None, 'todos'
    elif ctx.triggered_id == 'dash-btn-remover-legado':
        # Só aplica um filtro de data (data >= corte) para ocultar os
        # registros legados da visão — não apaga nada do banco.
        date_start = DATA_CORTE_LEGADO

    date_from = date_start or None
    date_to = date_end or None

    # "Origem dos registros" (filtro avançado): Sistema = só data >= corte
    # (mesmo efeito do "Remover filtro" do aviso); Histórico = só data < corte
    # (só os registros legados); Ambos = sem essa restrição extra.
    if adv_origem == 'sistema':
        date_from = max(date_from, DATA_CORTE_LEGADO) if date_from else DATA_CORTE_LEGADO
    elif adv_origem == 'historico':
        dia_anterior_corte = (datetime.strptime(DATA_CORTE_LEGADO, '%Y-%m-%d') - relativedelta(days=1)).strftime('%Y-%m-%d')
        date_to = min(date_to, dia_anterior_corte) if date_to else dia_anterior_corte

    # "Local de serviço" do filtro avançado tem prioridade sobre a pill
    # "Centro de Zoonoses" quando os dois estão ativos (o avançado é mais
    # específico — dá pra escolher qualquer um dos locais reais, não só esse).
    local_filter = adv_local or (LOCAL_CENTRO_ZOONOSES if quick_filter == 'zoonoses' else None)
    weekend_only = quick_filter == 'weekend'
    servico_filter = adv_servico if adv_servico and adv_servico != 'todos' else None
    especie_id = int(adv_especie) if adv_especie and adv_especie != 'todas' else None

    # "Portas de entrada" só fica VISÍVEL no panorama — nas outras telas
    # mantém o último conteúdo já renderizado (dash.no_update) e só some via
    # 'style', sem gastar tempo de rede à toa.
    entry_style = {} if view_mode == 'panorama' else {'display': 'none'}

    if view_mode == 'vacinacao':
        entry_section = dash.no_update
        kpis_vacina, totais = parallel(
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Vacinação', weekend_only),
            lambda: get_totais_acumulados(),
        )
        hero = build_hero_vacinacao(kpis_vacina, totais)
        kpi_row, rest_content = render_vacinacao_tab(
            date_start, date_end, quick_filter, local_filter, especie_id, kpis_vacina_base=kpis_vacina
        )
        warning_style = {'display': 'none'}
        back_link_style = {}
    elif view_mode == 'castracao':
        entry_section = dash.no_update
        kpis_castra, totais = parallel(
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Castração', weekend_only),
            lambda: get_totais_acumulados(),
        )
        hero = build_hero_castracao(kpis_castra, totais)
        kpi_row, rest_content = render_castracao_tab(
            date_start, date_end, quick_filter, local_filter, especie_id, kpis_castra_base=kpis_castra
        )
        warning_style = {'display': 'none'}
        back_link_style = {}
    else:
        # No panorama, "Portas de entrada" + hero + aba usam bases que se
        # sobrepõem (ex: KPI de Vacinação entra tanto no card de entrada
        # quanto no card do topo) — TUDO é buscado numa ÚNICA leva em
        # paralelo (8 consultas de uma vez) em vez de 3 ondas sequenciais.
        # Isso é o que fazia "Voltar ao panorama" demorar mais que abrir
        # Vacinação/Castração: as mesmas consultas, só que em série.
        (kpis_vacina, kpis_castra, kpis_all, especies_entry, totais,
         df_mes, df_fluxo_historico, df_departamentos) = parallel(
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Vacinação', weekend_only),
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Castração', weekend_only),
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, servico_filter, weekend_only),
            lambda: get_especies_vacinacao(date_from, date_to, local_filter, weekend_only),
            lambda: get_totais_acumulados(),
            lambda: get_atendimentos_por_mes(date_from, date_to, local_filter, weekend_only),
            lambda: get_fluxo_historico_departamentos(date_from, date_to, local_filter, 'Castração', weekend_only),
            lambda: get_departamentos_configurados('Castração'),
        )
        entry_section = build_entry_section(kpis_vacina, especies_entry, kpis_castra)
        hero = build_hero(totais)
        kpi_row, rest_content = render_dashboard_tab(
            date_start, date_end, quick_filter, local_filter, servico_filter, especie_id,
            kpis_all_base=kpis_all, kpis_vacina_base=kpis_vacina, kpis_castra_base=kpis_castra,
            df_mes=df_mes, df_fluxo_historico=df_fluxo_historico, df_departamentos=df_departamentos,
        )
        show_legacy_warning = date_start is None or date_start < DATA_CORTE_LEGADO
        warning_style = {} if show_legacy_warning else {'display': 'none'}
        back_link_style = {'display': 'none'}

    base = (hero, kpi_row, entry_section, entry_style, rest_content, warning_style, back_link_style)

    if ctx.triggered_id == 'dash-btn-limpar':
        return base + (date_start, date_end, quick_filter)

    if ctx.triggered_id == 'dash-btn-remover-legado':
        return base + (date_start, dash.no_update, dash.no_update)

    return base + (dash.no_update, dash.no_update, dash.no_update)


# ─── KPI Card Helper ────────────────────────────────────────────────────────
def kpi_card(value, label, variant='blue', icon=''):
    return html.Div([
        html.Div(icon, className=f'kpi-card__icon') if icon else html.Div(''),
        html.Div(label, className='kpi-card__label'),
        html.Div(value, className='kpi-card__value'),
    ], className=f'kpi-card kpi-card--{variant}')


# ─── Tab: Dashboard (réplica visual SEMMA) ──────────────────────────────────
def apply_especie_override(kpis_base, date_from, date_to, local, servico, weekend_only, especie_id):
    """
    Substitui vagas_ocupadas/scheduled/checked_in/em_fila pelo recorte de
    espécie (Cão/Gato), mantendo os demais campos (total_vagas, vagas_livres,
    taxa_ocupacao, nao_compareceram) como estavam — não existe um recorte de
    espécie que faça sentido pra "vaga livre"/"taxa de ocupação" (a vaga só
    passa a ser de um animal quando ocupada).
    """
    if not especie_id:
        return kpis_base
    especie_kpis = get_kpis_por_especie(date_from, date_to, local, servico, weekend_only, especie_id)
    merged = dict(kpis_base)
    merged.update(especie_kpis)
    return merged


def render_dashboard_tab(date_start, date_end, quick_filter, local_filter=None, servico_filter=None, especie_id=None,
                          kpis_all_base=None, kpis_vacina_base=None, kpis_castra_base=None,
                          df_mes=None, df_fluxo_historico=None, df_departamentos=None):
    date_from = date_start or None
    date_to = date_end or None
    weekend_only = quick_filter == 'weekend'

    # *_base são opcionais: quando render_dashboard já buscou esses mesmos
    # dados (numa leva maior, em paralelo com "Portas de entrada"/hero),
    # reaproveita em vez de repetir a consulta — só busca aqui se ninguém
    # passou nada pronto.
    if kpis_all_base is not None and kpis_vacina_base is not None and kpis_castra_base is not None:
        kpis_all, kpis_vacina, kpis_castra = kpis_all_base, kpis_vacina_base, kpis_castra_base
    else:
        # As 3 consultas de KPI são independentes entre si (serviços diferentes) —
        # rodam em paralelo em vez de em série.
        kpis_all, kpis_vacina, kpis_castra = parallel(
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, servico_filter, weekend_only),
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Vacinação', weekend_only),
            lambda: get_kpis_fact_resumo(date_from, date_to, local_filter, 'Castração', weekend_only),
        )

    if especie_id:
        kpis_all, kpis_vacina, kpis_castra = parallel(
            lambda: apply_especie_override(kpis_all, date_from, date_to, local_filter, servico_filter, weekend_only, especie_id),
            lambda: apply_especie_override(kpis_vacina, date_from, date_to, local_filter, 'Vacinação', weekend_only, especie_id),
            lambda: apply_especie_override(kpis_castra, date_from, date_to, local_filter, 'Castração', weekend_only, especie_id),
        )

    if df_mes is None or df_fluxo_historico is None or df_departamentos is None:
        df_mes, df_fluxo_historico, df_departamentos = parallel(
            lambda: get_atendimentos_por_mes(date_from, date_to, local_filter, weekend_only),
            lambda: get_fluxo_historico_departamentos(date_from, date_to, local_filter, 'Castração', weekend_only),
            lambda: get_departamentos_configurados('Castração'),
        )

    # "Portas de entrada" (build_entry_section) NÃO entra aqui — é renderizada
    # à parte pelo callback principal, num container sempre presente no DOM
    # (ver comentário em app.layout / entry-section-container).
    kpi_row = build_kpi_row(kpis_all, kpis_vacina, kpis_castra, quick_filter)
    rest = html.Div([
        build_month_chart(df_mes, quick_filter, servico_filter),
        html.Div([
            build_capacity_card(kpis_all),
            build_flow_card(df_fluxo_historico, df_departamentos),
        ], className='sv2-bottom-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})
    return kpi_row, rest


def build_hero(totais):
    def stat(icon, label, value, sub):
        return html.Div([
            html.Div([html.Span(icon), html.Span(label)], className='sv2-hero__stat-label'),
            html.Div(format_number(value), className='sv2-hero__stat-value'),
            html.Div(sub, className='sv2-hero__stat-sub'),
        ], className='sv2-hero__stat')

    return html.Div([
        html.Div([
            html.Div('O cuidado de hoje, em uma única leitura.', className='sv2-hero__title'),
            html.Div(
                'Acompanhe capacidade, execução e desfechos dos atendimentos de vacinação e '
                'castração, sem perder de vista cada etapa da jornada.',
                className='sv2-hero__subtitle'
            ),
        ]),
        html.Div([
            stat('✂️', 'Castrações', totais.get('Castração', 0), 'total acumulado'),
            stat('💉', 'Vacinação', totais.get('Vacinação', 0), 'doses acumuladas'),
        ], className='sv2-hero__stats'),
    ], className='sv2-hero')


def sv2_kpi_card(icon_class, icon_bg, icon_color, label, value):
    return html.Div([
        html.Div([
            html.Div(
                html.I(className=icon_class),
                className='sv2-kpi-card__icon',
                style={'background': icon_bg, 'color': icon_color}
            ),
            html.Div(label, className='sv2-kpi-card__label'),
        ], className='sv2-kpi-card__top'),
        html.Div(value, className='sv2-kpi-card__value'),
    ], className='sv2-kpi-card')


def build_kpi_row(kpis_all, kpis_vacina, kpis_castra, quick_filter=None):
    # Com qualquer filtro rápido além de "Todos" (Centro de Zoonoses ou Fim de
    # semana), o serviço funciona por agendamento — em vez do total genérico de
    # "Castrações", separa o que já foi realizado (compareceu/checked-in) do
    # que ainda está agendado para os próximos dias.
    if quick_filter in ('zoonoses', 'weekend'):
        return html.Div([
            sv2_kpi_card('fa-solid fa-paw', '#E7F2EA', 'var(--sv2-green-700)',
                         'Castrações realizadas', format_number(kpis_castra['vagas_checked_in'])),
            sv2_kpi_card('fa-solid fa-syringe', '#E7F2EA', 'var(--sv2-green-700)',
                         'Vacinações aplicadas', format_number(kpis_vacina['vagas_ocupadas'])),
            sv2_kpi_card('fa-regular fa-calendar-check', '#E7F2EA', 'var(--sv2-green-700)',
                         'Castrações agendadas', format_number(kpis_castra['vagas_scheduled'])),
            sv2_kpi_card('fa-regular fa-clock', '#FDEEF0', '#C1447E',
                         'Fila de castração', format_number(kpis_castra['em_fila'])),
        ], className='sv2-kpi-grid')

    return html.Div([
        sv2_kpi_card('fa-solid fa-calendar-days', '#E7F2EA', 'var(--sv2-green-700)',
                     'Atendimentos totais', format_number(kpis_all['vagas_ocupadas'])),
        sv2_kpi_card('fa-solid fa-syringe', '#E7F2EA', 'var(--sv2-green-700)',
                     'Vacinações totais', format_number(kpis_vacina['vagas_ocupadas'])),
        sv2_kpi_card('fa-solid fa-paw', '#E7F2EA', 'var(--sv2-green-700)',
                     'Castrações totais', format_number(kpis_castra['vagas_ocupadas'])),
        sv2_kpi_card('fa-regular fa-clock', '#FDEEF0', '#C1447E',
                     'Fila de castração', format_number(kpis_castra['em_fila'])),
    ], className='sv2-kpi-grid')


def sv2_entry_card(icon_class, badge_text, title, desc, stats, expand_id=None):
    # O clique fica no CARTÃO INTEIRO (não só na setinha) — a setinha continua
    # só como indicação visual, sem id/n_clicks próprio; o clique nela borbulha
    # pro cartão do mesmo jeito.
    card_kwargs = {'id': expand_id, 'n_clicks': 0} if expand_id else {}
    return html.Div([
        html.Div([
            html.Div(html.I(className=icon_class), className='sv2-entry-card__icon'),
            html.Div(badge_text, className='sv2-entry-card__badge'),
            html.Div('↗', className='sv2-entry-card__expand'),
        ], className='sv2-entry-card__top'),
        html.Div([
            html.Div(title, className='sv2-entry-card__title'),
            html.Div(desc, className='sv2-entry-card__desc'),
            html.Div([
                html.Div([
                    html.Div(s_label, className='sv2-stat-label'),
                    html.Div(format_number(s_value), className='sv2-stat-value'),
                ]) for s_label, s_value in stats
            ], className='sv2-entry-card__stats'),
        ], className='sv2-entry-card__body'),
    ], className='sv2-entry-card', **card_kwargs)


def build_entry_section(kpis_vacina, especies, kpis_castra):
    vacina_card = sv2_entry_card(
        'fa-solid fa-syringe',
        f"{format_number(kpis_vacina['vagas_ocupadas'])} aplicadas",
        'Vacinação',
        'Aplicação por demanda espontânea: acompanhe cobertura, doses aplicadas e estoque das campanhas.',
        [
            ('Doses aplicadas', kpis_vacina['vagas_ocupadas']),
            ('Caninos', especies.get('Canino', 0)),
            ('Felinos', especies.get('Felino', 0)),
        ],
        expand_id='btn-abrir-vacinacao'
    )
    castracao_card = sv2_entry_card(
        'fa-solid fa-paw',
        f"{format_number(kpis_castra['em_fila'])} em fila",
        'Castração',
        'Acompanhe a jornada pré-operatória, a execução do procedimento e as altas.',
        [
            ('Realizadas', kpis_castra['vagas_ocupadas']),
            ('Vagas livres', kpis_castra['vagas_livres']),
            ('Em fila', kpis_castra['em_fila']),
        ],
        expand_id='btn-abrir-castracao'
    )
    return html.Div([
        html.Div([
            html.Div([
                html.Div('Portas de entrada', className='sv2-card__eyebrow'),
                html.Div('Escolha um serviço para aprofundar a operação', className='sv2-card__title'),
            ]),
            html.Div('Clique para abrir os dados específicos', className='sv2-entry-hint'),
        ], className='sv2-card__header-row'),
        html.Div([vacina_card, castracao_card], className='sv2-entry-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '12px'})


def build_month_chart(df_mes, quick_filter=None, servico_filter=None):
    chart_title = 'Atendimentos no centro de zoonoses' if quick_filter == 'zoonoses' else 'Atendimentos por mês'
    total_vac = total_cas = 0
    if df_mes is None or df_mes.empty:
        fig = create_empty_figure()
    else:
        pivot = df_mes.pivot_table(
            index='ano_mes', columns='servico', values='total_ocupadas', aggfunc='sum', fill_value=0
        ).sort_index()
        mes_labels = [MESES_PT.get(idx[5:7], idx) for idx in pivot.index]
        vac_vals = pivot['Vacinação'] if 'Vacinação' in pivot.columns else [0] * len(pivot)
        cas_vals = pivot['Castração'] if 'Castração' in pivot.columns else [0] * len(pivot)
        # Filtro avançado "Serviço": mostra só a barra do serviço escolhido.
        if servico_filter == 'Vacinação':
            cas_vals = [0] * len(pivot)
        elif servico_filter == 'Castração':
            vac_vals = [0] * len(pivot)
        total_vac = int(sum(vac_vals))
        total_cas = int(sum(cas_vals))

        fig = go.Figure()
        fig.add_trace(go.Bar(x=mes_labels, y=vac_vals, name='Vacinação',
                              marker=dict(color='#1F9E4D', cornerradius=6),
                              text=vac_vals, textposition='outside'))
        fig.add_trace(go.Bar(x=mes_labels, y=cas_vals, name='Castração',
                              marker=dict(color='#A9D9BB', cornerradius=6),
                              text=cas_vals, textposition='outside'))
        fig.update_layout(
            barmode='group',
            bargap=0.4,
            bargroupgap=0.05,
            paper_bgcolor='white', plot_bgcolor='white',
            font=dict(family='Inter, sans-serif', color='#1F2937'),
            margin=dict(l=12, r=12, t=12, b=12),
            height=280,
            showlegend=False,
            # Sem zoom por arraste (clicar e arrastar não deve distorcer o
            # gráfico) — mantém só o hover, que é inofensivo.
            dragmode=False,
            xaxis=dict(showgrid=False, fixedrange=True),
            yaxis=dict(
                showgrid=True, gridcolor='#F3F4F6', showticklabels=True,
                tickfont=dict(size=11, color='#9CA3AF'), fixedrange=True
            ),
        )

    return html.Div([
        html.Div([
            html.Div([
                html.Div('Volume do período', className='sv2-card__eyebrow'),
                html.Div(chart_title, className='sv2-card__title'),
            ]),
            html.Div([
                html.Span(f'■ Vacinação  {format_number(total_vac)}',
                          style={'color': '#1F9E4D', 'fontWeight': 700, 'marginRight': '16px'}),
                html.Span(f'■ Castração  {format_number(total_cas)}',
                          style={'color': '#A9D9BB', 'fontWeight': 700}),
            ]),
        ], className='sv2-card__header-row'),
        dcc.Graph(figure=fig, config={'displayModeBar': False}),
    ], className='sv2-card')


def sv2_mini_stat(label, value):
    return html.Div([
        html.Div(label, className='sv2-stat-label'),
        html.Div(format_number(value), className='sv2-stat-value'),
    ])


def build_capacity_card(kpis_all):
    pct = kpis_all.get('taxa_ocupacao', 0) or 0
    ring_style = {
        'background': f'conic-gradient(#146C33 0%, #146C33 {pct}%, #E5ECE7 {pct}%, #E5ECE7 100%)'
    }
    return html.Div([
        html.Div([
            html.Div([
                html.Div('Capacidade agregada', className='sv2-card__eyebrow'),
                html.Div('Vagas e demanda do período', className='sv2-card__title'),
            ]),
            html.Div(f'{pct}% ocupado', className='sv2-badge-pct'),
        ], className='sv2-card__header-row'),
        html.Div([
            html.Div(
                html.Div([
                    html.Div(f'{pct}%', className='sv2-donut-inner__pct'),
                    html.Div('OCUPADO', className='sv2-donut-inner__label'),
                ], className='sv2-donut-inner'),
                className='sv2-donut-ring', style=ring_style
            ),
            html.Div([
                sv2_mini_stat('Vagas totais', kpis_all['total_vagas']),
                sv2_mini_stat('Ocupadas', kpis_all['vagas_ocupadas']),
                sv2_mini_stat('Livres', kpis_all['vagas_livres']),
                sv2_mini_stat('Em fila', kpis_all['em_fila']),
            ], className='sv2-capacity-stats'),
        ], className='sv2-capacity-body'),
    ], className='sv2-card')


def build_flow_card(df_fluxo, df_departamentos=None):
    # Quantidade real por departamento, a partir do HISTÓRICO de movimentação
    # (log_call_queue_department) — não do snapshot atual da fila. O snapshot
    # só guarda o status ATUAL de cada item, então uma etapa "de passagem"
    # (ex: Recepção, antes de avançar) apareceria zerada ali mesmo com
    # movimento real. Usa o MAIOR valor entre os status do departamento — o
    # primeiro status ao entrar é sempre o pico (quem chega, depois "vaza"
    # pros status seguintes, então a contagem só cai ou mantém).
    quantidades = {}
    if df_fluxo is not None and not df_fluxo.empty:
        agg = df_fluxo.groupby('departamento')['quantidade'].max()
        for nome, qtd in agg.items():
            quantidades[nome] = int(qtd)

    if df_departamentos is not None and not df_departamentos.empty:
        # Sempre mostra TODAS as etapas cadastradas para o serviço (mesmo as que
        # ainda não tiveram nenhum atendimento passar por elas) — evita a etapa
        # simplesmente desaparecer do card quando a fila real ainda está vazia.
        rows = df_departamentos.sort_values('ordem_fluxo').itertuples(index=False)
        steps = [(r.departamento, quantidades.get(r.departamento, 0)) for r in rows]
    elif quantidades:
        rows = df_fluxo.groupby(['departamento', 'ordem_fluxo'], as_index=False)['quantidade'].max() \
            .sort_values('ordem_fluxo').itertuples(index=False)
        steps = [(r.departamento, r.quantidade) for r in rows]
    else:
        steps = []

    if not steps:
        body = html.Div('Sem dados para exibir', className='empty-state')
    else:
        max_val = max((qtd for _, qtd in steps), default=1) or 1

        step_divs = []
        for i, (nome, qtd) in enumerate(steps, start=1):
            pct = round((qtd / max_val) * 100, 1)
            step_divs.append(html.Div([
                html.Div(str(i), className='sv2-flow-step__badge'),
                html.Div(nome, className='sv2-flow-step__label'),
                html.Div(format_number(qtd), className='sv2-flow-step__value'),
                html.Div(
                    html.Div(className='sv2-flow-step__fill', style={'width': f'{pct}%'}),
                    className='sv2-flow-step__track'
                ),
            ], className='sv2-flow-step'))
        body = html.Div(step_divs, className='sv2-flow-grid')

    return html.Div([
        html.Div([
            html.Div('Fluxo de atendimento', className='sv2-card__eyebrow'),
            html.Div('Etapas de Castração', className='sv2-card__title'),
        ], className='sv2-card__header-row'),
        body,
    ], className='sv2-card')


# ─── Tela de detalhe: Vacinação (réplica visual SEMMA) ─────────────────────
# Só usa categorias que existem de verdade no sistema. Onde o mockup do
# cliente tinha algo que não é rastreado aqui (ex: "recusada pelo tutor"),
# a tela mostra só o que é real (ver conversa/decisão registrada com o
# cliente): Desfechos = Compareceu/Agendado; Composição das doses aparece
# mesmo com 1 categoria só; Distribuição territorial = Top 5 + "Outros".
def build_hero_vacinacao(kpis_vacina, totais):
    # kpis_vacina/totais já vêm calculados de render_dashboard (em paralelo com
    # o restante da tela) — evita repetir a mesma consulta que render_vacinacao_tab
    # já faz logo em seguida.
    def stat(label, value, sub):
        return html.Div([
            html.Div(label, className='sv2-hero__stat-label'),
            html.Div(format_number(value), className='sv2-hero__stat-value'),
            html.Div(sub, className='sv2-hero__stat-sub'),
        ], className='sv2-hero__stat')

    return html.Div([
        html.Div([
            html.Div(html.I(className='fa-solid fa-syringe'), className='sv2-hero__icon-badge'),
            html.Div([
                html.Div('Vacinação', className='sv2-hero__title'),
                html.Div('Aplicação por demanda espontânea, sem agendamento', className='sv2-hero__subtitle'),
            ]),
        ], className='sv2-hero__title-row'),
        html.Div([
            stat('No período', kpis_vacina['vagas_ocupadas'], 'doses aplicadas'),
            stat('Acumulado', totais.get('Vacinação', 0), 'doses no total'),
        ], className='sv2-hero__stats'),
    ], className='sv2-hero')


def render_vacinacao_tab(date_start, date_end, quick_filter, local_filter=None, especie_id=None, kpis_vacina_base=None):
    date_from = date_start or None
    date_to = date_end or None
    local_filter = local_filter or (LOCAL_CENTRO_ZOONOSES if quick_filter == 'zoonoses' else None)
    weekend_only = quick_filter == 'weekend'

    # kpis_vacina_base é opcional: quando render_dashboard já calculou esse
    # mesmo KPI (pro hero, em paralelo), reaproveita em vez de repetir a
    # consulta — só recalcula aqui se ninguém passou nada pronto.
    kpis_vacina = kpis_vacina_base if kpis_vacina_base is not None else \
        get_kpis_fact_resumo(date_from, date_to, local_filter, 'Vacinação', weekend_only)
    if especie_id:
        # Espécie entra só nas "Doses aplicadas" (o KPI principal) — Locais
        # atendidos/Desfechos/Composição/Distribuição territorial continuam
        # olhando para todas as espécies juntas por enquanto.
        kpis_vacina = apply_especie_override(
            kpis_vacina, date_from, date_to, local_filter, 'Vacinação', weekend_only, especie_id
        )
    # As 5 consultas abaixo são independentes entre si — rodam em paralelo.
    locais_atendidos, desfechos, df_perfil, df_composicao, df_territorial = parallel(
        lambda: get_locais_atendidos(date_from, date_to, local_filter, weekend_only, 'Vacinação'),
        lambda: get_desfechos_agendamento(date_from, date_to, local_filter, weekend_only, 'Vacinação'),
        lambda: get_perfil_animais(date_from, date_to, local_filter, weekend_only, 'Vacinação'),
        lambda: get_composicao_doses(date_from, date_to, local_filter, weekend_only),
        lambda: get_distribuicao_territorial(date_from, date_to, local_filter, weekend_only, 'Vacinação'),
    )

    doses_aplicadas = kpis_vacina['vagas_ocupadas']
    media_por_posto = round(doses_aplicadas / locais_atendidos) if locais_atendidos else 0
    total_desfecho = desfechos['checked_in'] + desfechos['scheduled']
    taxa_aplicacao = round(desfechos['checked_in'] / total_desfecho * 100, 1) if total_desfecho else 0

    kpi_row = build_vacinacao_kpi_row(doses_aplicadas, locais_atendidos, media_por_posto, taxa_aplicacao)
    rest = html.Div([
        html.Div([
            build_desfechos_card(desfechos),
            build_perfil_animais_card(df_perfil),
        ], className='sv2-bottom-row'),
        html.Div([
            build_composicao_doses_card(df_composicao),
            build_distribuicao_territorial_card(df_territorial),
        ], className='sv2-bottom-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})
    return kpi_row, rest


def build_vacinacao_kpi_row(doses_aplicadas, locais_atendidos, media_por_posto, taxa_aplicacao):
    return html.Div([
        sv2_kpi_card('fa-solid fa-syringe', '#E7F2EA', 'var(--sv2-green-700)',
                     'Doses aplicadas', format_number(doses_aplicadas)),
        sv2_kpi_card('fa-solid fa-location-dot', '#E7F2EA', 'var(--sv2-green-700)',
                     'Locais atendidos', format_number(locais_atendidos)),
        sv2_kpi_card('fa-solid fa-chart-column', '#E7F2EA', 'var(--sv2-green-700)',
                     'Média por posto', format_number(media_por_posto)),
        sv2_kpi_card('fa-solid fa-percent', '#E7F2EA', 'var(--sv2-green-700)',
                     'Taxa de aplicação', f'{taxa_aplicacao}%'),
    ], className='sv2-kpi-grid')


def build_bar_row(color, label, value, pct):
    # O número/percentual mostrado continua exato (ex: "4  0.0%" quando o valor
    # é mesmo residual) — só a LARGURA VISUAL da barra tem um mínimo, senão
    # qualquer valor pequeno-mas-real (ex: 4 de 14.914 = 0,03%) desenha uma
    # barra com largura 0%, que parece vazia/quebrada mesmo tendo dado.
    bar_width = max(pct, 1.5) if value else 0
    return html.Div([
        html.Div([
            html.Div([
                html.Span(className='sv2-bar-row__dot', style={'background': color}),
                html.Span(label, className='sv2-bar-row__label'),
            ], className='sv2-bar-row__left'),
            html.Div(f'{format_number(value)}  {pct}%', className='sv2-bar-row__value'),
        ], className='sv2-bar-row__top'),
        html.Div(
            html.Div(className='sv2-bar-row__fill', style={'width': f'{bar_width}%', 'background': color}),
            className='sv2-bar-row__track'
        ),
    ], className='sv2-bar-row')


def build_desfechos_card(desfechos):
    total = desfechos['checked_in'] + desfechos['scheduled']

    def pct(v):
        return round(v / total * 100, 1) if total else 0

    rows = [
        build_bar_row('#1F9E4D', 'Compareceu', desfechos['checked_in'], pct(desfechos['checked_in'])),
        build_bar_row('#3F99CD', 'Agendado', desfechos['scheduled'], pct(desfechos['scheduled'])),
    ]
    return html.Div([
        html.Div([
            html.Div('Desfechos', className='sv2-card__eyebrow'),
            html.Div('Resultado dos atendimentos', className='sv2-card__title'),
        ]),
        html.Div(rows, className='sv2-bar-row-list'),
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


def build_perfil_animais_card(df_perfil):
    if df_perfil is None or df_perfil.empty:
        body = html.Div('Sem dados para exibir', className='empty-state')
    else:
        sections = []
        for especie, especie_label in [('Canino', 'Caninos'), ('Felino', 'Felinos')]:
            sub = df_perfil[df_perfil['especie'] == especie]
            femeas = int(sub[sub['sexo'] == 'F']['total'].sum())
            machos = int(sub[sub['sexo'] == 'M']['total'].sum())
            total_especie = femeas + machos
            if total_especie == 0:
                continue
            pct_f = round(femeas / total_especie * 100, 1)
            pct_m = round(machos / total_especie * 100, 1)
            sections.append(html.Div([
                html.Div(f'{especie_label} — {format_number(total_especie)} animais',
                          className='sv2-perfil__especie-title'),
                build_bar_row('#DE6E6E', 'Fêmeas', femeas, pct_f),
                build_bar_row('#3F99CD', 'Machos', machos, pct_m),
            ], className='sv2-perfil__especie'))
        body = html.Div(sections, className='sv2-bar-row-list') if sections \
            else html.Div('Sem dados para exibir', className='empty-state')

    return html.Div([
        html.Div([
            html.Div('Perfil dos animais', className='sv2-card__eyebrow'),
            html.Div('Fêmeas e machos por espécie', className='sv2-card__title'),
        ]),
        body,
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


def build_composicao_doses_card(df_composicao):
    if df_composicao is None or df_composicao.empty:
        return html.Div([
            html.Div('Composição das doses', className='sv2-card__eyebrow'),
            html.Div('Vacinas aplicadas por tipo', className='sv2-card__title'),
            html.Div('Sem dados para exibir', className='empty-state'),
        ], className='sv2-card')

    total = int(df_composicao['total'].sum())
    colors = ['#1F9E4D', '#3F99CD', '#8B5CF6', '#F5A623', '#EF4444', '#94A3B8']
    labels = df_composicao['tipo_vacina'].tolist()
    values = [int(v) for v in df_composicao['total'].tolist()]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68,
        marker=dict(colors=colors[:len(labels)]),
        textinfo='none', sort=False
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=160, width=160,
        dragmode=False,
        annotations=[dict(
            text=f'{format_number(total)}<br><span style="font-size:10px;color:#8B9A95">DOSES</span>',
            showarrow=False, font=dict(size=18, color='#1F2937')
        )]
    )

    legend_rows = []
    for i, (label, value) in enumerate(zip(labels, values)):
        pct = round(value / total * 100, 1) if total else 0
        legend_rows.append(html.Div([
            html.Span(className='sv2-legend-dot', style={'background': colors[i % len(colors)]}),
            html.Span(label, className='sv2-legend-label'),
            html.Span(f'{format_number(value)}  {pct}%', className='sv2-legend-value'),
        ], className='sv2-legend-row'))

    return html.Div([
        html.Div([
            html.Div('Composição das doses', className='sv2-card__eyebrow'),
            html.Div('Vacinas aplicadas por tipo', className='sv2-card__title'),
        ]),
        html.Div([
            dcc.Graph(figure=fig, config={'displayModeBar': False}, style={'flexShrink': 0}),
            html.Div(legend_rows, className='sv2-legend-list'),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '20px', 'flexWrap': 'wrap'}),
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


def build_distribuicao_territorial_card(df_territorial, unidade_label='DOSES', titulo='Doses aplicadas por unidade'):
    if df_territorial is None or df_territorial.empty:
        body = html.Div('Sem dados para exibir', className='empty-state')
    else:
        df_sorted = df_territorial.sort_values('total', ascending=False).reset_index(drop=True)
        total_geral = int(df_sorted['total'].sum())
        top5 = df_sorted.head(5)
        outros_total = int(df_sorted['total'][5:].sum())

        rows = [(r.local_nome, int(r.total)) for r in top5.itertuples(index=False)]
        if outros_total > 0:
            rows.append(('Outros', outros_total))

        row_divs = [html.Div([
            html.Div('UNIDADE', className='sv2-territorial__head'),
            html.Div(unidade_label, className='sv2-territorial__head sv2-territorial__head--num'),
            html.Div('PART.', className='sv2-territorial__head sv2-territorial__head--num'),
        ], className='sv2-territorial__row sv2-territorial__row--head')]

        for nome, qtd in rows:
            pct = round(qtd / total_geral * 100, 1) if total_geral else 0
            row_divs.append(html.Div([
                html.Div(nome, className='sv2-territorial__name'),
                html.Div(format_number(qtd), className='sv2-territorial__num'),
                html.Div(f'{pct}%', className='sv2-territorial__num'),
            ], className='sv2-territorial__row'))

        row_divs.append(html.Div([
            html.Div('Total', className='sv2-territorial__name sv2-territorial__row--total'),
            html.Div(format_number(total_geral), className='sv2-territorial__num sv2-territorial__row--total'),
            html.Div('100%', className='sv2-territorial__num sv2-territorial__row--total'),
        ], className='sv2-territorial__row'))

        body = html.Div(row_divs, className='sv2-territorial-table')

    return html.Div([
        html.Div([
            html.Div('Distribuição territorial', className='sv2-card__eyebrow'),
            html.Div(titulo, className='sv2-card__title'),
        ]),
        body,
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


# ─── Tela de detalhe: Castração (réplica visual SEMMA) ─────────────────────
# Mesma regra das telas anteriores: só usa categorias que existem de verdade.
# "Desfechos" aqui bateu quase 100% com o design porque o sistema real já
# rastreia status de nome igual (Aprovado/Reprovado/Desistente) — só
# "Tutor ausente" vem de outra fonte (nao_compareceram) e "Em andamento"
# junta Aguardando+Chamando. "Fluxo de atendimento" continua com as 2 etapas
# reais (Recepção + Assinatura de Termo), não as 5 do mockup genérico —
# já confirmado com o cliente na tela de panorama.
def build_hero_castracao(kpis_castra, totais):
    # kpis_castra/totais já vêm calculados de render_dashboard (em paralelo com
    # o restante da tela) — evita repetir a mesma consulta que render_castracao_tab
    # já faz logo em seguida.
    def stat(label, value, sub):
        return html.Div([
            html.Div(label, className='sv2-hero__stat-label'),
            html.Div(format_number(value), className='sv2-hero__stat-value'),
            html.Div(sub, className='sv2-hero__stat-sub'),
        ], className='sv2-hero__stat')

    return html.Div([
        html.Div([
            html.Div(html.I(className='fa-solid fa-paw'), className='sv2-hero__icon-badge'),
            html.Div([
                html.Div('Castração', className='sv2-hero__title'),
                html.Div('Da recepção à alta, com agenda e fila de espera', className='sv2-hero__subtitle'),
            ]),
        ], className='sv2-hero__title-row'),
        html.Div([
            stat('No período', kpis_castra['vagas_ocupadas'], 'castrações realizadas'),
            stat('Acumulado', totais.get('Castração', 0), 'castrações no total'),
        ], className='sv2-hero__stats'),
    ], className='sv2-hero')


def render_castracao_tab(date_start, date_end, quick_filter, local_filter=None, especie_id=None, kpis_castra_base=None):
    date_from = date_start or None
    date_to = date_end or None
    local_filter = local_filter or (LOCAL_CENTRO_ZOONOSES if quick_filter == 'zoonoses' else None)
    weekend_only = quick_filter == 'weekend'

    # kpis_castra_base é opcional: quando render_dashboard já calculou esse
    # mesmo KPI (pro hero, em paralelo), reaproveita em vez de repetir a
    # consulta — só recalcula aqui se ninguém passou nada pronto.
    kpis_castra = kpis_castra_base if kpis_castra_base is not None else \
        get_kpis_fact_resumo(date_from, date_to, local_filter, 'Castração', weekend_only)
    if especie_id:
        # Espécie entra só nas "Agendadas"/"Vagas livres"/"Comparecimento" (os
        # KPIs principais) — Desfechos/Fluxo/Distribuição territorial continuam
        # olhando para todas as espécies juntas por enquanto.
        kpis_castra = apply_especie_override(
            kpis_castra, date_from, date_to, local_filter, 'Castração', weekend_only, especie_id
        )
    # As 4 consultas abaixo são independentes entre si — rodam em paralelo.
    df_fluxo, df_fluxo_historico, df_departamentos, df_perfil, df_territorial = parallel(
        lambda: get_fluxo_departamentos(date_from, date_to, local_filter, 'Castração', weekend_only),
        lambda: get_fluxo_historico_departamentos(date_from, date_to, local_filter, 'Castração', weekend_only),
        lambda: get_departamentos_configurados('Castração'),
        lambda: get_perfil_animais(date_from, date_to, local_filter, weekend_only, 'Castração'),
        lambda: get_distribuicao_territorial(date_from, date_to, local_filter, weekend_only, 'Castração'),
    )

    total_checked_in = kpis_castra['vagas_checked_in']
    total_scheduled = kpis_castra['vagas_scheduled']
    comparecimento = round(total_checked_in / (total_checked_in + total_scheduled) * 100, 1) \
        if (total_checked_in + total_scheduled) else 0

    kpi_row = build_castracao_kpi_row(kpis_castra, comparecimento)
    rest = html.Div([
        html.Div([
            build_desfechos_castracao_card(df_fluxo, kpis_castra['nao_compareceram']),
            build_perfil_animais_card(df_perfil),
        ], className='sv2-bottom-row'),
        html.Div([
            build_fluxo_funil_card(df_fluxo, df_fluxo_historico, df_departamentos),
            build_distribuicao_territorial_card(
                df_territorial, unidade_label='CASTRAÇÕES', titulo='Castrações por unidade'
            ),
        ], className='sv2-bottom-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})
    return kpi_row, rest


def build_castracao_kpi_row(kpis_castra, comparecimento):
    return html.Div([
        sv2_kpi_card('fa-regular fa-calendar-check', '#E7F2EA', 'var(--sv2-green-700)',
                     'Agendadas', format_number(kpis_castra['vagas_scheduled'])),
        sv2_kpi_card('fa-solid fa-door-open', '#E7F2EA', 'var(--sv2-green-700)',
                     'Vagas livres', format_number(kpis_castra['vagas_livres'])),
        sv2_kpi_card('fa-regular fa-clock', '#FDEEF0', '#C1447E',
                     'Em fila', format_number(kpis_castra['em_fila'])),
        sv2_kpi_card('fa-solid fa-percent', '#E7F2EA', 'var(--sv2-green-700)',
                     'Comparecimento', f'{comparecimento}%'),
    ], className='sv2-kpi-grid')


def build_desfechos_castracao_card(df_fluxo, nao_compareceram):
    valores = {'Concluído': 0, 'Em andamento': 0, 'Desistente': 0, 'Reprovado': 0}
    if df_fluxo is not None and not df_fluxo.empty:
        by_status = df_fluxo.groupby('status')['quantidade'].sum()
        valores['Concluído'] = int(by_status.get('Aprovado', 0))
        valores['Em andamento'] = int(by_status.get('Aguardando', 0)) + int(by_status.get('Chamando', 0)) \
            + int(by_status.get('Em Atendimento', 0))
        valores['Desistente'] = int(by_status.get('Desistente', 0))
        valores['Reprovado'] = int(by_status.get('Reprovado', 0))
    valores['Tutor ausente'] = int(nao_compareceram or 0)

    total = sum(valores.values())

    def pct(v):
        return round(v / total * 100, 1) if total else 0

    cores = {
        'Concluído': '#1F9E4D', 'Em andamento': '#F5A623',
        'Desistente': '#94A3B8', 'Reprovado': '#EF4444', 'Tutor ausente': '#CBD5E1',
    }
    rows = [build_bar_row(cores[label], label, valor, pct(valor)) for label, valor in valores.items()]

    return html.Div([
        html.Div([
            html.Div('Desfechos', className='sv2-card__eyebrow'),
            html.Div('Resultado dos atendimentos', className='sv2-card__title'),
        ]),
        html.Div(rows, className='sv2-bar-row-list'),
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


def build_fluxo_funil_card(df_fluxo, df_fluxo_historico, df_departamentos):
    # O número principal de cada etapa vem do HISTÓRICO de movimentação
    # (log_call_queue_department), não do snapshot atual da fila: sk_call_queue
    # só guarda o status ATUAL de cada item, então uma etapa "de passagem" (ex:
    # Recepção, antes de avançar para Assinatura de Termo) apareceria zerada ali
    # mesmo com movimento real. Usamos o maior valor entre os status de cada
    # departamento no histórico — o primeiro status ao entrar é sempre o pico.
    quantidades = {}
    if df_fluxo_historico is not None and not df_fluxo_historico.empty:
        agg_hist = df_fluxo_historico.groupby('departamento')['quantidade'].max()
        for nome, qtd in agg_hist.items():
            quantidades[nome] = int(qtd)

    # "Aguardando" é o único número que faz sentido tirar do snapshot ATUAL
    # (quem está esperando agora, nesse instante) — não do histórico.
    aguardando = {}
    if df_fluxo is not None and not df_fluxo.empty:
        agg_wait = df_fluxo.groupby('departamento')['qtd_waiting'].sum()
        for nome, qtd in agg_wait.items():
            aguardando[nome] = int(qtd)

    if df_departamentos is not None and not df_departamentos.empty:
        rows = df_departamentos.sort_values('ordem_fluxo').itertuples(index=False)
        steps = [(r.departamento, quantidades.get(r.departamento, 0), aguardando.get(r.departamento, 0))
                 for r in rows]
    else:
        steps = []

    if not steps:
        body = html.Div('Sem dados para exibir', className='empty-state')
    else:
        step_divs = []
        for i, (nome, qtd, esperando) in enumerate(steps, start=1):
            step_divs.append(html.Div([
                html.Div(format_number(qtd), className='sv2-funnel-flow__circle'),
                html.Div(nome, className='sv2-funnel-flow__label'),
                html.Div(f'↓ {format_number(esperando)} aguardando', className='sv2-funnel-flow__sub'),
            ], className='sv2-funnel-flow__step'))
        body = html.Div(step_divs, className='sv2-funnel-flow')

    return html.Div([
        html.Div([
            html.Div('Fluxo de atendimento', className='sv2-card__eyebrow'),
            html.Div('Etapas da castração', className='sv2-card__title'),
        ]),
        html.Div('Quantos animais já passaram por cada etapa no período', className='sv2-card__desc'),
        body,
    ], className='sv2-card', style={'display': 'flex', 'flexDirection': 'column', 'gap': '20px'})


# ─── Tab: Departamentos ─────────────────────────────────────────────────────
def render_departamentos_tab(local, servico, departamento, date_from, date_to):
    df_fluxo = get_fluxo_departamentos(date_from, date_to, local, servico)
    df_fila = get_fila_temporal(date_from, date_to, local, servico, departamento)

    fig_fila_dept = create_fila_por_departamento_chart(df_fila)
    fig_status_dept = create_status_por_departamento_chart(df_fila)
    tabela_fluxo = create_fluxo_table(df_fluxo)

    return html.Div([
        html.Div([
            kpi_card('6', 'Total Dept.', 'navy', '🏢'),
            kpi_card('4', 'Ativos', 'teal', '✓'),
            kpi_card('2', 'Inativos', 'dark', '○'),
        ], className='kpi-grid'),

        html.Div([
            html.Div([
                html.H3('Fila por Departamento', className='chart-title'),
                dcc.Graph(id='grafico-fila-dept', figure=fig_fila_dept, config={'displayModeBar': False})
            ], className='chart-card'),

            html.Div([
                html.H3('Status por Departamento', className='chart-title'),
                dcc.Graph(id='grafico-status-dept', figure=fig_status_dept, config={'displayModeBar': False})
            ], className='chart-card'),
        ], className='chart-row chart-row--half'),

        html.Div([
            html.Div([
                html.H3('Detalhamento do Fluxo', className='chart-title'),
                tabela_fluxo
            ], className='table-card'),
        ], className='chart-row'),
    ])


# ─── Tab: Campanhas ─────────────────────────────────────────────────────────
def render_campanhas_tab(local, servico, date_from, date_to):
    """Aba de Campanhas - dados de vagas por local e campanhas encerradas"""
    if date_from is None or date_from == '':
        date_from = None
    if date_to is None or date_to == '':
        date_to = None

    df_vagas = get_vagas_temporal(date_from, date_to, local, servico)
    df_campanhas = get_campanhas_encerradas()
    kpis = get_kpis_fact_resumo(date_from, date_to, local, servico)

    fig_vagas_local = create_vagas_por_local_chart(df_vagas)
    fig_campanhas = create_campanhas_encerradas_chart(df_campanhas)

    return html.Div([
        html.Div([
            kpi_card(format_number(kpis['total_vagas']), 'Total Vagas', 'navy', '📋'),
            kpi_card(format_number(kpis['vagas_ocupadas']), 'Ocupadas', 'blue', '✓'),
            kpi_card(format_number(kpis['vagas_livres']), 'Disponíveis', 'teal', '○'),
            kpi_card(f"{kpis['taxa_ocupacao']}%", 'Ocupação', 'dark', '📈'),
        ], className='kpi-grid'),

        html.Div([
            html.Div([
                html.H3('Vagas por Local', className='chart-title'),
                dcc.Graph(id='grafico-vagas-local', figure=fig_vagas_local, config={'displayModeBar': False})
            ], className='chart-card'),

            html.Div([
                html.H3('Campanhas Encerradas', className='chart-title'),
                dcc.Graph(id='grafico-campanhas-encerradas', figure=fig_campanhas, config={'displayModeBar': False})
            ], className='chart-card'),
        ], className='chart-row chart-row--half'),
    ])


# ─── Tab: Castrações (Guinness Book) ───────────────────────────────────────
def render_castracoes_tab(local, servico, date_from, date_to):
    """Aba de Castrações - Gauge de progresso"""
    if date_from is None or date_from == '':
        date_from = None
    if date_to is None or date_to == '':
        date_to = None

    kpis = get_kpis_fact_resumo(date_from, date_to, local, servico)
    total_castrados = kpis.get('vagas_ocupadas', 0) or 0
    meta = 2000

    fig_gauge = create_gauge_castracoes(total_castrados, meta)

    return html.Div([
        html.Div([
            kpi_card(format_number(total_castrados), 'Total Castrados', 'navy', '🔪'),
            kpi_card(format_number(meta), 'Meta', 'teal', '🎯'),
            kpi_card(f"{(total_castrados/meta*100):.1f}%", 'Progresso', 'blue', '📊'),
        ], className='kpi-grid'),

        html.Div([
            html.Div([
                html.H3('Progresso Castrações', className='chart-title'),
                dcc.Graph(id='grafico-gauge', figure=fig_gauge, config={'displayModeBar': False})
            ], className='chart-card'),
        ], className='chart-row'),
    ])


# ─── Tab: Solicitações ──────────────────────────────────────────────────────
def render_solicitacoes_tab(local, servico, date_from, date_to):
    """Aba de Solicitações - Status das solicitações"""
    if date_from is None or date_from == '':
        date_from = None
    if date_to is None or date_to == '':
        date_to = None

    df_fila = get_fila_temporal(date_from, date_to, local, servico)
    kpis = get_kpis_fact_resumo(date_from, date_to, local, servico)

    fig_status = create_status_solicitacoes_chart(df_fila)

    return html.Div([
        html.Div([
            kpi_card(format_number(kpis.get('em_fila', 0)), 'Total Solicitações', 'navy', '📝'),
            kpi_card(format_number(kpis.get('vagas_ocupadas', 0)), 'Atendidas', 'teal', '✓'),
            kpi_card(format_number(kpis.get('nao_compareceram', 0)), 'Canceladas', 'dark', '✕'),
        ], className='kpi-grid'),

        html.Div([
            html.Div([
                html.H3('Status das Solicitações', className='chart-title'),
                dcc.Graph(id='grafico-status-solicitacoes', figure=fig_status, config={'displayModeBar': False})
            ], className='chart-card'),
        ], className='chart-row'),
    ])


# ─── Funções de Gráficos ───────────────────────────────────────────────────
def create_fila_por_departamento_chart(df):
    if df is None or df.empty:
        return create_empty_figure()

    df_agg = df.groupby(['departamento', 'status_fila']).agg({'quantidade': 'sum'}).reset_index()

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Chamando',
        'called': 'Chamado',
        'cancelled': 'Cancelado'
    }
    df_agg['status_fila'] = df_agg['status_fila'].map(status_map)

    fig = px.bar(
        df_agg,
        x='departamento',
        y='quantidade',
        color='status_fila',
        title='',
        labels={'departamento': '', 'quantidade': 'Pessoas', 'status_fila': 'Status'},
        barmode='group',
        color_discrete_map={
            'Aguardando': '#8B5CF6',
            'Chamando': '#3B82F6',
            'Chamado': '#10B981',
            'Cancelado': '#EF4444'
        }
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=12),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6')
    )

    return fig


def create_status_por_departamento_chart(df):
    if df is None or df.empty:
        return create_empty_figure()

    status_col = 'status_fila' if 'status_fila' in df.columns else 'status'
    if status_col not in df.columns or 'quantidade' not in df.columns:
        return create_empty_figure()

    status_vals = df[status_col].dropna().unique()
    valid_statuses = ['waiting', 'calling', 'called', 'cancelled']
    has_valid = any(s in valid_statuses for s in status_vals)
    if not has_valid:
        return create_empty_figure()

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Chamando',
        'called': 'Chamado',
        'cancelled': 'Cancelado'
    }

    df_filtered = df[df[status_col].isin(valid_statuses)].copy()
    df_filtered['status_pt'] = df_filtered[status_col].map(status_map)

    df_agg = df_filtered.groupby('status_pt', as_index=False)['quantidade'].sum()

    fig = px.pie(
        df_agg,
        values='quantidade',
        names='status_pt',
        title='',
        color_discrete_sequence=['#8B5CF6', '#3B82F6', '#10B981', '#EF4444']
    )

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=12),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )

    return fig


def create_vagas_por_local_chart(df):
    """Gráfico de vagas por local para aba Campanhas"""
    if df is None or df.empty:
        return create_empty_figure()

    df_agg = df.groupby('local_servico').agg({
        'total_vagas': 'sum',
        'vagas_ocupadas': 'sum'
    }).reset_index()
    df_agg['vagas_livres'] = df_agg['total_vagas'] - df_agg['vagas_ocupadas']

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_agg['vagas_ocupadas'],
        y=df_agg['local_servico'],
        name='Ocupadas',
        orientation='h',
        marker_color='#3B82F6',
        text=df_agg['vagas_ocupadas'],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        x=df_agg['vagas_livres'],
        y=df_agg['local_servico'],
        name='Livres',
        orientation='h',
        marker_color='#10B981',
        text=df_agg['vagas_livres'],
        textposition='outside'
    ))

    fig.update_layout(
        barmode='group',
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=12),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6', showticklabels=False),
        yaxis=dict(showgrid=False)
    )

    return fig


def create_campanhas_encerradas_chart(df):
    """Gráfico de campanhas encerradas com vagas oferecidas e atendidas"""
    if df is None or df.empty:
        return create_empty_figure()

    fig = go.Figure()

    # Barras agrupadas: vagas oferecidas e atendidas por campanha
    fig.add_trace(go.Bar(
        x=df['campanha'],
        y=df['total_vagas'],
        name='Vagas Oferecidas',
        marker_color='#3B82F6',
        text=df['total_vagas'],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        x=df['campanha'],
        y=df['total_atendidas'],
        name='Atendidas',
        marker_color='#10B981',
        text=df['total_atendidas'],
        textposition='outside'
    ))

    fig.update_layout(
        barmode='group',
        paper_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=80),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=False, tickangle=45),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6', showticklabels=False)
    )
    fig.update_xaxes(tickangle=45, ticks='outside')
    fig.update_yaxes(gridcolor='#f3f4f6', ticks='outside')

    return fig


def create_gauge_castracoes(valor, meta):
    """Gauge de progresso de castrações"""
    progresso = min((valor / meta) * 100, 100)

    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=valor,
        number={'font': {'size': 36, 'color': '#374151'}, 'suffix': f' / {meta}'},
        delta={'reference': meta, 'position': 'bottom'},
        gauge={
            'axis': {'range': [0, meta], 'tickwidth': 1, 'tickcolor': '#374151'},
            'bar': {'color': '#3B82F6'},
            'steps': [
                {'range': [0, meta * 0.5], 'color': '#FEE2E2'},
                {'range': [meta * 0.5, meta * 0.75], 'color': '#FEF3C7'},
                {'range': [meta * 0.75, meta], 'color': '#D1FAE5'}
            ],
            'threshold': {
                'line': {'color': '#1c2c51', 'width': 4},
                'value': meta
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=12),
        height=300
    )

    return fig


def create_status_solicitacoes_chart(df):
    """Gráfico de status de solicitações"""
    if df is None or df.empty:
        return create_empty_figure()

    df_agg = df.groupby('status_fila').agg({'quantidade': 'sum'}).reset_index()

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Em Atendimento',
        'called': 'Concluído',
        'cancelled': 'Cancelado'
    }
    df_agg['status_fila'] = df_agg['status_fila'].map(status_map)

    fig = px.pie(
        df_agg,
        values='quantidade',
        names='status_fila',
        title='',
        color_discrete_sequence=['#8B5CF6', '#3B82F6', '#10B981', '#EF4444']
    )

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#374151', family='DM Sans, sans-serif'),
        margin=dict(l=12, r=12, t=40, b=12),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')

    return fig


# ─── Funções de Tabelas ─────────────────────────────────────────────────────
def create_fluxo_table(df):
    if df is None or df.empty:
        return html.Div('Sem dados para exibir', className='empty-state')

    columns_to_show = ['departamento', 'ordem_fluxo', 'status', 'quantidade', 'qtd_waiting', 'qtd_calling', 'qtd_called', 'qtd_cancelled']
    df_display = df[[c for c in columns_to_show if c in df.columns]].copy()
    df_display = df_display.sort_values(['ordem_fluxo', 'status'])

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Chamando',
        'called': 'Chamado',
        'cancelled': 'Cancelado'
    }
    if 'status' in df_display.columns:
        df_display['status'] = df_display['status'].map(status_map)

    columns_renamed = {
        'departamento': 'Departamento',
        'ordem_fluxo': 'Ordem',
        'status': 'Status',
        'quantidade': 'Total',
        'qtd_waiting': 'Aguardando',
        'qtd_calling': 'Chamando',
        'qtd_called': 'Chamado',
        'qtd_cancelled': 'Cancelado'
    }
    df_display = df_display.rename(columns=columns_renamed)

    from dash import dash_table
    return dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_display.columns],
        page_size=15,
        style_table={'overflowX': 'auto'},
        style_header={
            'backgroundColor': '#1c2c51',
            'fontWeight': '600',
            'color': 'white',
            'borderBottom': '2px solid #3B82F6',
            'textAlign': 'center',
            'padding': '12px',
            'fontFamily': 'Sora, sans-serif',
            'fontSize': '0.78rem',
            'textTransform': 'uppercase',
            'letterSpacing': '0.06em'
        },
        style_cell={
            'padding': '10px',
            'fontFamily': 'DM Sans, sans-serif',
            'fontSize': '0.86rem',
            'color': '#374151',
            'borderBottom': '1px solid rgba(28, 44, 81, 0.10)',
            'textAlign': 'center'
        },
        style_data={'backgroundColor': 'white'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'}],
        style_as_list_view=True,
        sort_action='native',
    )


# ─── Server ─────────────────────────────────────────────────────────────────
app = app.server

if __name__ == '__main__':
    app.run(debug=False, port=8050)
