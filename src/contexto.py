"""Contexto geopolítico y macroeconómico: indicadores de riesgo y noticias recientes.

La geopolítica no se puede medir directamente, pero deja huella en ciertos
precios: el miedo sube el VIX y el oro, un conflicto en Medio Oriente sube el
petróleo, una crisis comercial mueve el dólar y los bonos. Aquí se mide cómo
se movieron esos precios y cómo suele reaccionar el activo a cada uno.
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import yfinance as yf

from src.procesamiento import CARPETA_DATOS

RUTA_INDICADORES_EJEMPLO = CARPETA_DATOS / "indicadores_ejemplo.csv"

# Cada indicador con lo que suele significar y el cambio a partir del cual se
# considera un movimiento importante en un mes.
INDICADORES = {
    "^VIX": {
        "nombre": "VIX (miedo del mercado)",
        "umbral": 0.15,
        "significado": "Sube cuando crece la incertidumbre (guerras, crisis, sorpresas). "
        "Los inversores suelen refugiarse entonces en sectores defensivos.",
    },
    "CL=F": {
        "nombre": "Petróleo WTI",
        "umbral": 0.07,
        "significado": "Sube con conflictos en zonas productoras o recortes de la OPEP. "
        "Encarece transporte y envases, lo que presiona los márgenes de las empresas de consumo.",
    },
    "GC=F": {
        "nombre": "Oro",
        "umbral": 0.04,
        "significado": "Es el refugio clásico ante tensiones geopolíticas; si sube, "
        "el mercado está buscando protección.",
    },
    "DX-Y.NYB": {
        "nombre": "Dólar (índice DXY)",
        "umbral": 0.02,
        "significado": "Un dólar fuerte reduce el valor de las ventas en el exterior de "
        "multinacionales como Procter & Gamble, Coca-Cola o Philip Morris.",
    },
    "^TNX": {
        "nombre": "Bono del Tesoro a 10 años",
        "umbral": 0.04,
        "significado": "Si su rendimiento sube, los activos de dividendo estable compiten "
        "peor con los bonos y suelen bajar.",
    },
}

CONSULTA_GEOPOLITICA = (
    "(geopolitical OR tariffs OR sanctions OR war OR conflict OR \"Middle East\" "
    "OR OPEC OR China trade) stock market"
)


def descargar_indicadores(hoy):
    """Cierres diarios de los indicadores de los últimos dos años."""
    datos = yf.download(
        list(INDICADORES),
        start=hoy - timedelta(days=760),
        end=hoy + timedelta(days=1),
        auto_adjust=True,
        progress=False,
    )["Close"]
    return datos.ffill().dropna(how="all")


def cargar_indicadores_ejemplo():
    return pd.read_csv(RUTA_INDICADORES_EJEMPLO, index_col="Fecha", parse_dates=True)


def analizar_indicadores(indicadores, cierres_activo, sesiones=21):
    """Cambio de cada indicador en el último mes y su efecto probable en el activo.

    El efecto se deduce de la correlación semanal de los dos últimos años: si el
    activo suele subir cuando el indicador sube y el indicador subió, suma; si
    suelen moverse en sentido contrario, resta.
    """
    semanal_activo = cierres_activo.resample("W").last().pct_change()
    filas = []

    for ticker, info in INDICADORES.items():
        if ticker not in indicadores.columns:
            continue
        serie = indicadores[ticker].dropna()
        if len(serie) <= sesiones:
            continue

        cambio = float(serie.iloc[-1]) / float(serie.iloc[-sesiones - 1]) - 1
        semanal = serie.resample("W").last().pct_change()
        correlacion = semanal_activo.corr(semanal)

        importante = abs(cambio) >= info["umbral"]
        if not importante or abs(correlacion) < 0.1:
            efecto = 0
        else:
            efecto = 1 if cambio * correlacion > 0 else -1

        filas.append(
            {
                "Ticker": ticker,
                "Indicador": info["nombre"],
                "Valor": float(serie.iloc[-1]),
                "Cambio 1 mes": cambio,
                "Correlación": correlacion,
                "Importante": importante,
                "Efecto": efecto,
                "Significado": info["significado"],
            }
        )

    return pd.DataFrame(filas)


def buscar_noticias(consulta, dias=30, maximo=8):
    """Titulares recientes de Google News (en inglés) para una búsqueda.

    Devuelve una lista de diccionarios con título, fuente, fecha y enlace.
    """
    parametros = urllib.parse.quote(f"{consulta} when:{dias}d")
    url = f"https://news.google.com/rss/search?q={parametros}&hl=en-US&gl=US&ceid=US:en"
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(peticion, timeout=15) as respuesta:
        raiz = ET.fromstring(respuesta.read())

    noticias = []
    titulos_vistos = set()
    for item in raiz.findall(".//item"):
        fuente = item.findtext("source") or ""
        titulo = item.findtext("title") or ""
        # Google añade " - Fuente" al final del título; se quita para no repetirla.
        if fuente and titulo.endswith(f" - {fuente}"):
            titulo = titulo[: -len(fuente) - 3]
        # La misma noticia suele aparecer en varios medios: se muestra una vez.
        if titulo.lower() in titulos_vistos:
            continue
        titulos_vistos.add(titulo.lower())
        noticias.append(
            {
                "titulo": titulo,
                "fuente": fuente,
                "fecha": parsedate_to_datetime(item.findtext("pubDate")),
                "enlace": item.findtext("link"),
            }
        )

    noticias.sort(key=lambda noticia: noticia["fecha"], reverse=True)
    return noticias[:maximo]
