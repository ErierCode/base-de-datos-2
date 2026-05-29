# Abre el proyecto Power BI y valida que existan tablas Gold Delta
$LakehouseRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PbipPath = Join-Path $PSScriptRoot "RetailX_Gold_Dashboard.pbip"
$GoldPath = Join-Path $LakehouseRoot "delta\gold\kpis_generales"

Write-Host "Lakehouse:" $LakehouseRoot

if (-not (Test-Path $GoldPath)) {
    Write-Warning "No existe delta/gold. Ejecuta primero el pipeline:"
    Write-Host "  docker exec -it retailx_dataops_spark bash -c 'python jobs/run_pipeline.py --rows 10000'"
    exit 1
}

$pbi = @(
    "${env:ProgramFiles}\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    "${env:ProgramFiles(x86)}\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    "$env:LOCALAPPDATA\Microsoft\WindowsApps\PBIDesktop.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($pbi) {
    Write-Host "Abriendo Power BI Desktop..."
    Start-Process $pbi -ArgumentList $PbipPath
} else {
    Write-Warning "Power BI Desktop no encontrado. Abre manualmente:"
    Write-Host $PbipPath
}
