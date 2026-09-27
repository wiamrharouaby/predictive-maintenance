#!/usr/bin/env python3
"""
Vérifier la configuration de la base de données
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

print("📋 Configuration de la Base de Données\n")

database_url = os.getenv("DATABASE_URL", "NOT SET")
print("DATABASE_URL: [masquee]")

# Masquer le mot de passe pour la sécurité
if database_url != "NOT SET":
    parts = database_url.split("@")
    if len(parts) == 2:
        user_part = parts[0].split("://")[1]
        host_part = parts[1]
        masked = f"postgresql://[user]:[password]@{host_part}"
        print(f"Masked: {masked}")

print(f"\nSQL_ECHO: {os.getenv('SQL_ECHO', 'False')}")

# Essayer de se connecter
print("\n🔗 Tentative de connexion...")
try:
    from backend.database import engine, test_connection
    result = test_connection()
    if result:
        print("✓ Connexion réussie!")
    else:
        print("✗ Connexion échouée")
except Exception as e:
    print(f"✗ Erreur: {e}")
