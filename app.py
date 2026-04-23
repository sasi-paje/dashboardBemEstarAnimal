import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from db import (
    get_kpis_fact_resumo,
    get_fact_resumo,
    get_vagas_temporal,
    get_fila_temporal,
    get_fluxo_departamentos,
    get_departamentos_flow,
    get_nao_compareceram_por_local,
    get_nao_compareceram_detalhado,
    get_atendimentos_por_hora,
    get_filter_options
)

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        '/assets/style.css'
    ],
    suppress_callback_exceptions=True
)

locais, servicos, departamentos = get_filter_options()

today = datetime.now().strftime('%Y-%m-%d')
one_month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')


def format_number(num):
    if num is None:
        return '--'
    if isinstance(num, float):
        return f'{num:,.1f}'.replace(',', '.')
    return f'{int(num):,}'.replace(',', '.')


def kpi_card(value, label, color_class='', icon=''):
    return html.Div([
        html.Div([
            html.Span(className=f'kpi-icon {icon}', children=icon if icon else ''),
            html.Div(value, className=f'kpi-value {color_class}'),
        ], className='kpi-header'),
        html.Div(label, className='kpi-label')
    ], className='card-kpi')


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


HEADER = html.Div([
    html.Div([
        html.Div([
            html.Span(className='logo-icon', children='🐾'),
            html.Div([
                html.H1('Bem-Estar Animal', className='title'),
                html.Span('Dashboard de Atendimento Veterinário', className='subtitle')
            ], className='title-group')
        ], className='header-left'),
        html.Div([
            html.Span(id='current-datetime', className='datetime'),
            html.Div(id='refresh-indicator', className='refresh-indicator', children=[
                html.Span(className='dot'),
                html.Span(id='last-update-text', children='Atualizado agora')
            ])
        ], className='header-right')
    ], className='header-content')
], className='app-header')


app.layout = html.Div([
    dcc.Store(id='last-update', data=None),
    HEADER,

    html.Div([
        html.Div([
            html.Div([
                html.Label('Local', className='filter-label'),
                dcc.Dropdown(
                    id='filtro-local',
                    options=[{'label': l, 'value': l} for l in locais],
                    value=None,
                    placeholder='Selecione',
                    clearable=True,
                    className='filter-dropdown'
                )
            ], className='filter-group'),

            html.Div([
                html.Label('Servico', className='filter-label'),
                dcc.Dropdown(
                    id='filtro-servico',
                    options=[{'label': s, 'value': s} for s in servicos],
                    value=None,
                    placeholder='Selecione',
                    clearable=True,
                    className='filter-dropdown'
                )
            ], className='filter-group'),

            html.Div([
                html.Label('Periodo', className='filter-label'),
                dcc.DatePickerRange(
                    id='date-picker',
                    start_date=one_month_ago,
                    end_date=today,
                    display_format='DD/MM/YYYY',
                    className='filter-datepicker'
                )
            ], className='filter-group'),

            html.Div([
                html.Label('', className='filter-label'),
                dbc.Button(
                    [html.Span('↻'), ' Atualizar'],
                    id='btn-refresh',
                    color='primary',
                    className='btn-refresh'
                )
            ], className='filter-group'),
        ], className='filters-bar')
    ], className='filters-container'),

    dcc.Tabs(id='tabs', value='tab-geral', className='tabs-wrapper', children=[
        dcc.Tab(label='📊 Visão Geral', value='tab-geral', className='tab-item', selected_className='tab-item-selected'),
        dcc.Tab(label='🏢 Departamentos', value='tab-departamentos', className='tab-item', selected_className='tab-item-selected'),
    ]),

    html.Div(id='tab-content', className='content-area'),

    dcc.Interval(
        id='interval-component',
        interval=1800000,
        n_intervals=0
    )
], className='app-container')


