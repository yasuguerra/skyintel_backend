import pandas as pd
import base64
import io
import logging
import requests
import re
from datetime import datetime, timedelta

# Dependencias de tu proyecto
from config import FB_ACCESS_TOKEN
from utils import query_ga

# --- Funciones de 'ops_sales.py' ---

columnas_esperadas = [
    'Fase actual', 'Tipo de aeronave', 'Fecha y hora del vuelo',
    'Número de pasajeros', 'Monto total a cobrar', 'Cliente', 'Aeronave', 'Operador',
    'Costo del vuelo (acordado con el operador)', 'Horas de vuelo', 'Mes', 'Ganancia',
    'Destino', 'dia', 'nombre_dia', 'hora'
]

def safe_sorted_unique(series):
    """Devuelve una lista ordenada de valores únicos y limpios de una serie de pandas."""
    return sorted([str(x) for x in series.dropna().unique() if str(x).strip() and str(x).lower() != 'nan'])

def clean_df(df):
    """Limpia y formatea las columnas del DataFrame de operaciones."""
    df['Fecha y hora del vuelo'] = pd.to_datetime(df['Fecha y hora del vuelo'], errors='coerce')
    df['Mes'] = df['Mes'].astype(str)
    df['hora'] = pd.to_numeric(df['hora'], errors='coerce')
    df['Ganancia'] = pd.to_numeric(df['Ganancia'], errors='coerce').fillna(0)
    df['Monto total a cobrar'] = pd.to_numeric(df['Monto total a cobrar'], errors='coerce').fillna(0)
    df['Número de pasajeros'] = pd.to_numeric(df['Número de pasajeros'], errors='coerce').fillna(0)
    return df

def try_read_csv(decoded):
    """Intenta leer un CSV con diferentes codificaciones."""
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try:
            df = pd.read_csv(io.StringIO(decoded.decode(enc)))
            return df, None
        except Exception as e:
            last_error = str(e)
            continue
    return None, f"No se pudo leer el archivo CSV. Intenta guardarlo como UTF-8 o Latin1. Error: {last_error}"

def unify_data(contents, filenames):
    """Unifica múltiples archivos CSV en un solo DataFrame."""
    all_dfs = []
    if not contents or not filenames:
        return pd.DataFrame(columns=columnas_esperadas + ['Archivo', 'Año']), "No files uploaded or empty content."

    for content, fname in zip(contents, filenames):
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)
        df, err = try_read_csv(decoded)
        if err:
            return None, err

        missing_cols = [col for col in columnas_esperadas if col not in df.columns]
        if missing_cols:
            return None, f"El archivo '{fname}' no tiene las columnas requeridas. Faltan: {', '.join(missing_cols)}"

        df['Archivo'] = fname
        match = re.search(r'(\d{4})', fname)
        df['Año'] = match.group(0) if match else fname.split('.')[0]
        all_dfs.append(df)

    if not all_dfs:
         return pd.DataFrame(columns=columnas_esperadas + ['Archivo', 'Año']), "No valid data processed from files."

    all_data = pd.concat(all_dfs, ignore_index=True)
    return all_data, None

# --- Funciones de 'web_social.py' ---

def get_facebook_data(endpoint, params={}):
    """Realiza una solicitud a la API Graph de Facebook."""
    base_url = "https://graph.facebook.com/v22.0/"
    url = f"{base_url}{endpoint}"
    params['access_token'] = FB_ACCESS_TOKEN
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error en la solicitud a la API Graph de Facebook: {e}")
        return {}

def get_facebook_posts(facebook_id):
    """Obtiene las publicaciones de una página de Facebook."""
    endpoint = f"{facebook_id}/posts"
    params = {'fields': 'id,message,created_time,likes.summary(true),comments.summary(true),shares,insights.metric(post_impressions)'}
    data = get_facebook_data(endpoint, params)
    return data.get('data', [])

def get_instagram_posts(instagram_id):
    """Obtiene los medios de una cuenta de Instagram."""
    endpoint = f"{instagram_id}/media"
    params = {'fields': 'id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,username,like_count,comments_count,insights.metric(impressions,reach,total_interactions,video_views)'}
    data = get_facebook_data(endpoint, params)
    return data.get('data', [])

