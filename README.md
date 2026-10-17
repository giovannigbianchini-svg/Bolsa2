# Bolsa2

Aplicación de Streamlit que analiza un ETF (por defecto XLP, consumo básico) con la estrategia de **ruptura de tendencia del RSI(5) en velas de 4 horas**, y la complementa con la estacionalidad de los últimos 10 años, la huella de las grandes instituciones y el contexto geopolítico reciente. Usa precios de Yahoo Finance y titulares de Google News hasta la fecha de hoy, y redacta una explicación del análisis con una conclusión.

## Estructura

```
Bolsa2/
├── .streamlit/
│   └── config.toml             # Tema visual y opciones del servidor
├── data/
│   ├── diario_ejemplo.csv      # Datos diarios (1999-2026) de XLP, XLU, XLV y SPY: máximo, mínimo, cierre y volumen
│   ├── velas_4h_ejemplo.csv    # Velas de 4 horas de los mismos ETFs (últimos 730 días)
│   └── indicadores_ejemplo.csv # VIX, petróleo, oro, dólar y bono a 10 años (últimos 2 años)
├── src/
│   ├── __init__.py
│   ├── procesamiento.py        # Descarga de precios, RSI, señales, estacionalidad y fuerza relativa
│   ├── instituciones.py        # Chaikin Money Flow, OBV, días de acumulación/distribución
│   ├── contexto.py             # Indicadores de riesgo geopolítico y noticias
│   ├── explicacion.py          # Redacción de la explicación y la conclusión
│   └── graficos.py             # Gráficos de Plotly
├── app.py                   # Interfaz de Streamlit (punto de entrada)
├── requirements.txt
└── README.md
```

## Ejecutar en local

Desde la carpeta `Bolsa2`:

```
pip install -r requirements.txt
streamlit run app.py
```

La app se abre en http://localhost:8501.

## Publicar en Streamlit Cloud

1. Sube el contenido de esta carpeta a un repositorio de GitHub, de modo que `app.py` y `requirements.txt` queden en la raíz del repositorio.
2. En https://share.streamlit.io elige **Create app**, selecciona el repositorio y la rama, y escribe `app.py` como *Main file path*.
3. Pulsa **Deploy**. Streamlit Cloud instala las dependencias de `requirements.txt` automáticamente.

## Uso

1. Elige el activo de la lista o escribe otro ticker.
2. Ajusta el nivel de sobreventa del RSI (20 por defecto), las semanas que mantienes la posición (4 a 6 por defecto) y cuántos meses muestra el gráfico.
3. Pulsa **Analizar**.

Arriba aparece la situación a la fecha de hoy (cierre, RSI, última señal, diagnóstico institucional y estacionalidad probable del mes) y debajo cinco pestañas:

- **🧭 Explicación del análisis:** conclusión (puntuación de −4 a +4 sumando gráfico, estacionalidad, instituciones y geopolítica), expectativa de rendimiento para el plazo elegido y una explicación en texto de cada parte.
- **📈 Gráfico 4h y señales:** velas de 4 horas y RSI(5) con las señales y la línea de tendencia que rompió el RSI en cada una, y el resultado de cada señal de los últimos 730 días con la caída máxima sufrida.
- **📅 Estacionalidad (últimos 10 años):** resultado real del mes anterior frente a su promedio, lo probable del mes actual y del próximo, el recorrido sesión a sesión del mes actual frente al promedio, y la tabla de todos los meses (10 años, historia completa y diferencia con SPY). El mes en curso no cuenta en las medias porque todavía no terminó.
- **🏦 Instituciones:** Chaikin Money Flow, OBV, días de acumulación y distribución, volumen relativo, fuerza relativa frente a SPY (rotación) y principales posiciones del ETF.
- **🌍 Geopolítica:** cómo se movieron en el último mes el VIX, el petróleo, el oro, el dólar y el bono a 10 años, si eso suele favorecer o perjudicar al activo (según la correlación de los dos últimos años), y titulares recientes de Google News.

## Cómo se detecta la señal

1. Se calcula el RSI de 5 periodos (método de Wilder) sobre los cierres de 4 horas. Cada sesión tiene dos velas: de 9:30 a 13:30 y de 13:30 a 16:00 (hora de Nueva York).
2. Se traza una línea entre los dos últimos máximos del RSI cuando el segundo es más bajo que el primero (tendencia bajista del RSI).
3. Hay señal de entrada cuando el RSI, después de tocar la zona de sobreventa, cruza esa línea hacia arriba. Se entra al cierre de esa vela.

Un máximo del RSI solo se da por confirmado cuando ya pasaron dos velas, así que las señales nunca usan información del futuro. Es una versión automática de lo que se dibuja a mano: puede no coincidir exactamente con las líneas que traces tú en el gráfico.

## Limitaciones

- Yahoo Finance solo ofrece datos de 1 hora de los últimos 730 días, por eso el resultado de las señales cubre ese período. La estacionalidad usa cierres diarios desde 1999.
- Los indicadores institucionales leen la huella del volumen y la fuerza relativa: son aproximaciones, no flujos reales de cada fondo. Yahoo Finance no ofrece tenedores institucionales ni flujos de ETFs, y los informes oficiales (13F) llegan con hasta 45 días de retraso.
- La geopolítica se mide por su efecto en los precios de riesgo; la app no interpreta el contenido de las noticias, solo las lista.
- Si Yahoo Finance no responde, marca **Usar datos de ejemplo (sin conexión)**. Esos datos llegan hasta la fecha en que se guardaron; las noticias y las posiciones del ETF necesitan conexión.

Este análisis usa datos históricos y no es una recomendación de inversión.
