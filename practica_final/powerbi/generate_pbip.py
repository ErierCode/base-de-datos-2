#!/usr/bin/env python3
"""Genera el proyecto Power BI (PBIP) del Módulo 8 — DataOps Control Center."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = "DataOps-Control-Center"
SCHEMA_VISUAL = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/visualContainer/2.6.0/schema.json"
)
SCHEMA_PAGE = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/page/1.0.0/schema.json"
)
SCHEMA_REPORT = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/report/1.0.0/schema.json"
)

# Puerto 5433 por defecto: en Windows suele haber otro Postgres en 5432 (conflicto con Power BI).
PG_SERVER = "localhost:5433"
PG_DB = "dcc_control"

TABLES = [
    {
        "name": "v_pbi_rendimiento",
        "columns": [
            ("id", "int64"),
            ("db_id", "int64"),
            ("motor", "string"),
            ("capture_time", "dateTime"),
            ("cpu_pct", "double"),
            ("connections", "int64"),
            ("locks", "int64"),
            ("deadlocks", "int64"),
            ("health_grade", "string"),
        ],
    },
    {
        "name": "v_pbi_heatmap",
        "columns": [
            ("db_id", "int64"),
            ("motor", "string"),
            ("hora", "int64"),
            ("dia_semana", "int64"),
            ("dia_nombre", "string"),
            ("operaciones", "int64"),
        ],
    },
    {
        "name": "v_pbi_top_slow",
        "columns": [
            ("id", "int64"),
            ("db_id", "int64"),
            ("motor", "string"),
            ("speed_class", "string"),
            ("duration_ms", "double"),
            ("query_preview", "string"),
            ("index_used", "string"),
            ("execution_plan_preview", "string"),
            ("duration_before_ms", "double"),
            ("duration_after_ms", "double"),
            ("improvement_pct", "double"),
            ("index_applied", "string"),
            ("created_at", "dateTime"),
        ],
    },
    {
        "name": "v_pbi_backups",
        "columns": [
            ("id", "int64"),
            ("kind", "string"),
            ("size_mb", "double"),
            ("duration_sec", "double"),
            ("restore_point", "dateTime"),
            ("sla_met", "boolean"),
            ("subido_nube", "boolean"),
            ("created_at", "dateTime"),
            ("notes", "string"),
        ],
    },
    {
        "name": "v_pbi_sla",
        "columns": [
            ("seconds_since_full_restore_point", "double"),
            ("target_rpo_sec", "int64"),
            ("target_rto_sec", "int64"),
            ("cumple_rpo", "boolean"),
            ("last_full_restore_point", "dateTime"),
        ],
    },
    {
        "name": "v_pbi_disponibilidad",
        "columns": [
            ("db_id", "int64"),
            ("motor", "string"),
            ("muestras_sanas", "int64"),
            ("total_muestras", "int64"),
            ("disponibilidad_pct", "double"),
        ],
    },
]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def m_partition(table: str) -> list[str]:
    return [
        "let",
        f'    Source = PostgreSQL.Database("{PG_SERVER}", "{PG_DB}", [CreateNavigationProperties=false]),',
        f'    Data = Source{{[Schema="public",Item="{table}"]}}[Data]',
        "in",
        "    Data",
    ]


def build_model_bim() -> dict:
    tables = []
    for t in TABLES:
        cols = []
        for name, dtype in t["columns"]:
            col: dict = {
                "name": name,
                "dataType": dtype,
                "sourceColumn": name,
            }
            if dtype == "dateTime":
                col["formatString"] = "General Date"
            elif dtype == "double":
                col["formatString"] = "0.00"
            cols.append(col)
        tables.append(
            {
                "name": t["name"],
                "columns": cols,
                "partitions": [
                    {
                        "name": t["name"],
                        "mode": "import",
                        "source": {"type": "m", "expression": m_partition(t["name"])},
                    }
                ],
            }
        )

    tables.append(
        {
            "name": "_Medidas",
            "measures": [
                {
                    "name": "Objetivo Disponibilidad",
                    "expression": "99.9",
                    "formatString": "0.0",
                },
                {
                    "name": "Disponibilidad Promedio",
                    "expression": "AVERAGE(v_pbi_disponibilidad[disponibilidad_pct])",
                    "formatString": "0.0",
                },
            ],
            "partitions": [
                {
                    "name": "_Medidas",
                    "mode": "import",
                    "source": {
                        "type": "calculated",
                        "expression": 'ROW("Placeholder", 1)',
                    },
                }
            ],
        }
    )

    return {
        "name": PROJECT,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-ES",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "es-ES",
            "tables": tables,
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps([t["name"] for t in TABLES])},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


def col_field(entity: str, prop: str) -> dict:
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": f"{entity}.{prop}",
        "active": True,
    }


def measure_field(entity: str, prop: str) -> dict:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": f"{entity}.{prop}",
    }


def visual_shell(name: str, vtype: str, x: int, y: int, w: int, h: int, query: dict, extra_objects: dict | None = None) -> dict:
    objects = extra_objects or {}
    return {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
        "visual": {
            "visualType": vtype,
            "query": query,
            "objects": objects,
        },
    }


def textbox_visual(name: str, title: str, y: int = 0) -> dict:
    return {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": 24, "y": y, "z": 1000, "width": 1232, "height": 56, "tabOrder": 0},
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": title,
                                            "textStyle": {
                                                "fontSize": "18pt",
                                                "fontWeight": "bold",
                                            },
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            },
        },
    }


def page_def(display_name: str, page_id: str, visuals: list[tuple[str, dict]]) -> None:
    base = ROOT / f"{PROJECT}.Report" / "definition" / "pages" / page_id
    write_json(
        base / "page.json",
        {
            "$schema": SCHEMA_PAGE,
            "name": page_id,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
            "objects": {
                "background": [
                    {
                        "properties": {
                            "color": {
                                "solid": {
                                    "color": {"expr": {"Literal": {"Value": "'#F5F7FA'"}}}
                                }
                            },
                            "transparency": {"expr": {"Literal": {"Value": "0D"}}},
                        }
                    }
                ]
            },
        },
    )
    for vname, vjson in visuals:
        write_json(base / "visuals" / vname / "visual.json", vjson)


def build_report() -> None:
    pages_order = []

    # Page 1 — Rendimiento temporal (líneas + tabla; sin segmentador que vacía el lienzo)
    p1_line = visual_shell(
        "line_rendimiento",
        "lineChart",
        24,
        72,
        1232,
        380,
        {
            "queryState": {
                "Category": {
                    "projections": [col_field("v_pbi_rendimiento", "capture_time")]
                },
                "Series": {
                    "projections": [col_field("v_pbi_rendimiento", "motor")]
                },
                "Y": {
                    "projections": [col_field("v_pbi_rendimiento", "cpu_pct")]
                },
            }
        },
    )
    p1_table = visual_shell(
        "tabla_rendimiento",
        "tableEx",
        24,
        468,
        1232,
        240,
        {
            "queryState": {
                "Values": {
                    "projections": [
                        col_field("v_pbi_rendimiento", "motor"),
                        col_field("v_pbi_rendimiento", "capture_time"),
                        col_field("v_pbi_rendimiento", "cpu_pct"),
                        col_field("v_pbi_rendimiento", "connections"),
                        col_field("v_pbi_rendimiento", "locks"),
                    ]
                }
            }
        },
    )
    page_def(
        "01 Rendimiento",
        "p01_rendimiento",
        [
            ("titulo", textbox_visual("titulo", "Rendimiento temporal — CPU, conexiones y bloqueos")),
            ("line_rendimiento", p1_line),
            ("tabla_rendimiento", p1_table),
        ],
    )
    pages_order.append("p01_rendimiento")

    # Page 2 — Heatmap (matriz)
    p2_matrix = visual_shell(
        "matrix_heatmap",
        "pivotTable",
        24,
        80,
        1232,
        600,
        {
            "queryState": {
                "Rows": {"projections": [col_field("v_pbi_heatmap", "dia_nombre")]},
                "Columns": {"projections": [col_field("v_pbi_heatmap", "hora")]},
                "Values": {
                    "projections": [col_field("v_pbi_heatmap", "operaciones")]
                },
            }
        },
    )
    page_def(
        "02 Heatmap",
        "p02_heatmap",
        [
            ("titulo", textbox_visual("titulo", "Heatmap de actividad — operaciones por hora y día")),
            ("matrix_heatmap", p2_matrix),
        ],
    )
    pages_order.append("p02_heatmap")

    # Page 3 — Top queries
    p3_table = visual_shell(
        "tabla_queries",
        "tableEx",
        24,
        80,
        1232,
        600,
        {
            "queryState": {
                "Values": {
                    "projections": [
                        col_field("v_pbi_top_slow", "motor"),
                        col_field("v_pbi_top_slow", "speed_class"),
                        col_field("v_pbi_top_slow", "duration_ms"),
                        col_field("v_pbi_top_slow", "query_preview"),
                        col_field("v_pbi_top_slow", "duration_before_ms"),
                        col_field("v_pbi_top_slow", "duration_after_ms"),
                        col_field("v_pbi_top_slow", "improvement_pct"),
                    ]
                }
            }
        },
    )
    page_def(
        "03 Top Queries",
        "p03_top_slow",
        [
            ("titulo", textbox_visual("titulo", "Top queries lentas — plan y optimización")),
            ("tabla_queries", p3_table),
        ],
    )
    pages_order.append("p03_top_slow")

    # Page 4 — Backups
    p4_table = visual_shell(
        "tabla_backups",
        "tableEx",
        24,
        80,
        800,
        600,
        {
            "queryState": {
                "Values": {
                    "projections": [
                        col_field("v_pbi_backups", "kind"),
                        col_field("v_pbi_backups", "size_mb"),
                        col_field("v_pbi_backups", "duration_sec"),
                        col_field("v_pbi_backups", "sla_met"),
                        col_field("v_pbi_backups", "created_at"),
                    ]
                }
            }
        },
    )
    p4_card = visual_shell(
        "card_sla",
        "card",
        840,
        80,
        416,
        200,
        {
            "queryState": {
                "Values": {
                    "projections": [col_field("v_pbi_sla", "cumple_rpo")]
                }
            }
        },
    )
    page_def(
        "04 Backups SLA",
        "p04_backups",
        [
            ("titulo", textbox_visual("titulo", "Estado de backups y cumplimiento SLA")),
            ("tabla_backups", p4_table),
            ("card_sla", p4_card),
        ],
    )
    pages_order.append("p04_backups")

    # Page 5 — Disponibilidad (tarjeta + tabla; el medidor con columna suelta queda en blanco)
    p5_card = visual_shell(
        "card_disp",
        "card",
        24,
        80,
        400,
        200,
        {
            "queryState": {
                "Values": {
                    "projections": [
                        measure_field("_Medidas", "Disponibilidad Promedio")
                    ]
                }
            }
        },
    )
    p5_table = visual_shell(
        "tabla_disp",
        "tableEx",
        640,
        80,
        616,
        400,
        {
            "queryState": {
                "Values": {
                    "projections": [
                        col_field("v_pbi_disponibilidad", "motor"),
                        col_field("v_pbi_disponibilidad", "disponibilidad_pct"),
                        col_field("v_pbi_disponibilidad", "total_muestras"),
                    ]
                }
            }
        },
    )
    page_def(
        "05 Disponibilidad",
        "p05_disponibilidad",
        [
            ("titulo", textbox_visual("titulo", "Disponibilidad global — objetivo 99,9 %")),
            ("card_disp", p5_card),
            ("tabla_disp", p5_table),
        ],
    )
    pages_order.append("p05_disponibilidad")

    report_dir = ROOT / f"{PROJECT}.Report" / "definition"
    write_json(
        report_dir / "pages" / "pages.json",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                "definition/pagesMetadata/1.0.0/schema.json"
            ),
            "pageOrder": pages_order,
            "activePageName": pages_order[0],
        },
    )
    write_json(
        report_dir / "version.json",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                "definition/versionMetadata/1.0.0/schema.json"
            ),
            "version": "2.0.0",
        },
    )
    write_json(
        report_dir / "report.json",
        {
            "$schema": SCHEMA_REPORT,
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": "5.55",
                    "type": "SharedResources",
                }
            },
            "layoutOptimization": "None",
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": "CY24SU10",
                            "path": "BaseThemes/CY24SU10.json",
                            "type": "BaseTheme",
                        }
                    ],
                }
            ],
        },
    )

    theme_path = report_dir / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json"
    write_json(
        theme_path,
        {
            "name": "CY24SU10",
            "dataColors": [
                "#118DFF",
                "#12239E",
                "#E66C37",
                "#6B007B",
                "#E044A7",
                "#744EC2",
                "#D9B300",
                "#D64550",
            ],
            "foreground": "#252423",
            "background": "#FFFFFF",
            "tableAccent": "#118DFF",
        },
    )


def main() -> None:
    sm_dir = ROOT / f"{PROJECT}.SemanticModel"
    # Solo el informe en artifacts; el modelo va enlazado en definition.pbir (byPath).
    write_json(
        ROOT / f"{PROJECT}.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write_json(
        sm_dir / "definition.pbism",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/"
                "semanticModel/definitionProperties/1.0.0/schema.json"
            ),
            "version": "4.0",
            "settings": {},
        },
    )
    write_json(sm_dir / "model.bim", build_model_bim())
    write_json(
        ROOT / f"{PROJECT}.Report" / "definition.pbir",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                "definitionProperties/2.0.0/schema.json"
            ),
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{PROJECT}.SemanticModel"}},
        },
    )
    build_report()
    print(f"PBIP generado en: {ROOT}")
    print(f"Abrir: {ROOT / f'{PROJECT}.pbip'}")


if __name__ == "__main__":
    main()
