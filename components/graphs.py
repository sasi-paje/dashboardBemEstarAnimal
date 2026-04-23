import plotly.express as px
import plotly.graph_objects as go

def grafico_ocupacao(df_vagas):
    if df_vagas.empty:
        return go.Figure()

    df_grouped = df_vagas.groupby('servico').agg({
        'total_vagas': 'sum',
        'total_vagas_ocupadas': 'sum',
        'total_vagas_livres': 'sum'
    }).reset_index()

    fig = px.bar(
        df_grouped,
        x='servico',
        y=['total_vagas_ocupadas', 'total_vagas_livres'],
        title='Ocupacao por Local',
        labels={'name_service': 'Local', 'value': 'Vagas', 'variable': 'Tipo'},
        color_discrete_map={
            'total_vagas_ocupadas': '#3B82F6',
            'total_vagas_livres': '#E5E7EB'
        },
        barmode='stack'
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#1a1a2e'),
        title=dict(font=dict(size=16)),
        legend=dict(
            title='',
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        ),
        margin=dict(l=20, r=20, t=60, b=20),
        height=300
    )

    fig.update_xaxes(
        title='',
        tickangle=0,
        gridcolor='#f3f4f6'
    )

    fig.update_yaxes(
        title='Quantidade',
        gridcolor='#f3f4f6'
    )

    return fig


def grafico_fila_status(df_fila):
    if df_fila.empty:
        return go.Figure()

    df_grouped = df_fila.groupby(['local_servico', 'status']).agg({
        'quantidade': 'sum'
    }).reset_index()

    fig = px.bar(
        df_grouped,
        x='local_servico',
        y='quantidade',
        color='status',
        title='Status da Fila por Local',
        labels={'local_servico': 'Local', 'quantidade': 'Pessoas', 'status': 'Status'},
        barmode='group'
    )

    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='#1a1a2e'),
        title=dict(font=dict(size=16)),
        legend=dict(
            title='',
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        ),
        margin=dict(l=20, r=20, t=60, b=20),
        height=300
    )

    fig.update_xaxes(
        title='',
        tickangle=0,
        gridcolor='#f3f4f6'
    )

    fig.update_yaxes(
        title='Quantidade',
        gridcolor='#f3f4f6'
    )

    return fig


def grafico_pizza_status(df_fila):
    if df_fila.empty:
        return go.Figure()

    df_grouped = df_fila.groupby('status').agg({
        'quantidade': 'sum'
    }).reset_index()

    fig = px.pie(
        df_grouped,
        values='quantidade',
        names='status',
        title='Distribuicao de Status',
        hole=0.4
    )

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(color='#1a1a2e'),
        title=dict(font=dict(size=16)),
        legend=dict(
            title='',
            orientation='v',
            yanchor='middle',
            y=0.5,
            xanchor='left',
            x=1.02
        ),
        margin=dict(l=20, r=60, t=60, b=20),
        height=300
    )

    return fig
