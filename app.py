# Bolsa2 — Ruptura de tendencia del RSI(5) en 4 horas, estacionalidad,
# instituciones y contexto geopolítico
# Ejecutar con: streamlit run app.py

from datetime import date

import pandas as pd
import streamlit as st

from src.contexto import (
    CONSULTA_GEOPOLITICA,
    analizar_indicadores,
    buscar_noticias,
    cargar_indicadores_ejemplo,
    descargar_indicadores,
)
from src.explicacion import (
    conclusion,
    explicar_estacionalidad,
    explicar_geopolitica,
    explicar_grafico,
    explicar_instituciones,
)
from src.graficos import (
    grafico_camino_mes,
    grafico_estacionalidad,
    grafico_flujo,
    grafico_fuerza_relativa,
    grafico_precio_rsi,
)
from src.instituciones import flujo_institucional, principales_posiciones, resumen_institucional
from src.procesamiento import (
    ACTIVOS,
    MESES,
    MESES_COMPLETOS,
    REFERENCIA,
    calcular_rsi,
    camino_del_mes,
    cargar_4h_ejemplo,
    cargar_diario_ejemplo,
    descargar_4h,
    descargar_diario,
    detectar_rupturas,
    entradas_por_mes,
    estacionalidad,
    estacionalidad_relativa,
    estado_fuerza_relativa,
    evaluar_senales,
    fuerza_relativa,
    mes_anterior,
    mes_siguiente,
    rendimiento_mes_anterior,
    rendimiento_mes_en_curso,
    resumen_mes,
)

st.set_page_config(page_title="Bolsa2 — Ruptura RSI(5) 4h", page_icon="📊", layout="wide")

# Años que se usan para la estacionalidad "probable" de cada mes.
ANIOS_ESTACIONALIDAD = 10


# La caché evita volver a descargar los mismos datos en cada interacción.
# `hoy` forma parte de la clave para que los datos se renueven cada día.
@st.cache_data(ttl=3600, show_spinner=False)
def obtener_datos(ticker, hoy, usar_ejemplo):
    if usar_ejemplo:
        return cargar_diario_ejemplo(ticker), cargar_4h_ejemplo(ticker)
    return descargar_diario(ticker, hoy), descargar_4h(ticker, hoy)


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_indicadores(hoy, usar_ejemplo):
    if usar_ejemplo:
        return cargar_indicadores_ejemplo()
    return descargar_indicadores(hoy)


@st.cache_data(ttl=1800, show_spinner=False)
def obtener_noticias(consulta, dias):
    try:
        return buscar_noticias(consulta, dias)
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def obtener_posiciones(ticker):
    return principales_posiciones(ticker)


def mostrar_noticias(noticias):
    if noticias is None:
        st.info("No se pudieron obtener noticias (hace falta conexión a internet).")
    elif not noticias:
        st.info("No se encontraron noticias recientes.")
    else:
        for noticia in noticias:
            st.markdown(
                f"- [{noticia['titulo']}]({noticia['enlace']}) — "
                f"*{noticia['fuente']}, {noticia['fecha']:%d/%m/%Y}*"
            )


hoy = date.today()
mes_actual = hoy.month
mes_previo = mes_anterior(mes_actual)
mes_proximo = mes_siguiente(mes_actual)

st.title("📊 Ruptura de tendencia del RSI(5) en 4 horas")
st.caption(
    f"Fecha de hoy: **{hoy:%d/%m/%Y}**. Todo el análisis usa datos hasta hoy; "
    f"el mes en curso ({MESES_COMPLETOS[mes_actual]}) no cuenta en la estacionalidad porque aún no terminó."
)

columna1, columna2, columna3 = st.columns(3)
nombre_activo = columna1.selectbox("Activo", ACTIVOS.keys())
otro_ticker = columna1.text_input("…o escribe otro ticker", placeholder="Ej.: XLE").strip().upper()
umbral = columna2.slider(
    "Sobreventa del RSI", min_value=5, max_value=40, value=20,
    help="El RSI debe bajar hasta este nivel antes de que una ruptura cuente como señal.",
)
semanas_minimas, semanas_maximas = columna2.slider(
    "Semanas que mantienes la posición", min_value=1, max_value=12, value=(4, 6)
)
meses_grafico = columna3.slider("Meses que muestra el gráfico", min_value=1, max_value=24, value=6)
usar_ejemplo = columna3.checkbox(
    "Usar datos de ejemplo (sin conexión)",
    help="Usa los precios guardados en la carpeta data/ en lugar de descargarlos de "
    "Yahoo Finance. Solo incluye los activos de la lista.",
)

