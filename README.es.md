# 🤖 Orquestacion Agentes Claude

🌐 **Español** · [English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-v9.5.0-blueviolet.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-131%20passing-3fb950.svg)](#-tests)
[![Claude Code](https://img.shields.io/badge/cerebro-Claude%20Code-8a63f0.svg)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-opcional-412991.svg)](#codex-opcional)

[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsors-pink?style=for-the-badge&logo=githubsponsors)](https://github.com/sponsors/elisaul77)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?style=for-the-badge&logo=paypal)](https://paypal.me/eflorezp)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buymeacoffee)](https://buymeacoffee.com/elisaul77)

**El Conductor planifica y reparte; los subagentes ejecutan, y otro agente revisa cada fase.**
Para tareas complejas de Claude Code (3 o más archivos, un módulo nuevo, un refactor) con un plan que apruebas tú, revisión automática por fase y reglas claras de lo que cada agente puede hacer sin preguntar.

```
tú ──> Conductor (planifica, nunca toca código)
         |
         |--> planning-agent ──> plans/*.md ──> (tu aprobación)
         |
         |--> implement-agent ──> review-agent ──> APPROVED | NEEDS_REVISION
         |                             ^
         |             codex-agent ----+  revisión cruzada (opcional)
         |
         |--> AgentArchitect ──> equipos de agentes nuevos
         |
         '--> skill externa ──> revisión aislada ──> biblioteca privada (por ruta)
```

---

## 🚀 Puesta en marcha

```bash
git clone https://github.com/elisaul77/Orquestacion_Agentes_claude.git
cd Orquestacion_Agentes_claude

cp -r skills/subagent-pool skills/arquitec-dev-ia skills/graphify ~/.claude/skills/
cp agents/*.agent.md ~/.claude/agents/
```

Después, en Claude Code, pide la orquestación con cualquiera de estas frases: `usa el conductor para…`, `delega en subagentes`, `tarea compleja: …`. Para diseñar un equipo nuevo: `diseña un equipo de agentes para…`.

<details>
<summary>Sin git: instalación con curl (núcleo: Conductor y 4 agentes)</summary>

```bash
BASE=https://raw.githubusercontent.com/elisaul77/Orquestacion_Agentes_claude/master
for skill in subagent-pool arquitec-dev-ia graphify; do
  mkdir -p ~/.claude/skills/${skill}
  curl -sSL "$BASE/skills/${skill}/SKILL.md" -o ~/.claude/skills/${skill}/SKILL.md
done
mkdir -p ~/.claude/skills/subagent-pool/assets
for f in prompts research interview-protocol agent-definitions; do
  curl -sSL "$BASE/skills/subagent-pool/assets/${f}.md" -o ~/.claude/skills/subagent-pool/assets/${f}.md
done
mkdir -p ~/.claude/agents
for agent in planning-agent implement-agent review-agent AgentArchitect; do
  curl -sSL "$BASE/agents/${agent}.agent.md" -o ~/.claude/agents/${agent}.agent.md
done
```

Para la instalación completa (incluidos los scripts de revisión de skills) usa la opción con `git clone`.

`arquitec-dev-ia` instalado así solo tiene su `SKILL.md` (sin `assets/` ni `references/`); usa `git clone` para la skill completa.

</details>

### Necesitas

- [Claude Code](https://claude.com/claude-code) y una carpeta `~/.claude/`.
- [graphify](#-graphify), recomendado en repos de más de 20 archivos: `planning-agent` lo usa para mapear el proyecto antes de planear.
- Opcional: `.claude/project-context.md` en tu proyecto. Si falta, el Conductor te sugiere `arquitec-dev-ia` antes de orquestar.

### Codex opcional

Solo si además tienes suscripción a ChatGPT/Codex. Sin ella el skill funciona solo con Claude, sin coste extra.

```bash
npm i -g @openai/codex && codex login          # una vez
cp agents/optional/codex-agent.agent.md ~/.claude/agents/
cp skills/subagent-pool/assets/codex-verdict.schema.json ~/.claude/skills/subagent-pool/assets/
```

Con el puente activo, el Conductor siempre cruza proveedores: si Claude implementa, Claude y Codex revisan en paralelo; si Codex implementa, revisa Claude. Los modelos se eligen solos desde tu caché local de Codex (ver [Las siete cosas](#6-nunca-revisa-codex-lo-que-hizo-codex)).

---

## 🤔 Qué es y qué no

**No es un framework.** Son ficheros Markdown (skills y agentes) que Claude Code carga. No hay servidor ni runtime; lo único ejecutable son los scripts de revisión de skills en `skills/subagent-pool/scripts/`.

**No sirve para arreglar un archivo.** Una tarea pequeña se hace directa: orquestar cuesta varias veces más tokens que un solo agente. El Conductor decide el esfuerzo según el tamaño (tier S, M o L).

**No decide por ti.** Apruebas el plan. Las acciones irreversibles (borrar, migrar, secretos, push, publicar, desplegar) pasan siempre por ti. Tras dos vueltas de revisión sin aprobar, el Conductor escala en lugar de seguir.

**Codex es opcional.** Mejora la revisión, pero nunca es una dependencia. Y no reemplaza a Claude Code: todo el flujo corre dentro de Claude Code.

---

## 🧠 Las siete cosas que no son obvias

### 1. El esfuerzo se escala al tamaño

Tier S (1–2 archivos, arreglo claro): no se orquesta. Tier M (3–6 archivos en una zona): planning, luego implement y review por fase, con una sola pausa para el plan. Tier L (módulo nuevo o decisión de diseño): además una ronda divergente antes de planear. Un sistema multi-agente gasta unas 15 veces los tokens de un chat, así que orquestar lo pequeño es un fallo, no rigor.

### 2. Fork o subagente fresco: decide el tamaño del contexto

Un fork hereda el contexto del Conductor. Por debajo de **~75k tokens** cuesta unas 50 % menos que un subagente fresco; por encima sale unas 2 veces más caro. En las pruebas la precisión no cambió, así que el Conductor elige según el contexto que tenga en ese momento.

### 3. El Conductor puede correr en Sonnet

En una tarea de 19 criterios ocultos, Sonnet acertó lo mismo que Opus con **−39 % de coste**. Si estás en Opus para una tarea de tier S o M, `/model sonnet` basta. La decisión es tuya.

### 4. Nada de `/advisor` con este skill

El advisor relee toda la conversación sin caché en cada llamada, y cada subagente hereda ese contexto. Sonnet con advisor Opus costó **+150 %** más que Sonnet solo, con la misma precisión y una delegación errática (entre 0 y 5 subagentes).

### 5. «Evita lo predecible» sube la originalidad

En 290 generaciones, la instrucción explícita de evitar la primera idea y lo típico subió la originalidad **+2,00 con Sonnet y +2,80 con Opus**. Elogio, insulto o erratas no dieron el mismo efecto. Por eso cada ronda creativa del skill lleva esa instrucción literal.

### 6. Nunca revisa Codex lo que hizo Codex

Un juez LLM tiende a preferir su propio texto (sesgo de autopreferencia, [arXiv 2410.21819](https://arxiv.org/abs/2410.21819)), así que el revisor siempre es de otro proveedor. Y no hay slugs de modelo escritos a mano: `codex-models.py` toma la última versión de cada familia (astra, sol, terra, luna) desde `~/.codex/models_cache.json`, comparando versiones numéricamente.

### 7. El modelo principal nunca lee una skill externa

Cada skill de terceros se revisa en dos contenedores aislados: un pre-scan sin red y un revisor cuya única salida es un proxy de allow-list. El pre-scan solo puede bajar un APPROVED a DOUBTFUL, nunca al revés. Apruebas cada ejecución con el coste estimado. El Conductor recibe solo el JSON del veredicto y la ruta del informe, nunca el código de la skill.

---

## 📊 Medido, no estimado

Cifras tomadas de [`research.md`](skills/subagent-pool/assets/research.md) y [CHANGELOG.md](CHANGELOG.md). Son mediciones sobre tareas de prueba, no garantías para tu proyecto.

| Medida | Resultado | Detalle |
|---|---|---|
| Mismo prompt en inglés vs español | **−30 %** tokens de entrada | [research](skills/subagent-pool/assets/research.md#language-and-tokens-own-measurement-2026-10-10) |
| Fork vs subagente fresco | Fork ~50 % más barato bajo ~75k de contexto, ~2× encima; precisión igual | [research](skills/subagent-pool/assets/research.md#fork-vs-fresh-subagent-own-measurement-2026-10-10) |
| Conductor Sonnet vs Opus | 19/19 en ambos; **−39 %** de coste (n = 5) | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| `/advisor` sobre Sonnet | **+150 %** de coste, misma precisión | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| «Evita lo predecible» | **+2,00** Sonnet (p = .005), **+2,80** Opus (p < .001); 290 muestras | [research](skills/subagent-pool/assets/research.md#own-experiment-2026-10-0910-spelling-and-tone-vs-creativity) |
| Multi-agente vs chat | ~15× tokens (referencia de Anthropic) | [research §2](skills/subagent-pool/assets/research.md#2-effort-scaling-and-multi-agent-cost) |

---

## 🧪 Tests

```bash
python3 -B -m unittest discover -s skills/subagent-pool/scripts
```

**131 tests**, solo biblioteca estándar de Python:

- `test_skills_lib.py` (103): validador de la biblioteca de skills revisadas. Esquema de `index.json` y `vetadas.json`, reglas de veto, búsqueda y re-revisión cuando el origen cambia.
- `test_skill_prescan.py` (13): pre-scan estático sobre los fixtures `skill-benign` y `skill-malicious`.
- `test_codex_models.py` (15): registro de modelos Codex. Comparación de versiones y caché ausente, corrupta o vieja.

`skill-review.sh` no tiene tests automáticos: su modo `--dry-run` imprime cada comando sin ejecutar ninguno.

---

## 🔒 Seguridad

La revisión de skills externas es la única parte que trata código de terceros:

- **Solo fuentes oficiales:** `anthropics/skills`, `openai/skills` y `vercel-labs/agent-skills`. Los agregadores solo apuntan al repo oficial, nunca dan contenido.
- **Contenedor 1 (pre-scan):** sin red (`--network none`), skill montada de solo lectura.
- **Contenedor 2 (revisor):** red interna cuya única salida es un proxy squid de allow-list, solo hacia la API del modelo.
- **Ambos:** `--read-only`, `--cap-drop ALL`, `no-new-privileges`, usuario no root, límites de memoria y de procesos.
- **Aprobación en cada ejecución:** `--approved-by-user`, sin consentimiento recordado. Cualquier duda (symlinks, ficheros opacos, pre-scan truncado) convierte APPROVED en DOUBTFUL.
- **Codex** corre como mucho con `workspace-write`; las acciones de tipo Approve vuelven como `BLOCKED`.

**Riesgo residual aceptado:** el revisor tiene una credencial de solo lectura junto a texto no confiable. Usa una clave dedicada y acotada para las revisiones, nunca la credencial de tu cuenta principal. Detalle en [skills-library.md](skills/subagent-pool/assets/skills-library.md).

---

## 📁 Estructura

```
Orquestacion_Agentes_claude/
├── .github/FUNDING.yml                # Botón de patrocinio de GitHub
├── AGENTS.md                          # Vista general, reglas y diagrama del sistema
├── CHANGELOG.md                       # Historial de versiones
├── FUNDING.md                         # Formas de apoyar el proyecto
├── LICENSE
├── README.md · README.es.md
├── agents/
│   ├── planning-agent.agent.md        # Investiga y redacta el plan (con graphify)
│   ├── implement-agent.agent.md       # Implementa código y tests por fase
│   ├── review-agent.agent.md          # Revisa y valida cada fase
│   ├── AgentArchitect.agent.md        # Diseña equipos de agentes nuevos
│   └── optional/
│       └── codex-agent.agent.md       # Puente opcional a OpenAI Codex
└── skills/
    ├── subagent-pool/                 # El Conductor (skill principal)
    │   ├── SKILL.md
    │   ├── assets/                    # Plantillas, evidencia y revisión de skills
    │   │   ├── prompts.md · agent-definitions.md · interview-protocol.md
    │   │   ├── research.md · codex-modes.md · codex-verdict.schema.json
    │   │   ├── skills-library.md · skill-review-prompt.md · official-sources.json
    │   │   └── skills-probadas-template/   # plantilla para tu repo privado de skills
    │   └── scripts/
    │       ├── codex-models.py        # Registro de modelos Codex (última versión por familia)
    │       ├── skills_lib.py          # Validador y búsqueda de la biblioteca
    │       ├── skill_prescan.py       # Pre-scan estático offline
    │       ├── skill-review.sh        # Revisión con gate en dos contenedores
    │       ├── test_*.py              # 131 tests (ver Tests)
    │       └── fixtures/              # Skills de prueba: una benigna, una maliciosa
    ├── arquitec-dev-ia/
    │   ├── SKILL.md                   # Documentación de contexto para IA
    │   ├── assets/                    # Plantillas (AGENTS, project-context, skill, Mermaid)
    │   └── references/docs.md
    └── graphify/
        ├── SKILL.md                   # Grafo de conocimiento (ver Graphify)
        └── .graphify_version
```

---

## 🧭 Graphify

**[graphify](https://github.com/safishamsi/graphify)** es una herramienta de terceros que convierte un repo (código, docs, PDFs, imágenes) en un grafo de conocimiento consultable. Si existe `graphify-out/`, `planning-agent` lo usa para encontrar los nodos centrales y las dependencias antes de planear.

```bash
uv tool install graphifyy   # el paquete en PyPI se llama graphifyy; el comando es graphify
graphify install            # registra el skill en Claude Code
```

---

## 📚 Documentación

| Documento | Contenido |
|---|---|
| [SKILL.md](skills/subagent-pool/SKILL.md) | El Conductor: reglas, tiers, flujo, Codex y revisión de skills |
| [prompts.md](skills/subagent-pool/assets/prompts.md) | Plantillas de tarea y contratos de retorno |
| [agent-definitions.md](skills/subagent-pool/assets/agent-definitions.md) | Roles, reglas de delegación y solución de problemas |
| [interview-protocol.md](skills/subagent-pool/assets/interview-protocol.md) | Protocolo completo para diseñar equipos (AgentArchitect) |
| [research.md](skills/subagent-pool/assets/research.md) | Evidencia y fuentes de cada regla |
| [codex-modes.md](skills/subagent-pool/assets/codex-modes.md) | Recetas de `debug` (Docker) y `browser` (Chrome de Flatpak) |
| [skills-library.md](skills/subagent-pool/assets/skills-library.md) | Biblioteca de skills revisadas y revisión con gate |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones y limitaciones conocidas |

---

## 🗺️ Lo que falta

- **Revisor del contenedor 2 sin probar de extremo a extremo** sobre una skill real.
- **`codex debug` dentro de Docker:** la alcanzabilidad desde el contenedor no está verificada.
- **Fechas de lanzamiento de modelos:** la tabla de `skills-library.md` tiene entradas `TODO`. Mientras tanto, la regla de frescura marca el candidato en lugar de descartarlo.
- **Modelo de decisión** para las llamadas de vetting (Decisions API de OpenAI o un decididor `luna`): aplazado hasta tener medidas.

---

## 🤝 Contribuir

1. Haz fork del repo y crea una rama (`feat/mi-mejora`, `docs/…`).
2. Sigue las convenciones del proyecto y los commits `tipo(ámbito): mensaje`.
3. Corre los tests antes del PR (ver [Tests](#-tests)).
4. Abre un Pull Request que describa el cambio.

Ideas: agentes especialistas (frontend, DevOps, ML), ejemplos de uso y escenarios de orquestación con sus tests. Reporta bugs en [GitHub Issues](https://github.com/elisaul77/Orquestacion_Agentes_claude/issues).

---

## 💖 Apoya el proyecto

Si te ahorra tiempo: ⭐ dale una estrella al repo, comparte el proyecto con otros usuarios de Claude Code y reporta lo que encuentres. Si quieres aportar dinero, las formas están en [FUNDING.md](FUNDING.md): GitHub Sponsors, PayPal, Buy Me a Coffee, Ko-fi y Patreon.

---

## 📄 Licencia

MIT — ver [LICENSE](LICENSE). Copyright (c) 2026 Elisaul Florez ([@elisaul77](https://github.com/elisaul77)).
