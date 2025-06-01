# Script de Verificación de Archivos Multimedia con FFMPEG

Este script realiza una verificación exhaustiva de archivos multimedia (video y audio) usando ffmpeg y ffprobe para validar la integridad de los archivos. Utiliza un método basado en saltos temporales en el archivo y, si falla, realiza una verificación completa del archivo.

-------------------------------------------------------------------------------------------------------------

# Descripción general
El script recorre de forma recursiva el directorio actual buscando archivos con extensiones válidas multimedia (video y audio). Para cada archivo pendiente de verificación (no marcado previamente como procesado):

Obtiene la duración del archivo.

Realiza verificaciones puntuales en saltos definidos a lo largo del tiempo (incluyendo el inicio y el final del archivo) para chequear la integridad.

Si la verificación por saltos falla, realiza una verificación completa del archivo.

Registra los resultados en un archivo Excel y un log de errores.

Guarda el progreso para evitar re-verificar archivos en ejecuciones futuras.

Muestra una barra de progreso visual durante la ejecución.

-------------------------------------------------------------------------------------------------------------

# Características principales
Verificación escalonada: primero verifica fragmentos puntuales, luego el archivo completo solo si es necesario.

Timeout para procesos ffmpeg: evita cuelgues o bloqueos por archivos corruptos.

Registro de errores y reporte en Excel: facilita análisis posteriores.

Continuidad de procesamiento: evita reprocesar archivos ya verificados usando un archivo de progreso.

Soporte para múltiples formatos: .mkv, .mp4, .avi, .mov, .webm, .flv, .mp3, .wav, .aac, .flac, .ogg, .m4a.

-------------------------------------------------------------------------------------------------------------

# Dependencias
Python 3.6+

rich (para barra de progreso)

openpyxl (para exportar reporte Excel)

ffmpeg y ffprobe (deben estar en la misma carpeta que el script o en el path)

-------------------------------------------------------------------------------------------------------------

# Estructura y funciones principales
# Variables globales
FFMPEG, FFPROBE: Rutas de los ejecutables ffmpeg y ffprobe.

EXTENSIONES_VALIDAS: Tupla con extensiones válidas a verificar.

LOG_ERRORES, REPORTE_EXCEL, ARCHIVO_PROGRESO: Archivos para logs, reporte Excel y guardado de progreso.

Listas para almacenar errores, omitidos, procesados y resultados.

-------------------------------------------------------------------------------------------------------------

# Funciones
ruta_local(nombre)
Devuelve la ruta absoluta del ejecutable para compatibilidad con PyInstaller.

ejecutar_verificacion(comando, timeout=None)
Ejecuta un comando en subprocess con timeout, leyendo salida en tiempo real para detectar errores y terminar si excede tiempo.

obtener_duracion(archivo)
Usa ffprobe para obtener la duración del archivo multimedia en segundos.

verificar_archivo(archivo, log)
Realiza la verificación por saltos en diferentes tiempos del archivo. Si falla, ejecuta la verificación completa.

verificar_completa_ffmpeg(archivo, log)
Ejecuta ffmpeg para verificar todo el archivo completo y detectar errores.

obtener_archivos()
Recorre directorios buscando archivos con extensiones válidas.

cargar_archivos_procesados()
Lee el archivo de progreso para saber qué archivos ya fueron verificados.

marcar_como_procesado(archivo)
Agrega un archivo a la lista de archivos procesados para evitar volver a procesarlo.

generar_excel(resultados)
Crea un archivo Excel con los resultados de la verificación.

main()
Función principal que coordina la verificación de todos los archivos pendientes, mostrando barra de progreso, registrando logs, y generando reportes.

-------------------------------------------------------------------------------------------------------------

# Uso
Coloca ffmpeg.exe y ffprobe.exe en el mismo directorio del script o en el PATH.

Ejecuta el script en la raíz de la carpeta donde quieres verificar archivos.

El script verificará todos los archivos multimedia no procesados y mostrará progreso en consola.

Al finalizar, se genera un archivo reporte_verificacion.xlsx con el resultado y un log de errores verificacion_errores.txt.

El archivo progreso.txt almacena los archivos ya verificados para no repetirlos en próximas ejecuciones.

Ejemplo de ejecución
bash
Copiar
Editar
python verificar_multimedia.py
Salida esperada:

yaml
Copiar
Editar
🔍 Verificando 10 archivo(s)...

>> Verificando ./videos/video1.mkv en t=1.0s
>> Verificando ./videos/video1.mkv en t=500.0s
...
📝 RESUMEN:
./videos/video1.mkv: VALIDADO
./audios/audio1.mp3: FALLÓ

✅ Validados: 9
❌ Fallidos: 1

📁 Reporte Excel generado: reporte_verificacion.xlsx
📄 Log de errores: verificacion_errores.txt
📌 Progreso guardado en: progreso.txt

-------------------------------------------------------------------------------------------------------------

# Consideraciones
El timeout para cada verificación por salto es 5 segundos (configurable).

Para archivos muy cortos, el salto entre puntos se ajusta automáticamente.

La verificación completa es más lenta pero más exhaustiva, se usa solo si falla la verificación por saltos.

Los archivos marcados en progreso.txt no se revisan nuevamente, elimina este archivo o su contenido para reiniciar todo.