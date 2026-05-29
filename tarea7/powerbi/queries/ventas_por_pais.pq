let
    LakehouseRoot = #"LakehouseRoot",
    DeltaPath = LakehouseRoot & "\delta\gold\ventas_por_pais",
    Source = DeltaLake.Table(DeltaPath)
in
    Source
