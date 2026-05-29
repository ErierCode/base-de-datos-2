# Aplica vistas SQL del Módulo 8 en postgres-control
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$sql = Join-Path $root "init\09-module8-powerbi-views.sql"
if (-not (Test-Path $sql)) { throw "No se encuentra $sql" }
Get-Content -Raw $sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
Write-Host "Vistas Power BI aplicadas en dcc_control."
