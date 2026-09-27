# 🏭 PFE Maintenance Prédictive ONEE

Système complet de maintenance prédictive pour centrale thermique utilisant Machine Learning, AI et une interface Streamlit professionnelle.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Démarrage](#démarrage)
- [Utilisation](#utilisation)
- [API REST](#api-rest)
- [Modèles ML](#modèles-ml)
- [Structure du projet](#structure-du-projet)

## 🎯 Vue d'ensemble

Ce projet PFE (Projet de Fin d'Études) implémente un système complet de **maintenance prédictive** pour une centrale thermique ONEE (Office National de l'Électricité). Il combine:

- **Backend Python**: FastAPI + PostgreSQL
- **Frontend**: Streamlit Dashboard
- **Machine Learning**: Détection d'anomalies + Prédiction RUL
- **AI**: Chatbot RAG avec LangChain
- **Authentification**: JWT sécurisé + Bcrypt

## ✨ Fonctionnalités

### 1. 🔐 Authentification Sécurisée
- Connexion privée ; comptes créés exclusivement par un administrateur
- JWT tokens avec expiration 24h
- Hachage Bcrypt des mots de passe
- Contrôle d'accès basé sur les rôles (Admin/Engineer/Viewer)

### 2. 📊 Dashboard Multi-pages
- **Dashboard Principal**: Vue globale du système
- **Monitoring Temps Réel**: Lectures capteurs en direct
- **Prédictions**: RUL et détection d'anomalies
- **Chatbot RAG**: Assistant technique intelligent
- **Gestion Maintenance**: Ordres et historique
- **Paramètres**: Configuration utilisateur

### 3. 🤖 Machine Learning
- **Détection d'Anomalies**: Isolation Forest
- **Prédiction RUL**: XGBoost (Remaining Useful Life)
- Entraînement automatique sur les données
- Scores de confiance

### 4. 💬 Chatbot RAG
- Recherche sémantique avec ChromaDB
- Base de connaissances complète
- Intégration Groq avec repli local
- Historique des conversations

### 5. 📈 Données Synthétiques
- 10 équipements (Turbines, Chaudières, Alternateurs, etc.)
- 50+ capteurs avec lectures réalistes
- 3 mois d'historique générable
- Anomalies synthétiques détectées

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│         STREAMLIT DASHBOARD (Frontend)          │
│  ┌────────────────────────────────────────────┐ │
│  │ Login │ Dashboard │ Monitoring │ Chatbot  │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                     │
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────┐
│      FASTAPI (Backend) - Port 8000              │
│  ┌────────────────────────────────────────────┐ │
│  │ /auth  │ /api/equipment │ /api/sensors    │ │
│  │ /api/readings │ /api/anomalies │ /health │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │PostgreSQL│ │ChromaDB  │ │ML Models │
    │   DB     │ │(RAG)     │ │(Storage) │
    └──────────┘ └──────────┘ └──────────┘
```

## 🚀 Installation

### Prérequis
- Python 3.8+
- PostgreSQL 12+
- pip ou pip3

### 1. Cloner le projet
```bash
git clone <repo-url>
cd pfe-maintenance-predictive
```

### 2. Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configurer la base de données PostgreSQL
```bash
# Créer la base de données
createdb pfe_maintenance

# Ou via psql
psql
# CREATE DATABASE pfe_maintenance;
# \q
```

## ⚙️ Configuration

### 1. Créer le fichier `.env`
```bash
cp .env.example .env
```

### 2. Mettre à jour `.env`
```env
# DATABASE
DATABASE_URL=postgresql://user:password@localhost:5432/pfe_maintenance

# SECURITY (IMPORTANT: Changer en production!)
SECRET_KEY=your-super-secret-key-min-32-chars

# AI/ML (Optionnel pour chatbot)
GROQ_API_KEY=your-groq-api-key
OPENAI_API_KEY=your-openai-api-key

# ENVIRONMENT
ENVIRONMENT=development
```

### 3. Initialiser la base de données
```bash
python scripts/init_db.py
```

Cela créera:
- Toutes les tables PostgreSQL
- Les utilisateurs de test (admin/engineer)
- Les types d'équipements et capteurs

## ▶️ Démarrage

### Sécurité des comptes

- L'inscription publique est désactivée.
- Les comptes sont créés dans **Paramètres > Gestion des utilisateurs** par un administrateur.
- Un nouveau compte doit remplacer son mot de passe temporaire à sa première connexion.
- Un compte n'est jamais supprimé avec son historique : il est archivé (`is_active=false`).

### Données de démonstration

Avec `SEED_DEMO_OPERATIONAL_DATA=true`, l'initialisation ajoute de façon idempotente :

- 24 procédures techniques dans la base de connaissances RAG ;
- une prédiction RUL de démonstration par équipement si aucune prédiction n'existe.

Les valeurs RUL de démonstration valident le pipeline et ne remplacent pas un entraînement sur des historiques industriels réels.

### Tests de sécurité

```bash
python -m unittest test_security_and_demo.py -v
```

### Option 1: Script de démarrage automatique
```bash
chmod +x run.sh
./run.sh
```

Cela démarrera:
- FastAPI API (port 8000)
- Streamlit Dashboard (port 8501)

### Option 2: Démarrage manuel

Terminal 1 - FastAPI:
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 - Streamlit:
```bash
streamlit run streamlit_app.py --server.port=8501
```

### Accès

- **Dashboard**: http://localhost:8501
- **API**: http://localhost:8000
- **Docs API**: http://localhost:8000/docs

### Comptes de test
- Les comptes initiaux sont créés uniquement lorsque `SEED_DEFAULT_USERS=true`.
- Tout mot de passe temporaire doit être remplacé à la première connexion.

## 📱 Utilisation

### Login
1. Accédez à http://localhost:8501
2. Entrez vos identifiants
3. Cliquez "Se connecter"

### Dashboard Principal
- Métriques globales (équipements, capteurs, alertes)
- Distribution des équipements
- Alertes récentes

### Monitoring Temps Réel
- Sélectionnez un équipement
- Visualisez les capteurs en direct
- Consultez l'historique des 7 derniers jours

### Prédictions
- **RUL**: Durée de vie restante estimée
- **Anomalies**: Détections automatiques avec scores

### Chatbot
- Posez des questions sur la maintenance
- Base de connaissances complète
- Réponses avec sources

### Maintenance
- Ordres actifs
- Historique des interventions

## 🔌 API REST

### Authentification
```
POST   /auth/login       - Se connecter (retourne JWT)
GET    /auth/me          - Profil utilisateur
POST   /auth/refresh     - Rafraîchir token
```

### Données
```
GET    /api/equipment    - Tous les équipements
GET    /api/sensors      - Tous les capteurs
GET    /api/readings     - Lectures des capteurs
GET    /api/anomalies    - Anomalies détectées
GET    /api/predictions  - Prédictions RUL
GET    /api/maintenance  - Ordres de maintenance
```

### Santé
```
GET    /health           - État de l'API
GET    /api/info         - Informations système
```

### Headers requis pour les endpoints sécurisés
```
Authorization: Bearer <token>
```

## 🤖 Modèles ML

### 1. Détection d'Anomalies (Isolation Forest)
- Entraîné sur les valeurs des capteurs
- Score de 0 à 1 (1 = anomalie certaine)
- Détecte 5% des données comme anomalies
- Mise à jour continue

### 2. Prédiction RUL (XGBoost)
- Prédit heures de vie utile restante
- Features: statistiques capteurs, déviations, historique
- Confiance: 85-95%
- Réentraîné automatiquement

### Fichiers modèles
```
models/
├── anomaly_detection.pkl
└── rul_prediction.pkl
```

## 📁 Structure du projet

```
pfe-maintenance-predictive/
├── backend/
│   ├── __init__.py
│   ├── main.py              # API FastAPI principale
│   ├── database.py          # Configuration PostgreSQL
│   ├── models.py            # Modèles SQLAlchemy
│   ├── auth.py              # Authentification JWT
│   ├── ml_models.py         # Modèles ML (Anomalies, RUL)
│   ├── rag_chatbot.py       # Chatbot RAG avec LangChain
│   └── data_generator.py    # Générateur données synthétiques
├── streamlit_app.py         # Dashboard Streamlit
├── scripts/
│   ├── 01_init_database.sql # Schéma PostgreSQL
│   └── init_db.py           # Script d'initialisation Python
├── requirements.txt         # Dépendances Python
├── .env.example            # Template variables d'environnement
├── run.sh                  # Script de démarrage
└── README.md               # Ce fichier
```

## 🔒 Sécurité

### Bonnes pratiques implémentées
✓ JWT tokens avec expiration
✓ Bcrypt hashing (12 rounds) des mots de passe
✓ CORS configuré
✓ Parameterized queries (SQLAlchemy)
✓ Session management par utilisateur
✓ Rôles et permissions

### À faire avant production
- [ ] Changer `SECRET_KEY` dans `.env`
- [ ] Changer les mots de passe des utilisateurs de test
- [ ] Configurer CORS pour domaines spécifiques
- [ ] Activer HTTPS
- [ ] Configurer rate limiting
- [ ] Activer les logs d'audit

## 🛠️ Dépannage

### Erreur: "Connexion PostgreSQL refusée"
```bash
# Vérifier que PostgreSQL est lancé
psql -U postgres

# Vérifier l'URL dans .env
DATABASE_URL=postgresql://user:password@localhost:5432/pfe_maintenance
```

### Erreur: "GROQ_API_KEY not set"
- Le chatbot fonctionne quand même (mode local)
- Pour activer les LLM, ajoutez votre clé API dans `.env`

### Streamlit prend du temps à démarrer
```bash
# Nettoyer le cache
streamlit cache clear

# Redémarrer
streamlit run streamlit_app.py
```

## 📚 Ressources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [LangChain](https://python.langchain.com/)
- [Scikit-learn ML](https://scikit-learn.org/)
- [XGBoost](https://xgboost.readthedocs.io/)

## 👨‍💻 Auteur

**PFE Projet de Fin d'Études**  
ONEE - Office National de l'Électricité  
Système de Maintenance Prédictive pour Centrale Thermique

## 📝 Licence

Confidentiel - Propriété ONEE

## 🤝 Support

Pour toute question ou problème:
1. Consultez la documentation
2. Vérifiez le fichier .env
3. Consultez les logs: `streamlit run --logger.level=debug`
4. Contactez l'équipe de support

---

**Version**: 1.0.0  
**Dernière mise à jour**: 2024-03-31
