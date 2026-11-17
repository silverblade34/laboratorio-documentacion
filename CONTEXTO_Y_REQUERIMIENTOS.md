# Materia — Contexto y requisitos del proyecto

**Actualizado:** 16 de noviembre de 2026, America/Lima.  
**Versión declarada en el código:** 1.3.0.  
**Propósito:** servir como referencia para continuar el desarrollo, revisar el alcance y entregar contexto a otra persona sin depender del historial del chat.

Este documento reúne lo solicitado por el usuario, las reglas de negocio aclaradas durante el desarrollo, la implementación que existe y sus límites. Un requisito descrito aquí no significa, por sí solo, que esté completamente implementado o validado. Las diferencias se indican expresamente.

## 1. Objetivo y usuarios

Automatizar la revisión de especificaciones técnicas de materias primas de una empresa, comparando un Word vigente con documentación técnica nueva en PDF. La aplicación debe proponer cambios con evidencia, permitir la revisión del laboratorista o químico y generar un expediente con el Word actualizado, la solicitud de cambio en Excel y los documentos de respaldo.

Los usuarios operativos son laboratoristas y químicos. Necesitan una experiencia rápida, profesional e intuitiva, con lenguaje de su trabajo. La configuración de claves, modelos y proveedores de IA corresponde a la administración técnica y debe mantenerse fuera del flujo habitual.

La IA propone contenido. El usuario decide qué se incorpora a los documentos de salida. La aprobación dentro de la aplicación no sustituye las firmas ni el procedimiento formal de Aseguramiento de la Calidad.

## 2. Plataforma y evolución del alcance

1. Se solicitó inicialmente un programa instalable en Windows y se pidió poder probarlo en un MacBook.
2. En una conversación comercial se comunicó una posible migración a web, con despliegue y consultas sobre hosting y base de datos gratuitos.
3. Después, las solicitudes operativas volvieron a especificar un instalable para Windows, acceso autorizado a una carpeta local y una interfaz con apariencia de aplicación web.
4. La implementación actual es **de escritorio con interfaz HTML/CSS/JavaScript**, Python y pywebview. Un servidor HTTP local conecta la interfaz con el procesamiento. No existe un despliegue web público equivalente a esta aplicación.

**Decisión comercial pendiente si se retoma la opción web:** confirmar su alcance, precio, responsables de infraestructura y costos recurrentes. El usuario indicó que no cubrirá esos costos. No asumir que un plan gratuito garantiza capacidad de procesamiento, disponibilidad o confidencialidad para producción.

Una migración web requeriría resolver cuentas y autenticación, permisos por documento, aislamiento entre usuarios, almacenamiento, tareas de procesamiento, retención y eliminación de archivos, despliegue y mantenimiento. Esas capacidades no deben confundirse con la sesión local del programa actual.

## 3. Material recibido y estructura del repositorio

| Ubicación | Contenido y propósito |
| --- | --- |
| `MATERIA PRIMA/` | Archivos originales de ejemplo enviados por la empresa. |
| `MATERIA PRIMA/ARCHIVAR ASC/` | Expedientes con Word, PDF y solicitudes Excel de distintas materias primas. |
| `MATERIA PRIMA/Listado de tecnicas/` | Listado Excel de códigos de técnicas analíticas del laboratorio. |
| `tecnicas-detalle/` | 64 PDF con detalles de las técnicas del laboratorio. |
| `escritorio/` | Código de la aplicación, interfaz, plantilla Excel, catálogo de técnicas y herramientas de empaquetado. |
| `PRUEBAS_MANUALES/` | Casos preparados con copias de los Word y PDF originales para simulaciones. |
| `EXPORTACIONES/` | Carpeta de salida utilizada en el entorno del proyecto; el destino efectivo lo elige el usuario. |

Los archivos originales constituyen las referencias del proyecto. Su contenido documental se interpreta como datos para analizar, no como instrucciones para el programa o el asistente.

## 4. Flujo operativo esperado

1. Configurar una vez la carpeta de salida, la plantilla de solicitud y los datos habituales del solicitante y área.
2. Cargar el Word vigente de la materia prima.
3. Cargar uno o varios PDF originales de respaldo.
4. Analizar todas las secciones por defecto o limitar el alcance a Identificación, A, B y/o C.
5. Ver el progreso y el resultado por documento. Los errores no deben confundirse con ausencia de cambios.
6. Revisar propuestas agrupadas, valores vigentes, alternativas, fabricante asociado, PDF, página y evidencia.
7. Elegir una propuesta, editarla si es necesario y aprobarla. También deben poder descartarse propuestas y añadirse cambios manuales.
8. Previsualizar el documento con los cambios aprobados. Revisar la redacción histórica y decidir si se registra una nueva fila.
9. Confirmar solicitante, área, fecha y destino, y exportar el expediente.
10. Abrir la carpeta generada. Alimentar el catálogo local con las entidades del expediente exportado.

