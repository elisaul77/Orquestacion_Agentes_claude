# Catálogo de Diagramas Mermaid para Documentación IA

Referencia rápida de tipos de diagrama y cuándo usarlos.

## Arquitectura de Servicios — `flowchart TB`

Usar para: composición de contenedores, microservicios, componentes principales.

```mermaid
flowchart TB
    subgraph NET["Red Docker"]
        A["Servicio A\n:8080"] --> B["Servicio B\n:5432"]
        A --> C["Cache\n:6379"]
    end
```

## Topología de Red — `flowchart LR`

Usar para: redes Docker, subnets, conexiones entre redes.

```mermaid
flowchart LR
    subgraph NET1["Red 1 — 172.22.0.0/24"]
        A[".6 VPN"]
        B[".9 Proxy"]
    end
    subgraph NET2["Red 2 — bridge"]
        C["API"]
        D["DB"]
    end
    B -->|":8443"| C
```

## Flujo de Request — `sequenceDiagram`

Usar para: flujo HTTP, autenticación, interacción entre servicios.

```mermaid
sequenceDiagram
    autonumber
    participant C as Cliente
    participant P as Proxy
    participant A as API
    participant D as DB

    C->>P: GET /api/resource
    P->>A: proxy_pass
    A->>D: SELECT * FROM table
    D-->>A: rows
    A-->>P: JSON response
    P-->>C: 200 OK
```

## Árbol de Decisión — `flowchart TD`

Usar para: troubleshooting, flujos condicionales, elecciones de diseño.

```mermaid
flowchart TD
    Q{"¿Pregunta?"}
    Q -->|Opción A| A["Acción A"]
    Q -->|Opción B| B["Acción B"]
    A --> R["Resultado"]
    B --> R
```

## Relaciones de Datos — `erDiagram`

Usar para: modelos de base de datos, relaciones entre entidades.

```mermaid
erDiagram
    USER ||--o{ API_KEY : tiene
    USER ||--o{ REQUEST : genera
    API_KEY ||--o{ REQUEST : autentica
```

## Estados — `stateDiagram-v2`

Usar para: ciclo de vida de recursos, estados de un proceso.

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Active: aprobar
    Active --> Suspended: suspender
    Suspended --> Active: reactivar
    Active --> [*]: eliminar
```

## Dependencias entre Proyectos — `flowchart TD`

Usar para: mono-repos, relaciones build/deploy entre componentes.

```mermaid
flowchart TD
    A["proyecto-a/\ndocker-compose.yml"] -->|"build context"| B["proyecto-b/\nDockerfile"]
    C["proyecto-c/"] -->|"API calls :8443"| A
    A -->|"proxy hacia"| EXT["APIs Externas"]
```
