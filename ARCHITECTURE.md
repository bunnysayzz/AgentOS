# 🏗️ AgentOS Studio — Architecture Guide

> **AgentOS Studio** is a full-stack AI agent orchestration platform that enables users to create, manage, and monitor AI agents, workflows, tools, prompts, and memory — all within isolated workspaces.

---

## 🔭 What It's Used For

AgentOS Studio is designed for:

| Purpose | Description |
|---------|-------------|
| **🤖 Agent Management** | Create and manage AI agents with configurable models, system prompts, and execution lifecycle (start/pause/resume/cancel) |
| **⚡ Workflow Automation** | Build sequential or approval-based workflows with manual/triggered execution |
| **🧠 Memory Systems** | Persistent session-based memory with search, consolidation, and importance scoring |
| **🔧 Tools Registry** | Register and version tool definitions (functions, APIs, code) with public/workspace visibility |
| **📝 Prompt Registry** | Version-controlled prompt templates with variable rendering and rollback support |
| **🔐 Secrets Manager** | Encrypted credential storage per workspace with environment scoping |
| **📦 Artifact Store** | Versioned binary/structured asset tracking with content type filtering |
| **🔌 MCP Gateway** | LLM model routing with cost tracking, usage analytics, and live chat completions |
| **📊 Telemetry & Audit** | Event logging, audit trails, cost dashboards, and duration analytics |
| **🔀 Execution Graphs** | Node-level execution tracing and debugging for agent/workflow runs |
| **👥 Workspace Isolation** | Multi-tenant workspaces with role-based access (Owner/Admin/Member/Viewer) |

---

## 🧩 High-Level Architecture

```mermaid
graph TB
    subgraph Client["🌐 Frontend (React + Vite)"]
        direction TB
        P[Pages<br/>15 route pages]
        C[Components<br/>Sidebar, Layout, etc.]
        S[Stores<br/>Auth, UI, Workspace]
        API[API Service<br/>Axios HTTP Client]
        IC[Icons<br/>45+ SVG Icons]
    end

    subgraph Server["⚙️ Backend (FastAPI + Python)"]
        direction TB
        R[API Layer<br/>14 route modules]
        SRV[Service Layer<br/>12 service modules]
        MDL[Data Models<br/>18 SQLAlchemy models]
        SCH[Pydantic Schemas<br/>Request/Response validation]
        AUTH[Auth & Security<br/>JWT + BCrypt]
    end

    subgraph Storage["💾 Storage Layer"]
        DB[(Cloud Firestore<br/>Google Firebase)]
    end

    Client <-->|HTTP/JSON| Server
    Server <-->|Firestore SDK| Storage
    Server ~~~|LLM API Calls| LLM[🤖 External LLMs<br/>GPT-4o, Claude, Gemini]
```

---

## 📂 Project Structure

```
agentos-studio/
├── backend/                          # Python FastAPI Backend
│   ├── app/
│   │   ├── api/                      # Route handlers (14 modules)
│   │   │   ├── __init__.py           # Router aggregation
│   │   │   ├── deps.py               # Dependency injection (auth, db)
│   │   │   ├── auth.py               # Auth routes (/auth/*)
│   │   │   ├── users.py              # User management
│   │   │   ├── workspaces.py         # Workspace CRUD + members
│   │   │   ├── agents.py             # Agent CRUD + execution lifecycle
│   │   │   ├── workflows.py          # Workflow CRUD + execution lifecycle
│   │   │   ├── tools.py              # Tool registry
│   │   │   ├── prompts.py            # Prompt registry + versioning
│   │   │   ├── memory.py             # Memory CRUD + search + consolidation
│   │   │   ├── secrets.py            # Secret storage
│   │   │   ├── artifacts.py          # Artifact registry
│   │   │   ├── mcp.py                # LLM routing + chat completions
│   │   │   ├── telemetry.py          # Events + audit logs
│   │   │   └── execution_graphs.py   # Execution node tracing
│   │   ├── core/                     # Core config
│   │   │   ├── config.py             # App settings
│   │   │   ├── database.py           # Firestore-backed data layer
│   │   │   └── security.py           # Firebase token verification
│   │   ├── models/                   # Enum definitions for schema compat
│   │   ├── schemas/                  # Pydantic request/response models
│   │   ├── services/                 # Business logic (12 modules)
│   │   └── main.py                   # FastAPI app factory
│   └── tests/                        # 220+ async tests
│
└── frontend/                         # React + TypeScript Frontend
    └── src/
        ├── components/               # Reusable UI components
        │   ├── Icons.tsx             # 45+ SVG icon system
        │   ├── Sidebar.tsx           # Navigation sidebar
        │   ├── Layout.tsx            # App layout wrapper
        │   ├── ProtectedRoute.tsx    # Auth guard
        │   └── WorkspaceSelector.tsx # Workspace dropdown
        ├── pages/                    # Route pages (15 pages)
        ├── services/
        │   └── api.ts                # Axios HTTP client
        ├── stores/                   # Zustand state management
        │   ├── authStore.ts          # Auth state + tokens
        │   ├── uiStore.ts            # Sidebar, theme state
        │   └── workspaceStore.ts     # Selected workspace
        └── utils/
            └── cn.ts                 # Tailwind class merging
```

