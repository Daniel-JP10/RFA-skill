# Privacidad de la skill RFA

> Estado: borrador pendiente de revisión legal. No es asesoría legal.

## Qué NO hace
- No incluye telemetría, analítica ni registro alguno de lo que escribe el usuario.
- No conserva el contenido de los documentos ni de las referencias después de una ejecución. Durante la ejecución, la herramienta de formateo escribe las referencias, y en modo documento el documento completo, en una carpeta temporal para que pandoc pueda leerlas; esa carpeta se borra al terminar. El contenido solo se guarda de forma permanente cuando el usuario pide un archivo de salida.
- No envía el texto del documento a ningún servicio.

## Qué datos salen del equipo del usuario
Solo los scripts de `references/` abren conexiones de red, y solo envían los datos mínimos de cada referencia:

| Servicio | Qué se envía | Para qué |
|---|---|---|
| Crossref (api.crossref.org) | DOI, o título, autor y año de una referencia | Verificar que la obra existe y recuperar sus metadatos |
| doi.org y Crosscite (data.crosscite.org) | DOI | Recuperar metadatos de DOIs de otras agencias de registro (por ejemplo, DataCite o Zenodo) |
| NCBI E-utilities (eutils.ncbi.nlm.nih.gov) | PMID | Resolver un PMID a su DOI |
| OpenAlex (api.openalex.org) | Nada en esta versión | Figura en la lista de hosts permitidos para una búsqueda futura; esa parte del código está desactivada y no hace ninguna solicitud |

## Variables de entorno opcionales
- `RFA_CONTACT_EMAIL`: si se define, se envía a Crossref en el User-Agent y como parámetro `mailto`, para usar su acceso identificado ("polite pool"). No se envía a ningún otro host. Es un dato personal del usuario: defínelo solo si estás de acuerdo.
- `NCBI_API_KEY`: clave propia del usuario para NCBI; solo se envía a NCBI. `OPENALEX_API_KEY` está reservada y no se usa en esta versión. Las claves solo se leen del entorno; nunca se escriben en archivos, salidas ni mensajes de error.
- `RFA_JOURNAL_ABBR_FILE`: ruta local opcional a una lista de abreviaturas de revistas.
- `RFA_PANDOC`: ruta local opcional al ejecutable de pandoc. Solo se usa para encontrar pandoc en el equipo.
- La biblioteca HTTP también respeta las variables estándar de proxy y certificados del sistema (por ejemplo `HTTPS_PROXY`, `NO_PROXY` y `REQUESTS_CA_BUNDLE`) y el archivo netrc del usuario. RFA no las define ni las envía.

## Fuera de nuestro control
El agente o la plataforma donde se ejecute la skill procesa el contenido del usuario bajo sus propias políticas de privacidad. RFA no controla ese tratamiento.