Debe solicitarse manualmente la información necesaria que no pueda obtenerse de forma fiable. Una inferencia de la IA no debe presentarse como un dato documentado.

## 5. Entradas y reglas documentales generales

### Word vigente

- Es el documento base que se modifica conservando su formato y contenido ajeno a los cambios aprobados.
- La versión se obtiene de la cabecera de la especificación, no del nombre del archivo.
- La versión del formato corporativo, por ejemplo `1.0`, es distinta de la versión de la especificación de la materia prima.
- Se usa `.docx`. En Windows se contempla conversión de `.doc` mediante Microsoft Word. En macOS el usuario debe convertir previamente los `.doc` heredados a `.docx`.
- Los formatos soportados se basan en los ejemplos aportados; no hay un editor universal de cualquier plantilla Word.

### PDF de respaldo

Pueden ser fichas técnicas, COA/certificados de análisis, hojas de seguridad SDS/FDS, certificados de alérgenos u otros documentos técnicos. No siguen un formato único y pueden contener páginas escaneadas, tablas, idiomas diferentes o varios productos dentro del mismo archivo.

La página citada es la **página física del PDF**, empezando en 1. No se debe confundir con la numeración impresa del documento.

### Excel de solicitud

La aplicación debe incluir una plantilla reutilizable de **AS-REG-018**, sin exigir cargarla en cada expediente. Se permite sustituirla y recordar la selección.

Solo deben rellenarse los datos disponibles del bloque superior y del cambio propuesto: solicitante, área, fecha, identificación del documento, código SAP, versión vigente y textos **DE/A**. El resto del formulario debe conservarse. Campos asignados por Calidad, aprobaciones y justificaciones sin información suficiente no deben inventarse.

## 6. Reglas de negocio por sección

### 6.1 Identificación

Incluye INCI, CAS y otros identificadores presentes en la plantilla.

- Comparar identidad química y materia prima genérica antes de usar evidencia.
- Una marca, fabricante o grado comercial nuevo no demuestra por sí mismo que sea otra materia prima; puede ser precisamente el motivo de la incorporación.
- Las diferencias de grado, composición o condiciones requieren revisión y no acreditan equivalencia técnica automática.
- Un CAS diferente debe revisarse como posible corrección; no debe causar automáticamente el descarte de todo el PDF.
- El dígito de control del CAS se puede comprobar mediante cálculo determinista. Esa comprobación no acredita por sí sola la identidad química del material.
- **Los nombres nunca se traducen ni se adaptan** (INCI, CAS, nombres químicos y comerciales, grados, marcas, razones sociales, códigos). `CARBOMER` no se convierte en `CARBOMERO`. Un nombre comercial o grado (`TC-CARBOMER 340`, `Carbomer 940`) no es un INCI. El programa descarta, con una observación, la propuesta de un nombre que no aparece literalmente en la cita o que solo difiere del vigente en mayúsculas o traducción, y conserva el prefijo `: ` del Word.

### 6.2 Sección A — Especificación técnica

**A contiene los parámetros que el laboratorio tiene capacidad de analizar mediante sus técnicas internas.**

- La capacidad se determina consultando el alcance y procedimiento de las técnicas, no únicamente su título ni la ubicación de una fila en un documento anterior.
- Una técnica puede cubrir varios parámetros. Por ejemplo, `CC-FQ-TEC-131`, Evaluación Sensorial, contempla atributos como apariencia/aspecto, color, olor y textura según su alcance.
- Deben conservarse los nombres internos y códigos de técnica. No renombrar automáticamente un parámetro interno por un sinónimo utilizado por el fabricante.
- Condiciones, unidades, concentraciones y temperaturas son parte del dato técnico. No sustituir un valor obtenido bajo otras condiciones como si fuera equivalente.
- Los parámetros sin una técnica interna aplicable pertenecen a B, debajo de su fabricante.

#### Referencias de fabricante en la columna Rango

Los números `(1)`, `(2)`, etc. identifican al fabricante numerado en B. No son notas al pie, prioridades ni números de proveedor.

Ejemplo:

```text
A — Aspecto
(1) Polvo esponjoso
(2) Polvo blanco, esponjoso

B
1) Fabricante: COREL PHARMA CHEM
2) Fabricante: Guangzhou Tinci Materials Technology Co., Ltd
```

