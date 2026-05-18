---
name: arquitect-dev-ia
description: >
  Documentación de contexto IA para proyectos: AGENTS.md, CLAUDE.md, copilot-instructions.md,
  skills y diagramas Mermaid. NO crea agentes ejecutables (.agent.md) — para eso usar AgentArchitect.
  Trigger: Cuando se necesite crear o refactorizar documentación de contexto para que agentes IA
  entiendan el proyecto, sus convenciones y su arquitectura.
license: MIT
metadata:
  author: eliflowi
  version: "2.0"
  scope: [root]
  auto_invoke: "Crear AGENTS.md, CLAUDE.md, copilot-instructions.md, documentar arquitectura, estructurar proyecto para IA"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, WebFetch, WebSearch, Task
---

# Arquitecto de Documentación de Contexto IA

> Skill para crear y mantener **documentación de contexto** orientada a agentes IA:
> `AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`, skills y diagramas Mermaid.
>
> ⚠️ **Límite de responsabilidad**: Esta skill NO crea agentes ejecutables (`.agent.md`).
> Para diseñar y generar equipos de agentes Claude Code → usar **AgentArchitect**.

---

## Cuándo Usar

| ✅ Esta skill | ❌ Usar AgentArchitect en su lugar |
|---|---|
| Crear/actualizar `AGENTS.md` (root o componente) | Crear agentes `.agent.md` en `.claude/agents/` |
| Crear/actualizar `CLAUDE.md` | Diseñar equipos Conductor + especialistas |
| Crear/actualizar `copilot-instructions.md` | Definir herramientas y modelos de agentes |
| Crear nuevas skills (SKILL.md) | Establecer jerarquía de orquestación |
| Documentar arquitectura con diagramas Mermaid | |
| Estructurar mono-repo para trabajo con IA | |
| Definir convenciones y cultura del proyecto | |
| Reducir contexto innecesario para evitar alucinaciones | |

---


## Filosofía Central

```mermaid
flowchart TD
    USER["👤 Usuario"] -->|petición| AGENT["🤖 Agente\nOrquestador"]
    AGENT -->|"1. consulta"| AGENTS_ROOT["📄 AGENTS.md Root"]
    AGENTS_ROOT -->|"2. dirige a"| AGENTS_COMP["📄 AGENTS.md\nComponente"]
    AGENTS_COMP -->|"3. invoca"| SKILL["⚡ Skill\nEspecífica"]
    SKILL -->|"4. contexto preciso"| AGENT
    AGENT -->|"5. trabaja"| CODEBASE["💻 Codebase"]
    CODEBASE -->|"6. resultado"| USER

    style AGENTS_ROOT fill:#4caf50,color:#fff
    style SKILL fill:#2196f3,color:#fff
    style AGENT fill:#ff9800,color:#fff
```

**Principio clave**: Menos contexto = menos alucinación. El agente solo debe recibir
lo que necesita, cuando lo necesita.

---

## Arquitectura de Documentación IA

### Jerarquía de Archivos

```mermaid
flowchart TB
    subgraph ROOT["📁 Raíz del Proyecto"]
        AGENTS_ROOT["AGENTS.md\n(índice general)"]
        CLAUDE_MD["CLAUDE.md\n(contexto para Claude Code)"]
        COPILOT["copilot-instructions.md\n(para GitHub Copilot)"]
    end

    subgraph COMPS["📁 Componentes / Sub-proyectos"]
        AGENTS_A["componenteA/AGENTS.md"]
        AGENTS_B["componenteB/AGENTS.md"]
        COPILOT_A["componenteA/.github/copilot-instructions.md"]
    end

    subgraph SKILLS["📁 .claude/skills/"]
        SK1["skill-a/SKILL.md"]
        SK2["skill-b/SKILL.md"]
        SK3["skill-c/SKILL.md\n+ assets/\n+ references/"]
    end

    AGENTS_ROOT -->|"referencia a"| COMPS
    AGENTS_ROOT -->|"lista disponibles"| SKILLS
    AGENTS_A -->|"invoca"| SK1
    AGENTS_A -->|"invoca"| SK2
    AGENTS_B -->|"invoca"| SK3

    style ROOT fill:#e8f5e9
    style SKILLS fill:#e3f2fd
    style COMPS fill:#fff3e0
```

### Regla de Tamaño

