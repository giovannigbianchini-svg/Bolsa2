"""Redacta la explicación del análisis a partir de los resultados.

Cada función devuelve texto en Markdown. Las reglas son sencillas y están a la
vista para que se puedan revisar o ajustar.
"""

import numpy as np

from src.procesamiento import MESES_COMPLETOS


def _porcentaje(valor):
    return f"{valor:+.2%}"


def explicar_grafico(ticker, rsi_actual, umbral, senal_activa, senales, operaciones, semanas_maximas):
    """Explica en qué punto está el RSI y qué dijeron las señales anteriores."""
    if senal_activa:
        situacion = (
            f"El RSI(5) de 4 horas está en **{rsi_actual:.0f}** y **acaba de romper su línea de "
            "tendencia bajista** después de pasar por sobreventa: es la señal de entrada de la estrategia."
        )
        puntos = 1
    elif rsi_actual <= umbral:
        situacion = (
            f"El RSI(5) de 4 horas está en **{rsi_actual:.0f}**, en zona de sobreventa (≤ {umbral}). "
            "Es la zona donde se prepara la entrada: falta que el RSI rompa hacia arriba la línea "
            "que une sus últimos máximos (línea discontinua en el gráfico)."
        )
        puntos = 1
    elif rsi_actual >= 100 - umbral:
        situacion = (
            f"El RSI(5) de 4 horas está en **{rsi_actual:.0f}**, en sobrecompra (≥ {100 - umbral}). "
            "El precio subió rápido en las últimas velas; entrar ahora sería comprar caro. "
            f"La estrategia pide esperar un retroceso que lleve el RSI a {umbral} o menos."
        )
        puntos = -1
    else:
        situacion = (
            f"El RSI(5) de 4 horas está en **{rsi_actual:.0f}**, en zona neutral. No hay señal: "
            f"hay que esperar a que baje a {umbral} o menos y luego rompa su línea bajista."
        )
        puntos = 0

    partes = [situacion]

    if senales:
        ultima = senales[-1]
        fila = operaciones.iloc[-1]
        partes.append(
            f"La última ruptura fue el **{ultima['fecha']:%d/%m/%Y}** a $ {fila['Precio entrada']:,.2f}; "
            f"estado: {fila['Estado'].lower()}."
        )

    cerradas = operaciones[operaciones["Estado"] == "Cerrada"] if not operaciones.empty else operaciones
    columna = f"Rend. {semanas_maximas} sem"
    if not cerradas.empty:
        partes.append(
            f"En los últimos dos años hubo **{len(cerradas)} señales cerradas**: "
            f"{(cerradas[columna] > 0).mean():.0%} ganaron a {semanas_maximas} semanas, con un rendimiento "
            f"medio de {_porcentaje(cerradas[columna].mean())} y una caída máxima media durante la "
            f"operación de {cerradas['Caída máx.'].mean():.2%}."
        )

    return " ".join(partes), puntos


def explicar_estacionalidad(ticker, resumen_anterior, real_anterior, resumen_actual,
                            en_curso, sesiones_en_curso, promedio_a_la_fecha, resumen_proximo):
    """Compara el mes anterior con su historia y estima el mes actual y el próximo."""
    nombre_anterior = MESES_COMPLETOS[resumen_anterior["mes"]]
    nombre_actual = MESES_COMPLETOS[resumen_actual["mes"]]
    nombre_proximo = MESES_COMPLETOS[resumen_proximo["mes"]]
    partes = []

    diferencia = real_anterior - resumen_anterior["media"]
    comparacion = "mejor" if diferencia > 0 else "peor"
    partes.append(
        f"**Mes anterior ({nombre_anterior}):** {ticker} terminó en {_porcentaje(real_anterior)}, "
        f"{comparacion} que su media de los últimos 10 años ({_porcentaje(resumen_anterior['media'])}, "
        f"positivo {resumen_anterior['positivos']:.0%} de las veces)."
    )

    texto_actual = (
        f"**Mes actual ({nombre_actual}), lo probable según los últimos 10 años:** media "
        f"{_porcentaje(resumen_actual['media'])}, mediana {_porcentaje(resumen_actual['mediana'])}, "
        f"positivo {resumen_actual['positivos']:.0%} de los años; la mitad de los años terminó entre "
        f"{_porcentaje(resumen_actual['p25'])} y {_porcentaje(resumen_actual['p75'])}."
    )
    if not np.isnan(en_curso):
        texto_actual += (
            f" En lo que va de mes ({sesiones_en_curso} sesiones) lleva {_porcentaje(en_curso)}"
        )
        if promedio_a_la_fecha is not None:
            adelanto = "por encima" if en_curso > promedio_a_la_fecha else "por debajo"
            texto_actual += (
                f", {adelanto} de lo que solía llevar a esta altura ({_porcentaje(promedio_a_la_fecha)})"
            )
        texto_actual += "."
        if en_curso > resumen_actual["p75"]:
            texto_actual += (
                " Ya superó lo que suele ganar en un mes completo, así que buena parte del "
                "movimiento estacional podría estar hecho."
            )
    partes.append(texto_actual)

    partes.append(
        f"**Mes próximo ({nombre_proximo}):** media de 10 años {_porcentaje(resumen_proximo['media'])}, "
        f"positivo {resumen_proximo['positivos']:.0%} de los años."
    )

    # La posición de 4 a 6 semanas abarca el resto de este mes y buena parte del próximo.
    media_conjunta = resumen_actual["media"] + resumen_proximo["media"]
    positivos = (resumen_actual["positivos"] + resumen_proximo["positivos"]) / 2
    if media_conjunta > 0.005 and positivos >= 0.6:
        puntos = 1
        partes.append(
            f"Para una posición de 4 a 6 semanas, {nombre_actual} y {nombre_proximo} juntos han sido "
            "**favorables** históricamente."
        )
    elif media_conjunta < 0 and positivos < 0.5:
        puntos = -1
        partes.append(
            f"Para una posición de 4 a 6 semanas, {nombre_actual} y {nombre_proximo} juntos han sido "
            "**desfavorables** históricamente."
        )
    else:
        puntos = 0
        partes.append("La estacionalidad de las próximas semanas es **neutral**: no ayuda ni perjudica.")

    return "\n\n".join(partes), puntos