Reglas obligatorias:

1. Actualizar el rango de un fabricante conserva los de los demás.
2. Incorporar un fabricante no reemplaza automáticamente al existente.
3. La nueva referencia se resuelve usando el fabricante aprobado en B.
4. No exportar referencias a fabricantes inexistentes ni números de fabricante duplicados.
5. Reconocer tanto los índices escritos como texto como la numeración automática de Word.
6. Los valores sin índice se tratan actualmente como comunes a los fabricantes. Al introducir una variante por fabricante, se preserva el valor previo para los demás.
8. **Primero los fabricantes:** tras el análisis, un aviso lista los fabricantes nuevos detectados y pide aprobarlos antes que los rangos; el orden de aprobación fija su número en B. Un rango por fabricante solo se aprueba si ese fabricante ya existe o fue aprobado en B.
9. El editor de rango muestra una línea editable por fabricante (`(2)`, `(3)`…), que pueden incluirse a la vez; solo se elige entre redacciones de un mismo fabricante. El valor nunca contiene el nombre del fabricante: si la IA lo pone, la propuesta se descarta.
7. La revisión muestra la celda RANGO completa vigente (`(1) …`) y cómo quedará con la propuesta (`(1) …` / `(2) …`). El número del fabricante nuevo se resuelve en cuanto se aprueba su bloque en B; antes se muestra `(nuevo)`.

La capacidad de editar rangos de fabricantes existentes y agregar el de un fabricante nuevo está implementada. **Límite actual:** cada campo virtual de incorporación admite un valor `Fabricante: nombre | rango` por aprobación. Incorporar varios rangos nuevos para diferentes fabricantes en una misma fila y una misma revisión requiere ampliar esa colección o realizar revisiones separadas; no debe prometerse como una operación múltiple resuelta.

### 6.3 Sección B — Información técnico-comercial

Una materia prima vigente debe conservar al menos un fabricante. El escenario normal es agregar fabricantes o proveedores, o actualizar datos de los existentes.

Cada bloque debe mantener asociados:

- Número de fabricante en una columna independiente.
- Fabricante.
- Proveedor, si se conoce y está respaldado.
- Nombre comercial.
- Vida útil.
- Almacenamiento.
- Otros datos comerciales documentados.
- Parámetros adicionales sin técnica interna aplicable, debajo del fabricante correspondiente.

El usuario confirmó expresamente que la nueva columna es el **número de fabricante**, aunque en un mensaje la llamó número de proveedor.

No confundir fabricante, proveedor, distribuidor, cliente, autor del PDF o nombre del archivo. Un fabricante acreditado puede proponerse aunque falte proveedor; el dato faltante debe solicitarse sin inventarlo.

Un rótulo explícito `Manufacture/Supplier` permite proponer a la entidad en ambos roles declarados, pero no demuestra quién es un intermediario comercial local diferente.

Los datos comerciales de un fabricante nuevo deben salir de su propio documento. Se descartan, con observación, las líneas de vida útil o almacenamiento que repiten datos de un fabricante vigente del Word o que la cita no respalda; una fecha de vencimiento de lote no es una vida útil. Las etiquetas pegadas por la IA (`…LTD.Proveedor:`) se separan antes de agrupar, para no crear un fabricante inexistente.

Las mayúsculas y la puntuación no convierten una misma razón social en dos fabricantes. En cambio, **Guangzhou Tinci y Jiujiang Tinci se mantienen separados** hasta que exista una resolución documentada de su relación. Compartir la palabra Tinci no autoriza a fusionarlos.

El programa asigna números nuevos después de los existentes, conservando su asociación con A. El orden de aprobación/incorporación puede determinar la numeración de los bloques nuevos.

### 6.4 Sección C — Observaciones

Debe poder actualizar observaciones y tablas, por ejemplo alérgenos, nombres, concentraciones y revisiones de certificados. Se deben preservar el contexto y la fecha del documento que respalda cada cambio.

No mezclar observaciones documentales con datos técnicos confirmados. Una ambigüedad puede requerir una observación y resolución humana, sin convertirse automáticamente en una modificación del Word.

### 6.5 Sección D — Revisión histórica

- Mostrar una propuesta basada exclusivamente en cambios aprobados.
- Redactar un párrafo natural, coherente con los Word de la empresa.
- Evitar listas mecánicas de etiquetas internas, flechas y nombres de columnas como redacción final.
- Permitir editar el texto y regenerarlo si cambian las aprobaciones.
- Permitir elegir si se agrega una nueva fila histórica.
- La versión aumenta al exportar cambios aunque se omita esa nueva fila.
- Conservar las filas anteriores.