ticker = otro_ticker or ACTIVOS[nombre_activo]
descripcion = next((nombre for nombre, valor in ACTIVOS.items() if valor == ticker), ticker)

# El botón evita que el cálculo se dispare mientras el usuario todavía está
# eligiendo los valores.
if st.button("Analizar"):

    if usar_ejemplo and ticker not in ACTIVOS.values():
        st.error("Los datos de ejemplo solo incluyen los activos de la lista.")
        st.stop()

    with st.spinner(f"Obteniendo precios de {ticker}, {REFERENCIA} e indicadores de mercado..."):
        try:
            diario, velas = obtener_datos(ticker, hoy, usar_ejemplo)
            diario_referencia, _ = obtener_datos(REFERENCIA, hoy, usar_ejemplo)
            indicadores = obtener_indicadores(hoy, usar_ejemplo)
        except Exception as error:
            st.error(
                f"No se pudieron obtener los precios: {error}\n\n"
                "Prueba de nuevo o marca «Usar datos de ejemplo»."
            )
            st.stop()

    if diario.empty or velas.empty:
        st.error(f"No se encontraron datos de {ticker}.")
        st.stop()

    cierres = diario["Close"]
    cierres_referencia = diario_referencia["Close"]
    con_referencia = ticker != REFERENCIA and not cierres_referencia.empty

    # ------------------------------------------------------------ Cálculos
    rsi = calcular_rsi(velas["Close"])
    senales = detectar_rupturas(rsi, umbral)
    operaciones = evaluar_senales(velas, senales, semanas_minimas, semanas_maximas)
    ultima_fecha = velas.index[-1]
    rsi_actual = float(rsi.iloc[-1])
    senal_activa = bool(senales) and senales[-1]["fecha"] in velas.index[-2:]

    tabla_10 = estacionalidad(cierres, hoy, ANIOS_ESTACIONALIDAD)
    tabla_total = estacionalidad(cierres, hoy)
    resumen_previo = resumen_mes(cierres, mes_previo, hoy, ANIOS_ESTACIONALIDAD)
    resumen_actual = resumen_mes(cierres, mes_actual, hoy, ANIOS_ESTACIONALIDAD)
    resumen_proximo = resumen_mes(cierres, mes_proximo, hoy, ANIOS_ESTACIONALIDAD)
    real_previo = rendimiento_mes_anterior(cierres, hoy)
    en_curso, sesiones_en_curso = rendimiento_mes_en_curso(cierres, hoy)
    camino_promedio, camino_actual = camino_del_mes(cierres, mes_actual, hoy, ANIOS_ESTACIONALIDAD)
    promedio_a_la_fecha = (
        float(camino_promedio.loc[sesiones_en_curso]) if sesiones_en_curso in camino_promedio.index else None
    )

    tabla_fuerza = fuerza_relativa(cierres, cierres_referencia) if con_referencia else None
    fuerza = estado_fuerza_relativa(tabla_fuerza) if con_referencia else 0
    flujo = flujo_institucional(diario)
    resumen_inst = resumen_institucional(flujo, fuerza)
    posiciones = None if usar_ejemplo else obtener_posiciones(ticker)

    tabla_indicadores = analizar_indicadores(indicadores, cierres)

    texto_grafico, puntos_grafico = explicar_grafico(
        ticker, rsi_actual, umbral, senal_activa, senales, operaciones, semanas_maximas
    )
    texto_estacional, puntos_estacional = explicar_estacionalidad(
        ticker, resumen_previo, real_previo, resumen_actual, en_curso, sesiones_en_curso,
        promedio_a_la_fecha, resumen_proximo,
    )
    texto_inst, puntos_inst = explicar_instituciones(ticker, resumen_inst, posiciones)
    texto_geo, puntos_geo = explicar_geopolitica(ticker, tabla_indicadores)
    puntos = {
        "Gráfico": puntos_grafico,
        "Estacionalidad": puntos_estacional,
        "Instituciones": puntos_inst,
        "Geopolítica": puntos_geo,
    }

    # Se dejan 3 días de margen para no avisar en fines de semana.
    if usar_ejemplo and (hoy - ultima_fecha.date()).days > 3:
        st.warning(
            f"Los datos de ejemplo llegan hasta el {ultima_fecha:%d/%m/%Y}, no hasta hoy. "
            "Desmarca la casilla para trabajar con precios actuales."
        )

    # ------------------------------------------------------------ Estado actual
    st.subheader(f"Situación de {ticker} a {hoy:%d/%m/%Y}")

    columna1, columna2, columna3, columna4, columna5 = st.columns(5)
    columna1.metric("Último cierre (4h)", f"$ {velas['Close'].iloc[-1]:,.2f}", f"{ultima_fecha:%d/%m %H:%M}")
    columna2.metric("RSI(5) actual", f"{rsi_actual:.1f}")
    if senales:
        ultima_senal = senales[-1]["fecha"]
        dias = (pd.Timestamp(hoy) - ultima_senal.normalize()).days
        columna3.metric("Última ruptura", f"{ultima_senal:%d/%m/%Y}", f"hace {dias} días", delta_color="off")
    else:
        columna3.metric("Última ruptura", "Ninguna")
    columna4.metric("Instituciones", resumen_inst["veredicto"])
    columna5.metric(
        f"{MESES[mes_actual]}: probable (10 años)", f"{resumen_actual['media']:+.2%}",
        f"lleva {en_curso:+.2%}" if not pd.isna(en_curso) else None, delta_color="off",
    )

    if senal_activa:
        st.success("**Señal de entrada activa:** el RSI acaba de romper su línea de tendencia bajista.")
    elif rsi_actual <= umbral:
        st.warning("**En sobreventa:** el RSI está en zona de entrada. Espera la ruptura de su línea bajista.")
    elif rsi_actual >= 100 - umbral:
        st.info("**En sobrecompra:** no es momento de entrar; espera un retroceso y una nueva sobreventa.")
    else:
        st.info("**Sin señal:** espera a que el RSI baje a sobreventa y rompa su línea bajista.")

    pestanas = st.tabs([
        "🧭 Explicación del análisis",
        "📈 Gráfico 4h y señales",
        "📅 Estacionalidad",
        "🏦 Instituciones",
        "🌍 Geopolítica",
    ])

    # ------------------------------------------------------------ Explicación
    with pestanas[0]:
        st.markdown(f"### Conclusión para {descripcion}")
        st.markdown(conclusion(
            ticker, puntos, operaciones, semanas_minimas, semanas_maximas, resumen_actual, resumen_proximo
        ))
        st.markdown("### 📈 Lo que dice el gráfico")
        st.markdown(texto_grafico)
        st.markdown("### 📅 Lo que dice la estacionalidad")
        st.markdown(texto_estacional)
        st.markdown("### 🏦 Lo que hacen las instituciones")
        st.markdown(texto_inst)
        st.markdown("### 🌍 Cómo le afecta la geopolítica reciente")
        st.markdown(texto_geo)

    # ------------------------------------------------------------ Gráfico
    with pestanas[1]:
        st.subheader("Velas de 4 horas y RSI(5)")
        inicio = ultima_fecha - pd.DateOffset(months=meses_grafico)
        senales_visibles = [senal for senal in senales if senal["fecha_maximo"] >= inicio]
        st.plotly_chart(
            grafico_precio_rsi(velas.loc[inicio:], rsi.loc[inicio:], senales_visibles, umbral),
            width="stretch",
        )
        st.caption(
            "Triángulos verdes: rupturas del RSI (señales de entrada). Línea discontinua: la línea de "
            f"tendencia bajista del RSI que se rompió. Líneas punteadas: sobreventa ({umbral}) y sobrecompra ({100 - umbral})."
        )

        st.subheader(f"Resultado de cada señal manteniendo {semanas_minimas}–{semanas_maximas} semanas")
        if operaciones.empty:
            st.info("No hubo señales en el período con datos de 4 horas (últimos 730 días).")
        else:
            cerradas = operaciones[operaciones["Estado"] == "Cerrada"]
            columna_maxima = f"Rend. {semanas_maximas} sem"
            columna1, columna2, columna3, columna4 = st.columns(4)
            columna1.metric("Señales", len(operaciones))
            if not cerradas.empty:
                columna2.metric("Ganadoras", f"{(cerradas[columna_maxima] > 0).mean():.0%}")
                columna3.metric(f"Media a {semanas_maximas} semanas", f"{cerradas[columna_maxima].mean():.2%}")
                columna4.metric("Caída máx. media", f"{cerradas['Caída máx.'].mean():.2%}")

            formato = {"Precio entrada": "$ {:,.2f}", "Caída máx.": "{:.2%}"}
            formato.update({f"Rend. {semanas} sem": "{:.2%}" for semanas in (semanas_minimas, semanas_maximas)})
            st.dataframe(
                operaciones.style.format(formato, na_rep="—").format_index(lambda indice: indice + 1),
                width="stretch",
            )
            st.caption("Se entra al cierre de la vela de la señal. «—» indica que aún no pasó ese tiempo.")

    # ------------------------------------------------------------ Estacionalidad
    with pestanas[2]:
        columna1, columna2, columna3 = st.columns(3)
        columna1.metric(
            f"{MESES_COMPLETOS[mes_previo].capitalize()} (anterior): resultado real",
            f"{real_previo:+.2%}",
            f"media 10 años {resumen_previo['media']:+.2%}", delta_color="off",
        )
        columna2.metric(
            f"{MESES_COMPLETOS[mes_actual].capitalize()} (actual): probable",
            f"{resumen_actual['media']:+.2%}",
            f"positivo {resumen_actual['positivos']:.0%} de los años", delta_color="off",
        )
        columna3.metric(
            f"{MESES_COMPLETOS[mes_proximo].capitalize()} (próximo): probable",
            f"{resumen_proximo['media']:+.2%}",
            f"positivo {resumen_proximo['positivos']:.0%} de los años", delta_color="off",
        )

        st.subheader(f"{MESES_COMPLETOS[mes_actual].capitalize()}: este año frente al promedio de los últimos {ANIOS_ESTACIONALIDAD}")
        st.plotly_chart(
            grafico_camino_mes(camino_promedio, camino_actual, MESES_COMPLETOS[mes_actual], ANIOS_ESTACIONALIDAD),
            width="stretch",
        )

        columna1, columna2 = st.columns(2)
        for columna, resumen, etiqueta in (
            (columna1, resumen_previo, "anterior"),
            (columna2, resumen_actual, "actual"),
        ):
            with columna:
                st.markdown(f"**{MESES_COMPLETOS[resumen['mes']].capitalize()} ({etiqueta}), últimos {ANIOS_ESTACIONALIDAD} años**")
                por_anio = resumen["por_anio"].rename("Rendimiento").to_frame()
                st.dataframe(
                    por_anio.sort_index(ascending=False).style.format("{:+.2%}"),
                    width="stretch", height=250,
                )

        st.subheader(f"Estacionalidad mensual de {ticker} (últimos {ANIOS_ESTACIONALIDAD} años)")
        st.plotly_chart(
            grafico_estacionalidad(tabla_10, {
                MESES[mes_previo]: "Anterior", MESES[mes_actual]: "Actual", MESES[mes_proximo]: "Próximo",
            }),
            width="stretch",
        )

        columna1, columna2 = st.columns(2)
        with columna1:
            st.markdown(f"**Entrando el primer día hábil de {MESES_COMPLETOS[mes_proximo]}, año por año**")
            entradas = entradas_por_mes(cierres, mes_proximo, semanas_minimas, semanas_maximas).tail(ANIOS_ESTACIONALIDAD)
            if entradas.empty:
                st.info("No hay suficientes datos.")
            else:
                resumen_entradas = pd.DataFrame(
                    {"Media": entradas.mean(), "Mediana": entradas.median(), "% positivos": (entradas > 0).mean()}
                )
                st.dataframe(resumen_entradas.style.format("{:.2%}"), width="stretch")
                st.dataframe(entradas.sort_index(ascending=False).style.format("{:.2%}"), width="stretch", height=250)

        with columna2:
            primer_anio = cierres.index[0].year
            st.markdown(f"**Tabla de estacionalidad: 10 años frente a toda la historia ({primer_anio}–{hoy.year})**")
            tabla = tabla_10[["Media", "% positivos"]].add_suffix(" 10a").join(
                tabla_total[["Media", "% positivos"]].add_suffix(" total")
            )
            if con_referencia:
                relativa = estacionalidad_relativa(cierres, cierres_referencia, hoy, ANIOS_ESTACIONALIDAD)
                tabla[f"vs {REFERENCIA} 10a"] = relativa["Diferencia media"]
            st.dataframe(tabla.style.format("{:+.2%}"), width="stretch", height=460)

    # ------------------------------------------------------------ Instituciones
    with pestanas[3]:
        columna1, columna2, columna3, columna4 = st.columns(4)
        columna1.metric("Diagnóstico", resumen_inst["veredicto"], f"puntuación {resumen_inst['puntos']:+d}", delta_color="off")
        columna2.metric("Chaikin Money Flow (20d)", f"{resumen_inst['cmf']:+.2f}")
        columna3.metric(
            f"Acumulación / distribución ({resumen_inst['sesiones']} sesiones)",
            f"{resumen_inst['dias_acumulacion']} / {resumen_inst['dias_distribucion']}",
        )
        columna4.metric("Volumen vs. habitual", f"{resumen_inst['volumen_relativo']:.0%}")

        st.markdown(texto_inst)
        st.plotly_chart(grafico_flujo(flujo), width="stretch")
        st.caption(
            "Estos indicadores leen la huella del volumen; no son datos reales de compras o ventas de "
            "cada fondo. Los informes oficiales de posiciones institucionales (13F) se publican con "
            "hasta 45 días de retraso."
        )

        if con_referencia:
            st.subheader(f"Rotación: fuerza relativa frente a {REFERENCIA} (último año)")
            st.plotly_chart(grafico_fuerza_relativa(tabla_fuerza, ticker, REFERENCIA), width="stretch")

        if posiciones is not None:
            st.subheader("Principales posiciones del ETF")
            st.dataframe(posiciones.style.format({"Peso": "{:.2%}"}), width="stretch")

    # ------------------------------------------------------------ Geopolítica
    with pestanas[4]:
        st.markdown(texto_geo)

        if not tabla_indicadores.empty:
            st.subheader("Indicadores de riesgo geopolítico y macro (último mes)")
            vista = tabla_indicadores[["Indicador", "Valor", "Cambio 1 mes", "Correlación", "Efecto"]].copy()
            vista["Efecto"] = vista["Efecto"].map({1: "🟢 Favorece", 0: "⚪ Neutral", -1: "🔴 Perjudica"})
            st.dataframe(
                vista.set_index("Indicador").style.format(
                    {"Valor": "{:,.2f}", "Cambio 1 mes": "{:+.1%}", "Correlación": "{:+.2f}"}
                ),
                width="stretch",
            )
            st.caption(
                f"Correlación: cómo se movió {ticker} cada semana frente al indicador en los dos últimos "
                "años (+1 mismo sentido, −1 sentido contrario). El efecto solo se marca si el indicador "
                "tuvo un movimiento importante y la relación es clara."
            )

        st.subheader("Titulares geopolíticos recientes (14 días)")
        mostrar_noticias(obtener_noticias(CONSULTA_GEOPOLITICA, 14))

        st.subheader(f"Noticias recientes sobre {ticker} (30 días)")
        mostrar_noticias(obtener_noticias(f"{ticker} ETF", 30))
        st.caption("Titulares de Google News en inglés. Cada enlace abre la noticia original.")

    st.divider()
    st.caption("Análisis con datos históricos de Yahoo Finance. No es una recomendación de inversión.")