---

## 🚏 API Route Map

```mermaid
graph LR
    subgraph Auth["🔐 Authentication /auth"]
        REG[POST /register]
        LOG[POST /login]
        REF[POST /refresh]
        ME[GET /me]
        LOT[POST /logout]
    end

    subgraph Users["👤 Users /users"]
        UL[GET /]
        UD[GET /{id}]
        UP[PATCH /{id}]
        UDEL[DELETE /{id}]
    end

    subgraph WS["📁 Workspaces /workspaces"]
        WL[GET /]
        WC[POST /]
        WGET[GET /{id}]
        WP[PATCH /{id}]
        WDEL[DELETE /{id}]
        WM[GET /{id}/members]
        WMA[POST /{id}/members]
        WMP[PATCH /{id}/members/{uid}]
        WMD[DELETE /{id}/members/{uid}]
    end

    subgraph Agents["🤖 Agents /workspaces/{wid}/agents"]
        AL[GET /]
        AC[POST /]
        AGET[GET /{id}]
        AP[PATCH /{id}]
        ADEL[DELETE /{id}]
        AEX[POST /{id}/execute]
        AEL[GET /{id}/executions]
        AEST[POST /{id}/executions/{eid}/start]
        AEPA[POST /.../{eid}/pause]
        AERE[POST /.../{eid}/resume]
        AECA[POST /.../{eid}/cancel]
    end

    subgraph Workflows["⚡ Workflows /workspaces/{wid}/workflows"]
        WL2[GET /, POST /]
        WGET2[GET /{id}, PATCH, DELETE]
        WEX[POST /{id}/execute]
        WEL[GET /{id}/executions]
        WSTART[POST /.../{eid}/start]
        WPAUSE[POST /.../{eid}/pause]
        WRESUME[POST /.../{eid}/resume]
        WCANCEL[POST /.../{eid}/cancel]
        WAPPROVE[POST /.../{eid}/approve]
    end

    subgraph Tools["🔧 Tools .../workspaces/{wid}/tools"]
        TL[GET /, POST /]
        TPUB[GET /tools/public]
        TGET[GET /tools/{id}]
        TPATCH[PATCH /tools/{id}]
        TDEL[DELETE /tools/{id}]
        TEXEC[GET /tools/{id}/executions]
    end

    subgraph Memory["🧠 Memory .../workspaces/{wid}/memory"]
        MCREATE[POST /sessions/{sid}]
        MGET[GET /sessions/{sid}]
        MDEL[DELETE /sessions/{sid}]
        MSEARCH[GET /search]
        MCONSOLIDATE[POST /consolidate]
        MSESSIONS[GET /sessions]
        MSESSIONDEL[DELETE /sessions/{sid}]
    end

    subgraph Prompts["📝 Prompts .../workspaces/{wid}/prompts"]
        PL[GET /, POST /]
        PPUB[GET /prompts/public]
        PGET[GET /prompts/{id}]
        PPATCH[PATCH /prompts/{id}]
        PDEL[DELETE /prompts/{id}]
        PVERSIONS[GET /prompts/{id}/versions]
        PCREATEVER[POST /prompts/{id}/versions]
        PRENDER[POST /prompts/{id}/render]
        PROLLBACK[POST /prompts/{id}/rollback/{v}]
    end

    subgraph Secrets["🔐 Secrets .../workspaces/{wid}/secrets"]
        SL[GET /, POST /]
        SGET[GET /{id}]
        SPATCH[PATCH /{id}]
        SDEL[DELETE /{id}]
    end

    subgraph Artifacts["📦 Artifacts .../workspaces/{wid}/artifacts"]
        ARL[GET /, POST /]
        ARGET[GET /{id}]
        ARPATCH[PATCH /{id}]
        ARDEL[DELETE /{id}]
    end

    subgraph MCP["🔌 MCP Gateway"]
        MCHAT[POST /mcp/chat/completions]
        MMODELS[GET /mcp/models]
        MSEED[POST /mcp/models/seed]
        MCOSTS[GET /mcp/costs]
        MCALLS[GET /mcp/calls]
    end

    subgraph Telemetry["📊 Telemetry .../workspaces/{wid}"]
        TEL[POST /events]
        TEGET[GET /events]
        TESTATS[GET /events/stats]
        TEGETID[GET /events/{id}]
        TAUDIT[GET /audit-logs]
    end

    subgraph Graphs["🔀 Execution Graphs .../workspaces/{wid}/executions/{eid}"]
        GG[GET /graph]
        GNODES[GET /graph/nodes]
        GNODE[GET /graph/nodes/{nid}]
    end
```

