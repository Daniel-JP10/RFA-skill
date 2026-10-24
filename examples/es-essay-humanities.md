# Ejemplo de uso: Ensayo académico en humanidades y literatura (es)

Este ejemplo muestra una interacción en español para un ensayo académico en el área de literatura, consultando la norma aplicable y ofreciendo la declaración de uso de IA sin asumirla por defecto.

## Consulta del usuario

"Estoy escribiendo un ensayo académico para un curso de literatura hispánica. ¿Qué estilo de citas debo utilizar y cómo debo estructurar el trabajo?"

## Comandos y salidas

<!-- rfa:run id=ex-humanities-es -->
```bash
python scripts/recommend.py --discipline literature --document-type academic-essay --language es
```

<!-- rfa:excerpt of=ex-humanities-es -->
```json
{
  "status": "ok",
  "reference_style": {
    "selection": "single_recommendation",
    "chosen": {
      "standard_id": "mla-9",
      "confidence": "high"
    },
    "allowed": [
      "mla-9",
      "chicago-18"
    ]
  },
  "sections": {
    "required": [],
    "recommended": []
  }
}
```

## Respuesta del asistente

Para un ensayo académico de literatura escrito en español:

1. **Norma de citación**: Se recomienda el estilo MLA (9.ª edición) con alta confianza.
   - Fuente oficial: MLA Handbook (9.ª edición).
   - Opciones permitidas: Si tu universidad o docente requiere el estilo Chicago (18.ª edición, ya sea autor-fecha o notas y bibliografía), indícalo para ajustar el formateo.
2. **Estructura**: la herramienta no devolvió secciones para este tipo de documento (`sections` está vacío) y la skill todavía no tiene una guía de estructura verificada para ensayos. Sigue la guía de tu curso o de tu institución; si quieres, la revisamos juntos.
3. **Uso de herramientas de IA**: Si utilizaste alguna herramienta de inteligencia artificial para edición de estilo o lluvia de ideas, podemos redactar una declaración transparente de uso según las políticas institucionales. Si no utilizaste IA, en general no hace falta una declaración, pero confirma la política de tu institución o del curso.
