#!/usr/bin/env python3
"""
Script pour initialiser les utilisateurs par défaut dans la base de données
Exécuter: python scripts/init_default_users.py
"""
import sys
import os

# Ajouter le chemin parent au sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Base, engine, create_default_users
from backend.models import User

def main():
    """Initialiser les utilisateurs par défaut"""
    print("🔧 Initialisation des utilisateurs par défaut...")
    
    # 1. Créer les tables
    print("\n1️⃣ Création des tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables créées")
    
    # 2. Créer les utilisateurs manquants sans supprimer les comptes existants
    print("\n2️⃣ Création des utilisateurs manquants...")
    create_default_users()
    
    # 4. Vérifier les utilisateurs
    print("\n4️⃣ Vérification des utilisateurs créés...")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"✓ Total d'utilisateurs dans la BD: {len(users)}")
        for user in users:
            print(f"  - {user.username} (role: {user.role}, active: {user.is_active})")
    finally:
        db.close()
    
    print("\n🎉 Initialisation terminée !")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
