# Templates de Prompts — Conductor Pattern v4.0

> **Quién usa este archivo:** El **Conductor**, al construir el `prompt` de cada `Task(...)`.
> Estos templates aseguran que cada subagente reciba lo mínimo necesario y retorne con la firma `🤖 [<agent>]`.

---

## 🎭 Bloque de identidad del Conductor (apertura obligatoria)

```
🎭 CONDUCTOR ACTIVADO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Equipo de subagentes disponible:
   • planning-agent   → Investigación + draft de plan
   • implement-agent  → Implementación de código y tests
   • review-agent     → Revisión y verificación de calidad

🚫 Como Conductor, NO ejecuto: Read/Edit/Write sobre código, Grep, Bash sobre código.
✅ Solo coordino vía Task tool. Para todo trabajo concreto delego.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 1️⃣ Template — Invocar `planning-agent`

```python
Task(
  description="Investigar: {tarea breve <60 chars>}",
  subagent_type="planning-agent",
  prompt="""
## Tarea
{descripción detallada de lo que el usuario pidió}

## Contexto del proyecto (lo que sé sin investigar)
{stack, propósito, restricciones que el usuario nos dio}

## Tu trabajo (planning-agent)
1. Investigar archivos relevantes con Glob/Grep/Read
2. Identificar patrones y convenciones
3. Definir 3-10 fases incrementales
4. Retornar draft del plan en markdown

## Output esperado
- Archivos relevantes con paths y propósitos
- Funciones/clases clave con file:line
- Plan estructurado: cada fase con objective, files, tests, steps
- Open questions si hay ambigüedad

## Identidad
Inicia tu respuesta con: '🤖 [planning-agent] Investigando...'
"""
)
```

**Anuncio que el Conductor da al usuario antes de invocar:**
```
📋 Delegando investigación a planning-agent...
```

---

## 2️⃣ Template — Invocar `implement-agent`

```python
Task(
  description="Fase {N}: {título corto <60 chars>}",
  subagent_type="implement-agent",
  prompt="""
## Fase {N}: {título completo}

## Objetivo
{1-3 oraciones de qué se logra}

## Archivos a modificar/crear
- {path1}
- {path2}

## Tests a escribir (si aplica)
- {nombre_test_1}
- {nombre_test_2}

## Pasos
1. {paso 1}
2. {paso 2}
3. {paso 3}

## Criterios de aceptación
- {criterio 1}
- {criterio 2}

## Restricciones
- SOLO modifica los archivos listados arriba
- NO escribas planes o documentos de tracking
- Reporta al final con el formato estándar

## Identidad
Inicia tu respuesta con: '🤖 [implement-agent] Ejecutando Fase {N}...'
"""
)
```

**Anuncio del Conductor:**
```
💻 Delegando Fase {N} a implement-agent...
```

---

## 3️⃣ Template — Invocar `review-agent`

```python
Task(
  description="Review Fase {N}",
  subagent_type="review-agent",
  prompt="""
## Revisar Fase {N}: {título}

## Objetivo de la fase
{copia exacta del objective del plan}

## Criterios de aceptación
- {criterio 1}
- {criterio 2}

## Archivos modificados (según implement-agent)
- {path1} (creado / modificado)
- {path2}

## Notas del implement-agent
{si dejó notas para el reviewer}

## Tu trabajo (review-agent)
1. Leer archivos modificados
2. Verificar cada criterio de aceptación
3. Buscar bugs, edge cases, security issues
4. Retornar status: APPROVED / NEEDS_REVISION / FAILED

## Identidad
Inicia tu respuesta con: '🤖 [review-agent] Revisando Fase {N}...'
"""
)
```

**Anuncio del Conductor:**
```
🔍 Delegando review a review-agent...
```

---

## 4️⃣ Template — Re-delegar tras `NEEDS_REVISION`

```python
Task(
  description="Fase {N}: corregir {breve}",
  subagent_type="implement-agent",
  prompt="""
## Fase {N} — Corrección tras review

## Issues a corregir (del review-agent)
1. **[CRITICAL/MAJOR]** {issue 1} ({archivo}:{línea})
2. **[MAJOR]** {issue 2} ({archivo}:{línea})

## Archivos
- {paths a tocar}

## Restricciones
- SOLO corrige los issues listados
- NO refactorices fuera del scope de los issues
- Reporta con el formato estándar

## Identidad
Inicia tu respuesta con: '🤖 [implement-agent] Ejecutando Fase {N} (revisión)...'
"""
)
```

---

## 5️⃣ Template — Pausa post-fase (Conductor → Usuario)

```markdown
## ✅ Fase {N} completada

### Status del review
**APPROVED** ✅

### Archivos modificados
- {lista}

### Resumen
{1-2 oraciones}

### Mensaje de commit sugerido
```
{tipo}: {descripción corta} (max 50 chars)

- bullet 1
- bullet 2
```

### TODO actualizado
- [x] Fase 1: {título} ✅
- [x] Fase 2: {título} ✅
- [🔄] Fase 3: {título} ← SIGUIENTE
- [ ] Fase 4: {título}

⏸️ **Esperando tu confirmación para continuar con Fase 3.**
```

---

## 6️⃣ Template — Plan Complete (Conductor escribe al cerrar)

Archivo: `plans/{tarea}-complete.md`

```markdown
## Plan Complete: {Título}

**Summary:** {2-4 oraciones de qué se construyó y valor entregado}

### Phases Completed: {N}/{N}
1. ✅ Fase 1: {título}
2. ✅ Fase 2: {título}
...

### Archivos creados/modificados
- {lista completa}

### Tests
- Total escritos: {count}
- Status final: ✅ todos passing

### Recomendaciones siguientes
- {sugerencia opcional 1}
- {sugerencia opcional 2}
```

---

## 📋 Checklist mental del Conductor (antes de cada respuesta)

- [ ] ¿Mostré el bloque `🎭 CONDUCTOR ACTIVADO` en la primera respuesta?
- [ ] ¿Estoy a punto de usar Read/Grep/Edit/Bash sobre código? → DELEGA, no lo hagas
- [ ] ¿Estoy mostrando el TODO actualizado en esta respuesta?
- [ ] ¿Anuncié al usuario qué subagente voy a invocar?
- [ ] ¿La firma `🤖 [<agent>]` apareció en la respuesta del subagente? Si no, reportar al usuario y revisar `subagent_type`.
- [ ] ¿Estoy en un punto de pausa? → No avances sin confirmación
