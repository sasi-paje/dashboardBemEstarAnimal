import dash_bootstrap_components as dbc
from dash import dash_table, html

def tabela_detalhamento(df):
    if df.empty:
        return html.Div('Sem dados para exibir', className='text-muted text-center p-4')

    df_display = df.copy()
    if 'hora_agendamento' in df_display.columns:
        df_display['hora_agendamento'] = df_display['hora_agendamento'].apply(
            lambda x: x.strftime('%H:%M') if x else ''
        )
    if 'data_agendamento' in df_display.columns:
        df_display['data_agendamento'] = df_display['data_agendamento'].apply(
            lambda x: x.strftime('%d/%m/%Y') if x else ''
        )

    return dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_display.columns],
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_header={
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold',
            'color': '#1a1a2e',
            'borderBottom': '2px solid #e5e7eb',
            'textAlign': 'center'
        },
        style_cell={
            'padding': '12px 15px',
            'fontFamily': '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
            'fontSize': '14px',
            'color': '#374151',
            'borderBottom': '1px solid #e5e7eb',
            'borderRight': 'none',
            'borderLeft': 'none'
        },
        style_data={
            'backgroundColor': 'white',
            'borderBottom': '1px solid #e5e7eb'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': '#f9fafb'
            }
        ],
        style_as_list_view=True,
        sort_action='native',
        filter_action='native',
    )


def tabela_nao_compareceam(df):
    if df.empty:
        return html.Div('Sem dados para exibir', className='text-muted text-center p-4')

    df_display = df.copy()
    if 'hora_agendamento' in df_display.columns:
        df_display['hora_agendamento'] = df_display['hora_agendamento'].apply(
            lambda x: x.strftime('%H:%M') if x else ''
        )
    if 'data_agendamento' in df_display.columns:
        df_display['data_agendamento'] = df_display['data_agendamento'].apply(
            lambda x: x.strftime('%d/%m/%Y') if x else ''
        )

    columns_to_show = ['booking_id', 'data_agendamento', 'hora_agendamento', 'local_servico', 'nome', 'cpf']
    columns_renamed = {
        'booking_id': 'Booking ID',
        'data_agendamento': 'Data',
        'hora_agendamento': 'Hora',
        'local_servico': 'Local',
        'nome': 'Nome',
        'cpf': 'CPF'
    }

    df_final = df_display[[col for col in columns_to_show if col in df_display.columns]].copy()
    df_final = df_final.rename(columns=columns_renamed)

    return dash_table.DataTable(
        data=df_final.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_final.columns],
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_header={
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold',
            'color': '#1a1a2e',
            'borderBottom': '2px solid #e5e7eb',
            'textAlign': 'center'
        },
        style_cell={
            'padding': '12px 15px',
            'fontFamily': '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
            'fontSize': '14px',
            'color': '#374151',
            'borderBottom': '1px solid #e5e7eb',
            'borderRight': 'none',
            'borderLeft': 'none'
        },
        style_data={
            'backgroundColor': 'white',
            'borderBottom': '1px solid #e5e7eb'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': '#f9fafb'
            }
        ],
        style_as_list_view=True,
        sort_action='native',
        filter_action='native',
    )