def process_facebook_posts(posts):
    """Procesa la respuesta de la API de publicaciones de Facebook a un DataFrame."""
    if not posts: return pd.DataFrame(columns=['id', 'message', 'created_time', 'likes_count', 'comments_count', 'shares_count', 'impressions'])
    df = pd.DataFrame(posts)
    if 'likes' in df.columns: df['likes_count'] = df['likes'].apply(lambda x: x['summary']['total_count'] if isinstance(x, dict) and 'summary' in x else 0)
    else: df['likes_count'] = 0
    if 'comments' in df.columns: df['comments_count'] = df['comments'].apply(lambda x: x['summary']['total_count'] if isinstance(x, dict) and 'summary' in x else 0)
    else: df['comments_count'] = 0
    if 'shares' in df.columns: df['shares_count'] = df['shares'].apply(lambda x: x.get('count', 0) if isinstance(x, dict) else 0)
    else: df['shares_count'] = 0
    if 'insights' in df.columns: df['impressions'] = df['insights'].apply(lambda x: next((item['values'][0]['value'] for item in x.get('data', []) if item.get('name') == 'post_impressions'), 0) if isinstance(x, dict) else 0)
    else: df['impressions'] = 0
    if 'created_time' in df.columns: df['created_time'] = pd.to_datetime(df['created_time']).dt.tz_localize(None)
    else: df['created_time'] = pd.NaT
    return df[['id', 'message', 'created_time', 'likes_count', 'comments_count', 'shares_count', 'impressions']]

def process_instagram_posts(posts):
    """Procesa la respuesta de la API de medios de Instagram a un DataFrame."""
    if not posts: return pd.DataFrame(columns=['id', 'caption', 'media_type', 'media_url', 'permalink', 'thumbnail_url', 'timestamp', 'username', 'like_count', 'comments_count', 'impressions', 'reach', 'engagement', 'video_views'])
    df = pd.DataFrame(posts)
    if 'insights' in df.columns:
        df['impressions'] = df['insights'].apply(lambda x: next((item['values'][0]['value'] for item in x.get('data', []) if item.get('name') == 'impressions'), 0) if isinstance(x, dict) else 0)
        df['reach'] = df['insights'].apply(lambda x: next((item['values'][0]['value'] for item in x.get('data', []) if item.get('name') == 'reach'), 0) if isinstance(x, dict) else 0)
        df['engagement'] = df['insights'].apply(lambda x: next((item['values'][0]['value'] for item in x.get('data', []) if item.get('name') == 'total_interactions'), 0) if isinstance(x, dict) else 0)
        df['video_views'] = df['insights'].apply(lambda x: next((item['values'][0]['value'] for item in x.get('data', []) if item.get('name') == 'video_views'), 0) if isinstance(x, dict) else 0)
    else:
        df['impressions'] = df['reach'] = df['engagement'] = df['video_views'] = 0
    if 'timestamp' in df.columns: df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    else: df['timestamp'] = pd.NaT
    for col in ['like_count', 'comments_count']:
        if col not in df.columns: df[col] = 0
    return df[['id', 'caption', 'media_type', 'media_url', 'permalink', 'thumbnail_url', 'timestamp', 'username', 'like_count', 'comments_count', 'impressions', 'reach', 'engagement', 'video_views']]

def get_funnel_data(steps_config, start_date, end_date):
    """Obtiene los datos para los gráficos de embudo desde Google Analytics."""
    counts = []
    labels = []
    for step in steps_config:
        labels.append(step['label'])
        if step['value'] == 'page_view':
            df_step_sessions = query_ga(metrics=['sessions'], dimensions=['eventName'], start_date=start_date, end_date=end_date)
            count = int(df_step_sessions['sessions'].sum()) if not df_step_sessions.empty else 0
        else:
            metric_to_use = 'eventCount'
            dim_to_use = 'eventName'
            df_step = query_ga(metrics=[metric_to_use], dimensions=[dim_to_use], start_date=start_date, end_date=end_date)
            if not df_step.empty:
                df_step_filtered = df_step[df_step[dim_to_use] == step['value']]
                count = int(df_step_filtered[metric_to_use].sum()) if not df_step_filtered.empty else 0
            else:
                count = 0
        counts.append(count)
    return labels, counts