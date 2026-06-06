# Telecom Pricing Monitor WebScraping- Perú 

Este proyecto es una herramienta automatizada de **Web Scraping y Visualización de Datos** diseñada para monitorear, extraer y comparar los planes y tarifas de los cuatro principales operadores de telecomunicaciones en el Perú: **Claro, Movistar, Entel y Bitel**.

<img width="1863" height="1039" alt="Captura desde 2026-06-06 01-38-13" src="https://github.com/user-attachments/assets/1dccb23b-371a-44bf-a9c1-cfef8bac2062" />


##  Características Principales

1. **Web Scraping Robusto**:
   - Extracción de planes móviles (Postpago) y planes fijos (Hogar/Internet).
   - Integración con **Selenium** para páginas dinámicas (ej. Movistar).
   - Uso de **BeautifulSoup** y **Requests** para extracción rápida de HTML estático.
2. **Almacenamiento Local**:
   - Guarda el histórico de extracciones en una base de datos local **SQLite** (`data/pricing.db`).
   - Permite la exportación opcional de los datos diarios a formato **CSV**.
3. **Dashboard Interactivo**:
   - Interfaz web construida con **Streamlit**.
   - Gráficos interactivos generados con **Plotly** (Comparativas de Precio vs. Velocidad, Precio vs. GB, Boxplots).
   - KPIs automáticos y segmentación mediante filtros laterales por operador y tipo de servicio.

##  Estructura del Proyecto

```bash
├── app.py                   # Dashboard interactivo en Streamlit
├── scrapers/
│   └── scraper.py           # Script principal de web scraping
├── data/                    # Carpeta generada automáticamente
│   ├── pricing.db           # Base de datos SQLite (generada al ejecutar el scraper)
│   └── planes_YYYYMMDD.csv  # (Opcional) Archivos de exportación CSV
├── requirements.txt         # Dependencias del proyecto
└── .gitignore               # Archivos ignorados por Git
```

##  Instalación y Requisitos

Asegúrate de tener **Python 3.10+** instalado. Adicionalmente, el scraper de Movistar requiere tener **Google Chrome** instalado en el sistema.

1. **Clona este repositorio**:
   ```bash
   git clone https://github.com/JimmyCjuro/Telecom_Pricing_WebScraping_Per-.git
   cd Telecom_Pricing_WebScraping_Per-
   ```

2. **Instala las dependencias**:
   Se recomienda usar un entorno virtual (`venv`).
   ```bash
   pip install -r requirements.txt
   ```

##  Uso

### 1. Ejecutar el Web Scraper

Para poblar la base de datos con las tarifas actuales, ejecuta el scraper. Puedes extraer de todos los operadores a la vez o de uno en específico:

```bash
# Extraer datos de TODOS los operadores
python scrapers/scraper.py

# Extraer datos de un solo operador (claro, movistar, entel, bitel)
python scrapers/scraper.py --operador claro

# Extraer datos y exportar a la vez un archivo CSV
python scrapers/scraper.py --exportar-csv
```

### 2. Levantar el Dashboard de Streamlit

Una vez ejecutado el scraper (y generada la base de datos `data/pricing.db`), levanta la interfaz gráfica:

```bash
streamlit run app.py
```
*Esto abrirá automáticamente una pestaña en tu navegador web en `http://localhost:8501`.*

---
*Desarrollado para el análisis del mercado de telecomunicaciones.*