def explicar_instituciones(ticker, resumen, posiciones):
    """Traduce los indicadores de volumen a lo que podrían estar haciendo las instituciones."""
    veredictos = {
        "Acumulación": "los indicadores apuntan a que las instituciones están **comprando (acumulando)**",
        "Distribución": "los indicadores apuntan a que las instituciones están **vendiendo (distribuyendo)**",
        "Neutral": "los indicadores **no muestran una dirección clara** del dinero institucional",
    }
    partes = [f"En {ticker}, {veredictos[resumen['veredicto']]}:"]

    flujo = "entrando" if resumen["cmf"] > 0 else "saliendo"
    partes.append(
        f"- **Chaikin Money Flow (20 días): {resumen['cmf']:+.2f}.** El dinero está {flujo}: "
        "los cierres quedan más cerca del " + ("máximo" if resumen["cmf"] > 0 else "mínimo")
        + " del día en las sesiones de más volumen."
    )
    partes.append(
        f"- **{resumen['dias_acumulacion']} días de acumulación y {resumen['dias_distribucion']} de "
        f"distribución** en las últimas {resumen['sesiones']} sesiones (días que suben o bajan con más "
        "volumen que el anterior, típicos de órdenes grandes)."
    )

    obv = "sube" if resumen["obv_20"] > 0 else "baja"
    partes.append(
        f"- **OBV:** en 20 sesiones {obv} el equivalente a {abs(resumen['obv_20']):.1f} días de volumen "
        f"medio, mientras el precio hizo {_porcentaje(resumen['precio_20'])}."
        + (" El volumen confirma la subida." if resumen["obv_20"] > 0 and resumen["precio_20"] > 0 else "")
        + (" El volumen confirma la bajada." if resumen["obv_20"] < 0 and resumen["precio_20"] < 0 else "")
        + (" El volumen no acompaña al precio: posible acumulación silenciosa." if resumen["obv_20"] > 0 > resumen["precio_20"] else "")
        + (" El volumen no acompaña al precio: posible distribución." if resumen["obv_20"] < 0 < resumen["precio_20"] else "")
    )

    actividad = "más" if resumen["volumen_relativo"] > 1 else "menos"
    partes.append(
        f"- **Volumen de las últimas 20 sesiones:** {resumen['volumen_relativo']:.0%} del habitual "
        f"({actividad} actividad de lo normal)."
    )

    rotacion = {
        1: "gana fuerza frente al S&P 500: hay **rotación hacia el activo**",
        -1: "pierde fuerza frente al S&P 500: el dinero está **rotando fuera del activo**",
        0: "se mueve parecido al S&P 500: sin rotación clara",
    }
    partes.append(f"- **Fuerza relativa:** {rotacion[resumen['fuerza']]}.")

    if posiciones is not None and not posiciones.empty:
        tres = posiciones.head(3)
        nombres = ", ".join(f"{empresa} ({peso:.0%})" for empresa, peso in zip(tres["Empresa"], tres["Peso"]))
        partes.append(
            f"\nLas tres mayores posiciones del ETF son {nombres}, que suman "
            f"{tres['Peso'].sum():.0%}: lo que hagan las instituciones con ellas mueve buena parte del ETF."
        )

    puntos = 1 if resumen["veredicto"] == "Acumulación" else -1 if resumen["veredicto"] == "Distribución" else 0
    return "\n".join(partes), puntos


