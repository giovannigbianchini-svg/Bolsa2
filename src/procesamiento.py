"""Lógica de negocio: descarga de precios, RSI, rupturas de tendencia y estacionalidad.

Este módulo no importa Streamlit a propósito, para poder probarlo o reutilizarlo
fuera de la app.
"""

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "data"
RUTA_DIARIO_EJEMPLO = CARPETA_DATOS / "diario_ejemplo.csv"
RUTA_4H_EJEMPLO = CARPETA_DATOS / "velas_4h_ejemplo.csv"

# ETFs disponibles en la lista. Los defensivos son los habituales en las
# rotaciones institucionales cuando el mercado busca refugio.
ACTIVOS = {
    "XLP (Consumo básico)": "XLP",
    "XLU (Servicios públicos)": "XLU",
    "XLV (Salud)": "XLV",
    "SPY (S&P 500)": "SPY",
}

# Índice de referencia para medir la fuerza relativa (rotación).
REFERENCIA = "SPY"

COLUMNAS_DIARIAS = ["High", "Low", "Close", "Volume"]

MESES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

MESES_COMPLETOS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# Minutos desde la medianoche en que abre la bolsa de Nueva York (9:30).
APERTURA_NY = 9 * 60 + 30


def descargar_diario(ticker, hoy):
    """Descarga máximos, mínimos, cierres y volumen diarios desde 1999 hasta hoy."""
    datos = yf.download(
        ticker,
        start="1999-01-01",
        end=hoy + timedelta(days=1),
        auto_adjust=True,
        progress=False,
        multi_level_index=False,
    )

    if datos.empty:
        return pd.DataFrame(columns=COLUMNAS_DIARIAS)

    return datos[COLUMNAS_DIARIAS].dropna()


def descargar_4h(ticker, hoy):
    """Descarga velas de 1 hora y las agrupa en velas de 4 horas.

    Yahoo Finance solo ofrece datos de 1 hora de los últimos 730 días.
    """
    horarias = yf.download(
        ticker,
        start=hoy - timedelta(days=729),
        end=hoy + timedelta(days=1),
        interval="1h",
        auto_adjust=True,
        progress=False,
        multi_level_index=False,
    )

    if horarias.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    return a_velas_4h(horarias)


def a_velas_4h(horarias):
    """Agrupa velas de 1 hora en dos velas de 4 horas por sesión.

    La primera va de 9:30 a 13:30 y la segunda de 13:30 al cierre (16:00),
    como las muestran la mayoría de plataformas para acciones de EE.UU.
    """
    indice = horarias.index
    if indice.tz is not None:
        indice = indice.tz_convert("America/New_York").tz_localize(None)

    datos = horarias[["Open", "High", "Low", "Close"]].copy()
    datos["Inicio"] = indice
    bloque = (indice.hour * 60 + indice.minute - APERTURA_NY) // 240

    velas = datos.groupby([indice.date, bloque]).agg(
        Inicio=("Inicio", "first"),
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
    )
    return velas.set_index("Inicio").rename_axis("Fecha").dropna()


def cargar_diario_ejemplo(ticker):
    """Lee los datos diarios guardados en data/diario_ejemplo.csv."""
    datos = pd.read_csv(RUTA_DIARIO_EJEMPLO, parse_dates=["Fecha"])
    datos = datos[datos["Ticker"] == ticker].drop(columns="Ticker")
    return datos.set_index("Fecha")


def cargar_4h_ejemplo(ticker):
    """Lee las velas de 4 horas guardadas en data/velas_4h_ejemplo.csv."""
    datos = pd.read_csv(RUTA_4H_EJEMPLO, parse_dates=["Fecha"])
    datos = datos[datos["Ticker"] == ticker].drop(columns="Ticker")
    return datos.set_index("Fecha")


def calcular_rsi(cierres, periodo=5):
    """RSI de Wilder, el mismo que usan TradingView y la mayoría de plataformas."""
    variacion = cierres.diff()
    subidas = variacion.clip(lower=0).ewm(alpha=1 / periodo, adjust=False).mean()
    bajadas = (-variacion.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False).mean()
    return (100 - 100 / (1 + subidas / bajadas)).rename("RSI")


