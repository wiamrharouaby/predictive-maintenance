# Schema du projet - Maintenance Predictive ONEE

Ce document resume l'architecture du projet pour comprendre rapidement le role de chaque partie.

## 1. Vue globale

```mermaid
flowchart LR
    U[Utilisateur<br/>Admin / Engineer / Viewer]

    subgraph Frontend
        S[Dashboard Streamlit<br/>streamlit_app.py]
        P1[Dashboard principal]
        P2[Monitoring temps reel]
        P3[Predictions & anomalies]
        P4[Evaluation ML]
        P5[Chatbot RAG]
        P6[Maintenance]
        P7[Settings]
    end

    subgraph Backend
        API[API FastAPI<br/>backend/main.py]
        AUTH[Authentification<br/>backend/auth.py]
        DBMOD[Modeles SQLAlchemy<br/>backend/models.py]
        ML[Pipeline ML<br/>backend/ml_models.py]
        RAG[Assistant RAG<br/>backend/rag_chatbot.py]
        ALERTS[Alertes automatiques<br/>backend/auto_alerts.py]
        GEN[Generateur donnees<br/>backend/data_generator.py]
    end

    subgraph Stockage
        PG[(PostgreSQL)]
        CH[(ChromaDB<br/>base vectorielle RAG)]
        MODEL[(Fichiers modeles ML<br/>models/)]
        SESSION[(Sessions Streamlit<br/>.streamlit_sessions.json)]
    end

    U --> S
    S --> P1
    S --> P2
    S --> P3
    S --> P4
    S --> P5
    S --> P6
    S --> P7

    S --> AUTH
    S --> DBMOD
    S --> ML
    S --> RAG
    S --> ALERTS

    API --> AUTH
    API --> DBMOD
    API --> ALERTS

    AUTH --> PG
    DBMOD --> PG
    ALERTS --> PG
    GEN --> PG
    ML --> PG
    ML --> MODEL
    RAG --> CH
    RAG --> PG
    S --> SESSION
```

## 2. Parcours utilisateur

```mermaid
sequenceDiagram
    actor User as Utilisateur
    participant UI as Streamlit Dashboard
    participant Auth as Authentification
    participant DB as PostgreSQL
    participant ML as Modeles ML
    participant RAG as Chatbot RAG
    participant Chroma as ChromaDB

    User->>UI: Ouvre l'application
    UI->>Auth: Verifie login / mot de passe
    Auth->>DB: Cherche utilisateur + role
    DB-->>Auth: Utilisateur valide
    Auth-->>UI: Session + token

    User->>UI: Consulte Dashboard / Monitoring
    UI->>DB: Charge equipements, capteurs, lectures, alertes
    DB-->>UI: Donnees industrielles
    UI-->>User: Metriques, tableaux, graphes

    User->>UI: Consulte Predictions / Evaluation ML
    UI->>ML: Entraine ou evalue les modeles
    ML->>DB: Lit les lectures capteurs
    ML-->>UI: Scores anomalies, RUL, metriques
    UI-->>User: Resultats ML

    User->>UI: Pose une question au chatbot
    UI->>RAG: Envoie la question
    RAG->>Chroma: Recherche les documents proches
    RAG->>DB: Charge base de connaissances si besoin
    RAG-->>UI: Reponse + sources
    UI-->>User: Reponse technique
```

## 3. Flux des donnees

```mermaid
flowchart TD
    A[Generation de donnees synthetiques<br/>scripts/generate_data.py ou data_generator.py]
    B[(PostgreSQL)]
    C[Equipements]
    D[Capteurs]
    E[Lectures capteurs]
    F[Anomalies]
    G[Alertes]
    H[Ordres de maintenance]
    I[Pipeline ML]
    J[Detection anomalies<br/>Isolation Forest]
    K[Prediction RUL<br/>XGBoost]
    L[Dashboard Streamlit]
    M[Decision maintenance]

    A --> B
    B --> C
    B --> D
    B --> E
    E --> I
    I --> J
    I --> K
    J --> F
    J --> G
    K --> G
    G --> H
    C --> L
    D --> L
    E --> L
    F --> L
    G --> L
    H --> L
    L --> M
```

## 4. Role des pages du dashboard

| Page | Role principal |
| --- | --- |
| Dashboard | Vue generale: equipements, capteurs, alertes, anomalies |
| Monitoring | Suivi temps reel des mesures capteurs par equipement |
| Predictions | Affiche RUL, risques et anomalies detectees |
| Evaluation ML | Mesure la qualite des donnees et les performances ML |
| Chatbot | Assistant technique base sur RAG et base de connaissances |
| Maintenance | Acquitter les alertes et creer des ordres de maintenance |
| Settings | Profil utilisateur, stats systeme, test base de donnees |

## 5. Architecture technique simplifiee

```mermaid
flowchart TB
    subgraph Couche presentation
        Streamlit[Streamlit<br/>Interface utilisateur]
    end

    subgraph Couche metier
        Auth[Auth + roles]
        Maintenance[Gestion maintenance]
        AutoAlerts[Alertes automatiques]
        MLModels[Modeles ML]
        Chatbot[Chatbot RAG]
    end

    subgraph Couche donnees
        PostgreSQL[(PostgreSQL)]
        ChromaDB[(ChromaDB)]
        ModelFiles[(Modeles sauvegardes)]
    end

    Streamlit --> Auth
    Streamlit --> Maintenance
    Streamlit --> AutoAlerts
    Streamlit --> MLModels
    Streamlit --> Chatbot

    Auth --> PostgreSQL
    Maintenance --> PostgreSQL
    AutoAlerts --> PostgreSQL
    MLModels --> PostgreSQL
    MLModels --> ModelFiles
    Chatbot --> ChromaDB
    Chatbot --> PostgreSQL
```

## 6. Resume tres simple

Le projet fonctionne comme un systeme de supervision industrielle:

1. Des donnees de capteurs sont stockees dans PostgreSQL.
2. Le dashboard Streamlit affiche l'etat des equipements.
3. Les modeles ML detectent les anomalies et estiment le RUL.
4. Les alertes sont creees selon les seuils ou les anomalies.
5. Les utilisateurs peuvent traiter les alertes et creer des ordres de maintenance.
6. Le chatbot RAG aide l'utilisateur avec des explications techniques et des procedures.