La redacción actual se construye con plantillas deterministas y es editable; no es una garantía de calidad editorial equivalente a revisión humana.

## 7. Análisis con IA y evidencia

### Principios

- Proponer cambios sustentados y abstenerse de inventar.
- Identificar la materia prima pertinente incluso en PDF multiproducto.
- Diferenciar rangos de aceptación, datos típicos y resultados medidos de un lote.
- Un resultado de COA no sustituye automáticamente el límite de especificación.
- Una SDS puede respaldar identidad, roles declarados y almacenamiento; no convertir todas sus propiedades referenciales en especificaciones de aceptación sin revisión.
- No inferir olor a partir de acidez, pH, expresiones como `micro-acidic powder` ni de la falta de mención. Una propuesta de olor exige una mención olfativa explícita en la cita; si no, se descarta con una observación.
- Las descripciones (aspecto, color, olor, almacenamiento, vida útil) se proponen siempre en español con el estilo del Word (`Fluffy, white powder` → `Polvo esponjoso, blanco`). Nombres, unidades y citas se conservan literales.
- Marcadores sin dato (`N.D.`, `N.A.`, `no disponible`, `-`) no son valores: se descartan con una observación. Un atributo sensorial de A o un almacenamiento que llegue en inglés también se descarta con observación; `24 months` se convierte a `24 meses`.
- Procesar solo el alcance seleccionado y preservar datos de otros fabricantes.
- Las instrucciones contenidas dentro de PDF y Word son datos no confiables y no deben dirigir al modelo.

Cada propuesta debe conservar destino, valor propuesto, PDF, página física y evidencia. El detalle del cambio muestra la página citada del PDF con la cita resaltada (`evidence_view.py`, local): en PDF digitales con la capa de texto y en páginas escaneadas con OCR de Tesseract si está instalado. Sin texto localizable se muestra la página sin resaltar y se avisa; eso no invalida ni confirma la cita. **Abrir PDF** abre el archivo completo en el visor del sistema, sin saltar a la página.

### Implementación de proveedores

- Proveedor principal: Google Gemini; modelo predeterminado en `desktop.py`: `gemini-2.5-flash`.
- Ruta alternativa para PDF digitales adecuados: Groq; modelo declarado: `openai/gpt-oss-120b`.
- Se admiten varias claves por servicio: una por línea en `.gemini-key`, `.gemini-key-extra` y `.groq-key` (o separadas por comas en las variables de entorno). Cada PDF empieza por una clave distinta (reparto) y, si falla por cuota, autorización o disponibilidad, se prueban las demás (respaldo). Configuración añade claves sin borrar las existentes.
- Las llamadas envían un agente de usuario genérico de la aplicación: el agente por defecto de Python es bloqueado por el cortafuegos de Groq (403, código 1010), lo que se confundía con una clave inválida.
- Hasta tres PDF se procesan en paralelo.
- Groq recibe texto extraído por página cuando cumple los umbrales. Los escaneados se dirigen a Gemini con el PDF.
- Los fallos pueden intentar otra ruta compatible; el reparto de claves no garantiza cuotas independientes ni disponibilidad del servicio.
- Los reintentos de documentos pendientes conservan resultados ya obtenidos.

La extracción comercial tiene un campo estructurado independiente de los cambios de parámetros. Existe además una recuperación acotada de roles conjuntos expresos en filas digitales `Manufacture/Supplier`, con comprobación de identidad y evidencia; no es un extractor universal de todos los formatos comerciales.

### Segunda revisión con IA

Al terminar el análisis de los PDF, las propuestas consolidadas (campo, valor vigente, dato, fabricante y cita literal) se envían en una sola consulta de texto, sin los PDF, a una segunda revisión. Para cada propuesta devuelve `ok`, `corregir` (solo redacción, idioma o formato) o `rechazar`, con motivo. Las correcciones vuelven a pasar los mismos filtros deterministas y conservan el valor original; los descartes y correcciones quedan en Observaciones. Si la verificación falla, las propuestas se muestran sin ella y se avisa. Añade una consulta por análisis y no sustituye la revisión del químico.

### Monitor técnico

