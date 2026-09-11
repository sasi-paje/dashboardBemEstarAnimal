import dash
from dash import dcc, html, callback, ctx, Input, Output, State
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.express as px
import plotly.graph_objects as go

from db import (
    get_kpis_fact_resumo,
    get_vagas_temporal,
    get_campanhas_encerradas,
    get_fila_temporal,
    get_fluxo_departamentos,
    get_departamentos_flow,
    get_filter_options,
    get_totais_acumulados,
    get_atendimentos_por_mes,
    get_especies_vacinacao,
)

LOCAL_CENTRO_ZOONOSES = 'Unidade de Vigilância e Controle de Zoonoses-UVCZ'

MESES_PT = {
    '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr', '05': 'Mai', '06': 'Jun',
    '07': 'Jul', '08': 'Ago', '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
}

app = dash.Dash(
    __name__,
    external_stylesheets=['/assets/style.css'],
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
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
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

    dcc.RadioItems(
        id='dash-quick-filter',
        options=[
            {'label': 'Todos', 'value': 'todos'},
            {'label': 'Centro de Zoonoses', 'value': 'zoonoses'},
            {'label': 'Fim de semana', 'value': 'weekend'},
        ],
        value='todos',
        className='sv2-pill-group',
        inputClassName='sv2-pill-input',
        labelClassName='sv2-pill-label',
    ),

    html.Button('Limpar', id='dash-btn-limpar', className='sv2-btn-limpar'),
    html.Button('Filtrar', id='dash-btn-filtrar', className='sv2-btn-filtrar'),
], className='sv2-filter-panel')


# ─── Layout Principal ───────────────────────────────────────────────────────
# Este app é responsável apenas pela tela de Dashboard — a navegação entre
# seções (Departamentos, Campanhas, etc.) já é feita pelo sistema principal.
app.layout = html.Div([
    dcc.Store(id='last-update', data=None),

    html.Div([
        DASHBOARD_FILTER_PANEL,
        html.Div(id='dashboard-content'),
    ], className='sv2-page-body'),

    dcc.Interval(
        id='interval-component',
        interval=1800000,
        n_intervals=0
    )
], className='app-container sv2-standalone')


# ─── Callback da tela de Dashboard ──────────────────────────────────────────
# Datas e pill são Input (não State): a tela reage na hora, sem precisar
# clicar em "Filtrar" — o botão fica só como atalho/confirmação visual.
@callback(
    [Output('dashboard-content', 'children'),
     Output('dash-date-start', 'date'),
     Output('dash-date-end', 'date'),
     Output('dash-quick-filter', 'value')],
    [Input('dash-date-start', 'date'),
     Input('dash-date-end', 'date'),
     Input('dash-quick-filter', 'value'),
     Input('dash-btn-filtrar', 'n_clicks'),
     Input('dash-btn-limpar', 'n_clicks'),
     Input('interval-component', 'n_intervals')]
)
def render_dashboard(date_start, date_end, quick_filter, n_filtrar, n_limpar, n_intervals):
    if ctx.triggered_id == 'dash-btn-limpar':
        date_start, date_end, quick_filter = None, None, 'todos'
        return render_dashboard_tab(date_start, date_end, quick_filter), date_start, date_end, quick_filter

    return render_dashboard_tab(date_start, date_end, quick_filter), dash.no_update, dash.no_update, dash.no_update


# ─── KPI Card Helper ────────────────────────────────────────────────────────
def kpi_card(value, label, variant='blue', icon=''):
    return html.Div([
        html.Div(icon, className=f'kpi-card__icon') if icon else html.Div(''),
        html.Div(label, className='kpi-card__label'),
        html.Div(value, className='kpi-card__value'),
    ], className=f'kpi-card kpi-card--{variant}')


