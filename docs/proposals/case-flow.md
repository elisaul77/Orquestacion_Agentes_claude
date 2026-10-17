# Proposal — case-care flow for subagent-pool (status: PROPOSED, 2026-10-17)

Evolve subagent-pool into a case-handling flow inspired by admission → triage → diagnosis → intervention → discharge,
**inside the existing instructions, contracts and agents** (no medical app, no new framework, no agent per stage).

## Brief (author's request, condensed)

1. **One case, one owner.** Every request has a case file; the Conductor keeps continuity and picks the next action.
2. **Admission:** objective, available context, constraints, success criterion. Ask only what is missing.
3. **Triage on four separate axes:** urgency (priority) · effort (direct vs phases) · uncertainty (investigate,
   consult, compare alternatives) · risk (controls, specialist verification). Urgency ≠ complexity. Touching data,
   APIs or security does **not** trigger the council by itself. Re-triage when diagnosis changes scope or risk.
4. **Diagnosis:** facts vs hypotheses vs evidence. Evidence tools chosen per case. "Enough evidence" = we can justify
   an understanding and propose an intervention (not that the fix is validated). Missing info comes from the project,
   a specialist or the user. Bounded loops with escalation.
5. **Consult vs council:** a consult answers one bounded question; the council compares alternatives when an important
   decision is still open. Unambiguous single/duo/council criteria, consistent with S/M/L.
6. **Intervention and review:** plan = scope, verification, recovery when relevant. Review outcome routes back:
   implementation defect → implementer · wrong hypothesis → diagnosis · goal verified → close.
   "Change verified" ≠ "deployed"; closing never authorizes a publish or deploy.
7. **Case file**, proportional: objective, classification + reason, owner, status, hypotheses, evidence, decisions,
   changes, verification, next action. Reuse `plans/` and the state files; small tasks stay short.

Validation cases: trivial change · bug with unknown cause · small sensitive change (specialist review, no automatic
council) · architectural decision with alternatives (council justified) · review failure by implementation · failure
by wrong hypothesis · information only the user has · investigation with no progress (bounded exit).
Structural tests must not be presented as evidence that a model routes correctly.

## Diagram 1 — roles

```mermaid
flowchart TD
    U["USUARIO<br/>Objetivo · Restricciones · Decisiones"]
    U <--> C["CONDUCTOR<br/>Coordina el caso y mantiene la continuidad"]
    C <--> EX[("EXPEDIENTE COMPARTIDO<br/>Contexto · Estado · Hipótesis · Evidencia<br/>Decisiones · Cambios · Verificación")]
    subgraph TRIAGE["EQUIPO DE TRIAGE"]
        T0["Triage principal<br/>Admisión · Prioridad · Ruta inicial"]
        T1["Triage técnico<br/>Alcance · Dependencias · Incertidumbre"]
        T2["Triage de riesgo<br/>Impacto · Reversibilidad · Controles"]
        T0 -->|"Si necesita explorar"| T1
        T0 -->|"Si necesita evaluar riesgo"| T2
        T1 -->|"Hallazgos"| T0
        T2 -->|"Controles necesarios"| T0
    end
    C <--> T0
    subgraph DIAG["EQUIPO DE DIAGNÓSTICO Y PLANIFICACIÓN"]
        P["planning-agent<br/>Generalista responsable del diagnóstico"]
        EV["Herramientas de evidencia<br/>Graphify · Código · Logs · Tests"]
        P <--> EV
    end
    C <--> P
    subgraph POOL["POOL DE ESPECIALISTAS · ACTIVACIÓN BAJO DEMANDA"]
        HUB["Interconsulta<br/>Pregunta concreta + contexto + resultado esperado"]
        AR["Arquitectura y contratos API"]
        SE["Seguridad y permisos"]
        DA["Datos y migraciones"]
        UI["Interfaz y accesibilidad"]
        PE["Rendimiento y concurrencia"]
        OP["Infraestructura y operación"]
        HUB <--> AR
        HUB <--> SE
        HUB <--> DA
        HUB <--> UI
        HUB <--> PE
        HUB <--> OP
    end
    C <--> HUB
    T1 -.->|"Consulta técnica"| HUB
    T2 -.->|"Consulta de riesgo"| HUB
    P <--> HUB
    subgraph JUNTA["COUNCIL · SOLO PARA DECISIONES IMPORTANTES ABIERTAS"]
        J["Generalista + especialistas pertinentes<br/>Propuestas independientes → contraste → recomendación"]
    end
    C <--> J
    P -->|"Problema y evidencia"| J
    HUB -->|"Especialistas seleccionados"| J
    subgraph IMPL["EQUIPO DE IMPLEMENTACIÓN"]
        I["implement-agent<br/>Ejecuta una fase con alcance definido"]
        IC["codex-agent · implement<br/>Ejecutor alternativo, si está habilitado"]
    end
    C -->|"Asignar fase"| I
    C -->|"Asignar fase alternativa"| IC
    I -->|"Cambios y comprobaciones"| C
    IC -->|"Cambios y comprobaciones"| C
    subgraph REVIEW["EQUIPO DE REVISIÓN"]
        R["review-agent<br/>Revisión independiente del resultado"]
        RE["Revisor de especialidad<br/>Según el riesgo del cambio"]
        RC["codex-agent · review<br/>Revisión adicional, si corresponde"]
    end
    C -->|"Solicitar verificación"| R
    C -->|"Solicitar control especializado"| RE
    C -->|"Solicitar segunda revisión"| RC
    R -->|"Veredicto y evidencia"| C
    RE -->|"Hallazgos"| C
    RC -->|"Hallazgos"| C
    HUB -.->|"Aporta la especialidad requerida"| RE
    AA["AgentArchitect<br/>Diseña roles cuando falta una especialidad"]
    C -->|"Solo si el pool no cubre el caso"| AA
    AA -.->|"Define la extensión del equipo"| HUB
    C --> AL["ALTA<br/>Resultado verificado · Evidencia · Pendientes"]
    AL --> U
```

