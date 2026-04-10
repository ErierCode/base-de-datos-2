"""
Simulador minimo de fallos de nodos para MoveFast.

Objetivo:
- Simular caida de nodo primario por shard (GT, MX, US)
- Mostrar continuidad del servicio via replica (AP: disponibilidad + tolerancia a particiones)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass
class Nodo:
    nombre: str
    activo: bool = True


@dataclass
class ShardPais:
    codigo: str
    primario: Nodo
    replica: Nodo
    solicitudes_atendidas: int = 0
    usando_replica: bool = False

    def atender_solicitud(self) -> str:
        if self.primario.activo:
            self.solicitudes_atendidas += 1
            self.usando_replica = False
            return f"[{self.codigo}] OK: solicitud atendida por PRIMARIO."
        if self.replica.activo:
            self.solicitudes_atendidas += 1
            self.usando_replica = True
            return f"[{self.codigo}] DEGRADADO: primario caido, atendiendo en REPLICA."
        return f"[{self.codigo}] ERROR: primario y replica caidos, no hay disponibilidad."

    def caer_primario(self) -> str:
        self.primario.activo = False
        return f"[{self.codigo}] EVENTO: caida del nodo primario."

    def recuperar_primario(self) -> str:
        self.primario.activo = True
        self.usando_replica = False
        return f"[{self.codigo}] EVENTO: primario recuperado."

    def estado(self) -> str:
        primario = "UP" if self.primario.activo else "DOWN"
        replica = "UP" if self.replica.activo else "DOWN"
        modo = "REPLICA" if self.usando_replica else "PRIMARIO"
        return (
            f"{self.codigo}: primario={primario}, replica={replica}, "
            f"modo={modo}, solicitudes={self.solicitudes_atendidas}"
        )


def imprimir_titulo(texto: str) -> None:
    print("\n" + "=" * 72)
    print(texto)
    print("=" * 72)


def imprimir_estados(shards: Dict[str, ShardPais]) -> None:
    print("\nEstado actual de shards:")
    for codigo in ["GT", "MX", "US"]:
        print(" - " + shards[codigo].estado())


def main() -> None:
    shards: Dict[str, ShardPais] = {
        "GT": ShardPais("GT", Nodo("GT-primario"), Nodo("GT-replica")),
        "MX": ShardPais("MX", Nodo("MX-primario"), Nodo("MX-replica")),
        "US": ShardPais("US", Nodo("US-primario"), Nodo("US-replica")),
    }

    imprimir_titulo("MoveFast - Simulacion de Caida de Nodos")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    imprimir_estados(shards)

    imprimir_titulo("Fase 1: Operacion normal")
    eventos = [
        ("GT", "Solicitud viaje #1"),
        ("MX", "Solicitud viaje #2"),
        ("US", "Solicitud viaje #3"),
    ]
    for codigo, etiqueta in eventos:
        print(f"{etiqueta} -> {shards[codigo].atender_solicitud()}")
    imprimir_estados(shards)

    imprimir_titulo("Fase 2: Caida de primario en MX")
    print(shards["MX"].caer_primario())
    print("Solicitud viaje #4 -> " + shards["MX"].atender_solicitud())
    print("Solicitud viaje #5 -> " + shards["MX"].atender_solicitud())
    imprimir_estados(shards)

    imprimir_titulo("Fase 3: Recuperacion de primario en MX")
    print(shards["MX"].recuperar_primario())
    print("Solicitud viaje #6 -> " + shards["MX"].atender_solicitud())
    imprimir_estados(shards)

    imprimir_titulo("Fase 4: Falla total en US (ejemplo de indisponibilidad)")
    shards["US"].caer_primario()
    shards["US"].replica.activo = False
    print("Solicitud viaje #7 -> " + shards["US"].atender_solicitud())
    imprimir_estados(shards)

    imprimir_titulo("Conclusiones de simulacion")
    print("- Con replica activa, el sistema mantiene continuidad (AP) en fallos parciales.")
    print("- Sin replica disponible, ese shard pierde disponibilidad.")
    print("- Esto justifica replicacion y monitoreo continuo por region.")


if __name__ == "__main__":
    main()
