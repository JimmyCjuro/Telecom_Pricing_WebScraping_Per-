"""
TelecomPricing Monitor — scraper.py
====================================
Extrae planes y precios de los 4 operadores móviles/fijos del Perú:
  · Claro   → requests + BeautifulSoup (HTML estático)
  · Entel   → requests + BeautifulSoup
  · Bitel   → requests + BeautifulSoup
  · Movistar→ Selenium (página con JS dinámico)

Salida: SQLite  →  pricing.db  (tabla: planes)
        CSV     →  data/planes_YYYYMMDD.csv

Uso rápido (Ubuntu):
  pip install requests beautifulsoup4 selenium pandas lxml webdriver-manager
  python scrapers/scraper.py
  python scrapers/scraper.py --operador claro          # solo uno
  python scrapers/scraper.py --exportar-csv            # también exporta CSV
"""

import re
import time
import sqlite3
import logging
import argparse
from pathlib import Path
from datetime import datetime, date

import requests
import pandas as pd
from bs4 import BeautifulSoup

# Selenium (solo para Movistar — página con renderizado JS)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False
    logging.warning("Selenium no instalado — Movistar será omitido.")

# ──────────────────────────────────────────────────────────────
# Configuración global
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TelecomScraper")

DB_PATH   = Path("data/pricing.db")
CSV_DIR   = Path("data")
HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-PE,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15   # segundos por request
DELAY   = 2    # segundos entre requests (respetar el servidor)


# ──────────────────────────────────────────────────────────────
# Helpers comunes
# ──────────────────────────────────────────────────────────────
def _precio(texto: str) -> float | None:
    """Extrae el primer número flotante de un texto tipo 'S/. 49.90/mes'."""
    nums = re.findall(r"\d+[.,]?\d*", texto.replace(",", "."))
    return float(nums[0]) if nums else None


def _gb(texto: str) -> float | None:
    """Extrae GB de texto como '50 GB', '1 TB' → 1024."""
    texto = texto.upper()
    match = re.search(r"(\d+[.,]?\d*)\s*(GB|TB)", texto)
    if not match:
        return None
    valor = float(match.group(1).replace(",", "."))
    return valor * 1024 if match.group(2) == "TB" else valor


def _mbps(texto: str) -> float | None:
    """Extrae Mbps de texto como '300 Mbps'."""
    match = re.search(r"(\d+[.,]?\d*)\s*[Mm]bps", texto)
    return float(match.group(1).replace(",", ".")) if match else None


