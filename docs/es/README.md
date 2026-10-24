# Asistente de redacción académica RFA

Una skill que ayuda a estructurar documentos académicos, verificar y formatear referencias, y redactar declaraciones de uso de IA. Está diseñada para evitar tres cosas: fuentes inventadas, decisiones silenciosas y uso oculto de IA.

## Qué obtienes
- Una recomendación de la norma de citación, la pauta de reporte y las secciones para un documento, con niveles de confianza y marcas de revisión.
- Verificación de referencias contra registros públicos y formateo con estilos CSL.
- Validación de citas: cada cita tiene su referencia y cada referencia está citada.
- Declaraciones de uso de IA acordes a la política del espacio de publicación, en inglés y español.

## Inicio rápido
Requisitos: Python 3.10 o posterior y los paquetes de `references/requirements.txt`. Pandoc 3.9 o posterior es opcional pero recomendado para el formateo de referencias; instálalo con `pip install pypandoc_binary` o con un paquete del sistema.

```bash
python scripts/recommend.py --list disciplines
python scripts/recommend.py --discipline psychology --document-type quantitative --language en
```

Consulta `SKILL.md` para el flujo de trabajo completo y `references/workflow.md` para el flujo de referencias.

## Estilos compatibles
<!-- BEGIN styles-table -->
| ID | Nombre | Edición | Fuente oficial | Verificado el | Requiere revisión |
|---|---|---|---|---|---|
| abnt-brasil | ABNT NBR 6023, 10520 and 14724 | NBR 6023:2025 (3rd ed., 22-Sep-2025; corrected version 2026); NBR 10520:2023 (2nd ed., 19-Jul-2023); NBR 14724:2024 (4th ed., 11-Dec-2024; in force since 11-Jan-2025) | - | 2026-10-19 | No |
| acm | ACM Reference Format | ACM Reference Format (web, updated 11-Jul-2023) | https://www.acm.org/publications/authors/reference-formatting | 2026-10-18 | No |
| acs | ACS Guide to Scholarly Communication | ACS Guide to Scholarly Communication (continuous digital edition; in 2020 it replaced the ACS Style Guide, 3rd ed., 2006) | https://pubs.acs.org/page/jacsat/submission/authors.html | 2026-10-19 | No |
| aip | AIP Publishing style | AIP Publishing Author Instructions (online) | https://publishing.aip.org/resources/researchers/author-instructions/ | 2026-10-19 | No |
| ama-11 | AMA Manual of Style, 11th edition | 11th | https://academic.oup.com/amamanualofstyle/pages/about | 2026-10-18 | No |
| ams | AMS Style Guide | AMS Style Guide: Journals (October 2017 revision) | https://www.ams.org/arc/styleguide/index.html | 2026-10-18 | No |
| apa-7 | APA Publication Manual, 7th edition | 7th | https://apastyle.apa.org/products/publication-manual-7th-edition | 2026-10-19 | No |
| aps | APS (Physical Review) style | APS Physical Review Style Guide | https://journals.aps.org/authors/references-physical-review-physical-review-letters | 2026-10-18 | No |
| apsa | APSA Style Manual | APSA Style Manual (2018 revision, 2023 update) | https://connect.apsanet.org/stylemanual/sample-page/about/ | 2026-10-18 | No |
| asa | ASA Style Guide | 7th (June 2022) | https://www.asanet.org/publications/journals/asa-style-guide/ | 2026-10-24 | No |
| bluebook | The Bluebook, 22nd edition | 22nd (published in late May 2025) | https://www.legalbluebook.com/ | 2026-10-19 | No |
| chicago-18 | The Chicago Manual of Style, 18th edition | 18th | https://www.chicagomanualofstyle.org/help-tools/what-s-new.html | 2026-10-19 | No |
| colombia-legal-hybrid | Colombian legal citation practice (not an official standard) | Documented practice without an official standard: APA 7 with an adaptation of the Bluebook, or Chicago notes plus the Bluebook | - | 2026-10-18 | Sí |
| cse | CSE Manual, 9th edition | 9th (The CSE Manual) | https://www.councilscienceeditors.org/cse-manual | 2026-10-19 | No |
| harvard | Harvard (institution-specific variants) | No single standard; main variant Cite Them Right (13th ed., 26-Jun-2025) | https://www.bloomsbury.com/uk/cite-them-right-9781350934252/ | 2026-10-19 | No |
| icontec-colombia | ICONTEC NTC 1486:2022 | NTC 1486:2022 (8th update; reapproved on 2024-12-04) | https://tienda.icontec.org/gp-documentacion-presentacion-de-trabajos-academicos-y-referencias-bibliograficas-ntc1486-2022.html | 2026-10-19 | No |
| ieee | IEEE Reference Guide | IEEE Editorial Style Manual for Authors and IEEE Reference Guide (online edition 2024/2025) | https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/ieee-editorial-style-manual/ | 2026-10-19 | Sí |
| institutional-overrides | Institution-specific rules | - | - | - | - |
| iso-690 | ISO 690:2021 | 4th (ISO 690:2021, June 2021) | https://www.une.org/encuentra-tu-norma/busca-tu-norma/norma?c=N0072646 | 2026-10-19 | No |
| mla-9 | MLA Handbook, 9th edition | 9th | https://style.mla.org/mla-handbook-ninth-edition/ | 2026-10-18 | No |
| oscola | OSCOLA, 5th edition | 5th (official PDF published online in March 2026; includes rule 3.7.13 on generative AI) | https://www.law.ox.ac.uk/oscola | 2026-10-19 | No |
| vancouver-nlm | Vancouver (ICMJE / NLM Citing Medicine) | ICMJE Recommendations (January 2026) + NLM Citing Medicine (2nd ed.) | https://www.icmje.org/news-and-editorials/updated_recommendations_jan2026.html | 2026-10-19 | No |
<!-- END styles-table -->