def detectar_rupturas(rsi, umbral=20, ventana=2):
    """Busca rupturas al alza de la línea de tendencia bajista del RSI.

    En cada vela se traza una línea entre los dos últimos máximos del RSI,
    siempre que el segundo sea más bajo que el primero (tendencia bajista).
    Hay señal cuando:
      1. el RSI tocó la zona de sobreventa (<= umbral) después del segundo máximo, y
      2. el RSI cruza esa línea de abajo hacia arriba.

    Un máximo solo se considera confirmado cuando ya pasaron `ventana` velas,
    así la señal nunca usa información del futuro.

    Devuelve una lista de diccionarios, uno por señal.
    """
    valores = rsi.to_numpy()
    fechas = rsi.index
    maximos = []
    senales = []
    ultimo_maximo_usado = None

    for t in range(len(valores)):
        i = t - ventana
        if i >= ventana and not np.isnan(valores[i]):
            if valores[i] == np.nanmax(valores[i - ventana:t + 1]):
                maximos.append(i)

        if len(maximos) < 2:
            continue

        p1, p2 = maximos[-2], maximos[-1]
        # Cada línea de tendencia solo puede dar una señal.
        if valores[p2] >= valores[p1] or p2 == ultimo_maximo_usado or t - 1 <= p2:
            continue

        pendiente = (valores[p2] - valores[p1]) / (p2 - p1)
        linea_actual = valores[p1] + pendiente * (t - p1)
        linea_anterior = valores[p1] + pendiente * (t - 1 - p1)

        if np.nanmin(valores[p2:t + 1]) > umbral:
            continue

        if valores[t] > linea_actual and valores[t - 1] <= linea_anterior:
            senales.append(
                {
                    "fecha": fechas[t],
                    "rsi": valores[t],
                    "fecha_maximo": fechas[p1],
                    "rsi_maximo": valores[p1],
                    "valor_linea": linea_actual,
                }
            )
            ultimo_maximo_usado = p2

    return senales


def evaluar_senales(velas, senales, semanas_minimas, semanas_maximas):
    """Calcula qué habría pasado al entrar en cada señal y mantener el activo.

    Se entra al cierre de la vela de la señal y se sale a las semanas indicadas.
    Si todavía no pasó ese tiempo, la operación figura como abierta.
    """
    filas = []

    for senal in senales:
        fecha = senal["fecha"]
        precio_entrada = float(velas.loc[fecha, "Close"])
        fila = {"Entrada": fecha, "Precio entrada": precio_entrada}

        for semanas in (semanas_minimas, semanas_maximas):
            salida = velas.loc[velas.index >= fecha + pd.Timedelta(weeks=semanas), "Close"]
            fila[f"Rend. {semanas} sem"] = (
                float(salida.iloc[0]) / precio_entrada - 1 if not salida.empty else np.nan
            )

        tramo = velas.loc[fecha:fecha + pd.Timedelta(weeks=semanas_maximas)]
        fila["Caída máx."] = float(tramo["Low"].min()) / precio_entrada - 1

        if np.isnan(fila[f"Rend. {semanas_maximas} sem"]):
            rendimiento_actual = float(velas["Close"].iloc[-1]) / precio_entrada - 1
            fila["Estado"] = f"Abierta ({rendimiento_actual:+.2%})"
        else:
            fila["Estado"] = "Cerrada"

        filas.append(fila)

    return pd.DataFrame(filas)


def mes_anterior(mes):
    return (mes - 2) % 12 + 1


def mes_siguiente(mes):
    return mes % 12 + 1


def rendimientos_mensuales(cierres, hoy):
    """Rendimiento de cada mes completo. El mes en curso se descarta."""
    mensuales = cierres.resample("ME").last().pct_change().dropna()
    return mensuales[mensuales.index.to_period("M") < pd.Period(hoy, "M")]


def estacionalidad(cierres, hoy, anios=None):
    """Tabla con el rendimiento medio, la mediana y el % de años positivos de cada mes.

    Con `anios` solo se usan las últimas apariciones completas de cada mes
    (por ejemplo, los últimos 10 octubres terminados).
    """
    mensuales = rendimientos_mensuales(cierres, hoy)
    agrupados = mensuales.groupby(mensuales.index.month)
    if anios:
        mensuales = agrupados.tail(anios)
        agrupados = mensuales.groupby(mensuales.index.month)

    tabla = pd.DataFrame(
        {
            "Media": agrupados.mean(),
            "Mediana": agrupados.median(),
            "% positivos": agrupados.apply(lambda serie: (serie > 0).mean()),
            "Años": agrupados.size(),
        }
    )
    tabla.index = [MESES[mes] for mes in tabla.index]
    return tabla


def estacionalidad_relativa(cierres, cierres_referencia, hoy, anios=None):
    """Rendimiento medio de cada mes del activo menos el de la referencia."""
    activo = rendimientos_mensuales(cierres, hoy)
    referencia = rendimientos_mensuales(cierres_referencia, hoy)
    diferencia = (activo - referencia).dropna()
    if anios:
        diferencia = diferencia.groupby(diferencia.index.month).tail(anios)
    agrupados = diferencia.groupby(diferencia.index.month)

    tabla = pd.DataFrame(
        {
            "Diferencia media": agrupados.mean(),
            "% meses mejor": agrupados.apply(lambda serie: (serie > 0).mean()),
        }
    )
    tabla.index = [MESES[mes] for mes in tabla.index]
    return tabla


