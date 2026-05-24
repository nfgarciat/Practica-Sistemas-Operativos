# Arranca los cuatro servicios del sistema en ventanas independientes.
# Ejecutar desde la raiz del proyecto:
#     powershell -ExecutionPolicy Bypass -File scripts\arrancar_windows.ps1

$DIR_PROYECTO = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$DIR_SRC      = Join-Path $DIR_PROYECTO "src"
$DIR_ARALMAC  = Join-Path $DIR_PROYECTO "aralmac"

New-Item -ItemType Directory -Force -Path (Join-Path $DIR_ARALMAC "ficheros")   | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DIR_ARALMAC "programas")  | Out-Null

Write-Host "Arrancando gesfich..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python `"$DIR_SRC\gesfich.py`" -f gf_pet -x `"$DIR_ARALMAC\ficheros`""

Write-Host "Arrancando gesprog..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python `"$DIR_SRC\gesprog.py`" -p gp_pet -x `"$DIR_ARALMAC\programas`""

Write-Host "Arrancando ejecutor..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python `"$DIR_SRC\ejecutor.py`" -e ej_pet -x `"$DIR_ARALMAC`""

Start-Sleep -Seconds 2

Write-Host "Arrancando ctrllt..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python `"$DIR_SRC\ctrllt.py`" -c cli_pet -f gf_pet -p gp_pet -e ej_pet"

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Sistema arrancado."
Write-Host "Ejecute el cliente:  python src\cliente.py -c cli_pet"
Write-Host "Para apagar todo, en el cliente escriba: apagar"
