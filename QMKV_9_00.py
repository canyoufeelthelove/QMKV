import os
import subprocess
import sys
import traceback
from time import time
from rich.progress import Progress
from openpyxl import Workbook

## realisa busqueda de archivo en subcarpetas
def ruta_local(nombre):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, nombre)
    return nombre

FFMPEG = ruta_local("ffmpeg.exe")
FFPROBE = FFMPEG.replace("ffmpeg", "ffprobe")

## extensiones que pueden ser verificadas por ffmpeg y ffprobe
EXTENSIONES_VALIDAS = (
    ".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv",
    ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"
)
## log de errores y reporte de verificacion se guardan en la misma carpeta que el script con espera de 5 segundos
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
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        inicio = time()
        while True:
            if proceso.poll() is not None:
                break
            if timeout and (time() - inicio) > timeout:
                proceso.kill()
                raise TimeoutError("Tiempo de espera excedido")
            linea = proceso.stderr.readline()
            if linea:
                yield linea.strip()
        proceso.wait()
        if proceso.returncode != 0:
            raise subprocess.CalledProcessError(proceso.returncode, comando)
    except Exception as e:
        raise e

def obtener_duracion(archivo):
    comando = [
        FFPROBE,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        archivo
    ]
    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        return float(resultado.stdout.strip())
    except ValueError:
        raise RuntimeError(f"No se pudo obtener la duración de {archivo}")

def verificar_archivo(archivo, log):
    try:
        duracion = obtener_duracion(archivo)
        paso = 500 # saltos de tiempo representados en segundos intervalos donde se verifica el archivo con mayor velociada para maquinas con poca capaciadd de procesamiento
        if duracion < paso:
            paso = max(10, duracion / 5)
## en el caso de que la duracion sea menor a 500 segundos se realisa la verificacion en proporcion a la duracion del video
        tiempos = [1.0]
        t_actual = paso
        while t_actual < duracion - 1:
            tiempos.append(t_actual)
            t_actual += paso
        tiempos.append(max(duracion - 1, 1))

        verificado_por_saltos = True
        log.write(f"--- Verificando archivo: {archivo} ---\n")
        log.write(f"[INFO] Método usado: Saltos de {paso:.1f} segundos + chequeo inicial y final\n")

        for tiempo in tiempos:
            print(f">> Verificando {archivo} en t={tiempo:.1f}s")
            comando = [
                FFMPEG, "-ss", str(tiempo), "-i", archivo,
                "-t", "1", "-v", "error", "-f", "null", "-"
            ]
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

        verificado_completo = True
        if not verificado_por_saltos:
            verificado_completo = verificar_completa_ffmpeg(archivo, log)
            if not verificado_completo:
                omitidos.append(archivo)
                log.write(f"[X] Falló verificación completa.\n")
            else:
                log.write(f"[OK] Verificación completa exitosa.\n")

        if verificado_por_saltos or verificado_completo:
            estado = "VALIDADO"
            procesados.append(archivo)
            marcar_como_procesado(archivo)
        else:
            estado = "FALLÓ"

        metodo = "Saltos+Inicio+Final" if verificado_por_saltos else "Completa"
        resultados_validacion.append((archivo, estado, metodo))
        log.write(f"[>>>] Resultado final: {estado}\n")

    except Exception as e:
        errores_duracion.append((archivo, str(e)))
        log.write(f"[!] Error al obtener duración de {archivo}: {e}\n")
        verificar_sin_duracion(archivo, log)

        if not verificar_completa_ffmpeg(archivo, log):
            omitidos.append(archivo)
            log.write(f"[X] Falla total en archivo sin duración\n")
            resultados_validacion.append((archivo, "FALLÓ", "Sin duración"))
        else:
            procesados.append(archivo)
            marcar_como_procesado(archivo)
            resultados_validacion.append((archivo, "VALIDADO", "Completa"))
## los archivos que no se pueden verificar se marcan como omitidos y se guardan en la lista de errores
def verificar_sin_duracion(archivo, log):
    saltos = 5 # en el caso de que falle el timepo de espera
    segundos_por_salto = 60
    for i in range(saltos):
        tiempo = i * segundos_por_salto
        comando = [
            FFMPEG, "-ss", str(tiempo), "-i", archivo,
            "-t", "1", "-v", "error", "-f", "null", "-"
        ]
        try:
            for _ in ejecutar_verificacion(comando, timeout=FFMPEG_TIMEOUT):
                pass
        except Exception as e:
            log.write(f"[X] Error (sin duración) en {archivo} t={tiempo}s: {e}\n")

def verificar_completa_ffmpeg(archivo, log):
    comando = [
        FFMPEG, "-i", archivo,
        "-v", "error",
        "-f", "null", "-"
    ]
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
