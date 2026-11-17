# Guía de uso de Materia

Guía para laboratoristas y químicos que actualizan especificaciones de materias primas a partir de documentos técnicos. El objetivo es generar un expediente revisado por una persona: Word, solicitud de cambio Excel y PDF de respaldo.

## 1. Qué preparar

- El **Word vigente** de la materia prima, preferiblemente `.docx`.
- Los **PDF originales** nuevos: fichas técnicas, COA, hojas de seguridad, certificados de alérgenos, etc.
- Nombre del solicitante, área y fecha de revisión.
- Una carpeta existente donde guardar los expedientes.

La solicitud Excel **AS-REG-018 ya está incluida**. No necesitas cargarla en cada ejecución. Si la empresa cambia el formato, un responsable puede sustituirla en Configuración.

Los PDF o su texto se envían al servicio de IA configurado. La previsualización de Word se genera localmente.

## 2. Abrir la aplicación

En este Mac puedes abrir `escritorio/Abrir-en-Mac.command` desde Finder o ejecutar:

```bash
cd "/Users/michellmarcospachecotacay/Documents/portafolio/laboratorio/escritorio" && ./Abrir-en-Mac.command
```

En Windows se utilizará el acceso directo del instalador cuando esté compilado y validado en ese equipo. Para ver páginas reales del documento se necesita Microsoft Word o LibreOffice instalado. En Mac se usa LibreOffice o el renderizador disponible en este entorno.

Si aparece un aviso de **versión anterior del motor**, conserva tus resultados antes de cerrar y vuelve a abrir la aplicación actualizada. Los cambios del programa no se incorporan automáticamente a una ventana ya abierta.

## 3. Configurar una vez

1. Entra en **Configuración**.
2. Pulsa **Elegir carpeta…**.
3. En el selector del sistema elige el directorio donde se guardarán los expedientes y confirma.
4. Completa **Solicitante** y **Área**.
5. Conserva la plantilla incluida o pulsa **Cambiar plantilla** si tienes una AS-REG-018 compatible autorizada.
6. Pulsa **Guardar preferencias**.

La aplicación comprueba que puede escribir en la carpeta. No necesitas elegirla de nuevo para cada materia prima.

En macOS, para llegar directamente a una ruta en un selector de archivos puedes pulsar **⌘⇧G**, escribir la ruta y confirmar. Para seleccionar varios PDF, puedes elegir el primero y hacer **Mayúsculas + clic** en el último, o usar **⌘ + clic** para archivos concretos. Confirma en la pantalla principal que figura el número correcto de PDF.

### Conexión y configuración técnica

El icono superior muestra si se ha verificado acceso a Internet. Puedes pulsarlo para comprobar de nuevo. No mide la intensidad de Wi-Fi ni garantiza que el servicio de IA tenga cuota o una credencial válida.

La configuración de claves y modelos corresponde al responsable técnico. Un laboratorista no necesita introducir una clave en cada análisis. No compartas capturas con credenciales visibles.

## 4. Cargar el expediente

1. Ve a **Especificaciones**.
2. Pulsa la tarjeta **Especificación vigente** y elige el Word.
3. Comprueba el **código SAP y la versión** que aparecen en pantalla.
4. Pulsa **Documentación de respaldo** y selecciona todos los PDF pertinentes.
5. Comprueba sus nombres y cantidad.

Puedes usar las tarjetas de carga o arrastrar archivos cuando el sistema lo permita. Si cargas otro Word, se inicia un nuevo expediente y se reinician las propuestas anteriores; exporta primero lo que quieras conservar.

El Word debe tener una estructura compatible con las plantillas de la empresa. Un `.doc` antiguo puede requerir conversión previa a `.docx`, especialmente en Mac.

## 5. Elegir las secciones

Por defecto se analizan todas:

| Sección | Qué se revisa |
| --- | --- |
| Identificación | INCI, CAS y campos identificativos de la plantilla. |
| A | Parámetros que el laboratorio puede analizar con sus técnicas internas. |
| B | Fabricantes, proveedores, datos comerciales y parámetros adicionales de cada fabricante. |
| C | Observaciones y tablas como alérgenos. |

Pulsa **Todas las secciones** para limitar el alcance y luego **Aplicar selección**. Cambiar el alcance reinicia las propuestas de análisis y puede retirar aprobaciones de secciones excluidas. Decide el alcance antes de revisar y aprobar.

## 6. Analizar y esperar la respuesta

Pulsa **Analizar documentos**. El programa procesa los PDF y muestra progreso. Espera a que vuelva a habilitarse el control y revisa tanto **Revisión de cambios** como **Observaciones**.

