# test_windows.ps1
# Prueba automatica completa del sistema en Windows.
# Ejecutar desde la raiz del proyecto:
#     powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1

$DIR_PROYECTO = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$DIR_SRC      = Join-Path $DIR_PROYECTO "src"
$DIR_ARALMAC  = Join-Path $DIR_PROYECTO "aralmac"

Write-Host "==== limpiando estado anterior ===="
Remove-Item -ErrorAction SilentlyContinue "$DIR_ARALMAC\ficheros\*" -Recurse
Remove-Item -ErrorAction SilentlyContinue "$DIR_ARALMAC\programas\*" -Recurse
New-Item -ItemType Directory -Force -Path "$DIR_ARALMAC\ficheros"  | Out-Null
New-Item -ItemType Directory -Force -Path "$DIR_ARALMAC\programas" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\tmp"                 | Out-Null
Set-Content "C:\tmp\entrada.txt" "hola mundo desde el lote"

Write-Host "==== arrancando servicios ===="
$pGF = Start-Process python -ArgumentList "`"$DIR_SRC\gesfich.py`"  -f gf_pet -x `"$DIR_ARALMAC\ficheros`"" -PassThru -WindowStyle Minimized
$pGP = Start-Process python -ArgumentList "`"$DIR_SRC\gesprog.py`"  -p gp_pet -x `"$DIR_ARALMAC\programas`"" -PassThru -WindowStyle Minimized
$pEJ = Start-Process python -ArgumentList "`"$DIR_SRC\ejecutor.py`" -e ej_pet -x `"$DIR_ARALMAC`"" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 2
$pCT = Start-Process python -ArgumentList "`"$DIR_SRC\ctrllt.py`" -c cli_pet -f gf_pet -p gp_pet -e ej_pet" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 2

Write-Host "==== enviando peticiones ===="
$env:PYTHONPATH = $DIR_SRC

$script = @"
import sys, time, protocolo, tuberia

def pedir(pet):
    t = tuberia.Tuberia('cli_pet', 'escritura')
    t.abrir()
    t.escribir_linea(protocolo.codificar(pet))
    t.cerrar()
    t = tuberia.Tuberia('cli_pet_resp', 'lectura')
    t.abrir()
    linea = t.leer_linea()
    t.cerrar()
    return protocolo.decodificar(linea)

print('>> Crear fichero entrada')
r1 = pedir({'servicio':'gesfich','operacion':'Crear'})
print(r1)
fid_in = r1['id-fichero']

print('>> Actualizar entrada con contenido')
print(pedir({'servicio':'gesfich','operacion':'Actualizar','id-fichero':fid_in,'ruta':r'C:\tmp\entrada.txt'}))

print('>> Crear fichero salida')
r2 = pedir({'servicio':'gesfich','operacion':'Crear'})
print(r2)
fid_out = r2['id-fichero']

print('>> Listar ficheros')
print(pedir({'servicio':'gesfich','operacion':'Leer'}))

print('>> Leer contenido entrada')
print(pedir({'servicio':'gesfich','operacion':'Leer','id-fichero':fid_in}))

print('>> Guardar programa more.com')
r3 = pedir({'servicio':'gesprog','operacion':'Guardar','ejecutable':r'C:\Windows\System32\more.com','args':[],'env':[]})
print(r3)
pid = r3['id-programa']

print('>> Listar programas')
print(pedir({'servicio':'gesprog','operacion':'Leer'}))

print('>> Leer programa por id')
print(pedir({'servicio':'gesprog','operacion':'Leer','id-programa':pid}))

print('>> Ejecutar more.com (stdin=entrada, stdout=salida)')
r4 = pedir({'servicio':'ejecutor','operacion':'Ejecutar','id-programa':pid,'stdin':fid_in,'stdout':fid_out})
print(r4)
eid = r4['id-ejecucion']

time.sleep(1)

print('>> Estado del proceso')
print(pedir({'servicio':'ejecutor','operacion':'Estado','id-ejecucion':eid}))

print('>> Listar todos los procesos')
print(pedir({'servicio':'ejecutor','operacion':'Estado'}))

print('>> Leer fichero salida (debe tener el contenido de entrada)')
print(pedir({'servicio':'gesfich','operacion':'Leer','id-fichero':fid_out}))

print('>> Borrar fichero entrada')
print(pedir({'servicio':'gesfich','operacion':'Borrar','id-fichero':fid_in}))

print('>> Borrar programa')
print(pedir({'servicio':'gesprog','operacion':'Borrar','id-programa':pid}))

print('>> Apagar el sistema')
print(pedir({'servicio':'ctrllt','operacion':'Terminar'}))
"@

python -c $script

Write-Host ""
Write-Host "==== prueba completada ===="

Start-Sleep -Seconds 1
Stop-Process -Id $pGF.Id -ErrorAction SilentlyContinue
Stop-Process -Id $pGP.Id -ErrorAction SilentlyContinue
Stop-Process -Id $pEJ.Id -ErrorAction SilentlyContinue
Stop-Process -Id $pCT.Id -ErrorAction SilentlyContinue