| Archivo | Líneas Recomendadas | Máximo |
|---------|-------------------|--------|
| `AGENTS.md` root | ~150 | 250 |
| `AGENTS.md` componente | ~150 | 300 |
| `copilot-instructions.md` | ~100 | 250 |
| `SKILL.md` | ~100 | 300 |

> **Si supera el máximo → dividir en archivos por componente o extraer a skills.**

---

## Patrón: AGENTS.md Root

El AGENTS.md root es el **punto de entrada** para cualquier agente. Debe contener:

```mermaid
flowchart LR
    subgraph AGENTS_STRUCTURE["Estructura AGENTS.md Root"]
        direction TB
        A["1. Visión general del proyecto\n(diagrama Mermaid obligatorio)"]
        B["2. Mapa de componentes\n(tabla con ubicación y stack)"]
        C["3. Skills disponibles\n(tabla con nombre, descripción, link)"]
        D["4. Auto-invoke\n(tabla acción → skill)"]
        E["5. Convenciones globales\n(idioma, commits, Docker)"]
    end

    A --> B --> C --> D --> E
```

### Template Mínimo

```markdown
# Proyecto — AGENTS.md

## Visión General
<!-- Diagrama Mermaid de arquitectura -->

## Componentes
| Componente | Ubicación | Stack | AGENTS.md |
|---|---|---|---|

## Skills Disponibles
| Skill | Descripción | URL |
|---|---|---|

## Auto-invoke Skills
| Acción | Skill |
|---|---|

## Convenciones
- Idioma: español
- Commits: conventional-commits
- Todo en Docker
```

---

## Patrón: Skills

### Estructura de Carpeta

```mermaid
flowchart TB
    subgraph SKILL_DIR["skills/{nombre-skill}/"]
        SKILL_MD["SKILL.md\n(obligatorio)"]
        ASSETS["assets/\n(opcional)"]
        REFS["references/\n(opcional)"]

        ASSETS --> TMPL["template.py\nschema.json\nejemplos"]
        REFS --> DOCS["docs.md\nlinks a docs locales"]
    end

    style SKILL_MD fill:#4caf50,color:#fff
    style ASSETS fill:#fff3e0
    style REFS fill:#e3f2fd
```

### Frontmatter Obligatorio

```yaml
---
name: nombre-skill            # lowercase, guiones
description: >
  Qué hace esta skill.
  Trigger: Cuándo invocarla.
license: MIT
metadata:
  author: eliflowi
  version: "1.0"
  scope: [root|ui|api|infra]  # dónde aplica
  auto_invoke: "Acción que trigerea esta skill"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---
```

### Decisión: assets/ vs references/

```mermaid
flowchart TD
    NEED{"¿Qué necesitas\nagregar?"}
    NEED -->|"Templates de código"| ASSETS["assets/"]
    NEED -->|"Schemas JSON"| ASSETS
    NEED -->|"Configs de ejemplo"| ASSETS
    NEED -->|"Links a docs locales"| REFS["references/"]
    NEED -->|"Guías existentes"| REFS

    ASSETS --> RULE_A["Archivos que el agente\ncopia/adapta"]
    REFS --> RULE_R["Punteros a archivos\nque ya existen en el repo"]

    style ASSETS fill:#ff9800,color:#fff
    style REFS fill:#2196f3,color:#fff
```

---

## Patrón: Diagramas Mermaid

**Regla crítica**: Siempre preferir diagramas Mermaid sobre texto narrativo para:

```mermaid
flowchart LR
    subgraph USAR_MERMAID["✅ Usar Mermaid Para"]
        A["Arquitectura de servicios"]
        B["Flujos de red / Docker"]
        C["Árboles de decisión"]
        D["Secuencias de operación"]
        E["Jerarquía de carpetas clave"]
        F["Dependencias entre componentes"]
    end

    subgraph NO_MERMAID["❌ No Usar Mermaid Para"]
        G["Listas simples"]
        H["Configs literales"]
        I["Comandos bash"]
    end
```

### Tipos de Diagrama por Situación

| Situación | Tipo Mermaid | Ejemplo |
|-----------|-------------|---------|
| Arquitectura de servicios | `flowchart TB` | Contenedores, puertos, redes |
| Flujo de request | `sequenceDiagram` | HTTP request → response |
| Decisiones | `flowchart TD` con nodos `{}` | Árbol de troubleshooting |
| Topología de red | `flowchart LR` con subgraphs | Docker networks |
| Timeline de deploy | `sequenceDiagram` | Pasos de despliegue |
| Relaciones de datos | `erDiagram` | Modelos/tablas DB |
| Estados | `stateDiagram-v2` | Ciclo de vida de un recurso |