- Un PDF puede producir varias propuestas, ninguna o un error.
- Cero propuestas no demuestra por sí solo que el documento no contenga información nueva.
- Si un PDF falla, usa **Reintentar pendientes**. No lo confundas con un documento analizado correctamente sin cambios.
- **Detener** solicita cancelar el trabajo pendiente; una consulta ya enviada puede tardar en terminar.
- Si el servicio no responde, puedes completar campos manualmente, pero debe quedar claro qué documentos no fueron analizados.

Un COA puede reunir varios productos. Verifica siempre que la página citada corresponde a la materia prima correcta. Un resultado medido de un lote no sustituye automáticamente un rango de aceptación.

## 7. Comparar y elegir propuestas

Cada fila muestra el campo o sección, el valor vigente, las opciones propuestas y su estado.

1. Lee la propuesta y el fabricante al que corresponde.
2. Revisa los PDF y las páginas citadas. La página indicada es la física del PDF, empezando por 1.
3. Pulsa el enlace del PDF o **Abrir PDF** para contrastar la evidencia. Si se abre al inicio, navega a la página indicada.
4. Pulsa **Elegir este valor**, **Elegir estos datos** o la flecha de revisión.
5. En el editor puedes seleccionar una alternativa, leer su respaldo y corregir el **Valor final editable**.
6. Pulsa **Aprobar** para incluirlo en la salida. Elegir una opción por sí solo no la aprueba.

### Opciones agrupadas

- `Polvo blanco y esponjoso` y `Polvo esponjoso blanco` pueden aparecer agrupados conservando ambos respaldos.
- Una descripción con un detalle adicional sigue siendo una alternativa revisable.
- Un mismo fabricante en mayúsculas y formato normal se agrupa por identidad de presentación.
- Dentro de un fabricante, pulsa **Comparar datos y elegir** para comparar los bloques de cada documento.
- Guangzhou Tinci y Jiujiang Tinci se mantienen separados; una similitud de nombre no demuestra equivalencia societaria.

Agrupar no fusiona automáticamente datos comerciales ni acredita equivalencia técnica. El editor conserva el texto original de la opción elegida.

### Cambios manuales y descartes

Usa **Cambio manual** o desmarca **Solo propuestas** para ver campos sin propuesta. Busca el campo, ábrelo, escribe el valor completo y apruébalo.

**Descartar cambio** retira su aprobación y sus propuestas de esa fila. Si necesitas conservar una opción para compararla después, vuelve al editor sin aprobarla en lugar de descartarla.

## 8. Fabricantes y sus rangos

Los índices de A son los números de fabricante de B:

```text
A — Aspecto
(1) Polvo esponjoso
(2) Polvo blanco, esponjoso

B
1) COREL PHARMA CHEM
2) Guangzhou Tinci Materials Technology Co., Ltd
```

Actualizar el rango de (2) no debe borrar el de (1). Al incorporar fabricantes se conservan los existentes y el programa asigna números nuevos en una columna independiente de B.

### Incorporar un fabricante

1. Abre **Agregar fabricante y su bloque comercial**.
2. Selecciona un documento y revisa su bloque.
3. Elige sus datos o pulsa **Añadir bloque de esta fuente**.
4. Si necesitas otro fabricante distinto, selecciona su fuente y añade su bloque; revisa el texto antes de aprobar.
5. Completa manualmente datos faltantes solo si tienes respaldo.
6. Aprueba los bloques comerciales.

Formato admitido cuando sea necesario escribirlo manualmente:

```text
Fabricante: Nombre completo
Proveedor: Proveedor documentado
Nombre Comercial: Nombre del producto
Tiempo de Vida útil: 24 meses
Almacenamiento: Condiciones documentadas
Parámetro adicional: Nombre | Rango | Referencia
```

Si no conoces el proveedor, no inventes uno. `Manufacture/Supplier` permite registrar el rol declarado en ese documento; no identifica necesariamente a un intermediario comercial local diferente.

### Agregar rangos de fabricantes nuevos

En A, abre la fila **agregar rango por fabricante** del parámetro correspondiente. Una línea por fabricante:

```text
Fabricante: Guangzhou Tinci Materials Technology Co., Ltd | Polvo blanco, esponjoso
Fabricante: Jiujiang Tinci Materials Technology Co., Ltd. | Polvo blanco y suelto
```

Puedes seleccionar una fuente y pulsar **Añadir rango de esta fuente** para incorporar otra línea. No incluyas dos alternativas del mismo fabricante sin resolver cuál debe quedar.

Aprueba también los bloques comerciales de esos fabricantes. Si el nombre del rango no coincide con un fabricante aprobado, la previsualización/exportación pedirá corregirlo en lugar de crear una referencia huérfana.

Los parámetros sin técnica interna aplicable pertenecen a B, bajo su fabricante. Si un PDF propone un parámetro debajo de otro fabricante, no lo apruebes: revisa la asociación. Los filtros son una ayuda; la revisión técnica sigue siendo necesaria.

## 9. Revisar el Word y el historial

Pulsa **Previsualizar Word**.

