# Memoria de aprendizaje de decisiones del usuario

Estado: implementada en la interfaz principal de escritorio. No ajusta los pesos del modelo ni garantiza por sí sola una mejora de precisión.

## Funcionamiento

1. El usuario revisa propuestas, modifica valores y los aprueba. Un borrador o una aprobación aislada todavía no alimentan la memoria.
2. Después de exportar correctamente el expediente, se registran los cambios finales aprobados: material SAP, sección, campo, fabricante, valor anterior, propuestas originales y sus evidencias, valor final, tipo de decisión, expediente, fecha UTC, versión de aplicación y modelo configurado. Las propuestas incluyen el proveedor que las produjo cuando está disponible.
3. Se distingue entre propuesta aceptada, propuesta corregida y cambio manual sin propuesta. Los descartes, los borradores y los campos sin cambio exportado no se registran en esta primera implementación.
4. En análisis posteriores se recupera la última decisión por campo compatible del mismo SAP, sección, etiqueta, tipo y fabricante. Los identificadores de fila no se usan como identidad. Una etiqueta o fabricante diferente no recupera el ejemplo anterior.
5. Se envían como máximo doce ejemplos, con textos acotados, dentro del contexto de la consulta inicial a Gemini, Groq u OpenRouter. No se envía la base completa. Los ejemplos orientan interpretación y redacción; las reglas exigen respaldo explícito en el documento actual. No se aplican cambios ni se aprueban valores automáticamente.

## Almacenamiento y control

Los datos se guardan en `aprendizajes.sqlite3`, junto al catálogo local. En Windows: `%LOCALAPPDATA%\MateriaPrima\aprendizajes.sqlite3`. En macOS se conserva la convención existente: `~/.local/share/MateriaPrima/aprendizajes.sqlite3` si `LOCALAPPDATA` no está definido.

La tabla `decision_v1` identifica la versión del registro. Repetir el guardado del mismo expediente y contenido no duplica la decisión. Una exportación posterior conserva una nueva decisión; para consulta se prioriza la más reciente.

En Configuración, **Aprender de los cambios aprobados y exportados** permite activar o desactivar tanto el registro como la recuperación. Está activado por defecto. La interfaz explica que ejemplos de decisiones anteriores se incluyen en consultas al servicio externo. Desactivar no borra los datos existentes. Para restablecer la memoria, cerrar la aplicación y eliminar únicamente `aprendizajes.sqlite3`. Borrar un análisis del historial no elimina sus aprendizajes: son almacenes independientes.

El programa y el esquema están incluidos en `escritorio/materia_prima/infrastructure/learning.py`; no necesitan archivos de `laboratorio` para funcionar. La memoria se crea por usuario durante el uso; no se distribuye con el instalador ni debe incluirse en la carpeta de código que se entrega a TI. Los Markdown explican el funcionamiento y no actúan como memoria operativa.

Si falla la memoria, se informa en las observaciones y se conserva el análisis o la exportación. No se importan aprendizajes retroactivamente de expedientes antiguos. La interfaz alternativa Tk no registra ni recupera aprendizajes en esta versión.

## Evaluación y evolución

Esta función reutiliza ejemplos humanos; una corrección puede ser específica de una fuente o contener errores. La coincidencia estricta limita la reutilización y el documento actual sigue siendo la autoridad. Para afirmar una mejora medible se debe comparar precisión, omisiones y propuestas sin respaldo con un conjunto de evaluación independiente. Las pruebas automatizadas verifican persistencia, aislamiento, clasificación de decisiones, deduplicación y preferencia de desactivación; no miden calidad del modelo remoto.

Una siguiente etapa puede incorporar revisión técnica de aprendizajes, explicación de la corrección, consulta y eliminación desde la interfaz, y evaluación de reglas versionadas. El entrenamiento de modelos requiere además datos autorizados y validación independiente.