def explicar_geopolitica(ticker, indicadores):
    """Resume qué indicadores de riesgo se movieron y si eso suele ayudar o perjudicar al activo."""
    if indicadores is None or indicadores.empty:
        return "No se pudieron obtener los indicadores de mercado.", 0

    importantes = indicadores[indicadores["Importante"]]
    if importantes.empty:
        texto = (
            "En el último mes ningún indicador de riesgo (VIX, petróleo, oro, dólar, bono a 10 años) "
            "tuvo un movimiento fuera de lo normal: el mercado no está descontando un evento "
            "geopolítico importante en este momento."
        )
        return texto, 0

    partes = ["En el último mes hubo movimientos importantes en:"]
    for _, fila in importantes.iterrows():
        direccion = "subió" if fila["Cambio 1 mes"] > 0 else "bajó"
        relacion = "en el mismo sentido que" if fila["Correlación"] > 0 else "en sentido contrario a"
        efecto = {1: "**le favorece**", -1: "**le perjudica**", 0: "tiene un efecto poco claro"}[fila["Efecto"]]
        partes.append(
            f"- **{fila['Indicador']}** {direccion} {abs(fila['Cambio 1 mes']):.1%}. {fila['Significado']} "
            f"En los dos últimos años {ticker} se movió {relacion} este indicador "
            f"(correlación semanal {fila['Correlación']:+.2f}), así que este movimiento {efecto}."
        )

    total = int(indicadores["Efecto"].sum())
    if total > 0:
        resumen = f"En conjunto, el contexto geopolítico y macro reciente **favorece** a {ticker}."
        puntos = 1
    elif total < 0:
        resumen = f"En conjunto, el contexto geopolítico y macro reciente **juega en contra** de {ticker}."
        puntos = -1
    else:
        resumen = "En conjunto, los efectos se compensan: el contexto es **neutral** para el activo."
        puntos = 0

    partes.append(f"\n{resumen} Los titulares de la pestaña *Geopolítica* ayudan a entender qué hay detrás.")
    return "\n".join(partes), puntos


def conclusion(ticker, puntos, operaciones, semanas_minimas, semanas_maximas, resumen_actual, resumen_proximo):
    """Une los cuatro análisis en una conclusión y una expectativa de rendimiento."""
    total = sum(puntos.values())
    nombres = {1: "a favor", 0: "neutral", -1: "en contra"}
    detalle = ", ".join(f"{area}: {nombres[valor]}" for area, valor in puntos.items())

    if puntos["Gráfico"] == -1:
        decision = (
            "**Esperar.** Aunque otros factores acompañen, el RSI está en sobrecompra; la estrategia "
            "pide esperar un retroceso y una nueva ruptura."
        )
    elif total >= 2:
        decision = "**Condiciones favorables** para preparar la entrada cuando se dé la ruptura del RSI."
    elif total <= -2:
        decision = "**Condiciones desfavorables:** mejor no entrar aunque aparezca una señal."
    else:
        decision = "**Condiciones mixtas:** entrar solo con la señal confirmada y con un tamaño de posición prudente."

    partes = [f"{decision} ({detalle}; puntuación {total:+d} sobre ±4)."]

    columna = f"Rend. {semanas_maximas} sem"
    cerradas = operaciones[operaciones["Estado"] == "Cerrada"] if not operaciones.empty else operaciones
    if len(cerradas) >= 3:
        partes.append(
            f"**Expectativa de rendimiento manteniendo {semanas_minimas}–{semanas_maximas} semanas** "
            f"(según las señales de los dos últimos años): media {_porcentaje(cerradas[columna].mean())}, "
            f"con la mitad de las operaciones entre {_porcentaje(cerradas[columna].quantile(0.25))} y "
            f"{_porcentaje(cerradas[columna].quantile(0.75))}."
        )
    partes.append(
        f"La estacionalidad de 10 años del mes actual y el próximo suma "
        f"{_porcentaje(resumen_actual['media'] + resumen_proximo['media'])} de media."
    )
    partes.append(
        "*Es un análisis estadístico con datos pasados: no garantiza resultados futuros "
        "ni es una recomendación de inversión.*"
    )
    return "\n\n".join(partes)