@callback(
    Output('tab-content', 'children'),
    Output('current-datetime', 'children'),
    [Input('tabs', 'value'),
     Input('btn-refresh', 'n_clicks'),
     Input('interval-component', 'n_intervals'),
     Input('filtro-local', 'value'),
     Input('filtro-servico', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date')]
)
def render_tab_content(selected_tab, n_clicks, n_intervals, local, servico, date_from, date_to):
    now = datetime.now()
    datetime_str = now.strftime('%d/%m/%Y %H:%M')

    if date_from is None or date_from == '':
        date_from = None
    if date_to is None or date_to == '':
        date_to = None

    if selected_tab == 'tab-geral':
        return render_geral_tab(local, servico, date_from, date_to), datetime_str
    else:
        return render_departamentos_tab(local, servico, date_from, date_to), datetime_str


def render_geral_tab(local, servico, date_from, date_to):
    kpis = get_kpis_fact_resumo(date_from, date_to, local, servico)
    df_fact = get_fact_resumo(date_from, date_to, local, servico)
    df_vagas = get_vagas_temporal(date_from, date_to, local, servico)
    df_fila = get_fila_temporal(date_from, date_to, local, servico)
    df_nao_grafico = get_nao_compareceram_por_local()
    df_nao_detalhes = get_nao_compareceram_detalhado(date_from, date_to, local, servico, limit=100)
    df_hora = get_atendimentos_por_hora()

    fig_ocupacao = create_ocupacao_chart(df_vagas)
    fig_fila_status = create_fila_pie_chart(df_fila)
    fig_temporal = create_temporal_chart(df_fact)
    fig_nao_por_local = create_nao_por_local_chart(df_nao_grafico)
    fig_hora = create_hora_chart(df_hora)

    tabela_nao = create_nao_table(df_nao_detalhes)

    return html.Div([
        html.Div([
            kpi_card(format_number(kpis['total_vagas']), 'Total Vagas', '', '📋'),
            kpi_card(format_number(kpis['vagas_ocupadas']), 'Ocupadas', 'blue', '✓'),
            kpi_card(format_number(kpis['vagas_livres']), 'Livres', 'green', '○'),
            kpi_card(f"{kpis['taxa_ocupacao']}%", 'Taxa Ocup.', 'yellow', '📈'),
            kpi_card(format_number(kpis['em_fila']), 'Em Fila', 'purple', '👥'),
            kpi_card(format_number(kpis['nao_compareceram']), 'Não Comp.', 'red', '✕'),
        ], className='kpi-grid'),

        html.Div([
            html.Div([
                html.Div([
                    html.H3('Ocupação por Local', className='chart-title'),
                    html.Span(f'{len(df_vagas["local_servico"].unique()) if not df_vagas.empty else 0} locais', className='chart-badge')
                ], className='chart-header'),
                dcc.Graph(figure=fig_ocupacao, config={'displayModeBar': False})
            ], className='chart-box'),

            html.Div([
                html.Div([
                    html.H3('Status da Fila', className='chart-title'),
                    html.Span(f'Total: {df_fila["quantidade"].sum() if not df_fila.empty else 0}', className='chart-badge')
                ], className='chart-header'),
                dcc.Graph(figure=fig_fila_status, config={'displayModeBar': False})
            ], className='chart-box'),
        ], className='charts-row'),

        html.Div([
            html.Div([
                html.H3('Evolução Temporal', className='chart-title'),
                dcc.Graph(figure=fig_temporal, config={'displayModeBar': False})
            ], className='chart-box-full'),
        ], className='charts-row'),

        html.Div([
            html.Div([
                html.H3('Atendimentos por Hora', className='chart-title'),
                dcc.Graph(figure=fig_hora, config={'displayModeBar': False})
            ], className='chart-box'),

            html.Div([
                html.H3('Não-Comparecimentos por Local', className='chart-title'),
                dcc.Graph(figure=fig_nao_por_local, config={'displayModeBar': False})
            ], className='chart-box'),
        ], className='charts-row'),

        html.Div([
            html.Div([
                html.H3('Detalhes Não-Comparecimentos', className='chart-title'),
                tabela_nao
            ], className='table-box'),
        ], className='tables-row'),
    ])


def render_departamentos_tab(local, servico, date_from, date_to):
    df_fluxo = get_fluxo_departamentos(date_from, date_to, local, servico)
    df_fila = get_fila_temporal(date_from, date_to, local, servico)

    fig_fila_dept = create_fila_por_departamento_chart(df_fila)
    fig_status_dept = create_status_por_departamento_chart(df_fluxo)
    tabela_fluxo = create_fluxo_table(df_fluxo)

    return html.Div([
        html.Div([
            html.Div([
                html.H3('Fila por Departamento', className='chart-title'),
                dcc.Graph(figure=fig_fila_dept, config={'displayModeBar': False})
            ], className='chart-box'),

            html.Div([
                html.H3('Status por Departamento', className='chart-title'),
                dcc.Graph(figure=fig_status_dept, config={'displayModeBar': False})
            ], className='chart-box'),
        ], className='charts-row'),

        html.Div([
            html.Div([
                html.H3('Detalhamento do Fluxo', className='chart-title'),
                tabela_fluxo
            ], className='table-box'),
        ], className='tables-row'),
    ])


def create_ocupacao_chart(df):
    if df.empty:
        return create_empty_figure()

    df_agg = df.groupby(['local_servico', 'servico']).agg({
        'total_vagas': 'sum',
        'vagas_ocupadas': 'sum',
        'vagas_nao_confirmadas': 'sum'
    }).reset_index()

    df_melt = df_agg.melt(
        id_vars=['local_servico', 'servico'],
        value_vars=['vagas_ocupadas', 'vagas_nao_confirmadas'],
        var_name='tipo',
        value_name='quantidade'
    )

    fig = px.bar(
        df_melt,
        x='local_servico',
        y='quantidade',
        color='tipo',
        title='',
        labels={'local_servico': '', 'quantidade': 'Vagas', 'tipo': ''},
        color_discrete_map={
            'vagas_ocupadas': '#3B82F6',
            'vagas_nao_confirmadas': '#E5E7EB'
        },
        barmode='stack'
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151', size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6', showticklabels=False)
    )
    fig.update_xaxes(tickangle=45, gridcolor='#f3f4f6', ticks='outside')
    fig.update_yaxes(gridcolor='#f3f4f6', ticks='outside')

    return fig


def create_fila_pie_chart(df):
    if df.empty:
        return create_empty_figure()

    df_agg = df.groupby(['status_fila']).agg({'quantidade': 'sum'}).reset_index()

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Chamando',
        'called': 'Chamado',
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
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')

    return fig


def create_temporal_chart(df):
    if df.empty:
        return create_empty_figure()

    df_grouped = df.groupby(['data']).agg({
        'total_vagas': 'sum',
        'vagas_ocupadas': 'sum',
        'nao_compareceram': 'sum'
    }).reset_index()
    df_grouped = df_grouped.sort_values('data')

    df_melt = df_grouped.melt(
        id_vars=['data'],
        value_vars=['total_vagas', 'vagas_ocupadas', 'nao_compareceram'],
        var_name='tipo',
        value_name='quantidade'
    )

    tipo_map = {
        'total_vagas': 'Total Vagas',
        'vagas_ocupadas': 'Ocupadas',
        'nao_compareceram': 'Não Comp.'
    }
    df_melt['tipo'] = df_melt['tipo'].map(tipo_map)

    fig = px.bar(
        df_melt,
        x='data',
        y='quantidade',
        color='tipo',
        title='',
        labels={'data': '', 'quantidade': 'Quantidade', 'tipo': ''},
        barmode='group',
        color_discrete_map={
            'Total Vagas': '#3B82F6',
            'Ocupadas': '#10B981',
            'Não Comp.': '#EF4444'
        },
        text='quantidade'
    )

    fig.update_traces(textposition='outside')

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6', showticklabels=False, title='')
    )

    return fig


