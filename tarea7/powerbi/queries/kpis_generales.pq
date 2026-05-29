let
    LakehouseRoot = #"LakehouseRoot",
    DeltaPath = LakehouseRoot & "\delta\gold\kpis_generales",
    Source = DeltaLake.Table(DeltaPath)
in
    Source