---

## 🗄️ Data Model Relationships

> These relationships are **conceptual** — everything is stored as Firestore documents/collections (no SQL tables, no migrations).

```mermaid
erDiagram
    users ||--o{ workspaces : "is owner"
    users ||--o{ workspace_members : "belongs to"
    workspaces ||--o{ workspace_members : "has members"
    workspaces ||--o{ agents : "contains"
    workspaces ||--o{ workflows : "contains"
    workspaces ||--o{ tools : "contains"
    workspaces ||--o{ prompts : "contains"
    workspaces ||--o{ secrets : "contains"
    workspaces ||--o{ artifacts : "contains"
    workspaces ||--o{ memory_entries : "stores"
    workspaces ||--o{ telemetry_events : "logs"
    workspaces ||--o{ audit_logs : "audits"

    agents ||--o{ agent_executions : "has"
    workflows ||--o{ workflow_executions : "has"
    tools ||--o{ tool_executions : "has"
    agent_executions ||--o{ execution_graph_nodes : "traces"
    workflow_executions ||--o{ execution_graph_nodes : "traces"

    prompts ||--o{ prompt_versions : "versions"
    llm_calls ||--o{ model_registry : "uses"

    users {
        uuid id PK
        string email UK
        string username UK
        string full_name
        string hashed_password
        datetime created_at
    }

    workspaces {
        uuid id PK
        string name
        string slug UK
        text description
        boolean is_personal
        uuid owner_id FK
    }

    workspace_members {
        uuid workspace_id FK
        uuid user_id FK
        enum role "OWNER|ADMIN|MEMBER|VIEWER"
    }

    agents {
        uuid id PK
        uuid workspace_id FK
        string name
        string model_name
        text system_prompt
        string status
    }

    agent_executions {
        uuid id PK
        uuid agent_id FK
        string status "pending|running|paused|completed|failed|cancelled"
        json input_data
        json output_data
        datetime created_at
    }

    memory_entries {
        uuid id PK
        uuid workspace_id FK
        string session_id
        string role
        text content
        string memory_type
        float importance
        json metadata
    }

    workflows {
        uuid id PK
        uuid workspace_id FK
        string name
        string trigger_type
        string status
    }

    prompts {
        uuid id PK
        uuid workspace_id FK
        string name
        string slug UK
        integer current_version
    }

    telemetry_events {
        uuid id PK
        uuid workspace_id FK
        string event_name
        string severity
        json body
    }
```

---

## 🔄 Service Layer Architecture

