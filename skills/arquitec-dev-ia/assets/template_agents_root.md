# {Nombre del Proyecto} — AGENTS.md

> {Descripción breve de una línea del proyecto}

## Visión General

<!-- Diagrama de arquitectura obligatorio — Mermaid flowchart TB -->
```mermaid
flowchart TB
    subgraph INTERNET["Internet"]
        CLIENT["Cliente"]
    end

    subgraph SERVER["Servidor / Infraestructura"]
        subgraph COMP_A["Componente A"]
            SVC_A1["Servicio A1\n:puerto"]
            SVC_A2["Servicio A2"]
        end
        subgraph COMP_B["Componente B"]
            SVC_B1["Servicio B1\n:puerto"]
        end
    end

    CLIENT -->|HTTPS| SVC_A1
    SVC_A1 --> SVC_A2
    SVC_A1 --> SVC_B1
```

## Componentes

| Componente | Ubicación | Stack | AGENTS.md |
|---|---|---|---|
| `componente-a/` | Descripción | Tech stack | [AGENTS.md](componente-a/AGENTS.md) |
| `componente-b/` | Descripción | Tech stack | [AGENTS.md](componente-b/AGENTS.md) |

## Skills Disponibles

### Genéricas
| Skill | Descripción | URL |
|---|---|---|
| `nombre-skill` | Qué hace | [SKILL.md](skills/nombre-skill/SKILL.md) |

### Específicas del Proyecto
| Skill | Descripción | URL |
|---|---|---|
| `proyecto-feature` | Qué hace | [SKILL.md](skills/proyecto-feature/SKILL.md) |

## Auto-invoke Skills

Cuando realices estas acciones, SIEMPRE invoca la skill correspondiente PRIMERO:

| Acción | Skill |
|---|---|
| Crear/modificar arquitectura de agentes | `arquitect-dev-ia` |
| Crear nueva skill | `skill-creator` |
| Hacer un commit | `proyecto-commit` |

## Convenciones

- **Idioma**: Español (código, docs, commits)
- **Diagramas**: Mermaid obligatorio para arquitectura y flujos
- **Docker**: Todo en contenedores
- **`.env`**: Nunca en git

## Workflow de Operaciones

```mermaid
flowchart TD
    A["Leer AGENTS.md del componente"] --> B{"¿Tiene dependencias\nde otros componentes?"}
    B -->|Sí| C["Verificar redes/volúmenes\ncompartidos"]
    B -->|No| D["Trabajar aislado"]
    C --> E["Implementar cambio"]
    D --> E
    E --> F["docker-compose up -d --build"]
    F --> G["Verificar health checks"]
```