## Diagram 2 — case flow

```mermaid
flowchart TD
    U["Petición del usuario"] --> A["CONDUCTOR<br/>Abrir expediente y definir éxito"]
    A --> T["EQUIPO DE TRIAGE<br/>Prioridad · Esfuerzo · Incertidumbre · Riesgo"]
    T --> D["PLANNING / GENERALISTA<br/>Examinar el caso"]
    D --> EV["OBTENER EVIDENCIA<br/>Inspección · Reproducción · Pruebas"]
    EV --> E{"¿Podemos justificar<br/>una intervención?"}
    E -->|"No"| F{"¿Qué falta?"}
    F -->|"Evidencia del proyecto"| D
    F -->|"Conocimiento especializado"| S["POOL DE ESPECIALISTAS<br/>Interconsulta acotada"]
    F -->|"Información del usuario"| Q["CONDUCTOR<br/>Pedir aclaración"]
    S -->|"Respuesta y evidencia"| D
    Q -->|"Respuesta del usuario"| D
    E -->|"Sí"| DE{"¿Hay alternativas importantes<br/>sin resolver?"}
    DE -->|"Sí"| J["COUNCIL<br/>Generalista + especialistas pertinentes"]
    J --> REC["Recomendación razonada"]
    REC --> UD{"¿Requiere una decisión<br/>del usuario?"}
    UD -->|"Sí"| US["CONDUCTOR + USUARIO<br/>Resolver la decisión"]
    US --> PL
    UD -->|"No"| PL
    DE -->|"No"| PL["PLAN DE INTERVENCIÓN<br/>Alcance · Contratos · Verificación"]
    PL --> I["IMPLEMENTADOR ASIGNADO<br/>implement-agent o ejecutor alternativo"]
    I --> R["REVIEW INDEPENDIENTE<br/>Revisor general + controles especializados necesarios"]
    R --> V{"Resultado de la revisión"}
    V -->|"Defecto en el cambio"| I
    V -->|"Hipótesis incorrecta"| D
    V -->|"Cambió alcance o riesgo"| T
    V -->|"Objetivo cumplido"| AL["CONDUCTOR<br/>Cerrar expediente con evidencia"]
    D -.->|"Sin avance tras el límite acordado"| ESC["CONDUCTOR + USUARIO<br/>Resolver bloqueo o ajustar alcance"]
    R -.->|"Revisiones agotadas"| ESC
    ESC -->|"Continuar con nuevo alcance"| T
    ESC -->|"Detener"| PA["Caso detenido<br/>Motivo y pendientes registrados"]
    AL --> FIN["Entrega al usuario"]
```