```mermaid
graph TB
    subgraph API["API Layer (Routes)"]
        direction LR
        AUTH_R["/auth"]
        WS_R["/workspaces"]
        AG_R["/agents"]
        WF_R["/workflows"]
        T_R["/tools"]
        P_R["/prompts"]
        M_R["/memory"]
        S_R["/secrets"]
        AR_R["/artifacts"]
        MCP_R["/mcp"]
        TEL_R["/telemetry"]
        EG_R["/graphs"]
    end

    subgraph Services["Service Layer (Business Logic)"]
        direction TB
        AS[auth_service<br/>register, login, refresh]
        WS_S[workspace_service<br/>CRUD, member management]
        AGS_S[agent_service<br/>CRUD, execute, lifecycle]
        WFS_S[workflow_service<br/>CRUD, execute, lifecycle]
        TS_S[tool_service<br/>CRUD, public tools]
        PS_S[prompt_service<br/>CRUD, version, render]
        MS_S[memory_service<br/>CRUD, search, consolidate]
        SS_S[secret_service<br/>CRUD, encrypted storage]
        ARS_S[artifact_service<br/>CRUD, versioned]
        MCP_S[mcp_service<br/>LLM routing, cost, chat]
        TELS_S[telemetry_service<br/>events, audit, stats]
        EGS_S[execution_graph_service<br/>node tracing]
    end

    subgraph Core["Core Layer"]
        DB[(Cloud Firestore)]
        JWT[Firebase Auth<br/>+ JWT]
        CFG[Config]
    end

    API --> Services
    Services --> Core
    Services <--> DB
```

---

## 🖥️ Frontend Component Hierarchy

```mermaid
graph TB
    APP[App.tsx<br/>Route Definitions]
    
    subgraph Public["🔓 Public Routes"]
        L[Login Page]
        R[Register Page]
    end

    subgraph Protected["🔐 Protected Routes"]
        LAYOUT[Layout.tsx<br/>Shell + Sidebar]
        SIDEBAR[Sidebar.tsx<br/>Navigation]
        WSEL[WorkspaceSelector.tsx]
        
        subgraph Pages["📄 Page Components"]
            D[Dashboard<br/>Stats + Quick Actions]
            WS[Workspaces<br/>List + Create]
            WD[WorkspaceDetail<br/>Overview + Members]
            AG[Agents<br/>List + Detail + Executions]
            WF[Workflows<br/>List + Detail + Executions]
            T[Tools<br/>Workspace/Public tabs]
            P[Prompts<br/>List + Versions + Render]
            MEM[Memory<br/>Session + Search]
            SEC[Secrets<br/>List + Create]
            ART[Artifacts<br/>List + Detail]
            MCP[MCP Gateway<br/>Models + Costs + Chat]
            TEL[Telemetry<br/>Stats + Events + Audit]
            EG[Execution Graphs<br/>Node Timeline]
        end
    end

    subgraph State["🗃️ Zustand Stores"]
        AUTH_STORE[authStore<br/>token, user, login/logout]
        UI_STORE[uiStore<br/>sidebar, mobile]
        WS_STORE[workspaceStore<br/>selected workspace]
    end

    subgraph ServicesLayer["🔌 Services"]
        API[api.ts<br/>Axios instance + interceptors]
    end

    subgraph UI["🎨 UI Components"]
        ICONS[Icons.tsx<br/>45+ SVG Icons]
        CN[cn.ts<br/>Tailwind merge]
    end

    APP --> Public
    APP --> Protected
    LAYOUT --> SIDEBAR
    Pages --> WSEL
    Pages --> API
    Pages --> State
    SIDEBAR --> State
    LAYOUT --> ICONS
```

---

## 🔐 Authentication Flow

```mermaid
sequenceDiagram
    actor U as User
    participant F as Frontend
    participant FA as Firebase Auth
    participant B as Backend
    participant FS as Cloud Firestore

    U->>F: Sign in (email/password or Google)
    F->>FA: Firebase Auth request
    FA-->>F: ID token
    F->>B: Call API (Bearer Firebase ID token)
    B->>B: Verify Firebase ID token (public certs)
    B->>FS: Read / write user data
    FS-->>B: Documents
    B-->>F: { user profile, workspaces }
    F-->>U: ✅ Redirect to /dashboard
```

