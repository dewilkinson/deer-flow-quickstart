# Component Diagram: Cobalt Multiagent (CMA)

This diagram illustrates the high-level system components and their external dependencies for the Project Cobalt agentic framework.

```mermaid
flowchart TD
    %% Define Root Entities
    User((User))

    subgraph UserEnv [User Environment]
        Client[Local Client]
        Hub[Obsidian Vault]
    end

    subgraph Core [Agentic Engine]
        VLI[VLI Interface]
        Planner[Graph Planner]
        Scout[The Scout: Data Gateway]
        Analyst[The Analyst: Logic]
        
        VLI --> Planner
        Planner --> Scout
        Scout --> Analyst
    end

    subgraph Backend [Cloud Backend - Railway]
        WebUI[Next.js Dashboard]
        Session[(Session Data)]
    end

    subgraph External [External Services]
        BrokerAPI[SnapTrade API]
        SearchAPI[Tavily Search]
        ModelGateway[LiteLLM Gateway]
    end

    %% Define Interconnects
    User --> Client
    Client --> Hub
    Client --> VLI
    
    WebUI --> Core
    Core --> Session
    
    Scout --> BrokerAPI
    Scout --> SearchAPI
    Core --> ModelGateway
```

### Role of Key Components:

1.  **User Environment**: Local persistence using the **Obsidian** knowledge hub. Dispatches are indexed as Markdown files.
2.  **Cloud Backend**: The containerized Python environment running **LangGraph** workflows and the Next.js management dashboard.
3.  **External Services**: Direct-to-source data retrieval (**SnapTrade**), contextual market search (**Tavily**), and multi-model LLM reasoning via **LiteLLM**.
