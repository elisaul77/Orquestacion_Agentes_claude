# Mermaid Diagram Catalog for AI Documentation

Quick reference of diagram types and when to use them.

## Service Architecture — `flowchart TB`

Use for: container composition, microservices, main components.

```mermaid
flowchart TB
    subgraph NET["Docker Network"]
        A["Service A\n:8080"] --> B["Service B\n:5432"]
        A --> C["Cache\n:6379"]
    end
```

## Network Topology — `flowchart LR`

Use for: Docker networks, subnets, connections between networks.

```mermaid
flowchart LR
    subgraph NET1["Network 1 — 172.22.0.0/24"]
        A[".6 VPN"]
        B[".9 Proxy"]
    end
    subgraph NET2["Network 2 — bridge"]
        C["API"]
        D["DB"]
    end
    B -->|":8443"| C
```

## Request Flow — `sequenceDiagram`

Use for: HTTP flow, authentication, interaction between services.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
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

## Decision Tree — `flowchart TD`

Use for: troubleshooting, conditional flows, design choices.

```mermaid
flowchart TD
    Q{"Question?"}
    Q -->|Option A| A["Action A"]
    Q -->|Option B| B["Action B"]
    A --> R["Result"]
    B --> R
```

## Data Relationships — `erDiagram`

Use for: database models, relationships between entities.

```mermaid
erDiagram
    USER ||--o{ API_KEY : has
    USER ||--o{ REQUEST : generates
    API_KEY ||--o{ REQUEST : authenticates
```

## States — `stateDiagram-v2`

Use for: resource lifecycle, process states.

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Active: approve
    Active --> Suspended: suspend
    Suspended --> Active: reactivate
    Active --> [*]: delete
```

## Project Dependencies — `flowchart TD`

Use for: mono-repos, build/deploy relationships between components.

```mermaid
flowchart TD
    A["project-a/\ndocker-compose.yml"] -->|"build context"| B["project-b/\nDockerfile"]
    C["project-c/"] -->|"API calls :8443"| A
    A -->|"proxy to"| EXT["External APIs"]
```
