import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc

# Dependencias de tu proyecto
from config import FACEBOOK_ID, INSTAGRAM_ID
from ai import get_openai_response
from layout_components import create_ai_insight_card, create_ai_chat_interface, add_trendline, generate_wordcloud
from data_processing import get_facebook_posts, get_instagram_posts, process_facebook_posts, process_instagram_posts

def register_callbacks(app):
    """Registra todos los callbacks de la sección Redes Sociales."""

    @app.callback(
        Output('social-subtabs-content', 'children'),
        Input('social-subtabs', 'value'),
        State('date-picker', 'start_date'),
        State('date-picker', 'end_date')
    )
    def render_social_subtab_content(subtab_sm, start_date, end_date):
        if not start_date or not end_date:
            return html.P("Selecciona un rango de fechas.", className="text-center mt-5")
        start_date_dt = pd.to_datetime(start_date).tz_localize(None)
        end_date_dt = pd.to_datetime(end_date).tz_localize(None)
        ai_insight_text = "No hay suficientes datos para un análisis IA."
        default_no_data_ai_text = "No hay suficientes datos para un análisis IA."

        fb_posts_raw = get_facebook_posts(FACEBOOK_ID)
        ig_posts_raw = get_instagram_posts(INSTAGRAM_ID)
        df_fb = process_facebook_posts(fb_posts_raw)
        df_ig = process_instagram_posts(ig_posts_raw)
        if not df_fb.empty: df_fb = df_fb[(df_fb['created_time'] >= start_date_dt) & (df_fb['created_time'] <= end_date_dt)]
        if not df_ig.empty: df_ig = df_ig[(df_ig['timestamp'] >= start_date_dt) & (df_ig['timestamp'] <= end_date_dt)]

        no_data_sm_msg = html.Div([html.P("No hay datos de redes sociales para el período seleccionado."), create_ai_insight_card(f'{subtab_sm}-ai-insight-visible'), html.Div(default_no_data_ai_text, id=f'{subtab_sm}-ai-insight-data', style={'display':'none'})])

        if subtab_sm == 'general_sm':
            if df_fb.empty and df_ig.empty: return no_data_sm_msg

            metrics_sm = {
                "FB Impresiones": df_fb['impressions'].sum() if not df_fb.empty else 0,
                "IG Impresiones": df_ig['impressions'].sum() if not df_ig.empty else 0,
                "IG Alcance": df_ig['reach'].sum() if not df_ig.empty else 0,
                "IG Interacciones": df_ig['engagement'].sum() if not df_ig.empty else 0,
                "FB Likes": df_fb['likes_count'].sum() if not df_fb.empty else 0,
                "IG Likes": df_ig['like_count'].sum() if not df_ig.empty else 0,
                "IG Video Views": df_ig['video_views'].sum() if not df_ig.empty else 0,
            }

            fig_ig_imp_trend = go.Figure().update_layout(title="Tendencia Impresiones Instagram (No data)")
            if not df_ig.empty and 'timestamp' in df_ig and 'impressions' in df_ig and len(df_ig) > 1:
                df_ig_trend_data = df_ig.sort_values('timestamp').set_index('timestamp')['impressions'].resample('D').sum().reset_index()
                if len(df_ig_trend_data) > 1:
                    fig_ig_imp_trend = px.line(df_ig_trend_data, x='timestamp', y='impressions', title='Tendencia Impresiones Diarias (Instagram)', markers=True)
                    add_trendline(fig_ig_imp_trend, df_ig_trend_data, 'timestamp', 'impressions')

            context_sm_gen = f"Métricas generales SM: {metrics_sm}. Tendencia de impresiones IG mostrada."
            prompt_sm_gen = "Analiza las métricas generales de Facebook e Instagram. ¿Qué plataforma destaca y en qué métrica? Diagnostica el rendimiento general y sugiere una acción poderosa."
            ai_insight_text = get_openai_response(prompt_sm_gen, context_sm_gen)

            return html.Div([
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([html.H5("Facebook", className="card-title text-primary")] + [html.P(f"{k.replace('FB ','')}: {v:,.0f}") for k,v in metrics_sm.items() if "FB" in k])), md=6, className="mb-3"),
                    dbc.Col(dbc.Card(dbc.CardBody([html.H5("Instagram", className="card-title text-danger")] + [html.P(f"{k.replace('IG ','')}: {v:,.0f}") for k,v in metrics_sm.items() if "IG" in k])), md=6, className="mb-3"),
                ]),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_ig_imp_trend), width=12)], className="mt-3"),
                create_ai_insight_card('general-sm-ai-insight-visible', title="💡 Diagnóstico y Acción (Métricas Generales SM)"),
                html.Div(ai_insight_text, id='general-sm-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('general_sm')
            ])

        elif subtab_sm == 'engagement_sm':
            if df_ig.empty or not all(k in df_ig for k in ['media_type', 'engagement', 'reach']):
                return html.Div([html.P("No hay datos suficientes de Instagram para analizar engagement."), create_ai_insight_card('engagement-sm-ai-insight-visible'), html.Div(default_no_data_ai_text, id='engagement-sm-ai-insight-data', style={'display':'none'})])

            df_ig_eng = df_ig.copy(); df_ig_eng['engagement_rate'] = (df_ig_eng['engagement'].fillna(0) / df_ig_eng['reach'].replace(0, np.nan).fillna(1) * 100).fillna(0)
            eng_by_type = df_ig_eng.groupby('media_type', as_index=False).agg(total_engagement=('engagement', 'sum'), avg_engagement_rate=('engagement_rate', 'mean')).sort_values('total_engagement', ascending=False)

            fig_eng_sum = px.bar(eng_by_type, x='media_type', y='total_engagement', title='Interacciones Totales por Formato (IG)', text_auto=True, color='media_type') if not eng_by_type.empty else go.Figure().update_layout(title='Interacciones Totales por Formato (IG) - No data')
            fig_eng_rate = px.bar(eng_by_type, x='media_type', y='avg_engagement_rate', title='Tasa de Engagement Promedio (%) por Formato (IG)', text_auto='.2f', color='media_type') if not eng_by_type.empty else go.Figure().update_layout(title='Tasa de Engagement Promedio (%) por Formato (IG) - No data')
            if not eng_by_type.empty: fig_eng_rate.update_yaxes(ticksuffix="%")

            if not eng_by_type.empty:
                context_sm_eng = f"Engagement Instagram por formato: {eng_by_type.to_string()}"
                prompt_sm_eng = "Analiza el engagement total y la tasa de engagement por formato en Instagram. ¿Qué formato es más efectivo? Diagnostica y sugiere una acción poderosa para mejorar el engagement."
                ai_insight_text = get_openai_response(prompt_sm_eng, context_sm_eng)
            else:
                ai_insight_text = "No hay datos de engagement para analizar."

            return html.Div([
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_eng_sum), md=6), dbc.Col(dcc.Graph(figure=fig_eng_rate), md=6)]),
                create_ai_insight_card('engagement-sm-ai-insight-visible', title="💡 Diagnóstico y Acción (Engagement IG)"),
                html.Div(ai_insight_text, id='engagement-sm-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('engagement_sm')
            ])

        elif subtab_sm == 'wordmap_sm':
            if df_fb.empty and df_ig.empty: return no_data_sm_msg
            text_fb = " ".join(df_fb['message'].dropna().astype(str)) if not df_fb.empty and 'message' in df_fb else ""
            text_ig = " ".join(df_ig['caption'].dropna().astype(str)) if not df_ig.empty and 'caption' in df_ig else ""
            combined_text = (text_fb + " " + text_ig).strip()
            wordcloud_src = generate_wordcloud(combined_text)

            if wordcloud_src:
                context_sm_wc = "Se ha generado un wordmap con las palabras más frecuentes en las publicaciones de Facebook e Instagram."
                prompt_sm_wc = "Observando un wordmap de las publicaciones, ¿qué temas generales parecen ser predominantes? Diagnostica si estos temas están alineados con la estrategia de contenido y sugiere una acción poderosa para optimizar el mensaje."
                ai_insight_text = get_openai_response(prompt_sm_wc, context_sm_wc)
            else:
                ai_insight_text = "No hay texto en las publicaciones para generar el wordmap o un análisis IA."

            return html.Div([
                html.Img(src=wordcloud_src, style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': 'auto'}) if wordcloud_src else html.P("No se pudo generar el Wordmap."),
                create_ai_insight_card('wordmap-sm-ai-insight-visible', title="💡 Diagnóstico y Acción (Wordmap)"),
                html.Div(ai_insight_text, id='wordmap-sm-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('wordmap_sm')
            ])

        elif subtab_sm == 'top_posts_sm':
            if df_fb.empty and df_ig.empty: return no_data_sm_msg
            df_fb_std = pd.DataFrame(); df_ig_std = pd.DataFrame()
            if not df_fb.empty: df_fb_std = df_fb[['id', 'message', 'created_time', 'likes_count', 'comments_count', 'impressions']].copy().rename(columns={'message': 'content', 'created_time': 'time', 'likes_count': 'likes', 'comments_count':'comments'}); df_fb_std['platform'] = 'Facebook'
            if not df_ig.empty: df_ig_std = df_ig[['id', 'caption', 'timestamp', 'like_count', 'comments_count', 'impressions', 'permalink', 'media_type']].copy().rename(columns={'caption': 'content', 'timestamp': 'time', 'like_count': 'likes', 'comments_count':'comments'}); df_ig_std['platform'] = 'Instagram'

            df_combined = pd.concat([df_fb_std, df_ig_std], ignore_index=True)
            if df_combined.empty: return html.Div([html.P("No hay publicaciones combinadas."), create_ai_insight_card('top-posts-sm-ai-insight-visible'), html.Div(default_no_data_ai_text, id='top-posts-sm-ai-insight-data', style={'display':'none'})])

            df_combined['total_impact'] = df_combined['likes'].fillna(0) + df_combined['comments'].fillna(0) + df_combined['impressions'].fillna(0)
            top_posts_df = df_combined.sort_values('total_impact', ascending=False).head(10)
            if top_posts_df.empty: return html.Div([html.P("No hay publicaciones con impacto."), create_ai_insight_card('top-posts-sm-ai-insight-visible'), html.Div(default_no_data_ai_text, id='top-posts-sm-ai-insight-data', style={'display':'none'})])

            table_rows_sm = []
            for _, row in top_posts_df.iterrows():
                content_display = row['content'][:75] + "..." if pd.notna(row['content']) and len(row['content']) > 75 else row.get('content', 'N/A')
                if row.get('platform') == 'Instagram' and pd.notna(row.get('permalink')): content_display = f"[{content_display}]({row['permalink']})"
                table_rows_sm.append({'Plataforma': row.get('platform'), 'Contenido': content_display, 'Fecha': pd.to_datetime(row['time']).strftime('%Y-%m-%d') if pd.notna(row.get('time')) else 'N/A', 'Likes': f"{row.get('likes',0):.0f}", 'Comentarios': f"{row.get('comments',0):.0f}", 'Impresiones': f"{row.get('impressions',0):.0f}", 'Impacto': f"{row.get('total_impact',0):.0f}"})

            context_sm_tp = f"Top posts por impacto (likes+comments+impressions): {top_posts_df[['platform', 'content', 'total_impact']].head(3).to_string()}"
            prompt_sm_tp = "Analiza las características comunes de las publicaciones con mayor impacto. ¿Qué tipo de contenido o plataforma funciona mejor? Diagnostica y sugiere una acción poderosa para replicar este éxito."
            ai_insight_text = get_openai_response(prompt_sm_tp, context_sm_tp)

            return html.Div([
                dash_table.DataTable(data=table_rows_sm, columns=[{'name': c, 'id': c, 'presentation': 'markdown' if c=='Contenido' else 'input'} for c in table_rows_sm[0].keys()], style_table={'overflowX': 'auto', 'minWidth': '100%'}, style_cell={'textAlign': 'left', 'padding': '10px', 'minWidth': '100px', 'width': '150px', 'maxWidth': '300px', 'whiteSpace': 'normal', 'height': 'auto'}, style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}, markdown_options={'html': True}, page_size=10, sort_action='native', filter_action='native'),
                create_ai_insight_card('top-posts-sm-ai-insight-visible', title="💡 Diagnóstico y Acción (Top Posts)"),
                html.Div(ai_insight_text, id='top-posts-sm-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('top_posts_sm')
            ])
        return html.P(f"Pestaña SM '{subtab_sm}' no implementada.")

    # Callbacks para actualizar las tarjetas de IA visibles
    sm_ai_insight_visible_ids = ['general-sm-ai-insight-visible', 'engagement-sm-ai-insight-visible', 'wordmap-sm-ai-insight-visible', 'top-posts-sm-ai-insight-visible']
    sm_ai_insight_data_ids = ['general-sm-ai-insight-data', 'engagement-sm-ai-insight-data', 'wordmap-sm-ai-insight-data', 'top-posts-sm-ai-insight-data']

    for visible_id, data_id in zip(sm_ai_insight_visible_ids, sm_ai_insight_data_ids):
        @app.callback(Output(visible_id, 'children'), Input(data_id, 'children'))
        def update_sm_ai_card_generic(ai_text):
            default_no_data_msg = "Análisis IA no disponible o datos insuficientes."
            specific_no_data_msgs = [
                "No hay suficientes datos para un análisis IA.",
                "No hay datos de engagement para analizar.",
                "No hay texto en las publicaciones para generar el wordmap o un análisis IA."
            ]
            if not ai_text: return html.P(default_no_data_msg)
            ai_text_strip = ai_text.strip()
            if not ai_text_strip or any(msg in ai_text_strip for msg in specific_no_data_msgs):
                return html.P(default_no_data_msg)
            return html.P(ai_text)

    # Registrar callbacks de chat
    sm_subtabs_with_chat = ['general_sm', 'engagement_sm', 'wordmap_sm', 'top_posts_sm']
    for tab_id in sm_subtabs_with_chat:
        @app.callback(
            Output(f'{tab_id}-chat-history', 'children'),
            Input(f'{tab_id}-chat-submit', 'n_clicks'),
            State(f'{tab_id}-chat-input', 'value'),
            State(f'{tab_id}-chat-history', 'children'),
            State('social-subtabs', 'value'),
            prevent_initial_call=True,
            memoize=True
        )
        def update_chat(n_clicks, user_input, history, current_tab_value, tab_id=tab_id):
            if not n_clicks or not user_input: return history
            if history is None: history = []
            elif not isinstance(history, list): history = [history]

            context = f"Estás en la pestaña '{tab_id}' (sub-pestaña actual de SM: {current_tab_value}). El usuario tiene una pregunta."
            ai_response = get_openai_response(user_input, context)

            new_history_entry_user = html.P([html.B("Tú: ", style={'color': '#007bff'}), user_input], style={'margin': '5px 0'})
            new_history_entry_ai = html.P([html.B("SkyIntel AI: ", style={'color': '#28a745'}), ai_response], style={'background': '#f0f0f0', 'padding': '8px', 'borderRadius': '5px', 'margin': '5px 0'})

            return history + [new_history_entry_user, new_history_entry_ai]