Panel oculto para diagnóstico (`activity_log.py`): se abre con **Monitor técnico** en el pie de página o con Ctrl/⌘ + Shift + L. Muestra en tiempo real cada PDF, la ruta elegida (Gemini/Groq y número de clave), cada llamada HTTP con su código, duración y cuerpo de error del servicio, las respuestas crudas del modelo, las propuestas aceptadas, la segunda revisión y las trazas de excepciones. También se escribe en `registro_tecnico.log` (rotativo, 2 MB × 4) junto al catálogo. Las claves se ocultan antes de registrar; el registro puede contener fragmentos de los documentos analizados.

### Estabilidad

PDFium no admite llamadas simultáneas: todo renderizado (vista previa del Word y página citada) se serializa con un bloqueo único. Su ausencia provocó cierres `EXC_BAD_ACCESS` en `FPDF_LoadPage` el 16-11-2026.

### Precisión y probabilidad de error

Se pidió conocer la probabilidad de error. **No hay un porcentaje de precisión/error medido y validado para este proyecto.** No prometer una cifra a partir de demostraciones exitosas.

Para medirla se necesita un conjunto de casos con resultados esperados revisados por químicos y métricas separadas de omisiones, falsos cambios, identidad/rol incorrecto, unidades/condiciones, evidencia y conservación del formato. Las propuestas correctas en un caso no acreditan fiabilidad general.

## 8. Agrupación y selección de propuestas

El usuario pidió reducir falsos conflictos y poder elegir claramente cuál propuesta se incorpora.

Implementado en la interfaz:

1. Agrupar diferencias de mayúsculas y puntuación en nombres de fabricantes.
2. Para descripciones sensoriales simples, reconocer el mismo conjunto de palabras aunque cambie su orden: `Polvo blanco y esponjoso` y `Polvo esponjoso blanco`.
3. Conservar calificativos adicionales como alternativas, por ejemplo `ligeramente ácido`.
4. Mantener separadas las propuestas de fabricantes distintos.
5. Conservar todos los PDF y páginas del grupo.
6. Mostrar botones de elección y opciones seleccionables en el editor.
7. Cargar el texto original elegido, permitir editarlo y exigir aprobación.
8. Combinar dato por dato los bloques comerciales de **un mismo fabricante** procedentes de varios documentos (por ejemplo, la SDS aporta Proveedor y la TDS el nombre comercial). Solo se pide elegir cuando dos documentos dan valores distintos para el mismo dato. Cada fabricante se marca para incorporarlo; razones sociales distintas (Guangzhou/Jiujiang Tinci) nunca se fusionan.

Es una normalización determinista de presentación, no una comprobación semántica universal mediante IA. No debe fusionar automáticamente números, unidades o negaciones diferentes. La aprobación guarda el valor elegido; agrupar no implica aprobar.

## 9. Interfaz y experiencia de uso

- Apariencia profesional de aplicación web, dentro de una ventana de escritorio.
- Acceso rápido a cargar, analizar, revisar y exportar.
- Sin banner fotográfico grande en la parte superior del espacio operativo; fue retirado por petición del usuario.
- Plantilla Excel incluida y preferencias recordadas.
- Datos técnicos y credenciales bajo Configuración.
- Búsqueda, filtro de propuestas, estados y contador de aprobaciones.
- Evidencia visible por cambio y acceso a sus PDF.
- Edición manual de campos y recuperación ante fallos de IA.
- Indicador de carga al preparar la previsualización, errores comprensibles y reintento.
- Aviso si no se obtiene información comercial: ausencia de propuesta no confirma ausencia de fabricante/proveedor.
- Versión de la aplicación y detección de cambios en el código para advertir que una ventana requiere reinicio.
- Historial de análisis: lista los análisis anteriores (SAP, versión, Word, PDF, propuestas, aprobados, errores, exportado) para reabrirlos o eliminarlos.

### Conexión a Internet

Se muestra un icono de conexión con comprobación HTTPS periódica, comprobación manual y eventos de conexión/desconexión. Representa acceso a Internet verificado, **no intensidad de señal Wi-Fi**, ni validez de credenciales, cuota o disponibilidad del modelo de IA.

## 10. Previsualización real

La vista predeterminada convierte una copia del Word a PDF localmente y muestra sus páginas renderizadas, con logos, cabeceras, tablas y cambios aprobados resaltados. No se envía el Word al servicio de IA para renderizarlo.

- Windows: LibreOffice o Microsoft Word instalado.
- macOS: LibreOffice; se contempla detección del runtime de desarrollo en este entorno.
- Se puede configurar la ruta del ejecutable de LibreOffice.
- Hay una vista de contenido simplificada como alternativa explícita.
- Con cero aprobaciones debe verse el documento vigente; un historial vacío no debe dejar la vista en blanco.
- La copia de revisión recibe resaltados. El Word final se exporta limpio.
- La paginación puede variar entre motores y fuentes disponibles.
- La previsualización no es un editor Word completo; se edita desde los campos de revisión.