def create_hora_chart(df):
    if df.empty:
        return create_empty_figure()

    total = int(df['total_chamados'].sum())

    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=total,
        number={'font': {'size': 36, 'color': '#374151'}},
        gauge={
            'axis': {'range': [0, 50], 'tickwidth': 1, 'tickcolor': '#374151'},
            'bar': {'color': '#3B82F6'},
            'steps': [
                {'range': [0, 35], 'color': '#EF4444'},
                {'range': [35, 45], 'color': '#F59E0B'},
                {'range': [45, 50], 'color': '#10B981'}
            ],
            'threshold': {
                'line': {'color': '#374151', 'width': 4},
                'value': 50
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280
    )

    return fig


def create_nao_por_local_chart(df):
    if df.empty:
        return create_empty_figure()

    mes_map = {
        '2026-04': 'Abr 2026',
        '2026-03': 'Mar 2026',
        '2026-02': 'Fev 2026',
        '2026-01': 'Jan 2026',
        '2025-12': 'Dez 2025',
        '2025-11': 'Nov 2025',
        '2025-10': 'Out 2025'
    }
    df['mes'] = df['ano_mes'].map(mes_map)

    fig = px.bar(
        df,
        x='local_servico',
        y='total',
        color='mes',
        title='',
        labels={'local_servico': '', 'total': 'Não Comp.', 'mes': 'Mês'},
        barmode='group',
        color_discrete_sequence=['#93C5FD', '#3B82F6', '#1D4ED8']
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6', title=''),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6', showticklabels=False, title='')
    )
    fig.update_xaxes(tickangle=45, gridcolor='#f3f4f6', ticks='outside')
    fig.update_yaxes(gridcolor='#f3f4f6', ticks='outside')

    return fig