# ─── Tab: Dashboard (réplica visual SEMMA) ──────────────────────────────────
def render_dashboard_tab(date_start, date_end, quick_filter):
    date_from = date_start or None
    date_to = date_end or None
    local_filter = LOCAL_CENTRO_ZOONOSES if quick_filter == 'zoonoses' else None
    weekend_only = quick_filter == 'weekend'

    totais = get_totais_acumulados()
    kpis_all = get_kpis_fact_resumo(date_from, date_to, local_filter, None, weekend_only)
    kpis_vacina = get_kpis_fact_resumo(date_from, date_to, local_filter, 'Vacinação', weekend_only)
    kpis_castra = get_kpis_fact_resumo(date_from, date_to, local_filter, 'Castração', weekend_only)
    especies = get_especies_vacinacao(date_from, date_to, local_filter, weekend_only)
    df_mes = get_atendimentos_por_mes(date_from, date_to, local_filter, weekend_only)
    df_fluxo = get_fluxo_departamentos(date_from, date_to, local_filter, 'Castração', weekend_only)

    return html.Div([
        build_hero(totais),
        build_kpi_row(kpis_all, kpis_vacina, kpis_castra),
        build_entry_section(kpis_vacina, especies, kpis_castra),
        build_month_chart(df_mes),
        html.Div([
            build_capacity_card(kpis_all),
            build_flow_card(df_fluxo),
        ], className='sv2-bottom-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'})


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


def sv2_kpi_card(icon, icon_bg, label, value):
    return html.Div([
        html.Div([
            html.Div(icon, className='sv2-kpi-card__icon', style={'background': icon_bg}),
            html.Div(label, className='sv2-kpi-card__label'),
        ], className='sv2-kpi-card__top'),
        html.Div(value, className='sv2-kpi-card__value'),
    ], className='sv2-kpi-card')


def build_kpi_row(kpis_all, kpis_vacina, kpis_castra):
    return html.Div([
        sv2_kpi_card('📅', '#E7F2EA', 'Atendimentos totais', format_number(kpis_all['vagas_ocupadas'])),
        sv2_kpi_card('💉', '#E7F2EA', 'Vacinações totais', format_number(kpis_vacina['vagas_ocupadas'])),
        sv2_kpi_card('✂️', '#E7F2EA', 'Castrações totais', format_number(kpis_castra['vagas_ocupadas'])),
        sv2_kpi_card('⏱️', '#FDEEF0', 'Fila de castração', format_number(kpis_castra['em_fila'])),
    ], className='sv2-kpi-grid')


def sv2_entry_card(icon, badge_text, title, desc, stats):
    return html.Div([
        html.Div([
            html.Div(icon, className='sv2-entry-card__icon'),
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
    ], className='sv2-entry-card')


def build_entry_section(kpis_vacina, especies, kpis_castra):
    vacina_card = sv2_entry_card(
        '💉',
        f"{format_number(kpis_vacina['vagas_ocupadas'])} aplicadas",
        'Vacinação',
        'Aplicação por demanda espontânea: acompanhe cobertura, doses aplicadas e estoque das campanhas.',
        [
            ('Doses aplicadas', kpis_vacina['vagas_ocupadas']),
            ('Caninos', especies.get('Canino', 0)),
            ('Felinos', especies.get('Felino', 0)),
        ]
    )
    castracao_card = sv2_entry_card(
        '✂️',
        f"{format_number(kpis_castra['em_fila'])} em fila",
        'Castração',
        'Acompanhe a jornada pré-operatória, a execução do procedimento e as altas.',
        [
            ('Realizadas', kpis_castra['vagas_ocupadas']),
            ('Vagas livres', kpis_castra['vagas_livres']),
            ('Em fila', kpis_castra['em_fila']),
        ]
    )
    return html.Div([
        html.Div([
            html.Div('Portas de entrada', className='sv2-card__eyebrow'),
            html.Div('Escolha um serviço para aprofundar a operação', className='sv2-card__title'),
        ]),
        html.Div([vacina_card, castracao_card], className='sv2-entry-row'),
    ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '12px'})


def build_month_chart(df_mes):
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
        total_vac = int(sum(vac_vals))
        total_cas = int(sum(cas_vals))

        fig = go.Figure()
        fig.add_trace(go.Bar(x=mes_labels, y=vac_vals, name='Vacinação', marker_color='#1F9E4D',
                              text=vac_vals, textposition='outside'))
        fig.add_trace(go.Bar(x=mes_labels, y=cas_vals, name='Castração', marker_color='#A9D9BB',
                              text=cas_vals, textposition='outside'))
        fig.update_layout(
            barmode='group',
            paper_bgcolor='white', plot_bgcolor='white',
            font=dict(family='Inter, sans-serif', color='#1F2937'),
            margin=dict(l=12, r=12, t=12, b=12),
            height=280,
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#F3F4F6', showticklabels=False),
        )

    return html.Div([
        html.Div([
            html.Div([
                html.Div('Volume do período', className='sv2-card__eyebrow'),
                html.Div('Atendimentos por mês', className='sv2-card__title'),
            ]),
            html.Div([
                html.Span(f'● Vacinação  {format_number(total_vac)}',
                          style={'color': '#1F9E4D', 'fontWeight': 700, 'marginRight': '16px'}),
                html.Span(f'● Castração  {format_number(total_cas)}',
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


def build_flow_card(df_fluxo):
    if df_fluxo is None or df_fluxo.empty:
        body = html.Div('Sem dados para exibir', className='empty-state')
    else:
        agg = df_fluxo.groupby(['departamento', 'ordem_fluxo'], as_index=False)['quantidade'].sum()
        agg = agg.sort_values('ordem_fluxo')
        steps = list(agg.itertuples(index=False))
        max_val = max([s.quantidade for s in steps], default=1) or 1

        step_divs = []
        for i, s in enumerate(steps, start=1):
            pct = round((s.quantidade / max_val) * 100, 1)
            step_divs.append(html.Div([
                html.Div(str(i), className='sv2-flow-step__badge'),
                html.Div(s.departamento, className='sv2-flow-step__label'),
                html.Div(format_number(s.quantidade), className='sv2-flow-step__value'),
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
