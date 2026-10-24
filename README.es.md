# 🤖 Orquestacion Agentes Claude

![Banner](docs/banner.png)

🌐 [English](README.md) · **Español**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-v9.13.0-blueviolet.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-228%20passing-3fb950.svg)](#-tests)
[![Claude Code](https://img.shields.io/badge/brain-Claude%20Code-8a63f0.svg)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-opcional-412991.svg)](#complementos-opcionales)

[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsors-pink?style=for-the-badge&logo=githubsponsors)](https://github.com/sponsors/elisaul77)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?style=for-the-badge&logo=paypal)](https://paypal.me/eflorezp)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buymeacoffee)](https://buymeacoffee.com/elisaul77)

**Un Conductor para Claude Code: planifica, reparte el trabajo entre subagentes especialistas y hace que otro agente revise cada fase.**
Pensado para trabajo complejo (3 archivos o más, un módulo nuevo, un refactor). Tú apruebas el plan, y nada irreversible ocurre sin ti.

```
tú ──> Conductor (acota y delega, nunca toca el código)
          │
          ├─ plan ──────► planning-agent                      (planes simples)
          │               o consejo de plan: spec · architect (decisión importante abierta)
          │                  · lateral · risk, que debaten
          │                         │
          │                  plans/*.md ──► tu aprobación
          │
          ├─ por fase ──► implement-agent ──► review-agent ──► APPROVED | NEEDS_REVISION
          │                                       ▲
          │                     codex-agent ──────┘  revisión de otro proveedor (opcional)
          │
          ├─ dominio nuevo ► AgentArchitect ──► equipo especialista nuevo
          └─ skill externa ► revisión aislada ──► biblioteca privada (por ruta)
```

---

## 🚀 Puesta en marcha

### Instalar

```bash
git clone https://github.com/elisaul77/Orquestacion_Agentes_claude.git
cd Orquestacion_Agentes_claude

python3 skills/subagent-pool/scripts/install.py --dry-run          # vista previa, no cambia nada
python3 skills/subagent-pool/scripts/install.py --with teams       # núcleo + los complementos que elijas
```

El instalador hace copia de seguridad de lo que ya tienes, copia las skills y los agentes, **fusiona** `settings.json` (nunca lo sobrescribe) y termina con los chequeos de doctor. Complementos: `teams`, `cost-hook`, `codex` y `claude-md` (ver la tabla de abajo). Puedes volver a ejecutarlo sin riesgo para actualizar.

> 🤖 **¿Lo instala un agente?** Indícale [INSTALL.md](INSTALL.md): te pregunta por los complementos, instala y te entrega el resultado.

Reinicia Claude Code, porque los agentes se cargan al abrir una sesión. Luego comprueba la instalación:

```bash
python3 ~/.claude/skills/subagent-pool/scripts/doctor.py
```

`doctor` solo lee, no cambia nada. Revisa la versión de la skill, los agentes, los complementos opcionales y, si le pasas `--remote host`, otros equipos por SSH. Cada fallo viene con el comando que lo arregla.

<details>
<summary>Sin git: instalación básica con curl</summary>

```bash
BASE=https://raw.githubusercontent.com/elisaul77/Orquestacion_Agentes_claude/master
for skill in subagent-pool arquitec-dev-ia graphify; do
  mkdir -p ~/.claude/skills/${skill}
  curl -sSL "$BASE/skills/${skill}/SKILL.md" -o ~/.claude/skills/${skill}/SKILL.md
done
mkdir -p ~/.claude/skills/subagent-pool/assets
for f in prompts research interview-protocol agent-definitions council; do
  curl -sSL "$BASE/skills/subagent-pool/assets/${f}.md" -o ~/.claude/skills/subagent-pool/assets/${f}.md
done
mkdir -p ~/.claude/agents
for agent in planning-agent implement-agent review-agent AgentArchitect \
             council-spec council-architect council-lateral council-risk; do
  curl -sSL "$BASE/agents/${agent}.agent.md" -o ~/.claude/agents/${agent}.agent.md
done
```

Así no se instalan los scripts (doctor, registro de costes, revisión de skills), y `arquitec-dev-ia` queda sin sus `assets/`. Para la instalación completa, usa `git clone`.

</details>

### Requisitos

- [Claude Code](https://claude.com/claude-code) y una carpeta `~/.claude/`.
- Python 3.10 o superior para los scripts. Solo usan la biblioteca estándar.
- Recomendado: un `.claude/project-context.md` en tu proyecto. Si no existe, el Conductor te sugiere ejecutar antes `arquitec-dev-ia`.

### Complementos opcionales

Cada uno es independiente. Sin ninguno, la skill funciona solo con Claude.

| Complemento | Qué añade | Cómo |
|---|---|---|
| **Equipos de agentes** | Los miembros del consejo debaten directamente entre ellos, en vez de por archivos | Añade `"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}` a `~/.claude/settings.json` (bandera experimental de Claude Code) |
| **Codex** | Revisión, implementación y coordinación por otro proveedor; el pensador lateral del consejo también consulta a Codex | `npm i -g @openai/codex && codex login`, y luego `cp agents/optional/codex-agent.agent.md ~/.claude/agents/` |
| **[graphify](https://github.com/safishamsi/graphify)** | `planning-agent` mapea los nodos centrales y las dependencias antes de planificar (repos de más de ~20 archivos) | `uv tool install graphifyy && graphify install` (el paquete de PyPI se llama `graphifyy`) |
| **Registro de costes** | Tokens por sesión y por modelo, subagentes incluidos | Hook `Stop` de [hooks.md](skills/subagent-pool/assets/hooks.md); informe con `cost_tracker.py report` |

---

## 🎯 Cómo se usa

Pídelo con tus palabras: `usa el conductor para…`, `delega en subagentes`, `tarea compleja: …`, o simplemente describe una funcionalidad o un refactor. Para diseñar un equipo nuevo: `diseña un equipo de agentes para…`.

Antes de planificar, el Conductor resume en una línea cómo ha leído la tarea:

```
Tier M · fix · single · urgency normal · uncertainty high · risk low — causa desconocida, módulo de auth sin tocar
```

- El **tier** es el esfuerzo: S, M o L.
- La **operación** puede ser feature, fix, tweak o refactor. Cada una tiene un primer paso obligatorio; por ejemplo, un fix empieza con un test que falla.
- El **nivel de plan** dice quién escribe el plan: single, duo o council.
- **Urgencia, incertidumbre y riesgo** son otros tres ejes. La urgencia fija la prioridad y nunca quita controles; la incertidumbre dice cuánto investigar; el riesgo, cuánta revisión de especialista.
- La línea es la primera línea obligatoria del Conductor para tier M y L. El tier S usa una sola línea: `Tier S · fix — direct`.

Si no estás de acuerdo, dilo y se hace como tú dices: `basta con un solo planner`, `que el plan lo haga el consejo`, `hazlo directo`. No hay nada más que configurar.

Esto es lo que te toca decidir:

1. **Las preguntas que cambian el plan.** Como mucho 3, cada una con una respuesta propuesta por defecto.
2. **El plan.** En el nivel council viene con un registro de decisiones (`decisions.md`) y los desacuerdos que hayan quedado abiertos.
3. **Las acciones que requieren aprobación** (borrar, migrar, secretos, push, publicar, desplegar), cuando aparezcan.
4. **El commit**, al final.

Si una tarea se interrumpe, se retoma desde `plans/{task}-state.md`; el Conductor te ofrece continuarla.

---

## 🏥 Ver a los agentes trabajando

**[Hospital de agentes](https://github.com/elisaul77/agent-hospital)** muestra en una vista isométrica y de solo lectura la actividad de Claude Code **y Codex**. Cada agente es un personaje; una sesión confirmada de subagent-pool abre el hospital completo con recepción, espera, diagnóstico, quirófano, revisión, consejo, dirección, archivo y alta. Con otra skill se muestran las salas pertinentes a la actividad observada. El consejo se convoca para decisiones importantes abiertas; su recorrido en dos pasos, desde escritorios hasta la mesa, está planificado para una versión posterior. El visor no ejecuta ni dirige agentes.

![Hospital de agentes: vista isométrica del modo demo](docs/agent-hospital.png)

```bash
git clone https://github.com/elisaul77/agent-hospital && cd agent-hospital
docker compose up -d --build
# Demo completa: http://127.0.0.1:8700/?mode=demo
docker compose -f docker-compose.yml -f compose.live.yml up -d --build
# Sesiones reales: http://127.0.0.1:8700/?mode=live
```

El modo live monta transcripciones y expedientes con `:ro`. En Codex, esta skill escribe `Hospital session: codex-<CODEX_THREAD_ID>` en el expediente cuando dispone del ID real; el visor exige también evidencia de subagentes para abrir el hospital completo. [Ver el GIF y la guía del hospital](https://github.com/elisaul77/agent-hospital).

---

## 🤔 Qué es y qué no es

**No es un framework.** Son archivos Markdown (skills y agentes) que carga Claude Code, más unos pocos scripts de Python que solo usan la biblioteca estándar. No hay servidor ni runtime.

**No es para tocar un solo archivo.** Orquestar cuesta varias veces los tokens de un solo agente, así que las tareas pequeñas se hacen directamente.

**No decide por ti.** Tú apruebas el plan y cada acción irreversible. Si la revisión falla dos veces seguidas, el Conductor se detiene y te pregunta en lugar de insistir.

**Codex es opcional y nunca sustituye a Claude Code.** Todo el flujo corre dentro de Claude Code; Codex aporta una segunda opinión.

---

## 👥 El equipo

| Agente | Rol | Escribe código del proyecto |
|---|---|---|
| **Conductor** (la skill `subagent-pool`) | Acota la tarea, elige el esfuerzo, delega y habla contigo | ❌ nunca |
| `planning-agent` | Explora el repo (con graphify si lo hay) y escribe un plan por fases | ❌ |
| `council-spec` | Consejo: qué significa "listo", en criterios que se puedan probar | ❌ |
| `council-architect` | Consejo: fases sobre los archivos reales; escribe el plan final | ❌ |
| `council-lateral` | Consejo: la opción no obvia (no construirlo, la mitad de piezas, un supuesto falso) — consulta a Codex, o a Opus sin Codex *(experimental — escrito y revisado, aún no medido en ejecuciones reales)* | ❌ |
| `council-risk` | Consejo: qué se rompe y cómo se demostrará cada afirmación | ❌ |
| `implement-agent` | Implementa una fase, empezando por el test | ✅ el único |
| `review-agent` | APPROVED / NEEDS_REVISION / FAILED, con evidencia para cada criterio | ❌ |
| `AgentArchitect` | Diseña y genera equipos especialistas para dominios nuevos | ❌ (escribe archivos de agentes) |
| `codex-agent` *(opcional)* | Puente a Codex: plan, implement, review, debug, browser, coordinate | en sandbox |

El modelo de cada agente se define en su propio archivo (`model:`) y lo decides tú. El Conductor nunca lo cambia.

---

## 🔄 Cómo avanza una tarea

**1. Admisión y triage de cuatro ejes.** El Conductor fija el objetivo y qué significa que salga bien, y luego puntúa cuatro ejes por separado: **urgencia** (prioridad; nunca quita controles), **esfuerzo** (S, M o L, abajo), **incertidumbre** (investigar, consultar o comparar alternativas) y **riesgo** (controles y revisión de especialista). El tier S se hace directo, sin archivo de caso. Para M y L el archivo de caso es `plans/{task}-state.md`. Si el diagnóstico cambia el alcance o el riesgo, el Conductor vuelve a hacer el triage.

| Tier | Señal | Flujo |
|---|---|---|
| S | 1–2 archivos, arreglo claro | Se hace directo, sin orquestar |
| M | 3–6 archivos, una sola zona | Plan, y luego implementación y revisión por fase |
| L | Módulo nuevo, refactor entre componentes, decisión de diseño | Lo mismo; el nivel de plan decide quién escribe el plan |

**2. Diagnóstico con falsador.** `planning-agent`, en modo Diagnóstico, devuelve hechos, hipótesis, evidencia, lo que falta (proyecto, especialista o usuario), la intervención propuesta y un **falsador**: la hipótesis más la observación (un comando y su resultado esperado) que la desmentiría. Dos rondas sin evidencia nueva detienen el bucle.

**3. Consultar o planificar.** Una **consulta** es un especialista que responde a una pregunta acotada (review-agent `mode=consult specialty=<x>`, o planning-agent para hechos de código) *(experimental — escrito y revisado, aún no medido en ejecuciones reales)*. El **consejo** solo se convoca cuando, tras el diagnóstico, queda abierta una decisión importante (open important decision).

| Nivel de plan | Cuándo | Quién |
|---|---|---|
| single | Enfoque claro: Tier M, o Tier L sin decisión importante abierta | `planning-agent` |
| duo | Una elección abierta que no es importante, o una petición vaga | architect + lateral, con borradores a ciegas; el architect sintetiza |
| council | Queda una decisión importante abierta tras el diagnóstico | los cuatro miembros, con una ronda de debate |

Los cambios sensibles (seguridad, una API pública, datos o dinero) suben el eje de **riesgo**: reciben revisión de especialista y nunca convocan por sí solos al consejo.

```
council   R1  borradores a ciegas ── spec · architect · lateral · risk (nadie lee a nadie)
          R2a objeciones          ── directas entre miembros, anotadas en debate.log
          R2b respuestas          ── cada uno responde lo que le objetaron
          R3  síntesis            ── architect: plans/{task}-draft.md + decisions.md
```

El Conductor solo marca las rondas; el contenido del debate nunca pasa por él. Sin la bandera de equipos, las mismas rondas se hacen por archivos. El protocolo completo está en [council.md](skills/subagent-pool/assets/council.md).

**4. Por fase, con ruteo según el origen.** `implement-agent` → `review-agent`, y Codex revisa en paralelo si está activo. Un NEEDS_REVISION también indica un `FAILURE_ORIGIN`, y el Conductor encamina el arreglo según él:

```
review ─► FAILURE_ORIGIN ─► implementation → implement-agent (máx. 2 bucles por fase)
                         ─► diagnosis      → planning-agent, citando el falsador
                         ─► scope          → nuevo triage
                         (3 re-enrutamientos por caso en total, después decides tú)
```

*Ruteo según el origen (`FAILURE_ORIGIN` y sus re-enrutamientos): experimental — escrito y revisado, aún no medido en ejecuciones reales.* Un hallazgo de un NEEDS_REVISION es vinculante: el Conductor nunca lo descarta, lo rebaja ni lo aplaza por su cuenta. Lo vuelve a delegar o te pregunta, y puedes aceptarlo como riesgo registrado.

FAILED va primero a ti. Cada fase aprobada se guarda en `plans/{task}-state.md`.

**5. Cierre: verificado, no desplegado.** Un informe final con lo que cambió, lo verificado, lo no verificado y los riesgos. Cerrar un caso significa que está verificado. Nunca autoriza publicar ni desplegar, que siguen siendo de nivel de aprobación. El commit espera tu visto bueno.

---

## 🧠 Las diez cosas que no son obvias

### 1. El plan es una decisión de equipo, y el equipo no debe ponerse de acuerdo demasiado pronto

Los agentes de un mismo modelo que ven las ideas de los demás acaban dando la misma respuesta. Por eso los borradores del consejo son a ciegas y solo hay una ronda de debate, con límites estrictos. Además, todas las propuestas del lateral quedan en `decisions.md`, se acepten o no, para que puedas imponer la que prefieras.

### 2. El esfuerzo se ajusta a la tarea

Un sistema multiagente gasta unas 15 veces los tokens de un chat. Orquestar algo pequeño es un error, no rigor.

### 3. Fork o subagente nuevo: decide el tamaño del contexto

Un fork hereda el contexto del Conductor. Por debajo de **~75k tokens** cuesta un 50 % menos que un subagente nuevo; por encima cuesta el doble. En nuestras pruebas la precisión fue la misma.

### 4. El Conductor puede ir en Sonnet

En una tarea con 19 criterios ocultos, Sonnet igualó a Opus con un **−39 % de coste**. Opus compensa en las decisiones de diseño del tier L.

### 5. Nada de `/advisor` con esta skill

El advisor relee toda la conversación sin caché en cada llamada, y cada subagente la hereda. Sonnet con un advisor Opus costó un **+150 %**, con la misma precisión y una delegación errática.

### 6. "Evita lo predecible" aumenta la originalidad

En 290 generaciones, pedir de forma explícita que se evite la primera idea subió la originalidad **+2,00 (Sonnet) y +2,80 (Opus)**. Halagar o insultar no ayudó. Por eso todos los prompts creativos de la skill incluyen esa frase.

### 7. Toda afirmación necesita evidencia, y se apunta de qué nivel es

Cada criterio de aceptación se marca como `[OBSERVED]`, `[DERIVED]`, `[INFERRED]` o `[UNKNOWN]`. Un comportamiento solo se da por cumplido cuando alguien lo ejecutó y vio el resultado. Los agentes también listan lo que **no** verificaron.

### 8. Codex nunca revisa a Codex

Un modelo que hace de juez tiende a preferir su propio texto ([arXiv 2410.21819](https://arxiv.org/abs/2410.21819)), así que la revisión siempre la hace el otro proveedor. Tampoco hay nombres de modelo fijos en el código: se usa la versión más reciente de cada familia que aparece en la caché local de Codex.

### 9. Codex puede anidar agentes; los subagentes de Claude no

Los subagentes de Claude no tienen ninguna herramienta para lanzar otros agentes. Una sesión de Codex sí, así que `codex-agent mode=coordinate` reparte fases independientes dentro de Codex. Usa roles sincronizados desde nuestros archivos de agentes, y Claude sigue revisando cada fase. Además, un agente nuevo de Claude solo carga tras reiniciar, mientras que un rol nuevo de Codex se puede usar al momento.

### 10. El modelo principal nunca lee una skill externa

Las skills de terceros se revisan en dos contenedores aislados. Primero pasa un análisis previo sin red, y después un revisor cuya única salida es un proxy con lista blanca. Apruebas cada ejecución sabiendo su coste estimado, y el Conductor solo recibe el veredicto y la ruta del informe.

---

## 📊 Medido, no estimado

Son mediciones sobre tareas de prueba, sacadas de [`research.md`](skills/subagent-pool/assets/research.md) y del [CHANGELOG](CHANGELOG.md). No garantizan el mismo resultado en tu proyecto.

| Medida | Resultado | Detalle |
|---|---|---|
| El mismo prompt en inglés y en español | **−30 %** de tokens de entrada | [research](skills/subagent-pool/assets/research.md#language-and-tokens-own-measurement-2026-10-10) |
| Fork frente a subagente nuevo | Fork ~50 % más barato con menos de ~75k de contexto, ~2× por encima; misma precisión | [research](skills/subagent-pool/assets/research.md#fork-vs-fresh-subagent-own-measurement-2026-10-10) |
| Conductor en Sonnet frente a Opus | 19/19 en ambos; **−39 %** de coste (n = 5) | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| `/advisor` sobre Sonnet | **+150 %** de coste, misma precisión | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| "Evita lo predecible" | **+2,00** Sonnet (p = 0,005), **+2,80** Opus (p < 0,001); 290 muestras | [research](skills/subagent-pool/assets/research.md#own-experiment-2026-10-0910-spelling-and-tone-vs-creativity) |
| Multiagente frente a chat | ~15× tokens (referencia de Anthropic) | [research §2](skills/subagent-pool/assets/research.md#2-effort-scaling-and-multi-agent-cost) |

El coste del consejo (entre 4 y 6 veces el de un plan simple) todavía es una estimación; mira [Lo que falta](#%EF%B8%8F-lo-que-falta).

### Qué se midió

- **Banco A/B** (`competition/`): 10 ejecuciones válidas de 12 directorios de ejecución, resultados iguales entre versiones. Cada ejecución está listada en [competition/RESULTS.md](competition/RESULTS.md). En una, la v9.10 ignoró un NEEDS_REVISION, y de ahí salió la regla de revisión vinculante (v9.12).
- **Uso real** (un proyecto de Forja y el caso del Hospital): el bloque de WARNINGS, la regla de no ejecutar git por parte del Conductor y la línea de orquestación explícita (v9.12) salen de ahí.
- **Aún sin medir:** el enrutamiento por FAILURE_ORIGIN, los re-enrutamientos, la consulta y la segunda voz del lateral. Son experimentales (marcados arriba).

---

## 📖 Respaldado por investigación reciente

Solo informativo: lo que dicen papers de 2026 (y una referencia de 2025) sobre reglas que esta skill ya aplica. Las cifras son de los autores, tomadas de los resúmenes; no se reprodujeron aquí.

| Paper | Hallazgo | Dónde aparece aquí |
|---|---|---|
| Engineering Reliable Commit Gates for Agentic AI — [doi:10.48550/arXiv.2609.10969](https://doi.org/10.48550/arXiv.2609.10969) | Votos entre modelos sobre la **misma** evidencia aprobaron 62,9 % de propuestas inseguras frente a 22,9 % con una fuente **independiente**; la fuente pesa más que la diversidad de modelos (40,9 vs 11,3 pts) | `INDEPENDENT_CHECK` del revisor; revisión cruzada con Codex |
| The Working Set of a Coding Agent: Coherence Debt — [doi:10.48550/arXiv.2608.16630](https://doi.org/10.48550/arXiv.2608.16630) | Sin un dato, los agentes inventan en vez de decir que están bloqueados; un archivo de convenciones obsoleto puede costar más que ninguno | Niveles de evidencia; `UNKNOWNS` |
| The Cost of Consensus (Bertalanič & Fortuna) — [doi:10.48550/arXiv.2605.00914](https://doi.org/10.48550/arXiv.2605.00914) | Debate sin roles entre 10 modelos iguales: hasta 85,5 % de conformidad con la mayoría, 2,1–3,4× tokens para igual o menor precisión | Consejo: roles distintos, borradores a ciegas, lateral de otro proveedor |
| How Coding Agents Fail Their Users — [doi:10.48550/arXiv.2605.29442](https://doi.org/10.48550/arXiv.2605.29442) | 20.574 sesiones reales: el 91,49 % de las correcciones visibles las hizo el usuario; crecen los autoinformes falsos | `[OBSERVED]` vs `[INFERRED]`, `NOT_VERIFIED` |
| TraceDev — [doi:10.48550/arXiv.2607.18886](https://doi.org/10.48550/arXiv.2607.18886) | Un Validador mantiene un grafo requisito → diseño → código; hasta 186–340 % sobre las baselines | `RF-n` + carpeta de spec (v9.13) |
| AdaptOrch — [doi:10.48550/arXiv.2602.16873](https://doi.org/10.48550/arXiv.2602.16873) | Topología elegida por el grafo de dependencias: +12–23 % con los mismos modelos | Tier y nivel de plan por tarea |
| Why Do Multi-Agent LLM Systems Fail? (Cemri et al.) — [doi:10.48550/arXiv.2503.13657](https://doi.org/10.48550/arXiv.2503.13657) | Taxonomía de referencia: diseño del sistema, desalineación entre agentes, verificación | Enrutado de revisiones por `FAILURE_ORIGIN` |

Puntos abiertos que plantean (en estudio, todavía no están en la skill): una revisión de Codex que ejecute sus propias comprobaciones en vez de leer el informe del implementador, un control de `project-context.md` desactualizado y los datos que necesita cada edición dentro del brief.

---

## 🧪 Tests

```bash
python3 -B -m unittest discover -s skills/subagent-pool/scripts
```

**228 tests**, solo con la biblioteca estándar. Dos se saltan en Python < 3.11 porque necesitan `tomllib`.

| Archivo | Tests | Qué cubre |
|---|---|---|
| `test_skills_lib.py` | 103 | Biblioteca de skills revisadas: esquema, reglas de veto, búsqueda y nueva revisión si cambia la fuente |
| `test_codex_models.py` | 15 | Registro de modelos de Codex: orden de versiones y caché ausente, corrupta o vieja |
| `test_skill_prescan.py` | 13 | Análisis previo sin red sobre un ejemplo benigno y otro malicioso |
| `test_trim_output.py` | 12 | El recorte de la salida de tests nunca pierde una línea de fallo (con salida real de unittest y pytest) |
| `test_cost_tracker.py` | 9 | Registro de costes: deduplicación de ids en streaming, subagentes, informe |
| `test_install.py` | 14 | Instalador: dry run, fusión de settings sin sobrescribir, copia de seguridad, bloque de CLAUDE.md, complemento Codex |
| `test_doctor.py` | 10 | Chequeo de instalación: desajustes, equipos remotos, roles de Codex, consejo, bandera de equipos |
| `test_sync_codex_agents.py` | 9 | Sincronización de agentes a roles de Codex: escapado TOML, bloques YAML, archivos ajenos |
| `test_instincts.py` | 4 | Almacén de lecciones por proyecto |
| `test_mutate.py` | 4 | La prueba de mutación corre en una copia aislada |
| `test_council.py` | 5 | Los agentes del consejo tienen `SendMessage` y el protocolo coincide con la skill |
| `test_caseflow.py` | 30 | Las reglas del flujo de casos están escritas (solo estructura, no comportamiento de enrutamiento) |

`skill-review.sh` no tiene tests automáticos; su `--dry-run` imprime todos los comandos sin ejecutarlos.

---

## 🔒 Seguridad

- **Niveles de aprobación.** Lo que se edita dentro del alcance aprobado y los tests van solos. Cualquier cosa fuera de ese alcance se reporta. Borrar, migrar, tocar secretos, hacer push, publicar o desplegar vuelve como `BLOCKED` hasta que lo apruebas.
- **Codex** corre en sandbox (`read-only`, y como mucho `workspace-write`). El miembro lateral del consejo solo llama a Codex (`read-only`) o a Opus (sin herramientas).
- **Las skills externas** se descargan solo de fuentes oficiales (`anthropics/skills`, `openai/skills`, `vercel-labs/agent-skills`) y se revisan en dos contenedores:
  - Análisis previo: `--network none`, con la skill montada en solo lectura.
  - Revisor: su única salida es un proxy squid con lista blanca hacia la API del modelo.
  - Ambos corren con `--read-only`, `--cap-drop ALL`, `no-new-privileges`, un usuario no root y límites de memoria y procesos.
  - Ante cualquier duda (enlaces simbólicos, archivos opacos, un análisis previo cortado), un APPROVED pasa a DOUBTFUL.

**Riesgo residual aceptado:** el revisor tiene una credencial de solo lectura junto a texto no confiable. Usa una clave dedicada y limitada. Los detalles están en [skills-library.md](skills/subagent-pool/assets/skills-library.md).

---

## 📁 Estructura

```
Orquestacion_Agentes_claude/
├── AGENTS.md · INSTALL.md · CHANGELOG.md · LICENSE · FUNDING.md
├── README.md · README.es.md · docs/banner.png
├── agents/
│   ├── planning-agent.agent.md        # Plan por fases (graphify)
│   ├── implement-agent.agent.md       # Código y tests, una fase cada vez
│   ├── review-agent.agent.md          # Veredicto con niveles de evidencia
│   ├── council-spec.agent.md          # Consejo: criterios de aceptación
│   ├── council-architect.agent.md     # Consejo: fases y síntesis final
│   ├── council-lateral.agent.md       # Consejo: la opción no obvia (consulta a Codex, o a Opus sin Codex)
│   ├── council-risk.agent.md          # Consejo: riesgos y verificación
│   ├── AgentArchitect.agent.md        # Diseña equipos especialistas nuevos
│   └── optional/codex-agent.agent.md  # Puente a OpenAI Codex
└── skills/
    ├── subagent-pool/                 # El Conductor
    │   ├── SKILL.md
    │   ├── assets/
    │   │   ├── prompts.md             # Plantillas y contratos de respuesta
    │   │   ├── council.md             # Protocolo del consejo de plan
    │   │   ├── agent-definitions.md · interview-protocol.md
    │   │   ├── research.md            # Evidencia detrás de cada regla
    │   │   ├── hooks.md               # Hook opcional del registro de costes
    │   │   ├── codex-modes.md · codex-verdict.schema.json
    │   │   ├── skills-library.md · skill-review-prompt.md · official-sources.json
    │   │   └── skills-probadas-template/
    │   └── scripts/
    │       ├── install.py             # Instalador (copia de seguridad, fusión, complementos)
│       ├── doctor.py              # Chequeo de instalación, solo lectura
    │       ├── trim_output.py         # Recorta la salida de tests sin perder ningún fallo
    │       ├── cost_tracker.py        # Registro de tokens (hook Stop) e informe
    │       ├── instincts.py           # Lecciones por proyecto
    │       ├── mutate.py              # ¿Los tests detectan fallos inyectados?
    │       ├── sync_codex_agents.py   # Agentes → roles de Codex
    │       ├── codex-models.py        # Modelo de Codex más reciente por familia
    │       ├── skills_lib.py · skill_prescan.py · skill-review.sh
    │       ├── test_*.py              # 228 tests
    │       └── fixtures/
    ├── arquitec-dev-ia/               # Documentación de contexto para IA; escribe project-context.md
    └── graphify/                      # Skill de grafo de conocimiento
```

---

## 📚 Documentación

| Documento | Contenido |
|---|---|
| [SKILL.md](skills/subagent-pool/SKILL.md) | El Conductor: tiers, niveles de plan, gobierno, flujo, Codex y revisión de skills |
| [council.md](skills/subagent-pool/assets/council.md) | Consejo de plan: rondas, límites de mensajes y modo por archivos |
| [prompts.md](skills/subagent-pool/assets/prompts.md) | Plantillas y contratos de respuesta de cada agente |
| [agent-definitions.md](skills/subagent-pool/assets/agent-definitions.md) | Roles, herramientas y resolución de problemas |
| [interview-protocol.md](skills/subagent-pool/assets/interview-protocol.md) | Diseño de equipos nuevos con AgentArchitect |
| [research.md](skills/subagent-pool/assets/research.md) | Evidencia y fuentes de cada regla |
| [hooks.md](skills/subagent-pool/assets/hooks.md) | Hook del registro de costes |
| [codex-modes.md](skills/subagent-pool/assets/codex-modes.md) | Recetas de Codex `debug` (Docker) y `browser` (Chrome Flatpak) |
| [skills-library.md](skills/subagent-pool/assets/skills-library.md) | Biblioteca de skills revisadas y revisión controlada |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |

---

## 🗺️ Lo que falta

- **El enrutamiento aún no se mide.** El banco A/B hizo 10 ejecuciones válidas con resultados iguales ([competition/RESULTS.md](competition/RESULTS.md)), pero el enrutamiento por FAILURE_ORIGIN, los re-enrutamientos y la consulta son experimentales: escritos y revisados, aún no medidos en ejecuciones reales. Los tests del flujo de casos comprueban que las reglas están escritas, no que un modelo las siga.
- **El consejo aún no se ha medido en un proyecto real.** Falta comparar un plan del consejo con el de un solo planner y medir su coste real; lo de 4 a 6 veces es una estimación.
- **Los equipos de agentes son una bandera experimental de Claude Code** y pueden cambiar. Si cambian, el consejo pasa al modo por archivos.
- **El revisor del contenedor 2 no se ha ejecutado de principio a fin** con una skill real.
- **`codex debug` dentro de Docker:** no está comprobado que Codex sea accesible desde el contenedor.
- **Fechas de lanzamiento de los modelos:** la tabla de `skills-library.md` tiene entradas `TODO`, así que por ahora la regla de frescura marca al candidato en vez de descartarlo.

---

## 🤝 Contribuir

1. Haz un fork y crea una rama (`feat/…`, `docs/…`).
2. Escribe los commits con el formato `type(scope): message`.
3. Pasa los tests antes de abrir el PR.
4. Describe el cambio en el Pull Request.

Las ideas son bienvenidas: agentes especialistas, ejemplos de uso, escenarios de orquestación con sus tests. Reporta los errores en [GitHub Issues](https://github.com/elisaul77/Orquestacion_Agentes_claude/issues).

## 💖 Apoya el proyecto

Si te ahorra tiempo, dale una estrella al repo, compártelo y cuenta lo que encuentres. Las opciones de apoyo económico están en [FUNDING.md](FUNDING.md).

## 📄 Licencia

MIT — ver [LICENSE](LICENSE). Copyright (c) 2026 Elisaul Florez ([@elisaul77](https://github.com/elisaul77)).
