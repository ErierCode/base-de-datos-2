let
    LakehouseRoot = #"LakehouseRoot",
    DeltaPath = LakehouseRoot & "\delta\gold\top_productos",
    Source = DeltaLake.Table(DeltaPath)
in
    Source