- **Páginas reales** muestra la copia convertida localmente a PDF, con logo, cabeceras y tablas.
- Los cambios aprobados se resaltan en la copia de revisión.
- Con cero aprobaciones se muestra el documento vigente.
- **Vista de contenido** es una alternativa simplificada si el renderizador no está disponible.

En el panel lateral:

1. Confirma la fecha.
2. Revisa y edita la redacción de **Revisión Histórica**.
3. Usa **Regenerar con los cambios aprobados** si necesitas reconstruir el resumen.
4. Activa o desactiva **Registrar nueva revisión histórica**.
5. Pulsa **Actualizar vista previa** y revisa todas las páginas.

Si cambias aprobaciones, revisa de nuevo el historial: el programa puede regenerarlo para que no describa cambios anteriores. La versión aumenta al exportar aunque no se añada una fila histórica.

Si aparece un error, lee el mensaje y corrige el dato o la configuración. No interpretes una pantalla de carga o un error como documento vacío. La paginación puede variar entre LibreOffice y Microsoft Word.

## 10. Exportar el expediente

1. Asegúrate de tener aprobaciones.
2. Pulsa **Preparar exportación**.
3. Confirma solicitante, área, fecha y carpeta.
4. Si hay documentos pendientes, resuélvelos o acepta conscientemente una salida parcial; quedarán registrados.
5. Pulsa **Crear expediente**.
6. Espera la confirmación y usa **Abrir carpeta**.

Se crea una subcarpeta como:

```text
01040500269_V2/
├── ET_01040500269_V2.docx
├── SC_01040500269_V2.xlsx
├── PDF de respaldo/
└── registro_de_cambios.json
```

Una segunda exportación no debe sobrescribir la anterior; añade un sufijo. El Word final no lleva los resaltados de la previsualización. La solicitud Excel se rellena en los datos superiores y DE/A; las áreas de revisión y aprobación de Calidad deben conservarse.

Abre Word y Excel para una última revisión antes de entregarlos. La aprobación en el aplicativo selecciona contenido para exportar; no sustituye las firmas ni el procedimiento formal de la empresa.

## 11. Consultar el catálogo y las técnicas

Después de exportar, entra en **Proveedores y fabricantes** para consultar las entidades registradas para el SAP cargado.

En **Configuración → Técnicas disponibles en el laboratorio → Consultar técnicas** puedes revisar el texto de referencia utilizado. Parte fue extraído por OCR y puede ser incompleto o contener errores; verifica el procedimiento original ante dudas de condiciones o capacidad analítica.

## 12. Simular con los archivos preparados

Las instrucciones están en [PRUEBAS_MANUALES/EMPEZAR_AQUI.md](PRUEBAS_MANUALES/EMPEZAR_AQUI.md).

Para practicar la incorporación de fabricantes:

- Word: `PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR/WORD_ENTRADA_V1.docx`.
- PDF: los tres archivos de su carpeta `PDF_ORIGINALES`.
- Conserva COREL como (1); revisa las incorporaciones de Tinci y sus rangos propios.
- No cargues la entrada antigua marcada `NO_USAR`.
- Usa una carpeta de salida de prueba, no el archivo oficial vigente.

## 13. Problemas frecuentes

| Situación | Qué hacer |
| --- | --- |
| No se habilita Analizar | Comprueba Word, PDF y secciones seleccionadas. |
| No se habilita Exportar | Aprueba al menos un cambio. |
| Sin conexión verificada | Comprueba la conexión y pulsa el indicador. El estado no comprueba claves ni cuotas. |
| Servicio sin respuesta | Revisa Observaciones, reintenta pendientes y evita asumir que no hay cambios. |
| Falta proveedor o vida útil | Contrasta otros documentos o completa el dato manualmente con respaldo. |
| Hay varias propuestas | Compara alternativas y evidencias; elige y aprueba la correcta. |
| La empresa aparece con otro nombre | No fusiones razones sociales distintas sin confirmación. |
| Un rango no encuentra fabricante | Aprueba su bloque B y revisa el nombre completo en la línea de A. |
| No se generan páginas reales | Configura LibreOffice o Word según el sistema, o usa Vista de contenido. |
| Aviso de motor anterior | Conserva resultados y reinicia la aplicación actualizada. |
| Cerraste la aplicación sin exportar | El análisis de la sesión puede perderse; no hay recuperación general de borradores implementada. |

## 14. Alcance de la validación

El detalle de las pruebas del 16/11/2026 y los problemas encontrados se documentará en [el informe de validación](VALIDACION_INTERFAZ/2026-11-16/INFORME_VALIDACION.md). Ese informe distingue lo probado en la interfaz nativa, lo verificado en los archivos de salida y lo pendiente.

La IA puede omitir o proponer datos incorrectos. No se dispone de una tasa de error medida para producción ni de una certificación de instalación Windows en este entorno Mac.
