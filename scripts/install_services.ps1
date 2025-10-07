### **6. `scripts/install_services.ps1`**

# Script para instalar servicios SAM con NSSM
# Ejecutar como Administrador

$ErrorActionPreference = "Stop"

# Configuración
$projectRoot = "C:\RPA\rpa_sam"
$pythonExe = "$projectRoot\.venv\Scripts\python.exe"
$logDir = "C:\RPA\Logs\SAM"

# Verificar que existen los recursos necesarios
if (!(Test-Path $pythonExe)) {
    Write-Error "Python no encontrado en: $pythonExe"
    exit 1
}

# Crear directorio de logs si no existe
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Definición de servicios
$services = @(
    @{
        Name = "SAM-Lanzador"
        Module = "sam.lanzador"
        DisplayName = "SAM - Servicio Lanzador"
        Description = "Orquesta la ejecución de robots RPA"
    },
    @{
        Name = "SAM-Balanceador"
        Module = "sam.balanceador"
        DisplayName = "SAM - Servicio Balanceador"
        Description = "Balancea la carga entre recursos disponibles"
    },
    @{
        Name = "SAM-Callback"
        Module = "sam.callback"
        DisplayName = "SAM - Servidor de Callbacks"
        Description = "Recibe notificaciones de ejecuciones completadas"
    },
    @{
        Name = "SAM-InterfazWeb"
        Module = "sam.web"
        DisplayName = "SAM - Interfaz Web"
        Description = "Dashboard de administración y monitoreo"
    }
)

Write-Host "Instalando servicios SAM..." -ForegroundColor Cyan

foreach ($svc in $services) {
    Write-Host "`nConfigurando: $($svc.DisplayName)" -ForegroundColor Yellow
    
    # Verificar si el servicio ya existe
    $existing = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Servicio ya existe. Eliminando..." -ForegroundColor Gray
        nssm stop $svc.Name
        nssm remove $svc.Name confirm
    }
    
    # Instalar servicio
    nssm install $svc.Name $pythonExe "-m" $svc.Module
    
    # Configurar servicio
    nssm set $svc.Name DisplayName $svc.DisplayName
    nssm set $svc.Name Description $svc.Description
    nssm set $svc.Name AppDirectory $projectRoot
    nssm set $svc.Name AppStdout "$logDir\$($svc.Name)_stdout.log"
    nssm set $svc.Name AppStderr "$logDir\$($svc.Name)_stderr.log"
    nssm set $svc.Name AppRotateFiles 1
    nssm set $svc.Name AppRotateOnline 1
    nssm set $svc.Name AppRotateBytes 10485760  # 10MB
    nssm set $svc.Name Start SERVICE_AUTO_START
    
    Write-Host "  ✓ Instalado correctamente" -ForegroundColor Green
}

Write-Host "`n✓ Todos los servicios instalados correctamente" -ForegroundColor Green
Write-Host "`nPara iniciar los servicios, ejecuta:" -ForegroundColor Cyan
Write-Host "  Start-Service -Name 'SAM-*'" -ForegroundColor White