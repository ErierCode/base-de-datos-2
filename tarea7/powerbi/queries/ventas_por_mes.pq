let
    LakehouseRoot = #"LakehouseRoot",
    DeltaPath = LakehouseRoot & "\delta\gold\ventas_por_mes",
    Source = DeltaLake.Table(DeltaPath)
in
    Source