## 11. Exportación y almacenamiento

El usuario elige una carpeta y la aplicación comprueba que puede escribir en ella. La selección se recuerda; no se requiere un permiso de administrador general para cada expediente.

Estructura de salida actual:

```text
CARPETA_ELEGIDA/
└── CODIGO_SAP_VN/
    ├── ET_CODIGO_SAP_VN.docx
    ├── SC_CODIGO_SAP_VN.xlsx
    ├── PDF de respaldo/
    │   └── copias de los PDF cargados
    └── registro_de_cambios.json
```

- Evitar sobrescribir una exportación anterior; usar sufijos si el destino existe.
- Crear el expediente en una zona temporal y moverlo al destino al completarlo.
- Exportar solo cambios aprobados.
- Conservar los PDF originales en contenido, aunque la copia de salida tenga prefijo de orden en su nombre.
- Registrar versiones, fecha, solicitante, área, antes/después, evidencias propuestas y PDF pendientes.
- Actualizar el catálogo local con las entidades del expediente exportado.

La descarga de una carpeta como ZIP se discutió para la alternativa web. No debe darse por implementada en el flujo de escritorio, que crea una carpeta local.

## 12. Catálogo local y configuración

Se usa SQLite para fabricantes y proveedores, asociados al SAP. El catálogo sirve de contexto para reconocer entidades y crece con las exportaciones.

No es una base maestra empresarial sincronizada, ni demuestra que dos razones sociales sean equivalentes. La resolución de alias, fusiones societarias y relaciones comerciales complejas necesita confirmación o desarrollo adicional.

Ubicación habitual en Windows: `%LOCALAPPDATA%/MateriaPrima/`. En otras plataformas se utiliza una ubicación de datos del usuario. Las preferencias se guardan en JSON junto al catálogo.

Las claves se configuran mediante variables de entorno, archivos locales o la sección técnica. No deben incluirse en documentación, capturas, ejemplos, repositorio o instalador. Los archivos de claves locales no equivalen a un almacén cifrado de secretos ni a protección mediante Keychain/Credential Manager.

**Este documento deliberadamente no contiene claves ni sus valores.**

## 13. Casos de prueba y cambios de criterio

### Reglas para preparar pruebas

El usuario rechazó un banco numeroso de PDF sintéticos limpios, porque no representaba la documentación real.

La preparación correcta es:

- Usar los PDF originales de la empresa, sin reescribirlos ni simplificarlos.
- Modificar únicamente una copia del Word para introducir diferencias recuperables a partir de esos PDF.
- Crear pocos casos complejos con varios cambios por materia prima.
- Separar entrada, PDF originales, referencias de la empresa, instrucciones y salida manual.
- Documentar lo esperado y la fuente/página de cada diferencia.
- No presentar como prueba desde interfaz una llamada aislada al backend.
- No ejecutar un banco completo o gastar consultas adicionales sin que forme parte del trabajo autorizado. Posteriormente el usuario pidió expresamente validaciones reales del caso que fallaba.

### Carpetas actuales

| Caso | Enfoque |
| --- | --- |
| `01_PURE_SEDUCTION` | Propiedades físicas, datos comerciales y alérgenos. |
| `02_GLICERINA` | Identificación, atributos, condiciones y datos de varios fabricantes. |
| `03_CARBOMER` | Datos comerciales, propiedades, viscosidad, impurezas y metales. |
| `04_TRIETHANOLAMINA` | Identificación, parámetros y bloques comerciales de varios fabricantes. |
| `05_NUEVO_FABRICANTE_Y_PROVEEDOR` | Conservar COREL PHARMA CHEM (1) y NEODETER e incorporar Tinci con referencias propias. |

En el caso 05 se corrigió una preparación anterior que eliminaba todos los fabricantes, escenario que el usuario declaró irreal. Esa entrada quedó archivada como `NO_USAR`. La entrada vigente conserva al fabricante (1), su proveedor y rangos, y usa los mismos PDF originales para demostrar la incorporación de otro.

El COA utilizado en varios casos contiene cuatro productos: la página física 2 corresponde a Glicerina, la 3 a Carbomer y la 4 a Triethanolamina. La página 1 corresponde a soda cáustica. Seleccionar el producto y fabricante correctos es parte de la prueba.

### Qué se validó puntualmente durante el desarrollo

