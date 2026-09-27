#!/usr/bin/env python3
"""
Dashboard de débuggage - Affiche l'état de la connexion et de l'authentification
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, test_connection
from backend.models import User
from backend.auth import authenticate_user, verify_password

st.set_page_config(page_title="Debug Auth", layout="wide")

st.title("🔧 Débuggage Authentification")

# 1. Tester la connexion BD
st.header("1️⃣ Connexion à la Base de Données")
try:
    result = test_connection()
    if result:
        st.success("✓ Connexion PostgreSQL réussie!")
    else:
        st.error("✗ Connexion PostgreSQL échouée")
except Exception as e:
    st.error(f"✗ Erreur: {e}")

# 2. Lister les utilisateurs
st.header("2️⃣ Utilisateurs dans la BD")
try:
    db = SessionLocal()
    users = db.query(User).all()
    st.write(f"Total: {len(users)} utilisateurs")
    
    for user in users:
        st.write(f"- **{user.username}** | email: {user.email} | role: {user.role} | active: {user.is_active}")
        st.code(f"Hash: {user.password_hash}", language="text")
    db.close()
except Exception as e:
    st.error(f"Erreur: {e}")

# 3. Tester l'authentification
st.header("3️⃣ Test Authentification")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Test Direct")
    test_username = st.text_input("Nom d'utilisateur", value="admin")
    test_password = st.text_input("Mot de passe", type="password", value="admin123")
    
    if st.button("Tester authentification"):
        db = SessionLocal()
        try:
            user = authenticate_user(db, test_username, test_password)
            if user:
                st.success(f"✓ Authentification réussie: {user.username}")
                st.write(f"Email: {user.email}")
                st.write(f"Role: {user.role}")
            else:
                st.error(f"✗ Authentification échouée pour {test_username}")
                
                # Diagnostic
                user_obj = db.query(User).filter(User.username == test_username).first()
                if not user_obj:
                    st.warning(f"Utilisateur '{test_username}' non trouvé")
                else:
                    st.info(f"Utilisateur trouvé: {user_obj.username}")
                    st.info(f"Is active: {user_obj.is_active}")
                    
                    # Tester verify_password
                    pwd_ok = verify_password(test_password, user_obj.password_hash)
                    st.info(f"Password correct: {pwd_ok}")
        except Exception as e:
            st.error(f"Erreur: {e}")
            import traceback
            st.code(traceback.format_exc(), language="python")
        finally:
            db.close()

with col2:
    st.subheader("Infos Session")
    st.write(f"Streamlit session state keys: {list(st.session_state.keys())}")
    if "authenticated" in st.session_state:
        st.write(f"Authenticated: {st.session_state.authenticated}")
    if "user" in st.session_state:
        st.write(f"User: {st.session_state.user}")
