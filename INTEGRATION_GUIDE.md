# 🔗 Guide d'Intégration et de Tests

## 1️⃣ Vérification de l'Installation

### 1.1 Vérifier les dépendances
```bash
# Vérifier que toutes les dépendances sont installées
pip list | grep -E "fastapi|streamlit|sqlalchemy|scikit-learn|xgboost|langchain"

# Sortie attendue:
# fastapi==0.104.1
# streamlit==1.28.1
# sqlalchemy==2.0.23
# scikit-learn==1.3.2
# xgboost==2.0.3
# langchain==0.0.352
```

### 1.2 Vérifier la connexion PostgreSQL
```bash
# Test direct
psql postgresql://user:password@localhost:5432/pfe_maintenance

# Depuis Python
python -c "
from backend.database import test_connection
if test_connection():
    print('✓ Connexion réussie')
else:
    print('✗ Erreur connexion')
"
```

## 2️⃣ Initialisation de la Base de Données

### 2.1 Exécuter le script d'initialisation
```bash
python scripts/init_db.py
```

### 2.2 Vérifier les tables créées
```sql
-- Se connecter à PostgreSQL
psql -U user -d pfe_maintenance

-- Lister les tables
\dt

-- Vérifier les utilisateurs
SELECT username, email, role FROM users;

-- Vérifier les types d'équipements
SELECT name FROM equipment_types;
```

### 2.3 Résultat attendu
```
 id | name | description
----+------+-------------------------------
    | Turbine | Turbine vapeur haute pression
    | Chaudière | Chaudière de récupération de chaleur
    | Alternateur | Alternateur synchrone de puissance
    ...
```

## 3️⃣ Tests des Composants

### 3.1 Test de l'Authentification
```python
# test_auth.py
from backend.database import SessionLocal
from backend.auth import authenticate_user, register_user, create_user_token

db = SessionLocal()

# Test 1: Login existant
user = authenticate_user(db, "admin", "admin123")
assert user is not None, "Authentification échouée"
print("✓ Test 1: Login réussi")

# Test 2: Création de token
token = create_user_token(user)
assert token.access_token, "Token non générée"
print("✓ Test 2: Token créé")

# Test 3: Enregistrement nouveau utilisateur
new_user = register_user(db, "testuser", "test@test.com", "pass123", "Test User")
assert new_user is not None, "Enregistrement échoué"
print("✓ Test 3: Nouvel utilisateur créé")

db.close()
```

Exécuter:
```bash
python test_auth.py
```

### 3.2 Test des Modèles ML
```python
# test_ml_models.py
from backend.ml_models import MLPipelineManager
from backend.data_generator import ThermalPowerPlantDataGenerator
import pandas as pd

# Générer des données
generator = ThermalPowerPlantDataGenerator()
data = generator.generate_all_data(num_days=7)

# Entraîner les modèles
manager = MLPipelineManager()
metrics = manager.train_all_models(data['readings'], data['equipment'])

print("Métriques d'entraînement:")
print(metrics)

# Test de prédiction
anomalies = manager.predict_anomalies(data['readings'])
rul_predictions = manager.predict_rul(data['readings'])

print(f"\n✓ Anomalies détectées: {sum(1 for a in anomalies.values() if a['is_anomaly'])}")
print(f"✓ Prédictions RUL: {len(rul_predictions)} équipements")
```

Exécuter:
```bash
python test_ml_models.py
```

### 3.3 Test du Chatbot RAG
```python
# test_chatbot.py
from backend.rag_chatbot import RAGChatbot, generate_default_knowledge_base

chatbot = RAGChatbot(provider="groq")

# Charger la base de connaissances
kb = generate_default_knowledge_base()
success = chatbot.add_knowledge_base(kb)
print(f"✓ Base de connaissances chargée: {success}")

# Test requête
response = chatbot.query("Quels sont les signes d'alerte pour une turbine?")
print(f"\nRéponse:\n{response['answer']}")
print(f"Confiance: {response['confidence']:.0%}")
print(f"Sources trouvées: {len(response['sources'])}")
```

Exécuter:
```bash
python test_chatbot.py
```

## 4️⃣ Tests de l'API REST

### 4.1 Démarrer l'API
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.2 Tests avec cURL ou Postman

#### Enregistrement
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "new@test.com",
    "password": "pass123",
    "full_name": "New User",
    "department": "IT"
  }'
```

#### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Réponse attendue:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "uuid...",
  "username": "admin",
  "role": "admin",
  "expires_in": 86400
}
```

#### Utiliser le token
```bash
TOKEN="<votre-token>"

curl -X GET "http://localhost:8000/api/equipment" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.3 Tester tous les endpoints
```python
# test_api.py
import requests
import json

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "admin", "password": "admin123"}
)
assert response.status_code == 200, "Login échoué"
token = response.json()["access_token"]
print("✓ Login réussi")

# Headers avec token
headers = {"Authorization": f"Bearer {token}"}

# Test tous les endpoints
endpoints = [
    "/api/equipment",
    "/api/sensors",
    "/api/readings",
    "/api/anomalies",
    "/api/predictions",
    "/api/maintenance"
]

for endpoint in endpoints:
    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
    assert response.status_code == 200, f"Erreur {endpoint}"
    print(f"✓ {endpoint}")

