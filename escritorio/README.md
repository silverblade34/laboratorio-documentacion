# Especificaciones de materias primas

[Contexto y requisitos detallados del proyecto](../CONTEXTO_Y_REQUERIMIENTOS.md) — referencia general de alcance, reglas de negocio, estado y pendientes.

Aplicación de escritorio para revisar cambios en especificaciones técnicas y preparar la solicitud AS-REG-018.

## Interfaz de escritorio

La entrada principal es `desktop.py`. Abre una ventana con interfaz HTML y CSS mediante pywebview. El procesamiento y la carpeta de expedientes se gestionan localmente. Las consultas a IA requieren conexión. En Windows la ventana usa Microsoft Edge WebView2, que debe estar instalado.

La pantalla de bienvenida incluye **Probar con un ejemplo preparado**. Los archivos y las instrucciones están en `ejemplo/COMO_PROBAR.md`. Las capturas de la prueba desde la interfaz están en `pruebas/interfaz`.

## Probar en macOS

Abre `Abrir-en-Mac.command` desde Finder o ejecuta `./Abrir-en-Mac.command` desde Terminal. El lanzador usa el entorno `.venv-mac` si está instalado. Si solo está disponible el runtime de Codex, abre la interfaz en el navegador local. En otro Mac requiere Python con Tkinter y prepara un entorno virtual para instalar las dependencias.

En macOS, guarda los Word heredados `.doc` como `.docx` antes de cargarlos.

## Configuración técnica

El administrador configura una vez la variable `GEMINI_API_KEY` o un archivo `.gemini-key` con la clave en `%LOCALAPPDATA%\MateriaPrima` en Windows. Para ejecutar desde el código fuente también se puede usar un archivo `.gemini-key` junto a `app.py`. El archivo local queda excluido del control de versiones y del instalador. Para repartir el tráfico, configura también `GEMINI_API_KEY_EXTRA` y `GROQ_API_KEY` o los archivos locales `.gemini-key-extra` y `.groq-key` en la misma carpeta de configuración. Para cambiar el modelo de Gemini usa la variable `MATERIA_PRIMA_GEMINI_MODEL`.

## Generar el instalador en Windows

