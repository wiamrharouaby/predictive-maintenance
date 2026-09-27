#!/bin/bash

# Script de démarrage pour le PFE Maintenance Prédictive

echo "=========================================="
echo "PFE MAINTENANCE PRÉDICTIVE - ONEE"
echo "=========================================="
echo ""

# Vérifier si .env existe
if [ ! -f .env ]; then
    echo "⚠️  Fichier .env non trouvé!"
    echo "Création de .env depuis .env.example..."
    cp .env.example .env
    echo "✓ Fichier .env créé - Mettez à jour les variables d'environnement"
fi

echo ""
echo "Installation des dépendances..."
pip install -r requirements.txt

echo ""
echo "Initialisation de la base de données..."
python scripts/init_db.py

echo ""
echo "=========================================="
echo "✓ INITIALISATION COMPLÈTE"
echo "=========================================="
echo ""
echo "Démarrage des services..."
echo ""
echo "1. API FastAPI: http://localhost:8000"
echo "2. Dashboard Streamlit: http://localhost:8501"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter"
echo ""

# Démarrer l'API FastAPI en arrière-plan
echo "Démarrage de l'API..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

# Attendre un moment pour que FastAPI démarre
sleep 3

# Démarrer Streamlit
echo "Démarrage du Dashboard Streamlit..."
streamlit run streamlit_app.py --server.port=8501

# Cleanup
kill $FASTAPI_PID 2>/dev/null
