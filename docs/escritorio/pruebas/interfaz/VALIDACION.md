# Validación desde la interfaz

Los archivos y evidencias citados se encuentran en `escritorio/pruebas/interfaz`, desde la raíz del repositorio.

Se recorrió la aplicación en una ventana visible de navegador con los mismos controles HTML de la ventana de escritorio. Se pulsó el botón del ejemplo, se inició el análisis real, se abrió la propuesta y su evidencia, se aprobó y se creó el expediente desde el asistente.

La prueba detectó el cambio de FABRICANTE DE PRUEBA a ESENCIAS MOLES S.A. usando la ficha técnica del ejemplo y Gemini 2.5 Flash. Luego se utilizó Cambio manual para modificar un proveedor y aprobarlo.

Se reabrieron los archivos del expediente generado para comprobar el fabricante, la versión 3, los bloques DE/A de Excel, el PDF adjunto y las evidencias del registro.

Las capturas muestran los pasos del recorrido:

- 01-bienvenida.png
- 02-resultado-analisis.png
- 03-revision-evidencia.png
- 04-expediente-creado.png
- 05-ventana-adaptada.png
- 06-configuracion.png
- 07-validacion-carpeta.png

El recorrido también comprobó que el asistente solicita una carpeta cuando falta. La selección nativa de carpeta requiere que el usuario elija su destino en el selector del sistema. La aplicación verifica escritura al guardar la selección.

El caso cubre un fabricante de un expediente. La compilación y ejecución del instalador de Windows están pendientes de validación en Windows.