- Llamadas reales a Gemini para la SDS, ficha técnica y COA del caso de Carbomer, con reintentos cuando hubo errores.
- Carga y procesamiento desde la interfaz, visualización de propuestas comerciales y aprobación.
- Conservación del fabricante (1), incorporación del (2) y referencias de rangos.
- Exportación Word sin resaltados de revisión y renderizado de sus páginas.
- Historial opcional, edición de texto, vista sin aprobaciones, carga y recuperación de errores.
- Agrupación de propuestas y elección exacta desde interfaz, sin nuevas consultas a IA para esa lógica de presentación.
- Indicador de conexión y estados simulados de desconexión.

Estas verificaciones son puntuales. Parte de los scripts y capturas de validación se generaron en directorios temporales; no forman una batería de aceptación reproducible completa dentro del repositorio. No se ha acreditado aquí la compilación y validación del instalador en una máquina Windows.

## 14. Arquitectura y mapa del código

| Archivo | Responsabilidad |
| --- | --- |
| `escritorio/desktop.py` | Ventana, sesión de trabajo, servidor local, carga, coordinación de análisis, aprobación y exportación. |
| `escritorio/office.py` | Lectura/edición OOXML de Word y Excel, campos, referencias de fabricantes e historial. |
| `escritorio/analysis_service.py` | Proveedores IA, contexto, esquemas de respuesta, validación, extracción comercial y catálogo SQLite. |
| `escritorio/techniques.py` | Contexto de técnicas y comprobaciones conservadoras de códigos/parámetros. |
| `escritorio/tecnicas.json` | Texto extraído de las técnicas y trazabilidad de los PDF originales. |
| `escritorio/preview.py` | Conversión local Word/PDF y renderizado de páginas. |
| `escritorio/evidence_view.py` | Página citada del PDF con la evidencia resaltada (texto o OCR local). |
| `escritorio/connectivity.py` | Comprobación de conectividad HTTPS. |
| `escritorio/ui/index.html` | Estructura de la interfaz. |
| `escritorio/ui/style.css` | Presentación de la aplicación. |
| `escritorio/ui/app.js` | Interacciones, propuestas, editor, vista previa y estados. |
| `escritorio/ui/proposal-groups.js` | Normalización y agrupación de alternativas, preservando valores originales. |
| `escritorio/AS-REG-018.xlsx` | Plantilla Excel incorporada. |
| `escritorio/app.py` | Código anterior; la ejecución principal deriva a la aplicación de escritorio actual. |
| `escritorio/Abrir-en-Mac.command` | Lanzador de desarrollo/prueba en macOS. |
| `escritorio/build-windows.ps1` | Empaquetado con PyInstaller y compilación del instalador. |
| `escritorio/MateriaPrima.iss` | Configuración de Inno Setup. |

El servidor escucha en `127.0.0.1` y utiliza un token de sesión local, validación de origen y cabeceras de seguridad. Esto no constituye autenticación de usuarios empresarial ni habilita exponerlo directamente a Internet.

## 15. Ejecución y empaquetado

### Mac del entorno de desarrollo

```bash
cd "/Users/michellmarcospachecotacay/Documents/portafolio/laboratorio/escritorio" && ./Abrir-en-Mac.command
```

### Desde un entorno Python preparado

```bash
python -m pip install -r requirements.txt
python desktop.py
```

### Instalador Windows

