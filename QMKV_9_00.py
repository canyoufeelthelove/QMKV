import os
import subprocess
import sys
import traceback
from time import time
from rich.progress import Progress
from openpyxl import Workbook

def ruta_local(nombre):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, nombre)
    return nombre

FFMPEG = ruta_local("ffmpeg.exe")
FFPROBE = FFMPEG.replace("ffmpeg", "ffprobe")

EXTENSIONES_VALIDAS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a")
LOG_ERRORES = "verificacion_errores.txt"
REPORTE_EXCEL = "reporte_verificacion.xlsx"
ARCHIVO_PROGRESO = "progreso.txt"
FFMPEG_TIMEOUT = 5

errores_duracion = []
errores_verificacion = []
omitidos = []
procesados = []
resultados_validacion = []

def ejecutar_verificacion(comando, timeout=None):
    try:
        proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
        inicio = time()
        while True:
            if proceso.poll() is not None:
                break
            if timeout and (time() - inicio) > timeout:
                proceso.terminate()  # Primero intentar terminar de forma amable
                try:
                    proceso.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proceso.kill()
                raise TimeoutError("Tiempo de espera excedido")
            linea = proceso.stderr.readline()
            if linea:
                yield linea.strip()
        # Asegurarse de vaciar los buffers
        proceso.stdout.close()
        proceso.stderr.close()
        proceso.wait()
        if proceso.returncode != 0:
            raise subprocess.CalledProcessError(proceso.returncode, comando)
    except Exception as e:
        raise e

def obtener_duracion(archivo):
    comando = [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", archivo]
    try:
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return float(resultado.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"No se pudo obtener la duración de {archivo}: {e}")

def verificar_archivo(archivo, log):
    try:
        duracion = obtener_duracion(archivo)
        paso = 500
        if duracion < paso:
            paso = max(10, duracion / 5)
        tiempos = [1.0] + [t for t in range(int(paso), int(duracion), int(paso))] + [max(duracion - 1, 1)]

        verificado_por_saltos = True
        log.write(f"--- Verificando archivo: {archivo} ---\n")
        log.write(f"[INFO] Método usado: Saltos de {paso:.1f} segundos + chequeo inicial y final\n")

        for tiempo in tiempos:
            print(f">> Verificando {archivo} en t={tiempo:.1f}s")
            comando = [FFMPEG, "-ss", str(tiempo), "-i", archivo, "-t", "1", "-v", "error", "-f", "null", "-"]
            try:
                for _ in ejecutar_verificacion(comando, timeout=FFMPEG_TIMEOUT):
                    pass
            except Exception as e:
                print(f"[X] Error en {archivo} t={tiempo:.1f}s: {e}")
                log.write(f"[X] Error en salto t={tiempo:.1f}s: {e}\n")
                verificado_por_saltos = False
                break

        if verificado_por_saltos:
            log.write("[OK] Verificación por saltos completada con éxito.\n")
        else:
            log.write("[!] Iniciando verificación completa por error en saltos...\n")

        if verificado_por_saltos or verificar_completa_ffmpeg(archivo, log):
            estado = "VALIDADO"
            procesados.append(archivo)
            marcar_como_procesado(archivo)
        else:
            estado = "FALLÓ"
            omitidos.append(archivo)

        metodo = "Saltos+Inicio+Final" if verificado_por_saltos else "Completa"
        resultados_validacion.append((archivo, estado, metodo))
        log.write(f"[>>>] Resultado final: {estado}\n")

    except Exception as e:
        errores_duracion.append((archivo, str(e)))
        log.write(f"[!] Error general en {archivo}: {e}\n")

def verificar_completa_ffmpeg(archivo, log):
    comando = [FFMPEG, "-i", archivo, "-v", "error", "-f", "null", "-"]
    try:
        for _ in ejecutar_verificacion(comando, timeout=FFMPEG_TIMEOUT * 6):
            pass
        return True
    except Exception as e:
        log.write(f"[X] Error completo en {archivo}: {e}\n")
        errores_verificacion.append((archivo, str(e)))
        return False

def obtener_archivos():
    archivos = []
    for raiz, _, ficheros in os.walk("."):
        for f in ficheros:
            if f.lower().endswith(EXTENSIONES_VALIDAS):
                archivos.append(os.path.join(raiz, f))
    return archivos

def cargar_archivos_procesados():
    if not os.path.exists(ARCHIVO_PROGRESO):
        return set()
    with open(ARCHIVO_PROGRESO, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def marcar_como_procesado(archivo):
    with open(ARCHIVO_PROGRESO, "a", encoding="utf-8") as f:
        f.write(archivo + "\n")

def generar_excel(resultados):
    wb = Workbook()
    ws = wb.active
    ws.title = "Verificación"
    ws.append(["Archivo", "Estado", "Método"])
    for archivo, estado, metodo in resultados:
        ws.append([archivo, estado, metodo])
    wb.save(REPORTE_EXCEL)

def main():
    archivos = obtener_archivos()
    ya_verificados = cargar_archivos_procesados()
    archivos = [a for a in archivos if a not in ya_verificados]

    if not archivos:
        print("No hay archivos pendientes por verificar.")
        return

    print(f"🔍 Verificando {len(archivos)} archivo(s)...\n")

    with open(LOG_ERRORES, "a", encoding="utf-8-sig", errors="ignore") as log:
        with Progress(transient=True) as barra:
            tarea = barra.add_task("[cyan]Verificando...", total=len(archivos))
            for archivo in archivos:
                try:
                    verificar_archivo(archivo, log)
                except Exception as e:
                    log.write(f"[!] Error general en {archivo}: {e}\n")
                barra.advance(tarea)

        log.write("\n=== RESUMEN ===\n")
        log.write(f"Total verificados esta sesión: {len(resultados_validacion)}\n")

    generar_excel(resultados_validacion)

    print("\n📝 RESUMEN:")
    for archivo, estado, _ in resultados_validacion:
        print(f"{archivo}: {estado}")

    print(f"\n✅ Validados: {sum(1 for _, e, _ in resultados_validacion if e == 'VALIDADO')}")
    print(f"❌ Fallidos: {sum(1 for _, e, _ in resultados_validacion if e == 'FALLÓ')}")
    print(f"\n📁 Reporte Excel generado: {REPORTE_EXCEL}")
    print("📄 Log de errores: verificacion_errores.txt")
    print("📌 Progreso guardado en: progreso.txt")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
    input("\nPresiona ENTER para salir...")


# linea para compilacion [ pyinstaller --onefile --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." --icon=QMKV.ico QMKV_9_00.py ]