def _get_soup(url: str) -> BeautifulSoup | None:
    """Descarga una URL y retorna el BeautifulSoup, o None si falla."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except requests.RequestException as e:
        log.error(f"Error descargando {url}: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Scrapers individuales por operador
# ──────────────────────────────────────────────────────────────

# ── CLARO ──────────────────────────────────────────────────────
def scrape_claro() -> list[dict]:
    """
    Extrae planes postpago de Claro Perú.
    URL: https://www.claro.com.pe/personas/servicios/movil/postpago/
    Estructura HTML objetivo:
      <div class="plan-card"> o similar con nombre, precio, GB
    """
    log.info("[Claro] Iniciando scraping...")
    planes = []

    urls = [
        "https://www.claro.com.pe/personas/movil/postpago/",
        "https://www.claro.com.pe/personas/hogar/internet/",
    ]

    for url in urls:
        soup = _get_soup(url)
        if not soup:
            continue

        # Estrategia 1: tarjetas con clase 'plan' o 'card'
        tarjetas = (
            soup.find_all("div", class_=re.compile(r"plan|card|tarifa", re.I))
            or soup.find_all("article")
        )

        for t in tarjetas:
            texto = t.get_text(" ", strip=True)

            # Buscar precio en el bloque de texto
            precio = _precio(texto)
            if not precio or precio < 20 or precio > 800:
                continue   # filtrar elementos que no son precios de planes

            nombre_tag = (
                t.find(class_=re.compile(r"nombre|title|name|plan-name", re.I))
                or t.find(["h2", "h3", "h4"])
            )
            nombre = nombre_tag.get_text(strip=True) if nombre_tag else "Plan Claro"
            if len(nombre) < 3:
                nombre = "Plan Claro"

            planes.append({
                "operador":    "Claro",
                "nombre_plan": nombre[:80],
                "precio_soles": precio,
                "gb_datos":    _gb(texto),
                "velocidad_mbps": _mbps(texto),
                "url_fuente":  url,
                "fecha_scraping": datetime.now().isoformat(),
            })

        time.sleep(DELAY)

    if not planes:
        log.warning("[Claro] No se encontraron planes.")

    log.info(f"[Claro] {len(planes)} planes encontrados.")
    return planes

# ── ENTEL ──────────────────────────────────────────────────────
def scrape_entel() -> list[dict]:
    """
    Extrae planes postpago de Entel Perú usando Selenium.
    """
    if not SELENIUM_OK:
        log.error("[Entel] Selenium no disponible, omitiendo scraping.")
        return []

    log.info("[Entel] Iniciando scraping (Selenium)...")
    planes = []

    opts = Options()
    opts.binary_location = "/usr/bin/chromium-browser"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")

    urls = [
        "https://www.entel.pe/planes/postpago",
        "https://www.entel.pe/hogar/internet/planes",
    ]

    try:
        driver = webdriver.Chrome(options=opts)

        for url in urls:
            driver.get(url)
            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[class*='plan'], [class*='card'], [class*='pack']")
                    )
                )
            except Exception:
                log.warning(f"[Entel] Timeout esperando elementos en {url}")

            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, "lxml")

            tarjetas = (
                soup.find_all(attrs={"data-plan": True})
                or soup.find_all("div", class_=re.compile(r"plan|card|pack", re.I))
                or soup.find_all(["article", "section"], class_=True)
            )

            for t in tarjetas:
                texto = t.get_text(" ", strip=True)
                precio = _precio(texto)
                if not precio or precio < 20 or precio > 800:
                    continue

                nombre_tag = t.find(["h2", "h3", "h4", "strong"]) or t.find(class_=re.compile(r"title|name", re.I))
                nombre = nombre_tag.get_text(strip=True) if nombre_tag else "Plan Entel"
                if len(nombre) < 3:
                    nombre = "Plan Entel"

                planes.append({
                    "operador":    "Entel",
                    "nombre_plan": nombre[:80],
                    "precio_soles": precio,
                    "gb_datos":    _gb(texto),
                    "velocidad_mbps": _mbps(texto),
                    "url_fuente":  url,
                    "fecha_scraping": datetime.now().isoformat(),
                })

        driver.quit()

    except Exception as e:
        log.error(f"[Entel] Error Selenium: {e}")
        return planes

    if not planes:
        log.warning("[Entel] No se encontraron planes.")

    log.info(f"[Entel] {len(planes)} planes encontrados.")
    return planes



# ── BITEL ──────────────────────────────────────────────────────
def scrape_bitel() -> list[dict]:
    """
    Extrae planes de Bitel.
    URL: https://www.bitel.com.pe/
    """
    log.info("[Bitel] Iniciando scraping...")
    planes = []

    urls = [
        "https://bitel.com.pe/planes/control/ilimitado",
        "https://bitel.com.pe/planes/casa/internet-fibra-optica",
    ]

    for url in urls:
        soup = _get_soup(url)
        if not soup:
            continue

        tarjetas = (
            soup.find_all("div", class_=re.compile(r"plan|card|pack|oferta", re.I))
            or soup.find_all(["article", "li"], class_=True)
        )

        for t in tarjetas:
            texto = t.get_text(" ", strip=True)
            precio = _precio(texto)
            if not precio or precio < 15 or precio > 600:
                continue

            nombre_tag = t.find(["h2", "h3", "h4"]) or t.find(class_=re.compile(r"title|name", re.I))
            nombre = nombre_tag.get_text(strip=True) if nombre_tag else "Plan Bitel"
            if len(nombre) < 3:
                nombre = "Plan Bitel"

            planes.append({
                "operador":    "Bitel",
                "nombre_plan": nombre[:80],
                "precio_soles": precio,
                "gb_datos":    _gb(texto),
                "velocidad_mbps": _mbps(texto),
                "url_fuente":  url,
                "fecha_scraping": datetime.now().isoformat(),
            })

        time.sleep(DELAY)

    if not planes:
        log.warning("[Bitel] No se encontraron planes.")

    log.info(f"[Bitel] {len(planes)} planes encontrados.")
    return planes



# ── MOVISTAR (Selenium) ────────────────────────────────────────
def scrape_movistar() -> list[dict]:
    """
    Extrae planes de Movistar usando Selenium (la página usa React/JS).
    Requiere Google Chrome instalado + webdriver-manager.

    Instalación en Ubuntu:
      sudo apt-get install -y google-chrome-stable
      pip install selenium webdriver-manager
    """
    if not SELENIUM_OK:
        log.error("[Movistar] Selenium no disponible, omitiendo scraping.")
        return []

    log.info("[Movistar] Iniciando Selenium (Chrome headless)...")
    planes = []

    opts = Options()
    opts.binary_location = "/usr/bin/chromium-browser"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")

    urls_mv = [
        "https://www.movistar.pe/planes-moviles",
        "https://www.movistar.pe/hogar/internet",
    ]

    try:
        # Using Selenium 4 native Selenium Manager
        driver  = webdriver.Chrome(options=opts)

        for url in urls_mv:
            driver.get(url)
            # Esperar que carguen las tarjetas de planes
            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[class*='plan'], [class*='card'], [class*='pack']")
                    )
                )
            except Exception:
                log.warning(f"[Movistar] Timeout esperando elementos en {url}")

            time.sleep(2)   # margen extra para JS asíncrono
            soup = BeautifulSoup(driver.page_source, "lxml")

            tarjetas = (
                soup.find_all(class_=re.compile(r"plan|card|pack", re.I))
                or soup.find_all("article")
            )

            for t in tarjetas:
                texto = t.get_text(" ", strip=True)
                precio = _precio(texto)
                if not precio or precio < 20 or precio > 800:
                    continue

                nombre_tag = t.find(["h2", "h3", "h4"]) or t.find(class_=re.compile(r"title|name", re.I))
                nombre = nombre_tag.get_text(strip=True) if nombre_tag else "Plan Movistar"
                if len(nombre) < 3:
                    nombre = "Plan Movistar"

                planes.append({
                    "operador":    "Movistar",
                    "nombre_plan": nombre[:80],
                    "precio_soles": precio,
                    "gb_datos":    _gb(texto),
                    "velocidad_mbps": _mbps(texto),
                    "url_fuente":  url,
                    "fecha_scraping": datetime.now().isoformat(),
                })

        driver.quit()

    except Exception as e:
        log.error(f"[Movistar] Error Selenium: {e}")
        return planes

    if not planes:
        log.warning("[Movistar] No se encontraron planes.")

    log.info(f"[Movistar] {len(planes)} planes encontrados.")
    return planes



# ──────────────────────────────────────────────────────────────
# Persistencia: SQLite + CSV
# ──────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    """Crea la base de datos y la tabla si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS planes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            operador        TEXT NOT NULL,
            nombre_plan     TEXT,
            precio_soles    REAL,
            gb_datos        REAL,
            velocidad_mbps  REAL,
            url_fuente      TEXT,
            fecha_scraping  TEXT,
            fecha_insercion TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_operador ON planes (operador)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fecha ON planes (fecha_scraping)
    """)
    conn.commit()
    log.info(f"Base de datos lista: {DB_PATH}")
    return conn


def guardar_planes(conn: sqlite3.Connection, planes: list[dict]) -> int:
    """Inserta los planes en SQLite. Retorna cantidad insertada."""
    if not planes:
        return 0
    df = pd.DataFrame(planes)
    df.to_sql("planes", conn, if_exists="append", index=False)
    conn.commit()
    log.info(f"Guardados {len(planes)} planes en {DB_PATH}")
    return len(planes)


def exportar_csv(conn: sqlite3.Connection) -> Path:
    """Exporta todos los registros de hoy a un CSV."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    hoy_file = date.today().strftime("%Y%m%d")
    hoy_query = date.today().strftime("%Y-%m-%d")
    csv_path = CSV_DIR / f"planes_{hoy_file}.csv"

    df = pd.read_sql(
        "SELECT * FROM planes WHERE fecha_scraping LIKE ? ORDER BY operador, precio_soles",
        conn,
        params=(f"{hoy_query}%",),
    )
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    log.info(f"CSV exportado: {csv_path}  ({len(df)} filas)")
    return csv_path


