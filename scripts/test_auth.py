#!/usr/bin/env python3
"""
Script de test d'authentification
Exécuter: python scripts/test_auth.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import User
from backend.auth import authenticate_user, verify_password, hash_password

def test_auth():
    """Tester l'authentification"""
    print("🧪 Test d'authentification...\n")
    
    admin_password = os.getenv("TEST_ADMIN_PASSWORD")
    if not admin_password:
        print("Test ignore: definissez TEST_ADMIN_PASSWORD hors du depot.")
        return True
    db = SessionLocal()
    
    try:
        # 1. Lister les utilisateurs
        print("1️⃣ Utilisateurs dans la BD:")
        users = db.query(User).all()
        for user in users:
            print(f"   - {user.username} | email={user.email} | role={user.role} | active={user.is_active}")
            print(f"     hash={user.password_hash[:50]}...")
        
        if not users:
            print("   ❌ Aucun utilisateur trouvé!")
            return False
        
        # 2. Tester la vérification du mot de passe pour admin
        print("\n2️⃣ Test de vérification du mot de passe (admin):")
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        if not admin_user:
            print("   ❌ Utilisateur admin non trouvé!")
            return False
        
        print(f"   Hash stocké: {admin_user.password_hash[:50]}...")
        
        password_correct = verify_password(admin_password, admin_user.password_hash)
        print(f"   verification du mot de passe configure: {password_correct}")
        
        password_wrong = verify_password("wrongpassword", admin_user.password_hash)
        print(f"   verify_password('wrongpassword', hash): {password_wrong}")
        
        # 3. Tester authenticate_user
        print("\n3️⃣ Test de authenticate_user:")
        auth_result = authenticate_user(db, "admin", admin_password)
        if auth_result:
            print(f"   ✓ Authentification réussie: {auth_result.username}")
        else:
            print(f"   ❌ Authentification échouée")
            return False
        
        print("\n✅ Tests passés!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_auth()
    sys.exit(0 if success else 1)