def create_nao_table(df):
    if df.empty:
        return html.Div('Sem dados para exibir', className='empty-state')

    columns_to_show = ['data_agendamento', 'local_servico', 'nome_tutor', 'cpf', 'nome_animal', 'porte', 'era_prioridade']
    df_display = df[[c for c in columns_to_show if c in df.columns]].head(50).copy()

    if 'data_agendamento' in df_display.columns:
        df_display['data_agendamento'] = pd.to_datetime(df_display['data_agendamento']).dt.strftime('%d/%m/%Y')

    columns_renamed = {
        'data_agendamento': 'Data',
        'local_servico': 'Local',
        'nome_tutor': 'Tutor',
        'cpf': 'CPF',
        'nome_animal': 'Animal',
        'porte': 'Porte',
        'era_prioridade': 'Prioridade'
    }
    df_display = df_display.rename(columns=columns_renamed)

    from dash import dash_table
    return dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_display.columns],
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_header={
            'backgroundColor': '#1a1a2e',
            'fontWeight': '600',
            'color': 'white',
            'borderBottom': '2px solid #3B82F6',
            'textAlign': 'center',
            'padding': '12px'
        },
        style_cell={
            'padding': '12px',
            'fontFamily': '"Inter", sans-serif',
            'fontSize': '13px',
            'color': '#374151',
            'borderBottom': '1px solid #e5e7eb',
            'textAlign': 'left'
        },
        style_data={'backgroundColor': 'white'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'},
            {'if': {'column_id': 'Prioridade', 'filter_query': '{Prioridade} = "Sim"'}, 'color': '#EF4444', 'fontWeight': '600'}
        ],
        style_as_list_view=True,
        sort_action='native',
    )


def create_fila_por_departamento_chart(df):
    if df.empty:
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
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6')
    )

    return fig


def create_status_por_departamento_chart(df):
    if df.empty:
        return create_empty_figure()

    status_map = {
        'waiting': 'Aguardando',
        'calling': 'Chamando',
        'called': 'Chamado',
        'cancelled': 'Cancelado'
    }
    df['status_pt'] = df['status'].map(status_map)

    df_agg = df.groupby('status_pt').agg({'quantidade': 'sum'}).reset_index()

    fig = px.pie(
        df_agg,
        values='quantidade',
        names='status_pt',
        title='',
        color_discrete_sequence=['#8B5CF6', '#3B82F6', '#10B981', '#EF4444']
    )

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )

    return fig


def create_fluxo_chart(df):
    if df.empty:
        return create_empty_figure()

    df_agg = df.groupby(['departamento', 'ordem_fluxo']).agg({'quantidade': 'sum'}).reset_index()
    df_agg = df_agg.sort_values('ordem_fluxo')

    fig = px.bar(
        df_agg,
        x='departamento',
        y='quantidade',
        title='',
        labels={'departamento': '', 'quantidade': 'Total'},
        color='ordem_fluxo',
        color_continuous_scale='Viridis'
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#374151'),
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor='#f3f4f6'),
        yaxis=dict(showgrid=True, gridcolor='#f3f4f6')
    )

    return fig


def create_fluxo_table(df):
    if df.empty:
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
            'backgroundColor': '#1a1a2e',
            'fontWeight': '600',
            'color': 'white',
            'borderBottom': '2px solid #3B82F6',
            'textAlign': 'center',
            'padding': '12px'
        },
        style_cell={
            'padding': '12px',
            'fontFamily': '"Inter", sans-serif',
            'fontSize': '13px',
            'color': '#374151',
            'borderBottom': '1px solid #e5e7eb',
            'textAlign': 'center'
        },
        style_data={'backgroundColor': 'white'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'}],
        style_as_list_view=True,
        sort_action='native',
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)