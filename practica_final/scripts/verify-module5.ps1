#Requires -Version 5.1
<#
.SYNOPSIS
  Verificacion Modulo 5: snapshot, desastre, restore con evidencia en consola.

.EXAMPLE
  .\scripts\verify-module5.ps1
  .\scripts\verify-module5.ps1 -SnapshotLabel PRE_IMPORT
  .\scripts\verify-module5.ps1 -SkipSnapshot
#>
param(
    [ValidateSet("PRE_DEPLOY", "PRE_TEST", "PRE_IMPORT")]
    [string] $SnapshotLabel = "PRE_TEST",
    [string] $RecoveryDatabase = "dcc_control_recovery",
    [switch] $SkipSnapshot
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

function Write-Banner([string] $Text) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor Cyan
}

function Write-Evidence([string] $Label, [string] $Value) {
    Write-Host ("  [{0,-22}] {1}" -f $Label, $Value) -ForegroundColor Green
}

function Invoke-ComposeRun([string[]] $RunArgs, [hashtable] $ExtraEnv = @{}) {
    $cmd = @("compose", "run", "--rm")
    foreach ($kv in $ExtraEnv.GetEnumerator()) {
        $cmd += "-e"
        $cmd += "$($kv.Key)=$($kv.Value)"
    }
    $cmd += "backup-worker"
    $cmd += $RunArgs
    Write-Host ("  > docker {0}" -f ($cmd -join " ")) -ForegroundColor DarkGray
    & docker @cmd
    if ($LASTEXITCODE -ne 0) {
        throw "Comando fallo (exit $LASTEXITCODE): docker $($cmd -join ' ')"
    }
}

function Invoke-PsqlQuery([string] $Sql) {
    $user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "dcc_admin" }
    $db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "dcc_control" }
    docker exec dcc-postgres-control psql -U $user -d $db -t -A -c $Sql 2>&1
}

function Test-TableExists([string] $Schema, [string] $Table) {
    $q = "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='$Schema' AND table_name='$Table');"
    $r = (Invoke-PsqlQuery $q | Out-String).Trim()
    return $r -eq "t"
}

function Get-BackupSummary() {
    $sql = @"
SELECT id, kind::text, round(size_mb::numeric,2), round(duration_sec::numeric,2),
       COALESCE(round(rto_observed_sec::numeric,2)::text,'-'),
       CASE WHEN sla_met THEN 'Si' ELSE 'No' END,
       CASE WHEN COALESCE(remote_url,'') <> '' OR cloud_object_key IS NOT NULL THEN 'S3' ELSE 'local' END,
       COALESCE(snapshot_label,'-'),
       left(checksum_sha256,16) || '...',
       created_at::text
FROM backup_history
ORDER BY id DESC
LIMIT 5;
"@
    Invoke-PsqlQuery $sql
}

$StartedAt = Get-Date
Write-Banner "DataOps - Verificacion Modulo 5 (Backup y Recovery + Nube)"
Write-Evidence "Inicio" $StartedAt.ToString("yyyy-MM-dd HH:mm:ss")
Write-Evidence "Proyecto" $ProjectRoot
Write-Evidence "Etiqueta snapshot" $SnapshotLabel

if (-not (Test-Path ".env")) {
    Write-Warning "No existe .env - S3 usara defaults de compose si aplican."
} else {
    Write-Evidence ".env" "Encontrado (credenciales no se muestran)"
}

Write-Host ""
Write-Host "Comprobando contenedores..." -ForegroundColor Yellow
$pg = docker ps --filter "name=dcc-postgres-control" --format "{{.Names}}" 2>$null
if (-not $pg) {
    Write-Host "Levantando postgres-control..." -ForegroundColor Yellow
    docker compose up -d postgres-control | Out-Null
    Start-Sleep -Seconds 8
}
$bw = docker ps --filter "name=dcc-backup-worker" --format "{{.Names}}" 2>$null
if (-not $bw) {
    Write-Host "Levantando backup-worker..." -ForegroundColor Yellow
    docker compose up -d backup-worker | Out-Null
    Start-Sleep -Seconds 3
}

