# Arquitectura y criterios de mantenimiento

## Ejecución

Desde la raíz del repositorio:

```sh
python -m pip install -r escritorio/requirements.txt
python escritorio/desktop.py
python -m unittest discover -s escritorio/tests -v
```

La compilación Windows se realiza con `escritorio/build-windows.ps1`. El flujo de integración ejecuta las regresiones antes de generar el instalador y comprueba el inicio del ejecutable. La compilación y la validación final de Word/WebView2 requieren Windows.

## Organización

- `escritorio/materia_prima/presentation`: ventana web, puente HTTP local y alternativa Tk.
- `escritorio/materia_prima/application`: coordinación del análisis, solicitudes a proveedores y validación de propuestas.
- `escritorio/materia_prima/domain`: manipulación de especificaciones, integridad de referencias y reglas de técnicas.
- `escritorio/materia_prima/infrastructure`: catálogo SQLite, memoria de decisiones humanas, historial, registro, salud de credenciales, conectividad, conversión y previsualización.
- `escritorio/materia_prima/paths.py`: resolución única de recursos desde fuentes y desde PyInstaller.
- `escritorio/ui`: recursos de la interfaz; `ejemplo` y `pruebas`: ejemplos y evidencias de validación.
- `escritorio/tests`: regresiones automatizadas. Los datos de usuario se aíslan en un directorio temporal.
- `docs/escritorio`: documentación técnica y contexto, fuera del producto.

Los lanzadores de la raíz conservan los comandos de inicio. Las importaciones internas usan el paquete completo, sin modificar globalmente la búsqueda de módulos en producción. La conversión de Word y el catálogo tienen módulos propios; el servicio conserva sus importaciones públicas para facilitar la transición.

## Límites y evolución

Esta es una separación inicial por responsabilidades. `Workspace` aún concentra estado, exportación y acciones HTTP; `analysis_service` conserva adaptadores de proveedores y reglas de normalización. La siguiente etapa debe extraer casos de uso y contratos de proveedor con pruebas de comportamiento. No se presenta esta estructura como una implementación completa de arquitectura hexagonal.

Las reglas de dominio no deben depender de ventanas ni servicios de red. Los cambios de formato deben mantener la conservación del paquete Word y la integridad entre fabricantes y rangos. Los adaptadores locales concentran los efectos sobre archivos y bases de datos. Las credenciales se mantienen fuera del repositorio y del instalador. Los recursos de solo lectura se resuelven independientemente del directorio de trabajo; el historial y las preferencias permanecen en la ubicación de usuario existente.

## Revisión de TI

Revisar el envío de PDF a proveedores externos, las credenciales, permisos de las carpetas de expedientes, retención de documentos y conectividad autorizada. Las menciones técnicas a los proveedores describen dependencias reales. No constituyen atribuciones de autoría.

Antes de distribuir: ejecutar regresiones, compilar en Windows, probar el instalador y recorrer selección, análisis, aprobación, previsualización y exportación con documentos de referencia. La prueba automática de inicio no sustituye esta aceptación funcional. Las dependencias tienen rangos de compatibilidad; queda pendiente fijar un conjunto reproducible y revisado por TI para cada versión publicada.
