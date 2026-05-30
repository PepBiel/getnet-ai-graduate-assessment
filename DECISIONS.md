# DECISIONS.md

Documento vivo de decisiones tecnicas. Cada seccion se ira ampliando conforme avance la solucion.

## Parte 1 - Pandas

### D1 - Exploracion antes de limpiar

- **Que hice**: cree un notebook de exploracion para visualizar formatos, nulos, duplicados y patrones temporales antes de implementar la limpieza reproducible en `src/parte1_pandas.py`.
- **Por que**: limpiar directamente sin mirar los datos puede ocultar problemas de calidad o introducir supuestos no defendibles. La exploracion separa observacion de datos y transformacion productiva.
- **Que descarte**: modificar el CSV original o limpiar de forma manual desde el notebook. El notebook queda como apoyo de EDA; la logica reutilizable vive en funciones.
- **Que supuse**: el CSV de entrada debe tratarse como read-only y cualquier transformacion debe ser reproducible desde codigo.

### D2 - Tratamiento de tipos en `load_clean`

- **Que hice**: parseo `amount` desde formato con coma decimal, parseo `transaction_date`, `reference_date`, `last_complaint_date` y `dat_process`, normalizo `status` y `channel`, y trato `mcc` como string.
- **Por que**: esos campos no son analizables de forma segura como strings originales. `mcc` es un codigo de categoria, no una magnitud numerica.
- **Que descarte**: usar `astype(float)` para importes, confiar en inferencia automatica de fechas o dejar `mcc` como entero.
- **Que supuse**: los importes siguen convencion local con `.` como miles y `,` como decimal; las fechas observadas pueden venir en ISO o `DD/MM/YYYY`.

### D3 - Trazabilidad y no sobrelimpieza

- **Que hice**: conserve columnas `*_raw` para importes y fechas antes de parsearlas; no elimine `cancellation_reason`, `last_complaint_date`, outliers ni filas posteriores a `reference_date` dentro de `load_clean`.
- **Por que**: `load_clean` debe producir un dataset limpio y auditable para analisis general. Los filtros predictivos deben aplicarse despues, donde el objetivo temporal sea explicito.
- **Que descarte**: filtrar globalmente todo lo posterior a `reference_date`, imputar importes nulos o eliminar variables sospechosas durante la carga.
- **Que supuse**: algunas transacciones posteriores a `reference_date` pueden servir para EDA, validaciones o controles de calidad, aunque no deben usarse para features predictivas.

### D4 - Deduplicacion por negocio

- **Que hice**: deduplique por columnas de negocio excluyendo `transaction_id` y columnas `*_raw`.
- **Por que**: `transaction_id` puede ser unico aunque dos filas representen el mismo evento de negocio. Excluir columnas raw evita que un mismo evento no se detecte como duplicado solo por diferencias de formato ya normalizadas.
- **Que descarte**: deduplicar solo por `transaction_id` o eliminar duplicados antes de parsear tipos.
- **Que supuse**: si todas las columnas de negocio normalizadas coinciden, conservar la primera fila es suficiente para KPIs de esta prueba.