# Health check
response = requests.get(f"{BASE_URL}/health")
assert response.status_code == 200
print("✓ Health check")
```

Exécuter:
```bash
python test_api.py
```

## 5️⃣ Tests du Dashboard Streamlit

### 5.1 Lancer Streamlit
```bash
streamlit run streamlit_app.py --logger.level=debug
```

### 5.2 Checklist des tests
- [ ] Login avec admin/admin123 ✓
- [ ] Navigation vers Dashboard ✓
- [ ] Vérifier les métriques (équipements, capteurs)
- [ ] Consulter Monitoring temps réel ✓
- [ ] Sélectionner un équipement et voir les capteurs ✓
- [ ] Voir les graphiques historiques ✓
- [ ] Consulter les Prédictions RUL ✓
- [ ] Voir les Anomalies détectées ✓
- [ ] Tester le Chatbot RAG ✓
  - Poser une question
  - Vérifier la réponse
  - Consulter les sources
- [ ] Consulter les Ordres de Maintenance ✓
- [ ] Vérifier les Paramètres utilisateur ✓
- [ ] Test de déconnexion ✓

### 5.3 Test de performance
```python
import time
from streamlit.testing.v1 import AppTest

# Test chargement page
start = time.time()
at = AppTest.from_file("streamlit_app.py")
at.run()
load_time = time.time() - start

print(f"Temps de chargement: {load_time:.2f}s")
assert load_time < 5, "Trop lent"
print("✓ Performance OK")
```

## 6️⃣ Tests de Charge

### 6.1 Tester l'API sous charge
```bash
# Installer Apache Bench
# Ubuntu/Debian:
sudo apt-get install apache2-utils

# MacOS:
brew install httpd

# Test de charge: 100 requêtes, 10 concurrentes
ab -n 100 -c 10 -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/equipment
```

### 6.2 Résultat attendu
```
Requests per second: 50-100
Time per request: 10-20ms
Failed requests: 0
```

## 7️⃣ Tests d'Intégration End-to-End

### 7.1 Scénario complet d'utilisation
```python
# test_e2e.py
import requests
import time
from backend.database import SessionLocal
from backend.models import Equipment, Alert

BASE_URL = "http://localhost:8000"

print("=== Test E2E: Scénario Complet ===\n")

# 1. Login
print("1. Authentification...")
login_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "admin", "password": "admin123"}
)
assert login_resp.status_code == 200
token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("   ✓ Login réussi")

# 2. Obtenir les équipements
print("\n2. Récupération des équipements...")
equip_resp = requests.get(f"{BASE_URL}/api/equipment", headers=headers)
assert equip_resp.status_code == 200
print(f"   ✓ {len(equip_resp.json())} équipements")

# 3. Obtenir les lectures
print("\n3. Récupération des lectures...")
readings_resp = requests.get(f"{BASE_URL}/api/readings", headers=headers)
assert readings_resp.status_code == 200
print(f"   ✓ Données reçues")

# 4. Obtenir les prédictions
print("\n4. Récupération des prédictions...")
pred_resp = requests.get(f"{BASE_URL}/api/predictions", headers=headers)
assert pred_resp.status_code == 200
print(f"   ✓ Prédictions reçues")

# 5. Obtenir les anomalies
print("\n5. Détection des anomalies...")
anom_resp = requests.get(f"{BASE_URL}/api/anomalies", headers=headers)
assert anom_resp.status_code == 200
print(f"   ✓ Anomalies détectées")

print("\n=== Test réussi! ===")
```

Exécuter:
```bash
# Terminal 1: API FastAPI
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Test E2E
python test_e2e.py
```

## 8️⃣ Checklist de Déploiement

Avant de mettre en production:

### Sécurité
- [ ] Changer `SECRET_KEY` dans `.env`
- [ ] Changer les mots de passe de test
- [ ] Configurer CORS correctement
- [ ] Activer HTTPS
- [ ] Configurer les logs d'audit

### Performance
- [ ] Optimiser les requêtes BD (indexes)
- [ ] Configurer le cache
- [ ] Tester sous charge
- [ ] Monitorer les ressources

### Base de données
- [ ] Sauvegarder régulièrement
- [ ] Tester la restauration
- [ ] Archiver les vieilles données

### Documentation
- [ ] Mise à jour du README
- [ ] Documentation API
- [ ] Guide d'administration
- [ ] Procédures de backup

### Maintenance
- [ ] Mettre en place la surveillance
- [ ] Configurer les alertes
- [ ] Plan de continuité
- [ ] Procédures de rollback

## 9️⃣ Dépannage Common Issues

### "Erreur: Database connection refused"
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql

# Redémarrer si nécessaire
sudo systemctl restart postgresql

# Vérifier les credentials
psql -U user -h localhost -d pfe_maintenance
```

### "Erreur: Module not found"
```bash
# Réinstaller les dépendances
pip install --upgrade -r requirements.txt

# Vérifier la version Python
python --version  # Doit être 3.8+
```

### "Streamlit: Permission denied"
```bash
# Rendre le script exécutable
chmod +x run.sh streamlit_app.py

# Vérifier les permissions du répertoire
ls -la
```

### "Groq/OpenAI not available"
- C'est normal - le chatbot fonctionne quand même en mode local
- Ajoutez votre API key si vous voulez activer les LLM

## 🔟 Ressources de Test

- **Postman Collection**: Demander au développeur
- **Test Data**: Généré automatiquement par `ThermalPowerPlantDataGenerator`
- **Logs**: Vérifier `streamlit logs` et sortie du terminal

---

**Version**: 1.0.0  
**Créé**: 2024-03-31