Con Python 3.12 de 64 bits e Inno Setup 6 instalados en Windows, abre PowerShell en esta carpeta y ejecuta:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build-windows.ps1
```

El resultado se guarda en `dist\MateriaPrima-Setup.exe`. El instalador incluye el runtime de la aplicación y crea un acceso en el menú Inicio. Microsoft Word instalado permite abrir los archivos heredados `.doc`. Los `.docx` y `.xlsx` se procesan directamente.

Para ejecutar desde código fuente en un equipo con Python y Tk:

```sh
python -m pip install -r requirements.txt
python desktop.py
```

## Flujo de trabajo

1. Selecciona el Word **vigente** y los PDF de respaldo. Todas las secciones se analizan por defecto. Abre **Elegir secciones** si quieres limitar el alcance.
2. Pulsa **Analizar documentos**. La aplicación procesa hasta tres PDF a la vez. Gemini recibe el PDF completo y sus credenciales se alternan. Groq puede recibir texto extraído localmente de los PDF digitales, separado por página. Los escaneados y los documentos sin texto suficiente se envían a Gemini. Si una ruta falla, se intenta otra compatible cuando está disponible. **Reintentar PDF pendientes** conserva las propuestas ya recibidas.
3. Compara **Antes** y **Después**. Abre cada propuesta para revisar la página y la evidencia. Puedes editarla, aprobarla o descartarla. Desmarca **Solo mostrar propuestas** para hacer cambios manuales.
4. Pulsa **Exportar Word y solicitud**. Completa solicitante y área, y confirma la fecha. La aplicación crea el Word y el Excel en una carpeta con el código SAP y la nueva versión. El Word agrega una entrada en **Revisión Histórica**. El Excel se genera con la plantilla **AS-REG-018** incluida, usando la versión anterior como vigente y los cambios aprobados en **DE/A**.
5. El catálogo SQLite local se alimenta con los proveedores y fabricantes de la especificación exportada. Se puede consultar desde **Catálogo local**. En Windows se guarda en `%LOCALAPPDATA%\MateriaPrima\catalogo.sqlite3`.

## Casos observados en los ejemplos

- **Pure Seduction** reúne cambios en Identificación, parámetros de A y la tabla de alérgenos de C. La ficha técnica da el rango de densidad relativa y el índice de refracción. El certificado de alérgenos da su propia fecha de revisión.
- **Glicerina, trietanolamina y otros materiales con varios fabricantes** requieren distinguir el fabricante del proveedor y mantener la relación entre ambos. Un COA puede identificar una entidad o reportar un resultado de lote. Los rangos de aceptación requieren respaldo explícito.
- **Disodium EDTA y solicitudes de Corporación Life** usan distribuciones distintas de DE/A. La aplicación localiza esos rótulos dentro del bloque de cambio propuesto.
- La versión del formato y la versión de la materia prima son campos diferentes. La aplicación toma la versión de la cabecera de la materia prima, incluso si el nombre del archivo indica otra.
- El listado de técnicas es material de referencia. La aplicación conserva los códigos vigentes salvo cambios aprobados en sus campos y el análisis pide a Gemini que se abstenga de inventar códigos internos.

La aprobación en la aplicación selecciona el contenido que se exporta. Los gráficos y firmas preexistentes del Word se conservan como parte de la plantilla y el flujo formal de Calidad se gestiona en la empresa. La salida se ajusta al formato de los ejemplos. Una plantilla distinta puede requerir adaptar los rótulos que identifican sus campos.

[Procesamiento de PDF con la API de Gemini](https://ai.google.dev/gemini-api/docs/generate-content/document-processing)


## Carpeta de expedientes y correcciones manuales

En **Carpeta y plantilla** elige una carpeta de salida y, si necesitas otro formato, una plantilla AS-REG-018 compatible. La aplicación recuerda la selección. En esa misma ventana puedes configurar manualmente las credenciales si falla el servicio.

**Editar manualmente** muestra todos los campos del alcance seleccionado. Busca el campo, ábrelo, escribe el valor correcto y apruébalo. Al exportar se solicitan solicitante y área si faltan. La exportación crea una subcarpeta con el código SAP y la versión. Incluye el Word, el Excel, los PDF de respaldo y un registro JSON con los cambios y las evidencias propuestas. Las exportaciones repetidas reciben un sufijo para conservar cada expediente.

Para abrir rápidamente desde Terminal:

```sh
cd "/Users/michellmarcospachecotacay/Documents/portafolio/laboratorio/escritorio" && ./Abrir-en-Mac.command
```

## Vista previa y revisión histórica

Pulsa **Previsualizar Word** para ver las páginas del documento convertido localmente a PDF, con los cambios aprobados resaltados. Incluye logos, cabeceras y tablas. Puede haber diferencias de paginación entre LibreOffice y Microsoft Word por fuentes o comportamiento del motor. La opción Vista de contenido permite una lectura simplificada. El Word exportado conserva el paquete original y se entrega sin resaltados de revisión.

En esa ventana puedes editar la redacción histórica, regenerarla con las aprobaciones actuales y elegir si se agrega una fila al historial. La versión aumenta en ambos casos. Si cambias las aprobaciones, se regenera el resumen para evitar que describa cambios anteriores. La fecha final se confirma al exportar.

El catálogo `tecnicas.json` proviene de los 64 PDF de `../tecnicas-detalle`. Para páginas escaneadas se extrajeron por OCR las primeras tres páginas, donde figuran objetivos y comienzo del procedimiento. Los resultados pueden contener errores OCR: consulta los documentos originales para condiciones o alcances específicos. En Configuración puedes consultar el texto usado en el análisis. Para actualizar las técnicas debe regenerarse el catálogo; no se sincroniza automáticamente con la carpeta.

El análisis recibe estos alcances para ubicar en A los parámetros analizables internamente y en B los demás, bajo su fabricante. Las nuevas filas de A requieren una técnica reconocida y una coincidencia conservadora de parámetro; esta comprobación no sustituye la revisión técnica del laboratorio. Los campos de B identifican su fabricante. La incorporación comercial admite líneas `Fabricante: nombre`, `Proveedor: nombre` y `Parámetro adicional: Nombre | Rango | Referencia`.

El caso `../PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR` queda pendiente de ejecución manual y usa únicamente PDF originales.

## Referencias entre A y B y páginas reales

Los índices de los rangos de A identifican a los fabricantes numerados en B. Se reconocen tanto números escritos como numeración automática de Word. Cada rango indexado se revisa por separado; modificar el fabricante (1) conserva el rango del (2). La incorporación de un fabricante añade un bloque numerado en una columna independiente. Los rangos nuevos usan `Fabricante: nombre completo | rango`; al exportar se resuelve el índice según el bloque aprobado y se comprueba que no existan referencias huérfanas.

La vista predeterminada ahora muestra las páginas del Word convertido localmente a PDF, incluyendo tablas, cabeceras, logos y paginación del renderizador. En Windows requiere LibreOffice o Microsoft Word instalado; en macOS usa LibreOffice, detectado automáticamente o indicado en Configuración. La disposición puede variar respecto a otro motor de Word por fuentes o diferencias de renderizado. La vista de contenido se conserva como alternativa explícita. Los resaltados se aplican solo a la copia de previsualización.

El icono de conexión comprueba acceso HTTPS a Internet periódicamente y permite una comprobación manual. No mide intensidad Wi-Fi ni garantiza que la clave, cuota o modelo de IA estén disponibles.

La entrada actual del caso 05 conserva COREL PHARMA CHEM como fabricante (1) y NEODETER como proveedor. Los PDF permiten demostrar la incorporación de Tinci sin reemplazar al fabricante existente. La entrada anterior sin fabricantes queda archivada y marcada NO_USAR.

## Elegir entre propuestas

La tabla agrupa las fuentes con valores equivalentes e incluye un botón para elegir el valor. Para atributos sensoriales simples se reconoce el mismo conjunto de palabras aunque cambie su orden; se conservan los calificativos adicionales como alternativas. No se agrupan por este criterio valores numéricos, unidades distintas o descripciones con negación. Los nombres de fabricantes se comparan sin diferencias de mayúsculas y puntuación; razones sociales distintas se mantienen separadas. Dentro de un fabricante pueden compararse los bloques comerciales de cada documento. Elegir una opción carga su texto original en el editor; únicamente se aplica después de aprobarlo y todos sus respaldos siguen disponibles.
