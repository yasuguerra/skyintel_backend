from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Dependencias de tu proyecto
from ai import get_openai_response
from data_processing import unify_data, clean_df, safe_sorted_unique

def register_ops_sales_callbacks(app):
    @app.callback(
        [
            Output('output-kpis', 'children'),
            Output('destino-filter', 'options'),
            Output('operador-filter', 'options'),
            Output('mes-filter', 'options'),
            Output('vuelos-mes', 'figure'),
            Output('ingresos-mes', 'figure'),
            Output('ganancia-mes', 'figure'),
            Output('ganancia-total-mes', 'figure'),
            Output('ops-total-mes', 'figure'),
            Output('vuelos-tiempo', 'figure'),
            Output('ingresos-tiempo', 'figure'),
            Output('ganancia-tiempo', 'figure'),
            Output('top-destinos-vuelos', 'figure'),
            Output('top-destinos-ganancia', 'figure'),
            Output('pasajeros-destino', 'figure'),
            Output('vuelos-operador', 'figure'),
            Output('ganancia-aeronave', 'figure'),
            Output('top-ganancia-operador', 'figure'),
            Output('top-ganancia-aeronave', 'figure'),
            Output('destino-heatmap', 'options'),
            Output('heatmap-gain-destino-dia', 'figure'),
            Output('heatmap-count-destino-dia', 'figure'),
            Output('heatmap-dia-hora', 'figure'),
            Output('ticket-promedio', 'figure'),
            Output('tabla-detallada', 'data'),
            Output('tabla-detallada', 'columns'),
            Output('error-message', 'children'),
            # Outputs para análisis IA
            Output('ai-insight-comparativo-general', 'children'),
            Output('ai-insight-vuelos-destinos', 'children'),
            Output('ai-insight-operadores-aeronaves', 'children'),
            Output('ai-insight-analisis-avanzado', 'children')
        ],
        [
            Input('upload-data', 'contents'),
            Input('upload-data', 'filename'),
            Input('destino-filter', 'value'),
            Input('operador-filter', 'value'),
            Input('mes-filter', 'value'),
            Input('destino-heatmap', 'value')
        ]
    )
    def update_dashboard(contents, filenames, destino_filter_val, operador_filter_val, mes_filter_val, destino_heatmap_val):
        empty_fig = go.Figure()
        no_ai_insight = "No hay suficientes datos para generar un análisis IA."
        initial_return_state = [
            [], [], [], [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig,
            empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig,
            empty_fig, empty_fig, empty_fig, empty_fig, [],
            empty_fig, empty_fig, empty_fig, empty_fig, [], [], '',
            no_ai_insight, no_ai_insight, no_ai_insight, no_ai_insight
        ]

        if contents is None or filenames is None:
            return initial_return_state

        df, err = unify_data(contents, filenames)
        if err:
            initial_return_state[-5] = err
            return initial_return_state

        if df.empty:
            initial_return_state[-5] = "No data to display after processing files."
            return initial_return_state

        df = clean_df(df)
        df_plot_original = df.copy()

        filtered_df = df.copy()
        if destino_filter_val: filtered_df = filtered_df[filtered_df['Destino'].astype(str).isin(destino_filter_val)]
        if operador_filter_val: filtered_df = filtered_df[filtered_df['Operador'].astype(str).isin(operador_filter_val)]
        if mes_filter_val: filtered_df = filtered_df[filtered_df['Mes'].astype(str).isin([str(m) for m in mes_filter_val])]

        if filtered_df.empty:
            initial_return_state[-5] = "No data matches the selected filters."
            initial_return_state[1] = [{'label': d, 'value': d} for d in safe_sorted_unique(df_plot_original['Destino'])]
            initial_return_state[2] = [{'label': o, 'value': o} for o in safe_sorted_unique(df_plot_original['Operador'])]
            initial_return_state[3] = [{'label': m, 'value': m} for m in safe_sorted_unique(df_plot_original['Mes'])]
            initial_return_state[19] = [{'label': d, 'value': d} for d in safe_sorted_unique(df_plot_original['Destino'])]
            return initial_return_state

        # KPIs
        kpi_cards_list = []
        for year_val in sorted(filtered_df['Año'].unique()):
            df_year = filtered_df[filtered_df['Año'] == year_val]
            if df_year.empty: continue
            kpi_cards_list.append(dbc.Col(dbc.Card([
                dbc.CardHeader(f"Resumen Año {year_val}", className="text-white", style={'backgroundColor': '#002859'}),
                dbc.CardBody([
                    html.H5("Vuelos Totales", className="card-title"), html.P(f"{df_year.shape[0]}", className="card-text fs-4 fw-bold"),
                    html.H5("Pasajeros Totales", className="card-title mt-2"), html.P(f"{int(df_year['Número de pasajeros'].sum())}", className="card-text fs-4 fw-bold"),
                    html.H5("Ingresos Totales", className="card-title mt-2"), html.P(f"${df_year['Monto total a cobrar'].sum():,.2f}", className="card-text fs-4 fw-bold"),
                    html.H5("Ganancia Total", className="card-title mt-2"), html.P(f"${df_year['Ganancia'].sum():,.2f}", className="card-text fs-4 fw-bold"),
                    html.H5("Ticket Promedio", className="card-title mt-2"), html.P(f"${df_year['Monto total a cobrar'].mean() if not df_year.empty else 0:,.2f}", className="card-text fs-4 fw-bold"),
                ])
            ], className="shadow-sm mb-4 h-100"), xs=12, sm=6, md=4, lg=3))
        output_kpis_children = dbc.Row(kpi_cards_list)

        # Opciones de Filtros
        destino_options = [{'label': d, 'value': d} for d in safe_sorted_unique(df_plot_original['Destino'])]
        operador_options = [{'label': o, 'value': o} for o in safe_sorted_unique(df_plot_original['Operador'])]
        mes_options = [{'label': m, 'value': m} for m in safe_sorted_unique(df_plot_original['Mes'])]
        destino_heatmap_options = [{'label': d, 'value': d} for d in safe_sorted_unique(df_plot_original['Destino'])]

        # Figuras
        df_plot = filtered_df.copy()
        meses_order = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        df_plot['MonthName'] = pd.Categorical(df_plot['Fecha y hora del vuelo'].dt.strftime('%B'), categories=meses_order, ordered=True)
        
        # Lógica de las figuras (igual que en tu archivo original)
        vuelos_mes_data = df_plot.groupby(['Año', 'MonthName'], observed=False).size().reset_index(name='Vuelos')
        fig_vuelos_mes = px.line(vuelos_mes_data, x='MonthName', y='Vuelos', color='Año', markers=True, title='Vuelos por Mes')
        ingresos_mes_data = df_plot.groupby(['Año', 'MonthName'], observed=False)['Monto total a cobrar'].sum().reset_index()
        fig_ingresos_mes = px.line(ingresos_mes_data, x='MonthName', y='Monto total a cobrar', color='Año', markers=True, title='Ingresos por Mes')
        ganancia_mes_data = df_plot.groupby(['Año', 'MonthName'], observed=False)['Ganancia'].sum().reset_index()
        fig_ganancia_mes = px.line(ganancia_mes_data, x='MonthName', y='Ganancia', color='Año', markers=True, title='Ganancia por Mes')

        df_plot['year_month'] = df_plot['Fecha y hora del vuelo'].dt.to_period('M').astype(str)
        ganancia_timeline = df_plot.groupby('year_month')['Ganancia'].sum().reset_index().sort_values('year_month')
        fig_ganancia_total_mes = go.Figure(go.Scatter(x=ganancia_timeline['year_month'], y=ganancia_timeline['Ganancia'], mode='lines+markers', name='Ganancia Mensual'))
        if ganancia_timeline.shape[0] > 1:
            x_fit = np.arange(len(ganancia_timeline)); y_fit = ganancia_timeline['Ganancia'].values
            z = np.polyfit(x_fit, y_fit, 1); p = np.poly1d(z)
            fig_ganancia_total_mes.add_trace(go.Scatter(x=ganancia_timeline['year_month'], y=p(x_fit), mode='lines', name='Tendencia', line=dict(dash='dash')))
        fig_ganancia_total_mes.update_layout(title='Ganancia Mensual Total + Tendencia', xaxis_title='Mes', yaxis_title='Ganancia', xaxis=dict(tickangle=45))

        ops_total_mes_data = df_plot.groupby('MonthName', observed=False).size().reset_index(name='Vuelos')
        ops_total_mes_data['MonthName_cat'] = pd.Categorical(ops_total_mes_data['MonthName'], categories=meses_order, ordered=True)
        ops_total_mes_data = ops_total_mes_data.sort_values('MonthName_cat')
        fig_ops_total_mes = go.Figure(go.Scatter(x=ops_total_mes_data['MonthName'], y=ops_total_mes_data['Vuelos'], mode='lines+markers', name='Operaciones Mensuales'))
        if ops_total_mes_data.shape[0] > 1:
            y_fit_ops = ops_total_mes_data['Vuelos'].values; x_fit_ops = np.arange(len(y_fit_ops))
            poly_degree_ops = min(2, len(y_fit_ops)-1) if len(y_fit_ops) > 2 else 1
            z_ops = np.polyfit(x_fit_ops, y_fit_ops, poly_degree_ops); p_ops = np.poly1d(z_ops)
            fig_ops_total_mes.add_trace(go.Scatter(x=ops_total_mes_data['MonthName'], y=p_ops(x_fit_ops), mode='lines', name='Tendencia', line=dict(dash='dash')))
        fig_ops_total_mes.update_layout(title='Operaciones Mensuales Totales + Tendencia')
            
        fig_vuelos_tiempo, fig_ingresos_tiempo, fig_ganancia_tiempo = go.Figure(), go.Figure(), go.Figure()
        for year_val_unique in df_plot['Año'].unique():
            df_year_ts = df_plot[df_plot['Año'] == year_val_unique].set_index('Fecha y hora del vuelo').sort_index()
            if not df_year_ts.empty:
                vuelos_sem = df_year_ts.resample('W').size().reset_index(name='Vuelos')
                fig_vuelos_tiempo.add_scatter(x=vuelos_sem['Fecha y hora del vuelo'], y=vuelos_sem['Vuelos'], mode='lines', name=f'Año {year_val_unique}')
                ingresos_sem = df_year_ts['Monto total a cobrar'].resample('W').sum().reset_index()
                fig_ingresos_tiempo.add_scatter(x=ingresos_sem['Fecha y hora del vuelo'], y=ingresos_sem['Monto total a cobrar'], mode='lines', name=f'Año {year_val_unique}')
                ganancia_sem = df_year_ts['Ganancia'].resample('W').sum().reset_index()
                fig_ganancia_tiempo.add_scatter(x=ganancia_sem['Fecha y hora del vuelo'], y=ganancia_sem['Ganancia'], mode='lines', name=f'Año {year_val_unique}')
        fig_vuelos_tiempo.update_layout(title='Vuelos por Semana'); fig_ingresos_tiempo.update_layout(title='Ingresos por Semana'); fig_ganancia_tiempo.update_layout(title='Ganancia por Semana')
        
        top_destinos_vuelos_data = df_plot.groupby(['Año', 'Destino'], observed=False).size().reset_index(name='Cantidad').sort_values(['Cantidad'], ascending=False)
        fig_top_destinos_vuelos = px.bar(top_destinos_vuelos_data, x='Destino', y='Cantidad', color='Año', barmode='group', title='Top Destinos por Número de Vuelos')
        top_destinos_ganancia_data = df_plot.groupby(['Año', 'Destino'], observed=False)['Ganancia'].sum().reset_index().sort_values(['Ganancia'], ascending=False)
        fig_top_destinos_ganancia = px.bar(top_destinos_ganancia_data, x='Destino', y='Ganancia', color='Año', barmode='group', title='Top Destinos por Ganancia')
        pasajeros_destino_data = df_plot.groupby(['Año', 'Destino'], observed=False)['Número de pasajeros'].sum().reset_index().sort_values(['Número de pasajeros'], ascending=False)
        fig_pasajeros_destino = px.bar(pasajeros_destino_data, x='Destino', y='Número de pasajeros', color='Año', barmode='group', title='Top Destinos por Pasajeros')
        
        vuelos_operador_data = df_plot.groupby(['Año', 'Operador'], observed=False).size().reset_index(name='Vuelos').sort_values(['Año', 'Vuelos'], ascending=[True, False])
        fig_vuelos_operador = px.bar(vuelos_operador_data, x='Operador', y='Vuelos', color='Año', barmode='group', title='Vuelos por Operador')
        ganancia_aeronave_data = df_plot.groupby(['Año', 'Aeronave'], observed=False)['Ganancia'].sum().reset_index().sort_values(['Año', 'Ganancia'], ascending=[True, False])
        fig_ganancia_aeronave = px.bar(ganancia_aeronave_data, x='Aeronave', y='Ganancia', color='Año', barmode='group', title='Ganancia por Aeronave')
        top_ganancia_operador_data = df_plot.groupby('Operador', observed=False)['Ganancia'].sum().reset_index().sort_values('Ganancia', ascending=False)
        fig_top_ganancia_operador = px.bar(top_ganancia_operador_data, x='Operador', y='Ganancia', title="Operadores con más Ganancias Totales")
        top_ganancia_aeronave_data = df_plot.groupby('Aeronave', observed=False)['Ganancia'].sum().reset_index().sort_values('Ganancia', ascending=False)
        fig_top_ganancia_aeronave = px.bar(top_ganancia_aeronave_data, x='Aeronave', y='Ganancia', title="Aeronaves con más Ganancias Totales")

        fig_heatmap_gain_destino, fig_heatmap_count_destino, fig_heatmap = empty_fig, empty_fig, empty_fig
        ticket_promedio_df_data = df_plot.groupby(['Año', 'Destino'], observed=False)['Monto total a cobrar'].mean().reset_index()
        fig_ticket_promedio = px.bar(ticket_promedio_df_data, x='Destino', y='Monto total a cobrar', color='Año', barmode='group', title='Ticket Promedio por Destino y Año')
        
        context_aa_parts = []
        if not ticket_promedio_df_data.empty:
            context_aa_parts.append(f"Ticket promedio por destino/año (top 5): {ticket_promedio_df_data.head().to_string()}")
        if 'Año' in df_plot.columns and df_plot['Año'].nunique() > 0:
            year_latest = sorted(df_plot['Año'].astype(str).unique())[-1]
            df_hm = df_plot[(df_plot['Año'].astype(str) == year_latest) & (df_plot['hora'] >= 6) & (df_plot['hora'] <= 18)].copy()
            dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            if not df_hm.empty:
                df_hm['nombre_dia'] = pd.Categorical(df_hm['nombre_dia'], categories=dias_orden, ordered=True)
                heatmap_data = df_hm.groupby(['nombre_dia', 'hora'], observed=False).size().reset_index(name='Vuelos')
                if not heatmap_data.empty:
                    fig_heatmap = px.density_heatmap(heatmap_data, x='hora', y='nombre_dia', z='Vuelos', title=f'Vuelos por Día y Hora ({year_latest}, 6am-6pm)', nbinsx=13, nbinsy=7, color_continuous_scale='rdylbu')
                    context_aa_parts.append(f"Heatmap vuelos día/hora (resumen): {heatmap_data.describe().to_string()}")
                if destino_heatmap_val and destino_heatmap_val in df_hm['Destino'].unique():
                    df_sel = df_hm[df_hm['Destino'] == destino_heatmap_val]
                    if not df_sel.empty:
                        heatmap_gain_data = df_sel.groupby(['nombre_dia', 'hora'], observed=False)['Ganancia'].sum().reset_index()
                        if not heatmap_gain_data.empty:
                             heatmap_gain_data['nombre_dia'] = pd.Categorical(heatmap_gain_data['nombre_dia'], categories=dias_orden, ordered=True)
                             fig_heatmap_gain_destino = px.density_heatmap(heatmap_gain_data, x='hora', y='nombre_dia', z='Ganancia', title=f'Heatmap Ganancia - {destino_heatmap_val}', nbinsx=13, nbinsy=7, color_continuous_scale='rdylbu')
                             context_aa_parts.append(f"Heatmap ganancia para {destino_heatmap_val} (resumen): {heatmap_gain_data.describe().to_string()}")
                        heatmap_count_data = df_sel.groupby(['nombre_dia', 'hora'], observed=False).size().reset_index(name='Vuelos')
                        if not heatmap_count_data.empty:
                            heatmap_count_data['nombre_dia'] = pd.Categorical(heatmap_count_data['nombre_dia'], categories=dias_orden, ordered=True)
                            fig_heatmap_count_destino = px.density_heatmap(heatmap_count_data, x='hora', y='nombre_dia', z='Vuelos', title=f'Heatmap Operaciones - {destino_heatmap_val}', nbinsx=13, nbinsy=7, color_continuous_scale='rdylbu')

        # Insights IA
        context_cg = f"Datos comparativos: Vuelos/mes: {vuelos_mes_data.to_string()}\nIngresos/mes: {ingresos_mes_data.to_string()}\nGanancia/mes: {ganancia_mes_data.to_string()}"
        ai_insight_comparativo = get_openai_response("Analiza tendencias comparativas de vuelos, ingresos y ganancias. Da un diagnóstico y una acción poderosa.", context_cg)
        context_vd = f"Top destinos por vuelos: {top_destinos_vuelos_data.head().to_string()}\nTop destinos por ganancia: {top_destinos_ganancia_data.head().to_string()}"
        ai_insight_vuelos = get_openai_response("Analiza los top destinos por vuelos y ganancia. Diagnostica y sugiere una acción para optimizar rutas o rentabilidad.", context_vd)
        context_oa = f"Vuelos por operador: {vuelos_operador_data.head().to_string()}\nGanancia por aeronave: {ganancia_aeronave_data.head().to_string()}"
        ai_insight_operadores = get_openai_response("Analiza rendimiento por operador y aeronave. ¿Qué diagnóstico y acción poderosa sugieres?", context_oa)
        ai_insight_avanzado = get_openai_response("Con base en heatmaps y ticket promedio, ¿qué patrones de demanda u oportunidad se observan? Da un diagnóstico y una acción poderosa.", "\n".join(context_aa_parts)) if context_aa_parts else no_ai_insight

        # Tabla
        display_columns = ['Año', 'Mes', 'Fecha y hora del vuelo', 'Destino', 'Operador', 'Aeronave', 'Número de pasajeros', 'Monto total a cobrar', 'Ganancia', 'Cliente', 'Fase actual']
        df_table_display = df_plot[[col for col in display_columns if col in df_plot.columns]].copy()
        df_table_display['Fecha y hora del vuelo'] = df_table_display['Fecha y hora del vuelo'].dt.strftime('%Y-%m-%d %H:%M')
        tabla_data = df_table_display.to_dict('records')
        tabla_columns = [{'name': col, 'id': col} for col in df_table_display.columns]

        return (
            output_kpis_children, destino_options, operador_options, mes_options,
            fig_vuelos_mes, fig_ingresos_mes, fig_ganancia_mes, fig_ganancia_total_mes, fig_ops_total_mes,
            fig_vuelos_tiempo, fig_ingresos_tiempo, fig_ganancia_tiempo, fig_top_destinos_vuelos,
            fig_top_destinos_ganancia, fig_pasajeros_destino, fig_vuelos_operador, fig_ganancia_aeronave,
            fig_top_ganancia_operador, fig_top_ganancia_aeronave, destino_heatmap_options,
            fig_heatmap_gain_destino, fig_heatmap_count_destino, fig_heatmap, fig_ticket_promedio,
            tabla_data, tabla_columns, '',
            ai_insight_comparativo, ai_insight_vuelos, ai_insight_operadores, ai_insight_avanzado
        )