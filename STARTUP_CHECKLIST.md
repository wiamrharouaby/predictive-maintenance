# ✅ Checklist de Démarrage du Projet

## 🔍 Avant de Commencer

- [ ] Python 3.8+ installé: `python --version`
- [ ] PostgreSQL 12+ installé: `psql --version`
- [ ] 2GB RAM disponible minimum
- [ ] Connexion internet (pour packages)
- [ ] Port 8000 et 8501 libres

## 📋 Installation (10 minutes)

### Étape 1: Repository Setup
```bash
[ ] cd /chemin/vers/projet
[ ] python -m venv venv
[ ] source venv/bin/activate
```

### Étape 2: Dépendances
```bash
[ ] pip install -r requirements.txt
```
**Temps:** ~3 minutes  
**Taille:** ~500MB

### Étape 3: Base de Données PostgreSQL
```bash
[ ] createdb pfe_maintenance
```
**Ou via pgAdmin/psql**

### Étape 4: Configuration
```bash
[ ] cp .env.example .env
[ ] Éditer .env avec vos credentials:
    - DATABASE_URL
    - SECRET_KEY
    - (GROQ_API_KEY optionnel)
```

### Étape 5: Initialisation Base de Données
```bash
[ ] python scripts/init_db.py
```
**Sortie attendue:**
```
✓ Connexion PostgreSQL réussie
✓ Tables créées avec succès
✓ Types d'équipements insérés
✓ Types de capteurs insérés
✓ Utilisateur admin créé
✓ Utilisateur engineer créé
✓ INITIALISATION COMPLÈTE
```

## ▶️ Démarrage de l'Application (2 minutes)

### Option 1: Automatique
```bash
[ ] chmod +x run.sh
[ ] ./run.sh
```

### Option 2: Manuel (Recommandé pour dev)
```bash
# Terminal 1: API
[ ] python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Attendre "Uvicorn running on http://0.0.0.0:8000"

# Terminal 2: Dashboard
[ ] streamlit run streamlit_app.py --server.port=8501

# Attendre "You can now view your Streamlit app in your browser"
```

## 🧪 Validation (5 minutes)

### Test 1: API Health
```bash
[ ] curl http://localhost:8000/health
```
**Résultat attendu:**
```json
{"status":"ok","database":"connected"}
```

### Test 2: API Docs
```bash
[ ] Open http://localhost:8000/docs
[ ] Voir la documentation Swagger
```

### Test 3: Dashboard Access
```bash
[ ] Open http://localhost:8501
[ ] Page de login visible
```

### Test 4: Authentication
```bash
[ ] Username: admin
[ ] Password: admin123
[ ] Click "Se connecter"
[ ] Dashboard visible
```

### Test 5: Data Visible
```bash
[ ] Métriques affichées (≥ 1 équipement)
[ ] Graphiques visibles
[ ] Navigation entre pages possible
```

## 🤖 Tests Automatisés (2 minutes)

```bash
[ ] python test_complete.py
```

**Résultats attendus:**
```
✓ Base de Données
✓ Authentification
✓ Générateur Données
✓ Modèles ML
✓ Chatbot RAG

Total: 5/5 suites réussies
```

## 📊 Vérifications Finales

### Pages du Dashboard
- [ ] Dashboard: Métriques visibles
- [ ] Monitoring: Graphiques historiques
- [ ] Prédictions: RUL et anomalies
- [ ] Chatbot: Peut poser questions
- [ ] Maintenance: Ordres affichés
- [ ] Settings: Profil utilisateur

### API Endpoints
```bash
[ ] curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/equipment
[ ] Données reçues
```

### ML Models
- [ ] Anomalies détectées (5-10)
- [ ] RUL prédictions (10 équipements)
- [ ] Modèles sauvegardés dans `/models`

### Chatbot
- [ ] Base de connaissances chargée (4 documents)
- [ ] Réponses générées
- [ ] Historique conservé

