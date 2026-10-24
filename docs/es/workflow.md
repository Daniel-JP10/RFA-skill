# Flujo de referencias: recuperar, verificar, formatear, validar

> Estado: borrador.

## Principio rector
Solo se citan trabajos que existen. Si una referencia no se puede verificar, no entra en la lista final: se pide al usuario el DOI o los datos completos. Nunca se completa de memoria un autor, un año, un DOI, un volumen ni un rango de páginas. Las herramientas apoyan esta regla pero no la imponen por sí solas, así que la validación final con `--require-verified` es obligatoria.

## Pasos
1. **Recuperar.** Entrada: DOI, PMID, o el título completo con autor y año. Varias referencias van en un archivo JSONL que se pasa con `--in`, un objeto JSON por línea con las claves `doi`, `pmid`, o `title`, `author` y `year`. `resolve_metadata.py` consulta Crossref, resuelve un PMID a través de NCBI y usa doi.org cuando el DOI es de otra agencia de registro. Códigos de salida: 0 todo verificado, 1 alguna sin verificar, 2 error de entrada, 3 todos los registros fallaron por error de red.
2. **Verificar.** Cada referencia termina en uno de estos estados:
   - `verified`: entra en la lista, con su procedencia (fuente y fecha de consulta).
   - `ambiguous`: se muestran hasta 3 candidatos y se pide al usuario que elija; la skill no elige en su lugar.
   - `not_found`, `unresolved_no_doi`, `error` o `invalid_input`: no entra en la lista; se pide el DOI o los datos.
3. **Reunir.** `--items-out` escribe los ítems verificados, y solo esos, en un archivo CSL-JSON. Ese archivo es la entrada de los pasos siguientes.
4. **Formatear.** `format_reference.py` aplica el estilo CSL de la norma elegida. Motor preferido: pandoc 3.9 o posterior. Motor de respaldo: citeproc-py, con advertencia de soporte parcial. Para estilos numéricos y NLM añade `--cross-check` y muestra ambas versiones cuando aparezca `backend_disagreement`. Los ítems sin procedencia verificada producen `unverified_item`.
5. **Ordenar.** `order_references.py`: alfabético para autor-fecha; para estilos numéricos, por orden de primera cita, lo que requiere `--cited-keys`.
6. **Validar.** `validate_citations.py --require-verified` revisa que cada cita tenga su referencia y cada referencia su cita, marca duplicados y campos obligatorios ausentes, y convierte las referencias no verificadas en errores.
7. **Revisar detalles.** `check_et_al_rules.py` muestra cuántos autores lista el estilo; `abbreviate_journal.py` aplica abreviaturas solo si hay una fuente de datos.

```bash
python references/scripts/resolve_metadata.py --in refs.jsonl --out resolved.json --items-out items.csl.json
python references/scripts/format_reference.py --items items.csl.json --style vancouver-nlm --cross-check
python references/scripts/validate_citations.py --doc paper.md --refs items.csl.json --require-verified
```

## Escribir con claves
El texto se redacta con claves del tipo `[@clave]` y las referencias viven en un archivo CSL-JSON. Así el formateo y la validación son mecánicos y no dependen de interpretar citas escritas a mano. Las referencias resueltas a través de doi.org reciben el mismo id apellido-año que las de Crossref; el id original se conserva en `x-rfa.upstream_id`.

## Qué no hace la skill
- No inventa referencias.
- No juzga si una fuente es relevante o de calidad.
- No sustituye la norma oficial ni la guía de la institución o la revista: si la institución exige una norma propia, prevalece.
