"""Genera fuentes heterogéneas RetailX: CSV (ERP/POS), JSON (Web/API) y XML (IoT/GPS)."""

import argparse
import csv
import json
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

PRODUCTS = [
    ("Laptop Pro 14", "Computadoras", 8500),
    ("Mouse Gamer X", "Accesorios", 180),
    ("Teclado Mecanico", "Accesorios", 450),
    ("Monitor 24", "Monitores", 1250),
    ("Audifonos BT", "Audio", 320),
    ("Silla Ergonomica", "Muebles", 1600),
    ("SSD 1TB", "Almacenamiento", 650),
    ("USB 64GB", "Almacenamiento", 75),
    ("Impresora Laser", "Impresion", 1450),
    ("Router WiFi 6", "Redes", 700),
]
COUNTRIES = ["Guatemala", "Mexico", "Estados Unidos", "El Salvador", "Honduras"]
CHANNELS = ["Tienda", "Web", "App", "Marketplace"]
PAYMENTS = ["Tarjeta", "Efectivo", "Transferencia", "PayPal"]

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from jobs.paths import RAW_CSV, RAW_JSON, RAW_XML


def _sale_row(sale_id: int, rng: random.Random) -> dict:
    product, category, base_price = rng.choice(PRODUCTS)
    quantity = rng.randint(1, 8)
    price = round(base_price * rng.uniform(0.85, 1.20), 2)
    start = datetime(2025, 1, 1)
    date = start + timedelta(days=rng.randint(0, 500))
    return {
        "id_venta": sale_id,
        "fecha": date.strftime("%Y-%m-%d"),
        "id_cliente": rng.randint(1, 120000),
        "pais": rng.choice(COUNTRIES),
        "sucursal": f"Sucursal-{rng.randint(1, 30)}",
        "producto": product,
        "categoria": category,
        "cantidad": quantity,
        "precio_unitario": price,
        "canal": rng.choice(CHANNELS),
        "metodo_pago": rng.choice(PAYMENTS),
        "monto": round(quantity * price, 2),
    }


def generate_csv(rows: int, output: str, rng: random.Random) -> None:
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "id_venta", "fecha", "id_cliente", "pais", "sucursal", "producto",
            "categoria", "cantidad", "precio_unitario", "canal", "metodo_pago",
        ])
        for i in range(1, rows + 1):
            row = _sale_row(i, rng)
            writer.writerow([
                row["id_venta"], row["fecha"], row["id_cliente"], row["pais"],
                row["sucursal"], row["producto"], row["categoria"], row["cantidad"],
                row["precio_unitario"], row["canal"], row["metodo_pago"],
            ])
    print(f"CSV generado: {output} ({rows:,} registros)")


def generate_json(rows: int, output: str, rng: random.Random, start_id: int) -> None:
    """Eventos Web/API en JSONL (semestructurado)."""
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        for i in range(rows):
            row = _sale_row(start_id + i, rng)
            event = {
                "id_venta": row["id_venta"],
                "fecha": row["fecha"],
                "id_cliente": row["id_cliente"],
                "pais": row["pais"],
                "producto": row["producto"],
                "categoria": row["categoria"],
                "cantidad": row["cantidad"],
                "precio_unitario": row["precio_unitario"],
                "canal": row["canal"],
                "metodo_pago": row["metodo_pago"],
                "monto": row["monto"],
                "evento": "compra_web",
                "user_agent": rng.choice(["Chrome", "Safari", "Firefox", "Edge"]),
            }
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"JSON generado: {output} ({rows:,} eventos)")


def generate_xml(rows: int, output: str, rng: random.Random, start_id: int) -> None:
    """Telemetría IoT/GPS en XML."""
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("telemetria_flota")
    for i in range(rows):
        row = _sale_row(start_id + i, rng)
        venta = ET.SubElement(root, "venta")
        ET.SubElement(venta, "id_venta").text = str(row["id_venta"])
        ET.SubElement(venta, "fecha").text = row["fecha"]
        ET.SubElement(venta, "id_cliente").text = str(row["id_cliente"])
        ET.SubElement(venta, "pais").text = row["pais"]
        ET.SubElement(venta, "producto").text = row["producto"]
        ET.SubElement(venta, "categoria").text = row["categoria"]
        ET.SubElement(venta, "cantidad").text = str(row["cantidad"])
        ET.SubElement(venta, "precio_unitario").text = str(row["precio_unitario"])
        ET.SubElement(venta, "monto").text = str(row["monto"])
        ET.SubElement(venta, "vehiculo_id").text = f"VEH-{rng.randint(1, 500)}"
        ET.SubElement(venta, "lat").text = str(round(rng.uniform(13.5, 17.5), 6))
        ET.SubElement(venta, "lon").text = str(round(rng.uniform(-92.5, -87.0), 6))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    print(f"XML generado: {output} ({rows:,} registros)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera CSV, JSON y XML de RetailX")
    parser.add_argument("--rows", type=int, default=1_000_000, help="Registros principales en CSV")
    parser.add_argument("--json-ratio", type=float, default=0.10, help="Proporción JSON vs CSV")
    parser.add_argument("--xml-ratio", type=float, default=0.05, help="Proporción XML vs CSV")
    args = parser.parse_args()

    rng = random.Random(710)
    json_rows = max(1, int(args.rows * args.json_ratio))
    xml_rows = max(1, int(args.rows * args.xml_ratio))
    json_start = args.rows + 1
    xml_start = args.rows + json_rows + 1

    generate_csv(args.rows, RAW_CSV, rng)
    generate_json(json_rows, RAW_JSON, rng, json_start)
    generate_xml(xml_rows, RAW_XML, rng, xml_start)


if __name__ == "__main__":
    main()
