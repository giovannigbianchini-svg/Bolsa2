"""Huella de las grandes instituciones a partir del precio y el volumen.

Las instituciones mueven tanto dinero que no pueden comprar o vender sin dejar
rastro en el volumen. Estos indicadores intentan detectar ese rastro; son
aproximaciones, no datos reales de compras o ventas de cada fondo.
"""

import numpy as np
import pandas as pd
import yfinance as yf

# Variación mínima del cierre para contar un día de acumulación o distribución.
VARIACION_MINIMA = 0.002


def flujo_institucional(diario, periodo_cmf=20):
    """Tabla diaria con el Chaikin Money Flow, el OBV y los días de acumulación/distribución.

    - Chaikin Money Flow (CMF): si el precio cierra cerca del máximo del día con
      mucho volumen, el dinero entra (CMF > 0); si cierra cerca del mínimo, sale.
    - On-Balance Volume (OBV): suma el volumen de los días que sube y resta el de
      los que baja. Si sube más rápido que el precio, alguien está acumulando.
    - Día de acumulación: sube al menos 0,2 % con más volumen que el día anterior.
      Día de distribución: baja al menos 0,2 % con más volumen que el día anterior.
    """
    cierre, maximo, minimo, volumen = (diario[c] for c in ("Close", "High", "Low", "Volume"))

    rango = (maximo - minimo).replace(0, np.nan)
    multiplicador = ((cierre - minimo) - (maximo - cierre)) / rango
    cmf = (multiplicador * volumen).rolling(periodo_cmf).sum() / volumen.rolling(periodo_cmf).sum()

    variacion = cierre.pct_change()
    obv = (np.sign(variacion).fillna(0) * volumen).cumsum()
    sube_volumen = volumen > volumen.shift()

    return pd.DataFrame(
        {
            "Close": cierre,
            "Volume": volumen,
            "CMF": cmf,
            "OBV": obv,
            "Acumulación": (variacion >= VARIACION_MINIMA) & sube_volumen,
            "Distribución": (variacion <= -VARIACION_MINIMA) & sube_volumen,
        }
    )


def resumen_institucional(flujo, estado_fuerza, sesiones=25):
    """Junta los indicadores en un diagnóstico: acumulación, distribución o neutral.

    `estado_fuerza` es +1, 0 o -1 según la fuerza relativa frente al mercado.
    """
    recientes = flujo.tail(sesiones)
    dias_acumulacion = int(recientes["Acumulación"].sum())
    dias_distribucion = int(recientes["Distribución"].sum())
    cmf = float(flujo["CMF"].iloc[-1])

    # Compara cuánto cambió el OBV en 20 sesiones con el volumen medio diario,
    # para que el número no dependa del tamaño del ETF.
    volumen_medio = float(flujo["Volume"].tail(100).mean())
    obv_20 = (float(flujo["OBV"].iloc[-1]) - float(flujo["OBV"].iloc[-21])) / volumen_medio
    precio_20 = float(flujo["Close"].iloc[-1]) / float(flujo["Close"].iloc[-21]) - 1
    volumen_relativo = float(flujo["Volume"].tail(20).mean()) / volumen_medio

    puntos = estado_fuerza
    puntos += 1 if cmf > 0.05 else -1 if cmf < -0.05 else 0
    puntos += 1 if dias_acumulacion >= dias_distribucion + 2 else -1 if dias_distribucion >= dias_acumulacion + 2 else 0
    puntos += 1 if obv_20 > 2 else -1 if obv_20 < -2 else 0

    if puntos >= 2:
        veredicto = "Acumulación"
    elif puntos <= -2:
        veredicto = "Distribución"
    else:
        veredicto = "Neutral"

    return {
        "veredicto": veredicto,
        "puntos": puntos,
        "cmf": cmf,
        "dias_acumulacion": dias_acumulacion,
        "dias_distribucion": dias_distribucion,
        "sesiones": sesiones,
        "obv_20": obv_20,
        "precio_20": precio_20,
        "volumen_relativo": volumen_relativo,
        "fuerza": estado_fuerza,
    }


def principales_posiciones(ticker):
    """Las 10 mayores posiciones del ETF según Yahoo Finance (None si no hay datos)."""
    try:
        posiciones = yf.Ticker(ticker).funds_data.top_holdings
    except Exception:
        return None
    if posiciones is None or posiciones.empty:
        return None
    return posiciones.rename(columns={"Name": "Empresa", "Holding Percent": "Peso"})