---

## ⚡ Execution Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running: start
    running --> completed: success
    running --> failed: error
    running --> paused: pause
    running --> cancelled: cancel
    paused --> running: resume
    cancelled --> [*]
    completed --> [*]
    failed --> [*]

    note right of pending
        Created but not yet started
        Initial state for all executions
    end note

    note right of running
        Actively executing
        Can be paused or cancelled
    end note

    note right of paused
        Suspended execution
        Can be resumed to continue
    end note

    note right of awaiting_approval
        Workflow-specific state
        Requires manual approval to continue
    end note

    awaiting_approval --> running: approve
```

---

## 🔄 Request Data Flow

```mermaid
flowchart LR
    subgraph Request["📤 Request Flow"]
        REQ[HTTP Request]
        MID[Middleware<br/>CORS, Logging]
        AUTH[Auth Dependency<br/>JWT Verification]
        WS_CHECK[Workspace Access<br/>Role Check]
        ROUTE[Route Handler]
        SCHEMA_IN[Pydantic Validation<br/>Request Schema]
        SERVICE[Service Layer<br/>Business Logic]
        MODEL[FirestoreDB Data Layer]
        DB[(Cloud Firestore)]
        SCHEMA_OUT[Pydantic Serialization<br/>Response Schema]
        RESP[JSON Response]
    end

    REQ --> MID --> AUTH --> WS_CHECK --> ROUTE
    ROUTE --> SCHEMA_IN --> SERVICE
    SERVICE --> MODEL --> DB
    DB --> MODEL --> SERVICE
    SERVICE --> SCHEMA_OUT --> RESP
```

---

## 🚀 Deployment Architecture

```mermaid
graph TB
    subgraph Local["💻 Local Development"]
        VITE[Vite Dev Server<br/>Port 5173]
        UVICORN[Uvicorn<br/>Port 8000]
        FS[(Cloud Firestore<br/>agentos-7f01e)]
    end

    subgraph Production["☁️ Production (Render)"]
        API[FastAPI Single Service<br/>Serves frontend + /api]
        FS_PROD[(Cloud Firestore)]
        FB_AUTH[Firebase Auth<br/>Email + Google Sign-In]
        FB_STORAGE[Firebase Storage<br/>Avatars / Artifacts]
    end

    USER([User Browser])
    USER -->|Dev| VITE
    USER -->|Prod| API
    VITE -->|/api/* Proxy| UVICORN
    UVICORN --> FS
    API --> FS_PROD
    API --> FB_AUTH
    API --> FB_STORAGE
```

---

## 🔑 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend Framework** | FastAPI (async) | Native async, auto-docs, Pydantic integration, high performance |
| **ORM** | None | Data access via Firestore SDK — no ORM, no migrations |
| **Database** | Firebase Cloud Firestore | Serverless, realtime, zero-ops, never powers off |
| **Auth** | JWT (access + refresh tokens) | Stateless, scalable, industry standard |
| **Frontend Framework** | React 18 + Vite | Modern, fast HMR, excellent DX |
| **State Management** | Zustand | Minimal boilerplate, TypeScript-first, tiny bundle size |
| **API Client** | Axios + TanStack Query | Automatic caching, refetching, error handling |
| **Styling** | Tailwind CSS | Utility-first, consistent design, dark theme |
| **Password Hashing** | Firebase Auth | Managed auth — email/password + Google Sign-In |
| **Data Store** | Firestore SDK | Async, serverless, no cold starts |

---

## 📊 By The Numbers

```mermaid
mindmap
  ((AgentOS Studio))
    🐍 Backend
      66 API Endpoints
      14 Route Modules
      12 Service Modules
      Firestore Collections
      220+ Passing Tests
    ⚛️ Frontend
      15 Page Components
      5 Shared Components
      45+ Custom SVG Icons
      3 Zustand Stores
    🔐 Security
      JWT Auth
      Role-Based Access
      Workspace Isolation
      Password Hashing
    📈 Telemetry
      Event Logging
      Audit Trails
      Cost Tracking
      Performance Metrics
```

---

> *This architecture document was generated from the live codebase. Update as the system evolves.*