La tabla se genera desde la capa de datos. Algunas normas no tienen un archivo CSL incluido, por lo que las referencias no se pueden formatear para ellas aunque se puedan recomendar.

## Principios
- Nunca inventa una fuente. El flujo excluye las referencias que no se pueden verificar en lugar de completarlas, y la verificación final `validate_citations.py --require-verified` convierte cualquier referencia no verificada en un error.
- Cuando las recomendaciones entran en conflicto, muestra las opciones y pregunta.
- Hace visible la incertidumbre: niveles de confianza, marcas de revisión pendiente y fechas de corte de los datos.
- Te ayuda a declarar el uso de IA según la política del espacio de publicación. No ayuda a ocultar el uso de IA ni a evadir detectores de texto generado por IA.
- No hay telemetría. Consulta `docs/es/privacy.md`.

## Limitaciones
Los datos son una versión fechada. Varias disciplinas se basan en muestras pequeñas de revistas. La orientación sobre estructura por tipo de documento aún no está disponible. Siempre confirma los requisitos con tu institución o revista.

## Desarrollo
Instala las dependencias de desarrollo con `pip install -r requirements-dev.txt`. Ejecútalo desde la carpeta de la skill, donde está el archivo. Incluye `pypandoc_binary`, que trae pandoc 3.9, de modo que todas las pruebas se ejecutan. Si prefieres un pandoc del sistema, usa la versión 3.9 o posterior: se observó que las versiones anteriores formatean de forma incorrecta los nombres en Vancouver y las citas en el texto, y las herramientas avisan con `pandoc_version_untested`. Define `RFA_PANDOC` para elegir un ejecutable de pandoc específico. Si no se encuentra pandoc, las herramientas indican el motivo y se utiliza el motor de respaldo con advertencias.

## Documentación
Esta es la versión en español; la documentación en inglés está en la raíz de la skill.

## Marcas
APA, MLA, Chicago, IEEE, AMA, ACS, CSE, ICMJE, Crossref, NLM, PubMed y los demás nombres de guías de estilo, editoriales y servicios mencionados en esta skill pertenecen a sus respectivos titulares. RFA es un proyecto independiente y no está afiliado a ninguno de ellos, ni cuenta con su patrocinio o respaldo. La skill ofrece reglas parafraseadas, enlaces a las fuentes oficiales y ejemplos propios; no reproduce los manuales.

## Licencia
MIT. Consulta `LICENSE`. Los archivos de estilo CSL de `references/csl/` conservan su propia licencia, CC BY-SA 3.0; consulta `references/csl/NOTICE.md`.