### Ejemplo: Arquitectura de Servicios

```mermaid
flowchart TB
    subgraph INTERNET["Internet"]
        CLIENT["Cliente"]
    end

    subgraph SERVER["Servidor"]
        subgraph PROXY["Reverse Proxy"]
            NGINX[":80/:443"]
        end
        subgraph APP["Aplicación"]
            API[":5000 API"]
            WORKER["Celery Worker"]
        end
        subgraph DATA["Datos"]
            DB["PostgreSQL"]
            CACHE["Redis"]
        end
    end

    CLIENT -->|HTTPS| NGINX
    NGINX -->|proxy_pass| API
    API --> DB
    API --> CACHE
    API --> WORKER

    style PROXY fill:#e3f2fd
    style APP fill:#e8f5e9
    style DATA fill:#fff3e0
```

### Ejemplo: Flujo de Decisión

```mermaid
flowchart TD
    START["¿Necesitas documentar\nalgo para agentes?"]
    START -->|"Arquitectura global"| ROOT_AGENTS["Editar AGENTS.md root"]
    START -->|"Componente específico"| COMP_AGENTS["Editar AGENTS.md componente"]
    START -->|"Patrón reutilizable"| NEW_SKILL["Crear nueva Skill"]
    START -->|"Instrucciones Copilot"| COPILOT["Editar copilot-instructions.md"]

    NEW_SKILL --> SIZE{"¿Skill > 300 líneas?"}
    SIZE -->|Sí| SPLIT["Dividir en skill + assets/"]
    SIZE -->|No| KEEP["Mantener en SKILL.md"]

    style START fill:#ff9800,color:#fff
    style NEW_SKILL fill:#2196f3,color:#fff
```

---

## Relación con AgentArchitect y subagent-pool

Esta skill produce **documentación de contexto** que los agentes ejecutables *leen*.
El ciclo completo es:

```mermaid
flowchart LR
    A["arquitect-dev-ia\n📄 Crea documentación\nAGENTS.md, CLAUDE.md\ndiagramas, skills"]
    B["AgentArchitect\n🏗️ Diseña y genera\n.agent.md ejecutables"]
    C["subagent-pool\n⚙️ Orquesta la\nejecución del trabajo"]

    A -->|"contexto que los agentes leen"| B
    B -->|"agentes listos para usar"| C

    style A fill:#4caf50,color:#fff
    style B fill:#9c27b0,color:#fff
    style C fill:#ff9800,color:#fff
```

- **Esta skill** → primero, para que el proyecto sea legible para cualquier agente IA
- **AgentArchitect** → cuando necesites crear un equipo de agentes ejecutables
- **subagent-pool** → cuando el equipo ya existe y hay trabajo que orquestar

---

## Flujo Completo: Crear Documentación IA para un Proyecto

```mermaid
flowchart TD
    A["1. Analizar estructura\ndel proyecto"] --> B["2. Identificar componentes\ny dependencias"]
    B --> C["3. Crear AGENTS.md root\ncon diagrama de arquitectura"]
    C --> D{"¿Proyecto tiene\nmúltiples componentes?"}
    D -->|Sí| E["4a. Crear AGENTS.md\npor componente"]
    D -->|No| F["4b. Documentar todo\nen AGENTS.md root"]
    E --> G["5. Identificar patrones\nrepetitivos"]
    F --> G
    G --> H{"¿Patrones reutilizables\ndetectados?"}
    H -->|Sí| I["6a. Crear Skills\npara cada patrón"]
    H -->|No| J["6b. Documentar en\nAGENTS.md directamente"]
    I --> K["7. Registrar skills en\nAGENTS.md (auto-invoke)"]
    J --> K
    K --> L["8. Crear copilot-instructions.md\n(si usa Copilot)"]
    L --> M["9. Validar: ¿cada archivo\n< 300 líneas?"]
    M -->|No| N["Refactorizar: extraer a skills"]
    M -->|Sí| O["✅ Documentación lista"]
    N --> M

    style A fill:#e3f2fd
    style O fill:#4caf50,color:#fff
```

---

## Convenciones para eliflowi.com

Estas son las convenciones específicas de este servidor multi-proyecto:

```mermaid
flowchart LR
    subgraph CONVENCIONES["Convenciones Globales"]
        direction TB
        LANG["🗣️ Idioma: Español\n(código, docs, commits)"]
        DOCKER["🐳 Docker siempre\n(cero servicios nativos)"]
        MERMAID["📊 Diagramas > Texto\n(Mermaid obligatorio)"]
        ENV["🔒 .env nunca en git\n(cada proyecto su .env)"]
        HEALTH["❤️ Health checks\n(en todos los servicios)"]
    end
```

| Convención | Regla |
|-----------|-------|
| Idioma | Español en todo: código, comments, docs, commits |
| Docker | Todo se ejecuta en contenedores, sin excepción |
| Diagramas | Mermaid obligatorio para arquitectura, flujos y decisiones |
| `.env` | Nunca en git — cada proyecto espera su propio `.env` |
| Health checks | Todos los servicios principales deben tenerlo |
| IPs fijas | En `infrastructure/`, cada servicio tiene IP estática `172.22.0.x` |
| Volúmenes externos | En `apigateway/`, crear con `docker volume create` previo |

---

## Checklist: Documentación IA Completa

```mermaid
flowchart LR
    subgraph CHECK["✅ Checklist"]
        direction TB
        C1["AGENTS.md root existe\ny tiene diagrama de arquitectura"]
        C2["Cada componente con\nsu propio AGENTS.md"]
        C3["Skills creadas para\npatrones repetitivos"]
        C4["Auto-invoke table\ncompleta en AGENTS.md"]
        C5["copilot-instructions.md\nactualizado"]
        C6["Ningún archivo de docs > 300 líneas"]
        C7["Diagramas Mermaid en\ntoda arquitectura"]
    end
```

- [ ] `AGENTS.md` root con diagrama de arquitectura Mermaid
- [ ] `AGENTS.md` por componente (si aplica)
- [ ] Skills para patrones repetitivos (commits, PRs, testing, etc.)
- [ ] Tabla auto-invoke en cada `AGENTS.md`
- [ ] `copilot-instructions.md` para Copilot
- [ ] Ningún archivo de documentación supera 300 líneas
- [ ] Toda arquitectura documentada con diagramas Mermaid
- [ ] Frontmatter completo en cada skill (`name`, `description`, `allowed-tools`, `metadata.scope`)
- [ ] `assets/` con templates y ejemplos cuando la skill es compleja
- [ ] `references/` apuntando a docs locales (no URLs web)

---

## Comandos Útiles

```bash
# Contar líneas de un archivo de agente
wc -l AGENTS.md

# Buscar todas las skills del proyecto
find . -name "SKILL.md" -type f

# Buscar todos los AGENTS.md
find . -name "AGENTS.md" -type f

# Buscar copilot-instructions
find . -path "*/.github/copilot-instructions.md" -type f

# Verificar que Mermaid es válido (si hay herramienta instalada)
# npx @mermaid-js/mermaid-cli -i archivo.md -o output.svg

# Ver estructura de skills
tree .claude/skills/ 2>/dev/null || find .claude/skills -type f | head -20
```

---

## Anti-patrones

```mermaid
flowchart LR
    subgraph BAD["❌ Anti-patrones"]
        direction TB
        X1["AGENTS.md de 800+ líneas\n→ El agente alucina"]
        X2["Todo en texto narrativo\n→ Ambigüedad"]
        X3["Skills sin frontmatter\n→ No se auto-invocan"]
        X4["Duplicar docs existentes\n→ Se desincroniza"]
        X5["URLs web en references/\n→ Usar paths locales"]
        X6["Un solo AGENTS.md gigante\n→ Dividir por componente"]
    end

    subgraph GOOD["✅ Buenas prácticas"]
        direction TB
        Y1["Max 300 líneas/archivo"]
        Y2["Diagramas Mermaid"]
        Y3["Frontmatter completo"]
        Y4["Referencias locales"]
        Y5["Paths locales"]
        Y6["Dividir por scope"]
    end

    X1 -.->|corregir| Y1
    X2 -.->|corregir| Y2
    X3 -.->|corregir| Y3
    X4 -.->|corregir| Y4
    X5 -.->|corregir| Y5
    X6 -.->|corregir| Y6
```

---

## Resources

- **Templates**: Ver [assets/](assets/) para templates de AGENTS.md y SKILL.md
- **Referencia**: Ver [references/](references/) para la guía de arquitectura del servidor eliflowi.com
```