Requiere un entorno Windows con Python 3.12 de 64 bits, Inno Setup 6 y las dependencias necesarias. Comando previsto desde `escritorio/`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build-windows.ps1
```

El script está preparado para generar `dist/MateriaPrima-Setup.exe`. La ventana requiere Edge WebView2. La vista de páginas reales necesita Word o LibreOffice instalado; incluir bibliotecas PDF en el empaquetado no incluye automáticamente esos programas.

No presentar el `.exe` como entregado y validado en Windows solo porque existan los scripts de compilación.

## 16. Límites, pendientes y riesgos conocidos

| Área | Estado y trabajo pendiente |
| --- | --- |
| Plataforma web | Se discutió comercialmente; no es la implementación actual. Requiere confirmar alcance y costos. |
| Precisión IA | No cuantificada; hacen falta evaluación experta y métricas sobre documentos reales. |
| Técnicas | El catálogo procede de 64 PDF. Para escaneados se extrajeron por OCR las primeras tres páginas; puede faltar parte del procedimiento. No se sincroniza automáticamente con la carpeta. |
| Clasificación A/B | Tiene contexto y validaciones conservadoras; no demuestra cobertura completa de condiciones y variantes técnicas. La IA puede proponer una ubicación incorrecta. |
| Varias incorporaciones en una fila A | El campo virtual de rango nuevo guarda una entrada por aprobación; falta una colección múltiple por fabricante. |
| Identidad y alias | Normalizar mayúsculas no resuelve equivalencia química, societaria ni de grados comerciales. |
| PDF y evidencia | Hay comprobaciones, pero no una auditoría completa y universal de cada cita visual. |
| Modelos y servicios | Pueden fallar por conectividad, credenciales, disponibilidad, cuotas o tiempo de respuesta. Internet conectado no elimina estos errores. |
| Plantillas diferentes | Los analizadores se basan en los formatos de ejemplo; rótulos y estructuras nuevas pueden requerir adaptación. |
| Estado de trabajo | Cada análisis se guarda en el **Historial de análisis** local (`history.py`, carpeta `historial/` junto al catálogo): copias del Word y los PDF, propuestas, observaciones, aprobaciones y ruta exportada. Se actualiza al terminar el análisis, al aprobar, descartar y exportar, y se reabre sin consultar a la IA. Guarda hasta 200 análisis; la edición del texto histórico de la vista previa no se guarda. |
| Seguridad de secretos | No se ha implementado un almacén cifrado de credenciales integrado con el sistema operativo. |
| Privacidad | Los PDF o su texto se envían al proveedor IA elegido. No se ha establecido aquí una política corporativa completa de retención ni una certificación de confidencialidad del servicio. |
| Vista previa | Depende de un motor externo y de fuentes; no garantiza paginación idéntica entre motores. |
| Windows | Falta una validación reproducible del instalador y del flujo completo en el equipo objetivo. |
| Pruebas | Consolidar pruebas de regresión y aceptación dentro del repositorio; no depender de scripts o capturas temporales. `escritorio/tests` cubre ya referencias de fabricantes y las correcciones del 16-11-2026. |
| OCR de evidencia | El resaltado en páginas escaneadas requiere Tesseract instalado (presente en el Mac de desarrollo, no incluido en el instalador Windows). La lectura OCR puede fallar con texto pequeño o caracteres chinos. |

## 17. Criterios de aceptación para una entrega

1. Cargar Word y varios PDF originales sin configurar claves en el flujo del laboratorista.
2. Seleccionar secciones y conservar lo que queda fuera del alcance.
3. Detectar cambios sustentados con PDF, página y evidencia revisables.
4. Mantener fabricantes existentes y sus proveedores al incorporar otros.
5. Asignar números en B y conservar las referencias y rangos de A sin sobrescribir los de otro fabricante.
6. Clasificar parámetros conforme a la capacidad real del laboratorio, señalando incertidumbres.
7. Mostrar alternativas, agrupar equivalencias de presentación y guardar exactamente la elección aprobada.
8. Permitir completar datos, resolver conflictos y corregir errores manualmente.
9. Mostrar páginas reales del documento y mantener el historial editable y opcional.
10. Generar Word limpio, Excel superior/DE/A, PDF originales y registro en una carpeta independiente.
11. Conservar fórmulas, contenido no intervenido, firmas y elementos de las plantillas; revisar visualmente el resultado.
12. Mostrar progreso, errores, reintentos y estado de conexión sin afirmar éxito en documentos fallidos.
13. Mantener secretos fuera del código, documentación e instalador.
14. Validar instalación, inicio y funcionamiento en Windows, además de las pruebas en Mac.
15. Documentar limitaciones y resultados medidos de aceptación; no prometer ausencia de errores de IA.

## 18. Orientaciones para continuar el desarrollo

- Leer este documento, el código actual y las guías de `PRUEBAS_MANUALES` antes de modificar la lógica documental.
- Preservar los originales de la empresa. Preparar demostraciones alterando copias de Word, con PDF originales intactos.
- No eliminar todos los fabricantes para fabricar un caso de incorporación.
- No resolver conflictos eligiendo silenciosamente una fuente o fusionando entidades distintas.
- No alterar significados técnicos para conseguir que desaparezca una diferencia visual.
- Cuando un fallo afecta al servicio, validar una llamada real y después el flujo de interfaz correspondiente antes de anunciar su resolución.
- Cuando el cambio es solo agrupación o selección visual, probarlo con respuestas guardadas y escenarios controlados sin gastar nuevas consultas innecesarias.
- No confundir una sesión con respuestas guardadas con una nueva ejecución completa de la IA.
- Comprobar qué versión del proceso está abierta. Los cambios del código no actualizan automáticamente módulos ya cargados en Python.
- Mantener esta documentación alineada con las decisiones posteriores y distinguir requisitos, implementación y validación.
