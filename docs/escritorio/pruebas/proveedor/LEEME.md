# Validación del fabricante

Los archivos y evidencias citados se encuentran en `escritorio/pruebas/proveedor`, desde la raíz del repositorio.

Se creó una copia del Word de Pure Seduction V2 y se sustituyó el fabricante por FABRICANTE DE PRUEBA. Se analizó la ficha técnica FT PURE SEDUCTION 275898 ACTUALIZADA.pdf de su carpeta.

La prueba real con Gemini 2.5 Flash detectó el fabricante respaldado por el PDF. Se aplicó la propuesta y se generaron salida_corregida.docx y solicitud.xlsx. Ambos archivos se reabrieron y se comprobó el fabricante corregido, el incremento de versión y el bloque A de la solicitud. resultado.json contiene las propuestas y las observaciones reales del servicio.

Los intentos previos con Gemini 3.5 Flash fallaron por tiempo de espera y saturación del servicio.

En una prueba adicional de interfaz se editó manualmente un proveedor, se aprobó y se exportó el expediente con Word, Excel, PDF y registro de cambios. Se comprobó la persistencia de la carpeta de salida.

Esta prueba cubre un fabricante en un expediente. No constituye una medición de precisión sobre todo el conjunto de documentos.
