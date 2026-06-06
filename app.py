import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from pathlib import Path

# Configuración de la página
st.set_page_config(
    page_title="Telecom Pricing Dashboard - Perú",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados (Aesthetics are important!)
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    .kpi-container {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .kpi-title {
        font-size: 1.1rem;
        color: #4B5563;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2563EB;
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# Función para cargar datos
@st.cache_data
def load_data():
    db_path = Path("data/pricing.db")
    if not db_path.exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    query = """
        SELECT 
            operador, nombre_plan, precio_soles, gb_datos, velocidad_mbps, 
            url_fuente, fecha_scraping
        FROM planes
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Procesamiento adicional
    df['fecha_scraping'] = pd.to_datetime(df['fecha_scraping'])
    
    # Clasificar el tipo de plan
    def classify_plan(row):
        nombre = str(row['nombre_plan']).lower()
        if 'hogar' in nombre or row['velocidad_mbps'] > 0:
            return 'Hogar / Fijo'
        elif 'postpago' in nombre or row['gb_datos'] > 0:
            return 'Móvil Postpago'
        else:
            return 'Otro'
            
    df['tipo_plan'] = df.apply(classify_plan, axis=1)
    
    return df

# Cargar datos
df = load_data()

if df.empty:
    st.error("No se encontraron datos en la base de datos (data/pricing.db). Ejecuta el scraper primero.")
    st.stop()

# --- SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2884/2884976.png", width=100)
st.sidebar.title("Filtros")

# Filtro Operador
operadores = sorted(df['operador'].unique().tolist())
selected_operadores = st.sidebar.multiselect(
    "Operador",
    options=operadores,
    default=operadores
)

# Filtro Tipo de Plan
tipos = sorted(df['tipo_plan'].unique().tolist())
selected_tipos = st.sidebar.multiselect(
    "Tipo de Plan",
    options=tipos,
    default=tipos
)

# Rango de Precios
min_precio = float(df['precio_soles'].min())
max_precio = float(df['precio_soles'].max())
rango_precio = st.sidebar.slider(
    "Rango de Precio (S/.)",
    min_value=min_precio,
    max_value=max_precio,
    value=(min_precio, max_precio)
)

# Aplicar filtros
filtered_df = df[
    (df['operador'].isin(selected_operadores)) &
    (df['tipo_plan'].isin(selected_tipos)) &
    (df['precio_soles'] >= rango_precio[0]) &
    (df['precio_soles'] <= rango_precio[1])
]

# --- MAIN CONTENT ---
st.markdown('<p class="main-header">📊 Telecom Pricing Dashboard - Perú</p>', unsafe_allow_html=True)
st.markdown("Comparativa de precios y planes de los principales operadores de telecomunicaciones en Perú.")

# --- KPIs ---
st.markdown("### Resumen")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-title">Total Planes</div>
        <div class="kpi-value">{len(filtered_df)}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    avg_price = filtered_df['precio_soles'].mean() if not filtered_df.empty else 0
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-title">Precio Promedio</div>
        <div class="kpi-value">S/. {avg_price:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    min_price = filtered_df['precio_soles'].min() if not filtered_df.empty else 0
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-title">Precio Mínimo</div>
        <div class="kpi-value">S/. {min_price:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    max_price = filtered_df['precio_soles'].max() if not filtered_df.empty else 0
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-title">Precio Máximo</div>
        <div class="kpi-value">S/. {max_price:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- GRÁFICOS ---
st.markdown("### Análisis Gráfico")

# Paleta de colores para operadores (Aesthetics)
color_map = {
    'Claro': '#EF4444',     # Red
    'Movistar': '#10B981',  # Green
    'Entel': '#3B82F6',     # Blue
    'Bitel': '#F59E0B'      # Yellow
}

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    # Boxplot de precios por operador
    if not filtered_df.empty:
        fig_box = px.box(
            filtered_df, x="operador", y="precio_soles", color="operador",
            color_discrete_map=color_map,
            title="Distribución de Precios por Operador",
            labels={"operador": "Operador", "precio_soles": "Precio (S/.)"},
            points="all"
        )
        fig_box.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        st.info("No hay datos para mostrar el gráfico de distribución de precios.")

with col_chart2:
    # Gráfico de barras promedio
    if not filtered_df.empty:
        avg_df = filtered_df.groupby('operador')['precio_soles'].mean().reset_index()
        fig_bar = px.bar(
            avg_df, x="operador", y="precio_soles", color="operador",
            color_discrete_map=color_map,
            title="Precio Promedio por Operador",
            labels={"operador": "Operador", "precio_soles": "Precio Promedio (S/.)"},
            text_auto='.2f'
        )
        fig_bar.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No hay datos para mostrar el gráfico de precio promedio.")


# Gráficos de dispersión para Móvil y Hogar
st.markdown("<br>", unsafe_allow_html=True)
col_scatter1, col_scatter2 = st.columns(2)

with col_scatter1:
    df_movil = filtered_df[filtered_df['gb_datos'].notnull() & (filtered_df['gb_datos'] > 0)]
    if not df_movil.empty:
        fig_scatter_gb = px.scatter(
            df_movil, x="gb_datos", y="precio_soles", color="operador",
            color_discrete_map=color_map,
            size="precio_soles", hover_data=["nombre_plan"],
            title="Precio vs GB de Datos (Planes Móviles)",
            labels={"gb_datos": "GB de Datos", "precio_soles": "Precio (S/.)", "operador": "Operador"}
        )
        fig_scatter_gb.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter_gb, use_container_width=True)
    else:
        st.info("No hay datos de planes móviles (con GB) para mostrar el gráfico.")

with col_scatter2:
    df_hogar = filtered_df[filtered_df['velocidad_mbps'].notnull() & (filtered_df['velocidad_mbps'] > 0)]
    if not df_hogar.empty:
        fig_scatter_mbps = px.scatter(
            df_hogar, x="velocidad_mbps", y="precio_soles", color="operador",
            color_discrete_map=color_map,
            size="precio_soles", hover_data=["nombre_plan"],
            title="Precio vs Velocidad (Planes Hogar/Fijo)",
            labels={"velocidad_mbps": "Velocidad (Mbps)", "precio_soles": "Precio (S/.)", "operador": "Operador"}
        )
        fig_scatter_mbps.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter_mbps, use_container_width=True)
    else:
        st.info("No hay datos de planes de hogar (con Mbps) para mostrar el gráfico.")

# --- TABLA DE DATOS ---
st.markdown("### Datos Detallados")
# Formatear la tabla para mostrar
display_df = filtered_df[['operador', 'tipo_plan', 'nombre_plan', 'precio_soles', 'gb_datos', 'velocidad_mbps', 'fecha_scraping', 'url_fuente']].copy()
display_df['fecha_scraping'] = display_df['fecha_scraping'].dt.strftime('%Y-%m-%d %H:%M')

# Renombrar columnas para mejor lectura
display_df.columns = ['Operador', 'Tipo', 'Plan', 'Precio (S/.)', 'GB Datos', 'Velocidad (Mbps)', 'Fecha Scraping', 'URL Fuente']

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "URL Fuente": st.column_config.LinkColumn("Enlace Fuente"),
        "Precio (S/.)": st.column_config.NumberColumn("Precio (S/.)", format="S/. %.2f")
    }
)
