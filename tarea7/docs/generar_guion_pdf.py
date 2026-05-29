"""Genera PDF legible del guion de video (pagina completa, sin texto cortado)."""
from pathlib import Path

from fpdf import FPDF

PDF_FILE = Path(__file__).parent / "Guion_Video_Laboratorio_RetailX.pdf"


def clean(text: str) -> str:
    rep = {
        "\u2014": "-", "\u2013": "-", "\u2192": "->",
        "\u201c": '"', "\u201d": '"', "\u00a1": "!", "\u00bf": "?",
    }
    for a, b in rep.items():
        text = text.replace(a, b)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class GuionPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, clean(f"Pagina {self.page_no()}"), align="C")

    def write_block(self, title: str, decir: str, mostrar: list[str]) -> None:
        w = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)

        self.ln(6)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(230, 240, 255)
        self.multi_cell(w, 8, clean(title), fill=True)
        self.ln(2)

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 80, 160)
        self.multi_cell(w, 6, clean("TEXTO PARA DECIR:"))
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(w, 5, clean(decir))
        self.ln(2)

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 120, 0)
        self.multi_cell(w, 6, clean("MOSTRAR EN PANTALLA:"))
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 9)
        for item in mostrar:
            self.set_x(self.l_margin)
            self.multi_cell(w, 5, clean(f"  * {item}"))
        self.ln(3)


