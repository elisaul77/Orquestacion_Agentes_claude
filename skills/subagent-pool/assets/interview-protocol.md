# Protocolo de Entrevista Completo — Agent Orchestration Design

> **Quién usa este archivo:** El **AgentArchitect** y el **Conductor** cuando diseñan una nueva orquestación.
> Para el Conductor en modo operativo, basta con la mini-entrevista de 3 preguntas en SKILL.md.

---

## Las 8 Preguntas (AOD Interview Protocol)

Haz las preguntas **en orden**. Para cuando tengas suficiente para diseñar la pirámide.

### Q1 — Punto de partida
> ¿Partimos de una **carpeta vacía** o debo estudiar un **proyecto existente** primero?

- **Carpeta vacía** → continuar a Q2
- **Proyecto existente** → workspace scan:
  1. Leer `README.md` en la raíz si existe
  2. Leer `.claude/CLAUDE.md` o `AGENTS.md` si existen
  3. Listar estructura top-level (`ls -la`)
  4. Leer 3-5 archivos clave para inferir convenciones (paleta, idioma, stack, templates)
  5. Resumir hallazgos al usuario en 4-8 bullets antes de continuar

### Q2 — Propósito / Problem statement
> Describe en 1-3 oraciones: **qué problema** quieres resolver y **cuál es el entregable final**.

### Q3 — Artefacto(s) de entrada
> ¿Con qué material empieza el equipo? Opciones típicas: código fuente, documentos (PDF/Word), datos (CSV/DB), APIs, UI, mix.

### Q4 — Artefacto(s) de salida
> ¿Qué entrega el equipo al terminar? Opciones típicas: código nuevo + tests, documentación estructurada en Markdown, dataset procesado, reporte, deployment.

### Q5 — Sub-dominios
> ¿El problema tiene sub-dominios claramente separables que justifiquen **sub-coordinadores** (ej: backend + frontend, migración + integración)? ¿Cuáles?

### Q6 — Capacidades especiales
Checklist (marca las que apliquen):
- [ ] TDD / tests automatizados
- [ ] Extracción + descripción de imágenes (visión)
- [ ] Verificación de UI en navegador
- [ ] Ejecución de terminal / scripts
- [ ] Acceso a repos externos (GitHub)
- [ ] Consultas web / documentación externa
- [ ] Manipulación de Jupyter notebooks
- [ ] Automatización de browser (clicks, formularios)

### Q7 — Puntos de pausa del usuario
> ¿En qué momentos el Conductor debe **pausar obligatoriamente** para esperar tu confirmación?

Defaults seguros:
1. Después de presentar el plan de fases
2. Después de cada fase revisada y aprobada
3. Al cerrar el proceso con el reporte final

### Q8 — Idioma y convenciones corporativas
> ¿Idioma de output (español/inglés)? ¿Hay convenciones corporativas (paleta de colores, templates, glosario) que los agentes deben respetar?

---

## Agrupación sugerida de rondas

**Ronda A** (independientes — hacer juntas):
- Q2 propósito, Q3 input, Q4 output, Q8 idioma/convenciones

**Ronda B** (dependen de A):
- Q5 sub-dominios, Q6 capacidades especiales

**Ronda C** (confirmación):
- Q7 puntos de pausa

---

## Reglas de la entrevista

- **Nunca preguntes todo de una vez** — máximo 4-5 preguntas por ronda
- **Prefiere opciones múltiples** con un default recomendado cuando aplique (reduce fatiga)
- **Siempre permite respuesta libre** además de las opciones
- **Refleja comprensión** tras cada ronda: "Entonces el equipo debe {resumen} — ¿correcto?"
- **Para de preguntar** cuando puedas completar el checklist de §7 de SKILL.md

---

## Reglas de decisión post-entrevista

### ¿Agregar sub-coordinadores? (Q5)
Solo si TODAS se cumplen:
1. El sub-dominio tiene flujo de trabajo diferente (herramientas distintas, criterios de review distintos)
2. Ejecutar en paralelo crea valor real
3. Un único trío Analyst/Executor/Reviewer no puede manejar ambos sub-dominios

Si alguna falla → pirámide plana.

### ¿Fusionar Analyst + Executor?
Solo si el análisis es trivial (< 10% del esfuerzo de la fase). Si no, mantenerlos separados.

### ¿Dividir el Reviewer?
Solo si la verificación requiere habilidades fundamentalmente distintas (ej. `CodeReviewer` + `UXReviewer`).

### Asignación de herramientas por rol
| Rol | Tools |
|-----|-------|
| Conductor | `Task`, `Write`/`Edit` (solo plans/) |
| Planner/Analyzer | `Read`, `Glob`, `Grep`, `Bash` (lectura), `WebSearch`, `WebFetch` |
| Executor/Implementer | `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Bash` |
| Reviewer | `Read`, `Glob`, `Grep`, `Bash` (lectura) |

**NUNCA dar al Conductor herramientas de ejecución** (`Bash` directo sobre código, `Edit` sobre archivos del proyecto).