def resumen(conn: sqlite3.Connection) -> None:
    """Imprime un resumen de los datos recolectados hoy."""
    hoy_query = date.today().strftime("%Y-%m-%d")
    df = pd.read_sql(
        """
        SELECT
            operador,
            COUNT(*)           AS total_planes,
            MIN(precio_soles)  AS precio_min,
            MAX(precio_soles)  AS precio_max,
            ROUND(AVG(precio_soles), 2) AS precio_promedio
        FROM planes
        WHERE fecha_scraping LIKE ?
        GROUP BY operador
        ORDER BY precio_promedio
        """,
        conn,
        params=(f"{hoy_query}%",),
    )
    print("\n" + "═" * 60)
    print("  RESUMEN COMPETENCIA — TELECOM PERÚ")
    print("═" * 60)
    print(df.to_string(index=False))
    print("═" * 60 + "\n")


# ──────────────────────────────────────────────────────────────
# Orquestador principal
# ──────────────────────────────────────────────────────────────

SCRAPERS = {
    "claro":    scrape_claro,
    "entel":    scrape_entel,
    "bitel":    scrape_bitel,
    "movistar": scrape_movistar,
}


def run(operadores: list[str], exportar_csv_flag: bool = False) -> pd.DataFrame:
    """
    Ejecuta los scrapers de los operadores indicados,
    guarda en SQLite y retorna un DataFrame con todos los planes.
    """
    conn  = init_db()
    todos = []

    for op in operadores:
        if op not in SCRAPERS:
            log.warning(f"Operador desconocido: {op}")
            continue
        try:
            planes = SCRAPERS[op]()
            guardar_planes(conn, planes)
            todos.extend(planes)
        except Exception as e:
            log.error(f"Error inesperado en {op}: {e}", exc_info=True)

    resumen(conn)

    if exportar_csv_flag:
        exportar_csv(conn)

    conn.close()

    return pd.DataFrame(todos) if todos else pd.DataFrame()


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TelecomPricing Monitor — Web Scraper de precios telecom Perú"
    )
    parser.add_argument(
        "--operador",
        choices=list(SCRAPERS.keys()) + ["todos"],
        default="todos",
        help="Operador a scrapear (default: todos)",
    )
    parser.add_argument(
        "--exportar-csv",
        action="store_true",
        help="Exportar resultados a CSV además de SQLite",
    )
    args = parser.parse_args()

    ops = list(SCRAPERS.keys()) if args.operador == "todos" else [args.operador]

    log.info(f"Iniciando scraping — Operadores: {ops}")
    df = run(ops, exportar_csv_flag=args.exportar_csv)

    if not df.empty:
        log.info(f"Total planes recolectados: {len(df)}")
    else:
        log.warning("No se recolectaron datos.")