## 🚨 Troubleshooting Rapide

### ❌ "Port 8501 already in use"
```bash
# Trouver le processus
lsof -i :8501
# Tuer le processus
kill -9 <PID>
# Ou changer le port dans .env
```

### ❌ "Database connection refused"
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql
# Redémarrer si nécessaire
sudo systemctl restart postgresql
# Vérifier l'URL dans .env
```

### ❌ "ModuleNotFoundError"
```bash
# Réinstaller les dépendances
pip install --upgrade -r requirements.txt
# Vérifier venv activé
which python  # Doit pointer vers venv/bin/python
```

### ❌ "No such table"
```bash
# Réinitialiser la BD
python scripts/init_db.py
# Ou manuellement:
psql -U postgres -d pfe_maintenance
# DROP SCHEMA public CASCADE;
# CREATE SCHEMA public;
```

## 📚 Documentation de Référence

| Document | Durée | Contenu |
|----------|-------|---------|
| QUICKSTART.md | 5 min | Démarrage rapide |
| README.md | 30 min | Guide complet |
| INTEGRATION_GUIDE.md | 45 min | Tests détaillés |
| PROJECT_SUMMARY.md | 20 min | Architecture overview |

## 🔑 Informations Critiques

### Comptes de Test
```
Username: admin        Password: admin123
Username: engineer     Password: engineer123
⚠️ À CHANGER EN PRODUCTION!
```

### Ports
```
FastAPI:  8000  (API + Swagger docs)
Streamlit: 8501 (Dashboard)
PostgreSQL: 5432 (DB)
```

### Base de Données
```
Name: pfe_maintenance
User: postgres (ou votre user)
Host: localhost:5432
Tables: 13 principales
```

### Fichiers Importants
```
.env                 - Configuration (NE PAS COMMITER)
requirements.txt     - Dépendances Python
README.md           - Documentation principale
scripts/init_db.py  - Initialisation BD
```

## ⏱️ Timeline Estimée

| Étape | Temps | Cumulé |
|-------|-------|--------|
| 1. Setup venv | 1 min | 1 min |
| 2. pip install | 3 min | 4 min |
| 3. createdb | 1 min | 5 min |
| 4. Configuration | 1 min | 6 min |
| 5. init_db.py | 2 min | 8 min |
| 6. Démarrage | 2 min | 10 min |
| 7. Tests | 5 min | 15 min |
| **Total** | **15 min** | |

## ✨ Après le Démarrage

### Première Utilisation (30 min)
1. Explorer le Dashboard
2. Consulter les équipements
3. Tester le Chatbot
4. Voir les prédictions ML
5. Consulter l'API Swagger

### Configuration Recommandée (1h)
1. [ ] Lire README.md complet
2. [ ] Changer les mots de passe de test
3. [ ] Configurer la sécurité (.env)
4. [ ] Ajouter des équipements réels
5. [ ] Configurer les alertes

### Validation en Production (2h)
1. [ ] Tester sur serveur
2. [ ] Configurer HTTPS
3. [ ] Activer les logs
4. [ ] Configurer la sauvegarde
5. [ ] Mettre en place le monitoring

## 📞 Support

### Problèmes Communs
Voir la section 9 de INTEGRATION_GUIDE.md

### Logs
```bash
# Streamlit debug
streamlit run streamlit_app.py --logger.level=debug

# API debug
export PYTHONDEBUG=1
python -m uvicorn backend.main:app --reload

# DB logs
sudo tail -f /var/log/postgresql/postgresql.log
```

### Ressources
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Python Docs](https://docs.python.org/)

## ✅ Signature de Complétion

```
Date de démarrage: __________
Date de complétion: __________

Démarré par: ____________________
Validé par: ____________________

Signature: ________________________
```

---

🎉 **Bon courage!** Le projet est prêt à l'emploi.

Si tout est coché ci-dessus, vous êtes prêt pour la production! 🚀