BLOCKS = [
    (
        "BLOQUE 0 - Introduccion (1 min) | Canva: diapositiva 1",
        "Hola. En este video presento el laboratorio de Data Lakehouse con Apache Spark y Delta Lake, "
        "aplicado al caso empresarial RetailX. Implemente un pipeline completo con arquitectura Medallion "
        "(Bronze, Silver y Gold), procesamiento con PySpark, persistencia en Delta Lake y un dashboard "
        "en Power BI conectado a la capa Gold.",
        [
            "Diapositiva 1 de Canva (portada: Data Lakehouse + Delta Lake + Apache Spark)",
            "Explorador de archivos: carpeta practicaBD/data-lakehouse/lakehouse",
        ],
    ),
    (
        "BLOQUE 1 - Problema RetailX y objetivos (2 min) | Canva: diapositivas 2 y 3",
        "RetailX opera con fuentes heterogeneas: transacciones en CSV (ERP/POS), eventos web en JSON, "
        "telemetria IoT en XML. Eso genera reportes lentos, duplicados en KPIs y poca escalabilidad. "
        "Los objetivos del laboratorio son: diferenciar DW, Data Lake y Lakehouse; disenar pipeline "
        "Medallion; procesar millones de registros con Spark; y usar Delta Lake con ACID y versionado.",
        [
            "Diapositiva 3 Canva: El problema Empresa RetailX",
            "Carpeta data/: sales_raw.csv, sales_events.json, fleet_telemetry.xml",
            "Diapositiva 2 Canva: Objetivos de aprendizaje (4 puntos)",
        ],
    ),
    (
        "BLOQUE 2 - DW vs Data Lake vs Lakehouse (1.5 min) | Canva: diapositiva 4",
        "El Data Warehouse es rigido y costoso. El Data Lake guarda todo en bruto pero sin transacciones. "
        "El Lakehouse combina almacenamiento economico con Delta Lake: consistencia ACID, versionado "
        "y time travel sobre archivos Parquet.",
        [
            "Diapositiva 4 Canva: DW vs Data Lake vs Lakehouse",
            "Carpeta delta/gold/kpis_generales/_delta_log (muestra metadatos Delta)",
        ],
    ),
    (
        "BLOQUE 3 - Arquitectura Medallion (2 min) | Canva: diapositiva 5",
        "Bronze: ingesta en crudo sin transformar (CSV, JSON, XML). Silver: limpieza, tipos correctos, "
        "deduplicacion y calidad. Gold: KPIs y agregados de negocio listos para analisis y Power BI.",
        [
            "Diapositiva 5 Canva: Bronze -> Silver -> Gold",
            "Explorador: delta/bronze/sales_csv, sales_json, sales_xml",
            "Explorador: delta/silver/sales_clean",
            "Explorador: delta/gold/ (kpis, ventas por categoria, pais, mes, top productos)",
        ],
    ),
    (
        "BLOQUE 4 - Apache Spark (1 min) | Canva: diapositiva 6",
        "Apache Spark procesa en memoria y en paralelo. Usamos PySpark en jobs separados por capa: "
        "Bronze, Silver, Gold, mas analisis de negocio y demostracion de time travel.",
        [
            "Diapositiva 6 Canva: Apache Spark",
            "Carpeta jobs/: 02_bronze.py, 03_silver.py, 04_gold.py, 06_analisis_negocio.py, 07_delta_time_travel.py",
        ],
    ),
    (
        "BLOQUE 5 - Laboratorio: Docker y generacion de datos (2.5 min) | Canva: diapositiva 7",
        "Levantamos Docker Compose con red lakehouse-net y contenedor retailx_dataops_spark. "
        "Generamos datos de prueba: ventas en CSV (hasta 1 millon), eventos JSON y telemetria XML. "
        "El job 01b genera 1M tuplas con SparkSession llamada RetailX, como pide el laboratorio.",
        [
            "Terminal: docker compose build y docker compose up -d",
            "Terminal: docker ps (contenedor retailx_dataops_spark)",
            "Terminal en contenedor: python jobs/run_pipeline.py --rows 10000",
            "Consola mostrando: CSV generado, Bronze, Silver, Gold creados",
            "Diapositiva 7 Canva: pasos 1 al 4 del laboratorio",
        ],
    ),
    (
        "BLOQUE 6 - Delta Lake: SQL y time travel (2 min) | Canva: diapositiva 8",
        "Paso 5: consultamos CSV con Spark SQL (groupBy cliente, sum monto). Paso 6: escribimos en Delta "
        "y se crea _delta_log con transacciones ACID. Paso 7: leemos desde Delta y mostramos time travel "
        "a versiones anteriores.",
        [
            "Terminal: salida de python jobs/02b_spark_sql_delta_lab.py",
            "Explorador: delta/lab/delta_ventas/_delta_log",
            "Terminal: salida de python jobs/07_delta_time_travel.py (historial versiones)",
            "Diapositiva 8 Canva: pasos 5 al 7",
        ],
    ),
    (
        "BLOQUE 7 - Analisis gerencial (2 min) | Canva: diapositiva 9 preguntas",
        "Respondemos las 4 preguntas de negocio con PySpark: cliente con mayor volumen de compra; "
        "top 10 ventas por importe; promedio de venta por cliente; y clientes que concentran "
        "el 80 por ciento del ingreso (analisis Pareto).",
        [
            "Diapositiva 9 Canva: Preguntas de analisis",
            "Terminal: python jobs/06_analisis_negocio.py (mostrar las 4 respuestas)",
        ],
    ),
    (
        "BLOQUE 8 - Proyecto final y Power BI (3 min) | Canva: diapositiva 9 proyecto",
        "El Lakehouse completo integra Bronze con tres formatos, Silver limpio, Gold analitico y "
        "dashboard Power BI. Gold se exporta a CSV en output/ para el modelo PBIP. "
        "Procesamos miles de transacciones en tres capas Medallion.",
        [
            "Archivo jobs/run_pipeline.py",
            "Carpeta output/: kpis_generales.csv, ventas_por_categoria.csv, etc.",
            "Power BI: panel Datos con 5 tablas",
            "Power BI: dashboard con tarjetas KPI y graficos",
            "Diapositiva 9 Canva: Proyecto final RetailX (1M, 3 capas)",
        ],
    ),
    (
        "BLOQUE 9 - Cierre (1 min)",
        "En resumen implemente un Lakehouse RetailX con fuentes heterogeneas, pipeline Medallion, "
        "Spark y Delta Lake, analisis gerencial, time travel y consumo en Power BI. "
        "El codigo esta en data-lakehouse/lakehouse. Gracias por ver el video.",
        [
            "Diapositiva 5 Canva (Medallion) como cierre visual",
            "Arbol completo del proyecto",
            "Dashboard Power BI final",
        ],
    ),
]


def main() -> None:
    pdf = GuionPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(w, 10, clean("Guion para video"), align="C")
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(w, 8, clean("Laboratorio Data Lakehouse RetailX"), align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        w, 5,
        clean(
            "Basado en: presentacion Canva (Data Lakehouse + Delta Lake + Apache Spark). "
            "Duracion sugerida: 12-18 minutos. Lee en voz alta lo que dice TEXTO PARA DECIR "
            "y muestra en pantalla lo que dice MOSTRAR EN PANTALLA."
        ),
        align="C",
    )

    for title, decir, mostrar in BLOCKS:
        pdf.write_block(title, decir, mostrar)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(w, 8, clean("ANEXO - Comandos para la demo"))
    pdf.set_font("Helvetica", "", 9)
    comandos = [
        "cd data-lakehouse/lakehouse",
        "docker compose up -d",
        "docker exec -it retailx_dataops_spark bash",
        "python jobs/run_pipeline.py --rows 10000",
        "python jobs/06_analisis_negocio.py",
        "python jobs/07_delta_time_travel.py",
    ]
    for cmd in comandos:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, 5, clean(f"  $ {cmd}"))

    pdf.output(str(PDF_FILE))
    print(f"PDF regenerado: {PDF_FILE}")


if __name__ == "__main__":
    main()
