"""Gráficos de Plotly que muestra la app."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

AZUL = "#2a78d6"
AMBAR = "#eda100"
VERDE = "#1a9e5c"
GRIS = "#8a94a3"

# Oculta fines de semana y horas sin mercado para que las velas queden seguidas.
SALTOS_SIN_MERCADO = [
    dict(bounds=["sat", "mon"]),
    dict(bounds=[16, 9.5], pattern="hour"),
]


def grafico_precio_rsi(velas: pd.DataFrame, rsi: pd.Series, senales: list, umbral: float):
    """Velas de 4 horas arriba y RSI con sus líneas de tendencia abajo."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35], vertical_spacing=0.04,
    )

    fig.add_trace(
        go.Candlestick(
            x=velas.index, open=velas["Open"], high=velas["High"],
            low=velas["Low"], close=velas["Close"], name="Precio", showlegend=False,
        ),
        row=1, col=1,
    )

    if senales:
        fechas = [senal["fecha"] for senal in senales]
        fig.add_trace(
            go.Scatter(
                x=fechas, y=velas.loc[fechas, "Low"] * 0.995, mode="markers",
                marker=dict(symbol="triangle-up", size=12, color=VERDE),
                name="Ruptura RSI",
                hovertemplate="%{x|%d/%m/%Y %H:%M}<extra>Ruptura RSI</extra>",
            ),
            row=1, col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=rsi.index, y=rsi, line=dict(color=AZUL, width=1.5), name="RSI(5)",
            hovertemplate="%{x|%d/%m/%Y %H:%M}<br>RSI %{y:.1f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # Línea de tendencia que rompió el RSI en cada señal.
    for senal in senales:
        fig.add_trace(
            go.Scatter(
                x=[senal["fecha_maximo"], senal["fecha"]],
                y=[senal["rsi_maximo"], senal["valor_linea"]],
                mode="lines", line=dict(color=AMBAR, width=1.5, dash="dash"),
                showlegend=False, hoverinfo="skip",
            ),
            row=2, col=1,
        )

    fig.add_hline(y=umbral, line=dict(color=GRIS, dash="dot"), row=2, col=1)
    fig.add_hline(y=100 - umbral, line=dict(color=GRIS, dash="dot"), row=2, col=1)

    fig.update_xaxes(rangebreaks=SALTOS_SIN_MERCADO, rangeslider_visible=False)
    fig.update_yaxes(title_text="Precio", tickprefix="$ ", row=1, col=1)
    fig.update_yaxes(title_text="RSI(5)", range=[0, 100], row=2, col=1)
    fig.update_layout(
        height=620,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(t=40),
    )
    return fig


def grafico_estacionalidad(tabla: pd.DataFrame, meses_destacados: dict):
    """Barras con el rendimiento medio de cada mes.

    `meses_destacados` es un diccionario {mes abreviado: etiqueta}, por ejemplo
    {"Sep": "Anterior", "Oct": "Actual", "Nov": "Próximo"}.
    """
    datos = tabla.rename_axis("Mes").reset_index()
    datos["Grupo"] = datos["Mes"].map(meses_destacados).fillna("Resto del año")
    colores = {"Resto del año": AZUL, "Anterior": GRIS, "Actual": AMBAR, "Próximo": VERDE}
    fig = px.bar(
        datos, x="Mes", y="Media", color="Grupo", text_auto=".2%",
        color_discrete_map=colores, category_orders={"Grupo": list(colores)},
        custom_data=["% positivos"],
    )
    fig.update_traces(
        hovertemplate="%{x}<br>Media %{y:.2%}<br>Años positivos %{customdata[0]:.0%}<extra></extra>"
    )
    fig.update_layout(
        legend_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title=None,
        yaxis_title="Rendimiento medio",
        yaxis_tickformat=".1%",
        margin=dict(t=40),
    )
    return fig


def grafico_camino_mes(promedio: pd.Series, actual, nombre_mes: str, anios: int):
    """Rendimiento acumulado sesión a sesión: promedio de los últimos años frente a este año."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=promedio.index, y=promedio, name=f"Promedio últimos {anios} años",
            line=dict(color=GRIS, width=2, dash="dash"),
            hovertemplate="Sesión %{x}<br>%{y:+.2%}<extra></extra>",
        )
    )
    if actual is not None and not actual.empty:
        fig.add_trace(
            go.Scatter(
                x=actual.index, y=actual, name="Este año", mode="lines+markers",
                line=dict(color=AMBAR, width=3),
                hovertemplate="Sesión %{x}<br>%{y:+.2%}<extra></extra>",
            )
        )
    fig.add_hline(y=0, line=dict(color=GRIS, width=1))
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title=f"Sesión de {nombre_mes}",
        yaxis_title="Rendimiento acumulado",
        yaxis_tickformat="+.1%",
        margin=dict(t=40),
    )
    return fig


def grafico_flujo(flujo: pd.DataFrame, sesiones: int = 120):
    """Precio y OBV arriba, Chaikin Money Flow abajo, de las últimas sesiones."""
    datos = flujo.tail(sesiones)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.06,
        specs=[[{"secondary_y": True}], [{}]],
    )
    fig.add_trace(
        go.Scatter(x=datos.index, y=datos["Close"], name="Precio", line=dict(color=AZUL, width=2),
                   hovertemplate="%{x|%d/%m/%Y}<br>$ %{y:,.2f}<extra></extra>"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=datos.index, y=datos["OBV"], name="OBV", line=dict(color=AMBAR, width=1.5),
                   hovertemplate="%{x|%d/%m/%Y}<br>OBV %{y:,.0f}<extra></extra>"),
        row=1, col=1, secondary_y=True,
    )
    fig.add_trace(
        go.Bar(
            x=datos.index, y=datos["CMF"], name="Chaikin Money Flow",
            marker_color=[VERDE if valor >= 0 else "#d64545" for valor in datos["CMF"]],
            hovertemplate="%{x|%d/%m/%Y}<br>CMF %{y:+.2f}<extra></extra>",
        ),
        row=2, col=1,
    )
    for tipo, color, simbolo in (("Acumulación", VERDE, "triangle-up"), ("Distribución", "#d64545", "triangle-down")):
        dias = datos[datos[tipo]]
        fig.add_trace(
            go.Scatter(
                x=dias.index, y=dias["Close"], mode="markers", name=f"Día de {tipo.lower()}",
                marker=dict(color=color, symbol=simbolo, size=8),
                hovertemplate="%{x|%d/%m/%Y}<extra>" + tipo + "</extra>",
            ),
            row=1, col=1,
        )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(title_text="Precio", tickprefix="$ ", row=1, col=1)
    fig.update_yaxes(title_text="OBV", showgrid=False, row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="CMF", row=2, col=1)
    fig.update_layout(
        height=560,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(t=40),
    )
    return fig


def grafico_fuerza_relativa(tabla: pd.DataFrame, ticker: str, referencia: str):
    """Línea con el cociente activo / referencia y su media móvil."""
    datos = tabla.rename_axis("Fecha").reset_index().melt(
        id_vars="Fecha", var_name="Serie", value_name="Valor"
    )
    fig = px.line(
        datos, x="Fecha", y="Valor", color="Serie",
        color_discrete_sequence=[AZUL, AMBAR],
    )
    fig.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.4f}")
    fig.update_layout(
        legend_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title=None,
        yaxis_title=f"{ticker} / {referencia}",
        margin=dict(t=40),
    )
    return fig
