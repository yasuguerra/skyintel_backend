# google_ads_api.py (VERSIÓN FINAL CORREGIDA)

import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from google.auth.exceptions import RefreshError

# ---------- 1) Localizar el YAML ----------
PROJECT_YAML = Path(__file__).resolve().parent / "google-ads.yaml"

def load_client(config_path: str | os.PathLike | None = None) -> GoogleAdsClient:
    """
    Carga GoogleAdsClient con la siguiente prioridad:
      1) Ruta explícita `config_path`
      2) Variable de entorno GOOGLE_ADS_CONFIGURATION_FILE_PATH
      3) google-ads.yaml junto al proyecto (PROJECT_YAML)
      4) ~/.google-ads.yaml (comportamiento por defecto del SDK)
    """
    if config_path:
        return GoogleAdsClient.load_from_storage(str(config_path))

    env_path = os.getenv("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
    if env_path:
        return GoogleAdsClient.load_from_storage(env_path)

    if PROJECT_YAML.exists():
        return GoogleAdsClient.load_from_storage(str(PROJECT_YAML))

    return GoogleAdsClient.load_from_storage()

def load_client_safe(config_path: str | os.PathLike | None = None) -> GoogleAdsClient:
    """
    Igual que load_client() pero captura RefreshError para
    devolver un RuntimeError con mensaje amigable; útil en Dash.
    """
    try:
        return load_client(config_path)
    except RefreshError as e:
        raise RuntimeError(
            "⚠️ Credenciales de Google Ads inválidas o revocadas. "
            "Genera un refresh_token nuevo y actualiza google-ads.yaml."
        ) from e

# ---------- 2) GAQL queries ----------
GAQL = """
SELECT
  segments.date,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_micros
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
ORDER BY segments.date
"""

GAQL_KEYWORDS = """
SELECT
  segments.date,
  ad_group_criterion.keyword.text,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros
FROM keyword_view
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND ad_group_criterion.status != 'REMOVED'
"""

# --- SECCIÓN CORREGIDA ---
GAQL_GEO = """
SELECT
  segments.date,
  campaign.name, -- Se puede añadir el nombre de la campaña para más contexto
  segments.geo_target_city,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros
FROM geographic_view -- <-- CAMBIO CLAVE: Se usa geographic_view en lugar de campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND segments.geo_target_city IS NOT NULL
"""
# --- FIN DE LA SECCIÓN CORREGIDA ---


# ---------- 3) Funciones de descarga ----------
def fetch_ads_metrics(client: GoogleAdsClient,
                      customer_id: str,
                      start: str,
                      end: str) -> pd.DataFrame:
    """Métricas por campaña, día a día."""
    svc = client.get_service("GoogleAdsService")
    resp = svc.search_stream(customer_id=customer_id,
                             query=GAQL.format(start=start, end=end))
    rows = []
    for batch in resp:
        for r in batch.results:
            rows.append({
                "date": r.segments.date,
                "campaign": r.campaign.name,
                "clicks": r.metrics.clicks,
                "impressions": r.metrics.impressions,
                "conversions": r.metrics.conversions,
                "cost": r.metrics.cost_micros / 1_000_000,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ctr"] = df.clicks / df.impressions.replace({0: None})
    df["cpc"] = df.cost / df.clicks.replace({0: None})
    return df

def fetch_keyword_metrics(client: GoogleAdsClient,
                          customer_id: str,
                          start: str,
                          end: str) -> pd.DataFrame:
    """Top keywords."""
    svc = client.get_service("GoogleAdsService")
    resp = svc.search_stream(customer_id=customer_id,
                             query=GAQL_KEYWORDS.format(start=start, end=end))
    rows = []
    for batch in resp:
        for r in batch.results:
            rows.append({
                "date": r.segments.date,
                "keyword": r.ad_group_criterion.keyword.text,
                "clicks": r.metrics.clicks,
                "impressions": r.metrics.impressions,
                "conversions": r.metrics.conversions,
                "cost": r.metrics.cost_micros / 1_000_000,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ctr"] = df.clicks / df.impressions.replace({0: None})
    df["cpc"] = df.cost / df.clicks.replace({0: None})
    return df

def fetch_geo_metrics(client: GoogleAdsClient,
                      customer_id: str,
                      start: str,
                      end: str) -> pd.DataFrame:
    """Clicks por ciudad."""
    svc = client.get_service("GoogleAdsService")
    resp = svc.search_stream(customer_id=customer_id,
                             query=GAQL_GEO.format(start=start, end=end))
    rows = []
    for batch in resp:
        for r in batch.results:
            rows.append({
                "date": r.segments.date,
                "city": r.segments.geo_target_city,
                "clicks": r.metrics.clicks,
                "impressions": r.metrics.impressions,
                "conversions": r.metrics.conversions,
                "cost": r.metrics.cost_micros / 1_000_000,
            })
    return pd.DataFrame(rows)