Write-Banner "Estado inicial"
$accountsBefore = Test-TableExists "workload" "accounts"
$beforeTxt = if ($accountsBefore) { "Si" } else { "No" }
Write-Evidence "workload.accounts existe" $beforeTxt
Write-Host ""
Write-Host "Ultimos 5 registros en backup_history:" -ForegroundColor Yellow
Get-BackupSummary

if (-not $SkipSnapshot) {
    Write-Banner "Paso 1/3 - Snapshot ($SnapshotLabel)"
    Invoke-ComposeRun @("python", "main.py", "snapshot", $SnapshotLabel)
    Write-Evidence "Snapshot" "FULL registrado con etiqueta $SnapshotLabel"
} else {
    Write-Banner "Paso 1/3 - Snapshot omitido (-SkipSnapshot)"
}

Write-Banner "Paso 2/3 - Simulacion de desastre (DROP workload.accounts)"
Invoke-ComposeRun @("python", "disaster_demo.py")
$accountsAfterDisaster = Test-TableExists "workload" "accounts"
$disasterTxt = if ($accountsAfterDisaster) { "Si (inesperado)" } else { "No (OK)" }
Write-Evidence "Tras desastre: tabla existe" $disasterTxt

Write-Banner "Paso 3/3 - Restore cadena FULL -> DIFF -> INC + medicion RTO"
Invoke-ComposeRun @("python", "restore_demo.py", "--measure-rto") @{ RECOVERY_DATABASE = $RecoveryDatabase }

$recoveryCount = "?"
try {
    $recoveryCount = docker exec dcc-postgres-control psql -U dcc_admin -d $RecoveryDatabase -t -A -c "SELECT COUNT(*) FROM workload.accounts;" 2>&1 | Out-String
    $recoveryCount = $recoveryCount.Trim()
} catch {
    $recoveryCount = "error al consultar $RecoveryDatabase"
}
Write-Evidence "BD recuperacion" $RecoveryDatabase
Write-Evidence "Filas workload.accounts" $recoveryCount

Write-Banner "Metricas SLA (backup_sla_targets + ultimo FULL)"
$slaSql = @"
SELECT target_rpo_sec, target_rto_sec,
       round(EXTRACT(EPOCH FROM (NOW() - bh.restore_point))::numeric, 1) AS sec_desde_full,
       round(bh.rto_observed_sec::numeric, 2) AS rto_observado_sec,
       CASE WHEN bh.sla_met THEN 'Si' ELSE 'No' END AS sla_ultimo_full,
       (bh.remote_url IS NOT NULL OR bh.cloud_object_key IS NOT NULL) AS en_nube
FROM backup_sla_targets t
LEFT JOIN LATERAL (
  SELECT * FROM backup_history WHERE kind='FULL' ORDER BY id DESC LIMIT 1
) bh ON true
WHERE t.id = 1;
"@
Invoke-PsqlQuery $slaSql

Write-Banner "Historial reciente (evidencia informe)"
Get-BackupSummary

$EndedAt = Get-Date
$ElapsedSec = [math]::Round(($EndedAt - $StartedAt).TotalSeconds, 0)
$disasterOk = if (-not $accountsAfterDisaster) { "CONFIRMADO" } else { "REVISAR" }

Write-Banner "Resumen para informe (copiar/pegar)"
Write-Host ""
Write-Host "Modulo 5 - Prueba: $($StartedAt.ToString('yyyy-MM-dd HH:mm:ss')) -> $($EndedAt.ToString('HH:mm:ss')) (${ElapsedSec}s)"
Write-Host "1. Snapshot: etiqueta $SnapshotLabel (FULL + S3 si S3_BUCKET en .env)."
Write-Host "2. Desastre: DROP workload.accounts - ausente tras paso 2: $disasterOk"
Write-Host "3. Restore: base $RecoveryDatabase; RTO en backup_history.rto_observed_sec"
Write-Host "4. Cuentas recuperadas: $recoveryCount filas en workload.accounts"
Write-Host "Evidencia: captura S3 dcc-control/FULL/ + UI Backup (5) + esta consola."
Write-Host ""

Write-Banner "Verificacion finalizada"
if (-not $accountsAfterDisaster) {
    Write-Host "OK: desastre aplicado. BD principal sin workload.accounts (restore demo en $RecoveryDatabase)." -ForegroundColor Green
} else {
    Write-Host "AVISO: workload.accounts sigue existiendo tras desastre." -ForegroundColor Yellow
}