def resumen_mes(cierres, mes, hoy, anios=10):
    """Estadísticas de un mes en sus últimas `anios` apariciones completas.

    Devuelve un diccionario con la media, la mediana, el % de años positivos,
    el rango habitual (percentiles 25 y 75) y el rendimiento de cada año.
    """
    mensuales = rendimientos_mensuales(cierres, hoy)
    del_mes = mensuales[mensuales.index.month == mes].tail(anios)
    del_mes.index = del_mes.index.year

    return {
        "mes": mes,
        "media": del_mes.mean(),
        "mediana": del_mes.median(),
        "positivos": (del_mes > 0).mean(),
        "p25": del_mes.quantile(0.25),
        "p75": del_mes.quantile(0.75),
        "por_anio": del_mes,
    }


def rendimiento_mes_anterior(cierres, hoy):
    """Rendimiento real del último mes terminado."""
    mensuales = rendimientos_mensuales(cierres, hoy)
    return float(mensuales.iloc[-1]) if not mensuales.empty else np.nan


def rendimiento_mes_en_curso(cierres, hoy):
    """Rendimiento desde el último cierre del mes anterior hasta hoy."""
    inicio_mes = pd.Timestamp(hoy).replace(day=1)
    previos = cierres[cierres.index < inicio_mes]
    del_mes = cierres[cierres.index >= inicio_mes]
    if previos.empty or del_mes.empty:
        return np.nan, 0
    return float(del_mes.iloc[-1]) / float(previos.iloc[-1]) - 1, len(del_mes)


def camino_del_mes(cierres, mes, hoy, anios=10):
    """Rendimiento acumulado sesión a sesión dentro de un mes.

    Devuelve el camino promedio de los últimos `anios` años y el camino de este
    año (None si el mes no es el actual).
    """
    caminos = {}
    for anio in sorted(set(cierres.index.year)):
        del_mes = cierres[(cierres.index.year == anio) & (cierres.index.month == mes)]
        if del_mes.empty:
            continue
        previos = cierres[cierres.index < del_mes.index[0]]
        if previos.empty:
            continue
        caminos[anio] = (del_mes / float(previos.iloc[-1]) - 1).reset_index(drop=True)

    tabla = pd.DataFrame(caminos)
    tabla.index = tabla.index + 1

    actual = None
    if mes == hoy.month and hoy.year in tabla.columns:
        actual = tabla.pop(hoy.year).dropna()

    historicos = tabla[sorted(tabla.columns)[-anios:]]
    # Solo se muestran las sesiones que existieron en al menos la mitad de los años.
    historicos = historicos[historicos.notna().sum(axis=1) >= len(historicos.columns) / 2]
    return historicos.mean(axis=1), actual


def entradas_por_mes(cierres, mes, semanas_minimas, semanas_maximas):
    """Qué habría pasado entrando el primer día hábil de un mes, año por año."""
    filas = []

    for anio in sorted(set(cierres.index.year)):
        dias_del_mes = cierres[(cierres.index.year == anio) & (cierres.index.month == mes)]
        if dias_del_mes.empty:
            continue

        fecha = dias_del_mes.index[0]
        precio = float(dias_del_mes.iloc[0])
        fila = {"Año": anio}

        for semanas in (semanas_minimas, semanas_maximas):
            salida = cierres[cierres.index >= fecha + pd.Timedelta(weeks=semanas)]
            fila[f"Rend. {semanas} sem"] = (
                float(salida.iloc[0]) / precio - 1 if not salida.empty else np.nan
            )

        filas.append(fila)

    return pd.DataFrame(filas).set_index("Año").dropna()


def fuerza_relativa(cierres, cierres_referencia, dias=252, media=50):
    """Cociente activo / referencia del último año y su media móvil.

    Si el cociente sube, el activo lo hace mejor que el mercado: es una señal
    indirecta de que el dinero está rotando hacia él.
    """
    cociente = (cierres / cierres_referencia).dropna()
    tabla = pd.DataFrame({"Fuerza relativa": cociente})
    tabla[f"Media {media} días"] = cociente.rolling(media).mean()
    return tabla.tail(dias)


def estado_fuerza_relativa(tabla):
    """+1 si el activo gana fuerza frente al mercado, -1 si la pierde, 0 si no está claro."""
    cociente, media = tabla.iloc[:, 0], tabla.iloc[:, 1]
    pendiente = media.iloc[-1] - media.iloc[-21]
    if cociente.iloc[-1] > media.iloc[-1] and pendiente > 0:
        return 1
    if cociente.iloc[-1] < media.iloc[-1] and pendiente < 0:
        return -1
    return 0
