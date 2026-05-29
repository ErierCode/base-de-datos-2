let
    LakehouseRoot = #"LakehouseRoot",
    DeltaPath = LakehouseRoot & "\delta\gold\ventas_por_categoria",
    Source = DeltaLake.Table(DeltaPath)
in
    Source
