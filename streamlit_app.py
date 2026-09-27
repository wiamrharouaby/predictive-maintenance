"""
Dashboard Streamlit pour Systeme de Maintenance Predictive ONEE
Application multi-pages avec authentification
"""
import os
import base64
import hashlib
import html
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import json
import secrets
import time
import uuid
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import joinedload

# Import des modules backend
from backend.database import SessionLocal, init_db
from backend.models import (
    User, Equipment, Sensor, SensorReading, Anomaly, Alert,
    RULPrediction, MaintenanceOrder, ChatHistory, ChatConversation
)
from backend.auth import (
    authenticate_user,
    create_user_token,
    hash_password,
    register_user,
    validate_password_strength,
)
from backend.ml_models import MLPipelineManager
from backend.rag_chatbot import RAGChatbot, generate_default_knowledge_base
from backend.data_generator import ThermalPowerPlantDataGenerator
from backend.auto_alerts import start_auto_alert_scheduler, run_auto_alert_cycle

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image_to_data_uri(image_path: Path) -> str:
    """Return an embeddable data URI for a local image asset."""
    if not image_path.exists():
        logger.warning("Logo introuvable: %s", image_path)
        return ""

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


APP_DIR = Path(__file__).resolve().parent
AUTH_LOGO_DATA_URI = image_to_data_uri(APP_DIR / "public" / "onee-auth-logo.jpeg")

# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================

st.set_page_config(
    page_title="ONEE | Maintenance prédictive",
    page_icon="public/onee-pylon.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalise
st.markdown("""
<style>
    :root {
        --onee-bg: #070b12;
        --onee-panel: rgba(15, 23, 42, 0.82);
        --onee-border: rgba(148, 163, 184, 0.22);
        --onee-text: #f8fafc;
        --onee-muted: #9ca3af;
        --onee-blue: #38bdf8;
    }

    .stApp {
        background:
            radial-gradient(circle at 18% 10%, rgba(56, 189, 248, 0.13), transparent 28rem),
            linear-gradient(135deg, #070b12 0%, #0b1220 48%, #101827 100%);
    }

    div[data-testid="stDecoration"] {
        background: linear-gradient(90deg, #38bdf8, #22c55e, #ef4444);
    }

    #MainMenu,
    footer,
    .stDeployButton,
    .stAppDeployButton,
    [data-testid="stAppDeployButton"],
    [data-testid="stStatusWidget"],
    [data-testid="stHeaderActionElements"] {
        display: none !important;
        visibility: hidden !important;
    }

    header[data-testid="stHeader"] {
        height: 2.75rem !important;
        background: transparent !important;
    }

    .block-container {
        padding-top: 1rem;
    }

    /* Menus déroulants Streamlit : flèche stable et curseur adapté. */
    div[data-testid="stSelectbox"] div[data-baseweb="select"],
    div[data-testid="stMultiSelect"] div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        cursor: pointer !important;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
        min-height: 2.65rem;
        padding-right: 0.65rem;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] svg,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] svg {
        display: block !important;
        width: 18px !important;
        min-width: 18px !important;
        height: 18px !important;
        flex: 0 0 18px !important;
        color: #cbd5e1 !important;
        fill: currentColor !important;
        cursor: pointer !important;
        pointer-events: none !important;
    }

    div[data-testid="stSelectbox"] input {
        cursor: pointer !important;
        caret-color: transparent !important;
    }

    div[data-testid="stMultiSelect"] input {
        cursor: text !important;
    }

    div[data-baseweb="popover"] [role="option"],
    ul[role="listbox"] li {
        cursor: pointer !important;
    }

    .auth-shell {
        min-height: calc(100vh - 5rem);
        display: grid;
        grid-template-columns: minmax(0, 0.95fr) minmax(360px, 1.05fr);
        gap: 2.25rem;
        align-items: center;
        max-width: 1180px;
        margin: 0 auto;
    }

    .auth-hero {
        padding: 2rem 0;
    }

    .brand-mark {
        width: min(100%, 440px);
        min-height: 126px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid rgba(56, 189, 248, 0.24);
        border-radius: 14px;
        background: rgba(248, 250, 252, 0.96);
        box-shadow: 0 22px 70px rgba(14, 165, 233, 0.2);
        padding: 0.85rem 1rem;
        margin-bottom: 1.3rem;
        box-sizing: border-box;
    }

    .brand-mark img {
        width: 100%;
        height: auto;
        display: block;
    }

    .auth-kicker {
        color: var(--onee-blue);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.7rem;
    }

    .auth-title {
        color: var(--onee-text);
        font-size: clamp(2.4rem, 5vw, 4.8rem);
        line-height: 0.98;
        font-weight: 900;
        margin: 0;
    }

    .auth-subtitle {
        color: #cbd5e1;
        max-width: 520px;
        font-size: 1.05rem;
        line-height: 1.7;
        margin: 1.35rem 0 1.7rem;
    }

    .auth-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem;
    }

    .auth-badge {
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 999px;
        color: #dbeafe;
        background: rgba(15, 23, 42, 0.58);
        padding: 0.55rem 0.8rem;
        font-size: 0.86rem;
        font-weight: 700;
    }

    .auth-card {
        border: 1px solid var(--onee-border);
        background: var(--onee-panel);
        border-radius: 18px;
        padding: 1.35rem 1.35rem 1.15rem;
        box-shadow: 0 28px 90px rgba(0, 0, 0, 0.36);
        backdrop-filter: blur(18px);
    }

    .auth-card-title {
        color: var(--onee-text);
        font-size: 1.25rem;
        font-weight: 850;
        margin: 0 0 0.15rem;
    }

    .auth-card-copy {
        color: var(--onee-muted);
        margin: 0 0 1.2rem;
        font-size: 0.93rem;
    }

    .test-accounts {
        border: 1px solid rgba(56, 189, 248, 0.18);
        border-radius: 12px;
        background: rgba(8, 47, 73, 0.42);
        padding: 0.95rem 1rem;
        margin-top: 1rem;
        color: #dbeafe;
    }

    .test-accounts strong {
        color: #7dd3fc;
    }

    .test-accounts code {
        color: #e0f2fe;
        background: rgba(2, 6, 23, 0.35);
        border: 1px solid rgba(125, 211, 252, 0.16);
        border-radius: 6px;
        padding: 0.08rem 0.32rem;
    }

    .auth-card [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        margin-bottom: 1rem;
    }

    .auth-card [data-baseweb="tab"] {
        color: #cbd5e1;
        font-weight: 800;
        padding-left: 0.3rem;
        padding-right: 0.3rem;
    }

    .auth-card label,
    .auth-card .stTextInput label {
        color: #e5e7eb !important;
        font-weight: 750;
        font-size: 0.86rem;
    }

    .auth-card .stTextInput input {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 10px;
        background: rgba(30, 41, 59, 0.92);
        color: var(--onee-text);
        min-height: 2.8rem;
    }

    .auth-card .stTextInput input:focus {
        border-color: rgba(56, 189, 248, 0.72);
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.13);
    }

    .auth-card .stButton button,
    div[data-testid="stForm"] .stButton button,
    div[data-testid="stFormSubmitButton"] button {
        border-radius: 10px;
        min-height: 2.85rem;
        font-weight: 850;
        border: 1px solid #38bdf8 !important;
        background: linear-gradient(90deg, #0369a1, #0284c7) !important;
        color: #ffffff !important;
        box-shadow: 0 14px 34px rgba(14, 165, 233, 0.24);
    }

    div[data-testid="stFormSubmitButton"] button:hover {
        border-color: #7dd3fc !important;
        background: linear-gradient(90deg, #075985, #0369a1) !important;
    }

    .auth-card .stAlert {
        border-radius: 10px;
    }

    .auth-panel-title {
        color: #f8fafc;
        font-size: 1.75rem;
        font-weight: 900;
        margin: 0 0 0.25rem;
    }

    .auth-panel-copy {
        color: #aab4c4;
        font-size: 0.98rem;
        margin: 0 0 1.25rem;
    }

    .auth-access-note {
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 12px;
        background: rgba(8, 47, 73, 0.3);
        color: #cbd5e1;
        padding: 0.85rem 0.95rem;
        margin-top: 1rem;
        font-size: 0.86rem;
        line-height: 1.55;
    }

    .auth-access-note strong {
        color: #7dd3fc;
    }

    .auth-side-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
        max-width: 500px;
        margin-top: 1.75rem;
    }

    .auth-side-stat {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.52);
        padding: 0.95rem;
        min-height: 5.6rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }

    .auth-side-stat strong {
        display: block;
        color: #f8fafc;
        font-size: 1rem;
        line-height: 1.3;
        margin-bottom: 0.3rem;
    }

    .auth-side-stat span {
        color: #9ca3af;
        font-size: 0.84rem;
        font-weight: 700;
        line-height: 1.4;
    }

    .auth-form-note {
        border: 1px solid rgba(34, 197, 94, 0.22);
        border-radius: 12px;
        background: rgba(20, 83, 45, 0.18);
        color: #bbf7d0;
        padding: 0.8rem 0.95rem;
        margin-top: 1rem;
        font-size: 0.9rem;
        line-height: 1.5;
    }

    .auth-form-card {
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 18px;
        background: rgba(15, 23, 42, 0.72);
        box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
        padding: 1rem 1.15rem 1.1rem;
    }

    .test-accounts {
        display: none !important;
    }

    .auth-top-spacer {
        height: clamp(1.5rem, 7vh, 5rem);
    }

    div[data-testid="stMetric"] {
        min-height: 132px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #cbd5e1;
        font-weight: 750;
    }

    .dashboard-state-card,
    .dashboard-alert-card {
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.62);
        color: #cbd5e1;
    }

    .dashboard-state-card {
        min-height: 255px;
        padding: 1.3rem 1.4rem;
    }

    .dashboard-state-title {
        color: #f8fafc;
        font-size: 1.15rem;
        font-weight: 850;
        margin-bottom: 0.35rem;
    }

    .dashboard-state-main {
        color: #86efac;
        font-size: 1.45rem;
        font-weight: 900;
        margin-bottom: 1rem;
    }

    .dashboard-state-line {
        border-top: 1px solid rgba(148, 163, 184, 0.14);
        padding: 0.55rem 0;
    }

    .dashboard-alert-card {
        padding: 0.9rem 1rem;
        margin-bottom: 0.7rem;
    }

    .dashboard-alert-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.35rem;
    }

    .dashboard-alert-title {
        color: #f8fafc;
        font-weight: 850;
    }

    .dashboard-alert-status {
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        color: #dbeafe;
        font-size: 0.78rem;
        font-weight: 750;
        white-space: nowrap;
    }

    .dashboard-alert-meta {
        color: #94a3b8;
        font-size: 0.84rem;
        margin-bottom: 0.25rem;
    }

    .dashboard-alert-message {
        color: #cbd5e1;
        font-size: 0.9rem;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #07111f 0%, #0b1220 58%, #070b12 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.16);
        z-index: 999;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.35rem;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        display: none;
    }

    .sidebar-brand {
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
        padding: 0.95rem;
        margin-bottom: 0.85rem;
    }

    .sidebar-brand-title {
        color: #f8fafc;
        font-weight: 900;
        font-size: 1.15rem;
        margin: 0;
    }

    .sidebar-brand-subtitle {
        color: #38bdf8;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }

    .sidebar-user {
        color: #cbd5e1;
        font-size: 0.88rem;
        margin: 0.35rem 0 1rem;
    }

    section[data-testid="stSidebar"] [role="radiogroup"] {
        gap: 0.35rem;
    }

    section[data-testid="stSidebar"] [role="radiogroup"] label {
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 0.35rem 0.55rem;
        transition: background 160ms ease, border-color 160ms ease;
    }

    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(56, 189, 248, 0.09);
        border-color: rgba(56, 189, 248, 0.18);
    }

    section[data-testid="stSidebar"] [role="radiogroup"] p {
        color: #dbeafe;
        font-weight: 750;
    }

    section[data-testid="stSidebar"] .stButton button {
        border-radius: 10px;
        border: 1px solid rgba(248, 113, 113, 0.24);
        background: rgba(127, 29, 29, 0.26);
        color: #fecaca;
        font-weight: 850;
    }

    .readonly-select-current {
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 10px;
        background: rgba(15, 23, 42, 0.82);
        color: #f8fafc;
        padding: 0.75rem 0.9rem;
        font-weight: 800;
        margin: 0.25rem 0 0.45rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .alert-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 10px;
        border-radius: 4px;
    }
    .alert-warning {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 10px;
        border-radius: 4px;
    }

    @media (max-width: 900px) {
        .auth-top-spacer {
            height: 0.75rem;
        }

        .auth-shell {
            grid-template-columns: 1fr;
            gap: 1.2rem;
            align-items: start;
        }

        .auth-hero {
            padding: 0.5rem 0 0;
        }

        .auth-card {
            padding: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE MANAGEMENT
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "token" not in st.session_state:
    st.session_state["token"] = None
if "sid" not in st.session_state:
    st.session_state["sid"] = None

SESSION_TTL_HOURS = int(os.getenv("STREAMLIT_SESSION_TTL_HOURS", "24"))
SESSION_STORE_PATH = Path(os.getenv("STREAMLIT_SESSION_STORE", ".streamlit_sessions.json"))
if not SESSION_STORE_PATH.is_absolute():
    SESSION_STORE_PATH = APP_DIR / SESSION_STORE_PATH
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))
_LOGIN_ATTEMPTS: dict[str, dict[str, float | int]] = {}


def _session_store_key(sid: str) -> str:
    """Eviter de stocker les identifiants de session en clair sur disque."""
    return hashlib.sha256(sid.encode("utf-8")).hexdigest()


def _login_attempt_key(username: str) -> str:
    return (username or "").strip().lower()


def _is_login_locked(username: str) -> bool:
    attempt = _LOGIN_ATTEMPTS.get(_login_attempt_key(username))
    return bool(attempt and float(attempt["locked_until"]) > time.time())


def _register_login_failure(username: str) -> None:
    key = _login_attempt_key(username)
    attempt = _LOGIN_ATTEMPTS.setdefault(key, {"count": 0, "locked_until": 0.0})
    attempt["count"] = int(attempt["count"]) + 1
    if int(attempt["count"]) >= MAX_LOGIN_ATTEMPTS:
        attempt["locked_until"] = time.time() + LOGIN_LOCKOUT_SECONDS


def _clear_login_failures(username: str) -> None:
    _LOGIN_ATTEMPTS.pop(_login_attempt_key(username), None)


def _load_session_store() -> dict:
    if not SESSION_STORE_PATH.exists():
        return {}
    try:
        with SESSION_STORE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_session_store(store: dict) -> None:
    try:
        with SESSION_STORE_PATH.open("w", encoding="utf-8") as handle:
            json.dump(store, handle)
    except Exception:
        logger.exception("Impossible d'enregistrer les sessions Streamlit")

def get_query_param(name: str, default: str = "") -> str:
    try:
        if hasattr(st, "query_params"):
            value = st.query_params.get(name, default)
        else:
            value = st.experimental_get_query_params().get(name, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value or default
    except Exception:
        return default

def set_query_params(**updates: str) -> None:
    try:
        if hasattr(st, "query_params"):
            for key, value in updates.items():
                if value is None:
                    st.query_params.pop(key, None)
                else:
                    st.query_params[key] = str(value)
            return

        params = st.experimental_get_query_params()
        for key, value in updates.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        st.experimental_set_query_params(**params)
    except Exception:
        pass

def set_query_param(name: str, value: str) -> None:
    set_query_params(**{name: value})

def remove_query_param(name: str) -> None:
    try:
        set_query_params(**{name: None})
    except Exception:
        pass

def clear_query_params() -> None:
    try:
        if hasattr(st, "query_params"):
            st.query_params.clear()
        else:
            st.experimental_set_query_params()
    except Exception:
        pass

def create_browser_session(user: dict) -> str:
    sid = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    store = _load_session_store()
    store[_session_store_key(sid)] = {
        "user": user,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    _save_session_store(store)
    return sid

def restore_session_from_sid() -> None:
    """Restaurer la session apres actualisation sans mettre le JWT dans l'URL."""
    if st.session_state.get("authenticated"):
        return

    sid = get_query_param("sid")
    if not sid:
        return

    store = _load_session_store()
    session_key = _session_store_key(sid)
    session = store.get(session_key)
    if not session:
        remove_query_param("sid")
        return

    try:
        expires_at = datetime.fromisoformat(session["expires_at"])
    except Exception:
        expires_at = datetime.utcnow() - timedelta(seconds=1)

    if expires_at < datetime.utcnow():
        store.pop(session_key, None)
        _save_session_store(store)
        remove_query_param("sid")
        return

    st.session_state.authenticated = True
    st.session_state.user = session["user"]
    st.session_state.token = create_user_token(session["user"]).access_token
    st.session_state.sid = sid

restore_session_from_sid()

if "ml_manager" not in st.session_state:
    st.session_state.ml_manager = MLPipelineManager()

if "chatbot" not in st.session_state:
    st.session_state.chatbot = RAGChatbot(provider="groq")

# Initialiser la base et appliquer les migrations une fois par processus.
@st.cache_resource
def initialize_database_once():
    init_db()
    return True


initialize_database_once()

if "auto_alert_scheduler_started" not in st.session_state:
    start_auto_alert_scheduler()
    st.session_state.auto_alert_scheduler_started = True

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def login_user(username: str, password: str) -> bool:
    """Authentifier un utilisateur"""
    import traceback

    username = (username or "").strip()
    if not username or not password:
        return False
    if _is_login_locked(username):
        logger.warning("Connexion temporairement bloquee apres plusieurs echecs")
        return False
    
    db = None
    try:
        db = SessionLocal()
        user = authenticate_user(db, username, password)

        if not user:
            _register_login_failure(username)
            logger.warning("Echec d'authentification")
            return False

        _clear_login_failures(username)
        
        # IMPORTANT: copier les donnees AVANT fermeture session
        safe_user = {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "department": user.department,
            "must_change_password": bool(user.must_change_password),
        }

        token_data = create_user_token(safe_user)

        st.session_state.authenticated = True
        st.session_state.user = safe_user
        st.session_state.token = token_data.access_token
        st.session_state.sid = create_browser_session(safe_user)
        # Toujours ouvrir le chatbot sur une nouvelle discussion apres connexion.
        # Les conversations existantes restent accessibles depuis le panneau lateral.
        st.session_state.pop("chat_conversations_user_id", None)
        st.session_state.active_chat_conversation_id = None
        st.session_state.chat_history = []
        st.session_state.pop("chat_history_cache_key", None)
        st.session_state.pop("pending_chat_question", None)
        set_query_params(sid=st.session_state.sid, page=get_query_param("page", "dashboard"))

        return True
        
    except Exception as e:
        logger.error(f"âŒ Erreur lors de la connexion: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if db is not None:
            db.close()

def logout_user():
    """Deconnecter l'utilisateur"""
    sid = st.session_state.get("sid") or get_query_param("sid")
    if sid:
        store = _load_session_store()
        store.pop(_session_store_key(sid), None)
        store.pop(sid, None)
        _save_session_store(store)
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.token = None
    st.session_state.sid = None
    st.session_state.pop("chat_history", None)
    st.session_state.pop("chat_history_user_id", None)
    st.session_state.pop("chat_conversations_user_id", None)
    st.session_state.pop("active_chat_conversation_id", None)
    st.session_state.pop("chat_history_cache_key", None)
    st.session_state.pop("pending_chat_question", None)
    clear_query_params()

def get_db():
    """Obtenir une session de base de donnees"""
    return SessionLocal()

SEVERITY_EXAMPLE_ALERTS = {
    "critical": {
        "title": "Surchauffe critique de la turbine",
        "score": 0.91,
        "description": (
            "Température critique détectée sur la turbine. Réduire la charge, "
            "contrôler le circuit de refroidissement et lancer une inspection immédiate."
        ),
    },
    "high": {
        "title": "Vibration élevée détectée",
        "score": 0.72,
        "description": (
            "Vibration élevée détectée : diagnostic rapide et contrôle "
            "mécanique recommandés."
        ),
    },
    "medium": {
        "title": "Dérive modérée de température",
        "score": 0.45,
        "description": (
            "Dérive modérée de température : surveillance renforcée lors "
            "des prochains cycles."
        ),
    },
    "low": {
        "title": "Variation mineure de pression",
        "score": 0.18,
        "description": (
            "Variation mineure de pression : aucun impact immédiat, "
            "événement conservé pour le suivi."
        ),
    },
    "high_pressure": {
        "severity": "high",
        "title": "Pression élevée de la chaudière",
        "score": 0.76,
        "description": (
            "La pression vapeur dépasse la plage normale de fonctionnement. "
            "Vérifier les soupapes, le régulateur et le circuit vapeur sous 8 heures."
        ),
    },
}


def ensure_severity_example_alerts(db) -> None:
    """Créer une seule fois les alertes de référence utilisées dans tous les modules."""
    equipment_list = (
        db.query(Equipment)
        .filter(Equipment.is_active.is_(True))
        .order_by(Equipment.equipment_code)
        .all()
    )
    if not equipment_list:
        return

    examples_created = False
    for example_index, (example_key, definition) in enumerate(
        SEVERITY_EXAMPLE_ALERTS.items()
    ):
        severity = definition.get("severity", example_key)
        existing_alert = (
            db.query(Alert)
            .filter(Alert.title == definition["title"])
            .first()
        )
        if existing_alert is not None:
            continue
        equipment = equipment_list[example_index % len(equipment_list)]
        db.add(Alert(
            equipment_id=equipment.id,
            title=definition["title"],
            message=definition["description"],
            alert_type="ml_anomaly",
            severity=severity,
            status="active",
            created_at=datetime.now(ZoneInfo("Africa/Casablanca")) - timedelta(
                minutes=(example_index + 1) * 12
            ),
        ))
        examples_created = True
    if examples_created:
        db.commit()


def has_role(*roles: str) -> bool:
    """Verifier le role de l'utilisateur connecte."""
    user = st.session_state.get("user") or {}
    return user.get("role") in set(roles)

def can_manage_maintenance() -> bool:
    """Droits necessaires pour traiter alertes et ordres."""
    return has_role("admin", "engineer", "technician")

def initialize_demo_data():
    """Initialiser les donnees de demonstration"""
    if not st.session_state.get("demo_data_initialized", False):
        with st.spinner("Generation des donnees de demonstration..."):
            generator = ThermalPowerPlantDataGenerator()
            demo_data = generator.generate_all_data(num_days=7)
            
            st.session_state.demo_data = demo_data
            st.session_state.demo_data_initialized = True
            logger.info(f"e Donnees de demo generees: {len(demo_data['readings'])} lectures")

def readonly_choice(label, options, key, format_func=lambda value: value):
    """Selection non editable: affiche une liste de choix sans champ de saisie."""
    if not options:
        return None

    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]

    selected = st.session_state[key]
    st.markdown(f"**{label}**")
    st.markdown(
        f'<div class="readonly-select-current">{format_func(selected)}</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Changer la selection", expanded=False):
        selected = st.radio(
            label,
            options=options,
            index=options.index(st.session_state[key]),
            format_func=format_func,
            key=f"{key}_radio",
            label_visibility="collapsed",
        )
        st.session_state[key] = selected

    return selected


# ============================================================
# PAGE: AUTHENTIFICATION
# ============================================================


def page_auth_final():
    """Ecran de connexion final."""

    st.markdown('<div class="auth-top-spacer"></div>', unsafe_allow_html=True)
    left_col, right_col = st.columns([0.9, 1.1], gap="large")

    with left_col:
        st.markdown(f"""
            <section class="auth-hero">
                <div class="brand-mark" aria-label="Logo ONEE">
                    <img src="{AUTH_LOGO_DATA_URI}" alt="Office National de l'Electricite et de l'Eau Potable" />
                </div>
                <div class="auth-kicker">Supervision industrielle · ONEE</div>
                <h1 class="auth-title">Plateforme intelligente de maintenance prédictive</h1>
                <p class="auth-subtitle">
                    <strong>Centrale Thermique de Mohammedia – ONEE</strong><br>
                    Supervision, détection d'anomalies et aide à la décision pour les équipements critiques.
                </p>
                <div class="auth-badges">
                    <span class="auth-badge">IA & Détection d'anomalies</span>
                    <span class="auth-badge">Chatbot RAG</span>
                    <span class="auth-badge">Prédiction RUL</span>
                </div>
                <div class="auth-side-grid">
                    <div class="auth-side-stat"><strong>📡 Supervision</strong><span>Suivi des mesures capteurs</span></div>
                    <div class="auth-side-stat"><strong>📈 Prédiction RUL</strong><span>Durée de vie restante estimée</span></div>
                    <div class="auth-side-stat"><strong>🚨 Alertes</strong><span>Détection et priorisation</span></div>
                    <div class="auth-side-stat"><strong>📋 Maintenance</strong><span>Ordres et historique des interventions</span></div>
                </div>
            </section>
        """, unsafe_allow_html=True)

    with right_col:
        with st.container(border=True, width=900):
            st.markdown("""
                <p class="auth-panel-title">Connexion</p>
                <p class="auth-panel-copy">
                    Accédez à votre espace sécurisé de supervision et de maintenance.
                </p>
            """, unsafe_allow_html=True)

            with st.form("login_form"):
                username = st.text_input("Nom d'utilisateur", placeholder="Votre identifiant ONEE")
                password = st.text_input("Mot de passe", type="password", placeholder="Votre mot de passe")

                submitted = st.form_submit_button("Se connecter", use_container_width=True, type="primary")

                if submitted:
                    if login_user(username, password):
                        st.rerun()
                    elif _is_login_locked(username):
                        st.error("Trop de tentatives. Réessayez dans quelques minutes.")
                    else:
                        st.error("Identifiants invalides.")

            st.markdown("""
                <div class="auth-access-note">
                    <strong>🔒 Accès sécurisé à la plateforme</strong><br>
                    Les comptes utilisateurs sont gérés par l'administrateur.<br>
                    En cas d'oubli du mot de passe, contactez l'administrateur.
                </div>
            """, unsafe_allow_html=True)


def page_force_password_change():
    """Imposer le remplacement du mot de passe temporaire avant tout acces."""
    st.title("🔐 Sécurisation de votre compte")
    st.info(
        "Vous utilisez un mot de passe temporaire. Définissez votre mot de passe personnel "
        "avant d’accéder à la plateforme."
    )
    with st.form("force_password_change_form"):
        new_password = st.text_input("Nouveau mot de passe", type="password")
        confirmation = st.text_input("Confirmer le nouveau mot de passe", type="password")
        submitted = st.form_submit_button(
            "Enregistrer mon mot de passe",
            type="primary",
            use_container_width=True,
        )
        if submitted:
            current_user = st.session_state.user
            errors = validate_password_strength(
                new_password,
                current_user.get("username", ""),
                current_user.get("email", ""),
                current_user.get("full_name", ""),
            )
            if new_password != confirmation:
                st.error("Les deux mots de passe ne correspondent pas.")
            elif errors:
                st.error("Mot de passe trop faible : " + ", ".join(errors) + ".")
            else:
                db = get_db()
                try:
                    db_user = db.query(User).filter(
                        User.id == uuid.UUID(current_user["id"])
                    ).first()
                    if db_user is None or not db_user.is_active:
                        st.error("Compte introuvable ou désactivé.")
                        return
                    db_user.password_hash = hash_password(new_password)
                    db_user.must_change_password = False
                    db_user.updated_at = datetime.utcnow()
                    db.commit()
                    st.session_state.user["must_change_password"] = False
                    sid = st.session_state.get("sid")
                    if sid:
                        store = _load_session_store()
                        stored = store.get(_session_store_key(sid))
                        if stored:
                            stored["user"] = st.session_state.user
                            _save_session_store(store)
                    st.success("Mot de passe mis à jour. Votre espace est maintenant accessible.")
                    st.rerun()
                finally:
                    db.close()


# ============================================================
# PAGE: DASHBOARD PRINCIPAL
# ============================================================

def page_dashboard():
    """Dashboard principal"""
    
    st.title("📊 Tableau de bord principal")

    db = get_db()

    try:
        ensure_severity_example_alerts(db)
        equipment_count = db.query(Equipment).filter(Equipment.is_active == True).count()
        sensor_count = db.query(Sensor).filter(Sensor.is_active == True).count()
        active_alerts = db.query(Alert).filter(Alert.status == "active").count()
        anomalies = db.query(Anomaly).filter(Anomaly.acknowledged_by == None).count()

        col1, col2, col3, col4 = st.columns(4)
        with col1.container(border=True):
            st.metric("⚙️ Équipements actifs", equipment_count)
            st.caption("Équipements actuellement supervisés")
        with col2.container(border=True):
            st.metric("📡 Capteurs supervisés", sensor_count)
            st.caption("Mesures disponibles dans la plateforme")
        with col3.container(border=True):
            st.metric("🚨 Alertes actives", active_alerts)
            st.caption("🔴 Action requise" if active_alerts else "🟢 Situation normale")
        with col4.container(border=True):
            st.metric("🔍 Anomalies à vérifier", anomalies)
            st.caption("🟠 Vérification requise" if anomalies else "🟢 Aucune anomalie")

        st.divider()

        col1, col2 = st.columns([1.1, 0.9])

        with col1:
            st.subheader("Distribution des équipements")
            type_rows = []
            equipment_rows = (
                db.query(Equipment)
                .options(joinedload(Equipment.equipment_type))
                .filter(Equipment.is_active.is_(True))
                .all()
            )
            for equipment in equipment_rows:
                type_rows.append({
                    "Type": equipment.equipment_type.name if equipment.equipment_type else "Non classe",
                    "Équipement": equipment.equipment_code,
                })
            if type_rows:
                type_df = pd.DataFrame(type_rows)
                type_counts = type_df["Type"].value_counts().reset_index()
                type_counts.columns = ["Type", "Nombre"]
                fig = px.pie(type_counts, values="Nombre", names="Type", hole=0.52)
                fig.update_traces(
                    textinfo="label+value",
                    hovertemplate="%{label}<br>%{value} équipement(s)<br>%{percent}<extra></extra>",
                )
                fig.update_layout(
                    height=300,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend_title_text="Type d'équipement",
                )
                st.plotly_chart(fig, use_container_width=True, key="dashboard_equipment_type_chart")
            else:
                st.info("Aucun équipement actif.")

        with col2:
            st.subheader("État du système")
            active_alert_rows = db.query(Alert).filter(Alert.status == "active").all()
            if active_alert_rows:
                severity_labels = {
                    "critical": "🔴 Critiques",
                    "high": "🟠 Élevées",
                    "medium": "🟡 Moyennes",
                    "low": "🔵 Faibles",
                }
                severity_counts = pd.Series(
                    [alert.severity or "low" for alert in active_alert_rows]
                ).value_counts()
                severity_lines = "".join(
                    f'<div class="dashboard-state-line">{label} : '
                    f'<strong>{int(severity_counts.get(level, 0))}</strong></div>'
                    for level, label in severity_labels.items()
                )
                st.markdown(
                    f'<div class="dashboard-state-card">'
                    f'<div class="dashboard-state-title">⚠️ Surveillance requise</div>'
                    f'<div class="dashboard-state-main" style="color:#fca5a5">'
                    f'{active_alerts} alerte(s) active(s)</div>{severity_lines}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="dashboard-state-card">'
                    f'<div class="dashboard-state-title">🟢 État du système</div>'
                    f'<div class="dashboard-state-main">Fonctionnement normal</div>'
                    f'<div class="dashboard-state-line">Aucune alerte active</div>'
                    f'<div class="dashboard-state-line">'
                    f'{"Aucune anomalie non confirmée" if anomalies == 0 else f"{anomalies} anomalie(s) à vérifier"}'
                    f'</div><div class="dashboard-state-line">'
                    f'{equipment_count}/{equipment_count} équipements supervisés</div></div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        st.subheader("Historique récent des alertes")

        alerts = (
            db.query(Alert)
            .options(joinedload(Alert.equipment))
            .order_by(Alert.created_at.desc().nullslast())
            .limit(8)
            .all()
        )

        if alerts:
            for alert in alerts:
                severity_label = {
                    "critical": "🔴 Critique",
                    "high": "🟠 Élevée",
                    "medium": "🟡 Moyenne",
                    "low": "🔵 Faible",
                }.get(alert.severity, "⚪ Information")
                status_label = {
                    "active": "⚠ Active",
                    "acknowledged": "✓ Acquittée",
                    "resolved": "✓ Résolue",
                    "closed": "✓ Clôturée",
                }.get(alert.status, alert.status or "Inconnu")
                equipment_name = alert.equipment.name if alert.equipment else "Équipement inconnu"
                alert_date = (
                    alert.created_at.strftime("%d/%m/%Y %H:%M")
                    if alert.created_at else "Date indisponible"
                )
                st.markdown(
                    f'<div class="dashboard-alert-card">'
                    f'<div class="dashboard-alert-head"><div class="dashboard-alert-title">'
                    f'{severity_label} — {html.escape(alert.title or "Alerte")}</div>'
                    f'<span class="dashboard-alert-status">{html.escape(status_label)}</span></div>'
                    f'<div class="dashboard-alert-meta">{html.escape(equipment_name)} · {alert_date}</div>'
                    f'<div class="dashboard-alert-message">{html.escape(alert.message or "")}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.success("Aucune alerte enregistrée")
    except Exception as e:
        st.warning(f"Erreur lors du chargement du dashboard: {str(e)}")
    finally:
        db.close()

# ============================================================
# PAGE: MONITORING EN TEMPS ReEL
# ============================================================

def page_monitoring():
    """Page de monitoring temps reel"""
    
    st.title("Supervision dynamique")

    st.markdown("""
    <style>
        .sensor-card {
            border: 1px solid var(--onee-border);
            border-left: 5px solid #22c55e;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: rgba(15, 23, 42, 0.78);
            min-height: 220px;
        }
        .sensor-card.warning { border-left-color: #facc15; background: rgba(113, 63, 18, 0.16); }
        .sensor-card.critical { border-left-color: #ef4444; background: rgba(127, 29, 29, 0.17); }
        .sensor-card.unknown { border-left-color: #94a3b8; }
        .sensor-card-title { color: #cbd5e1; font-size: .88rem; margin-bottom: .4rem; }
        .sensor-card-value { color: #f8fafc; font-size: 1.75rem; font-weight: 700; line-height: 1.2; }
        .sensor-card-meta { color: #cbd5e1; font-size: .78rem; margin-top: .45rem; }
        .sensor-badges { display: flex; flex-wrap: wrap; gap: .35rem; margin: .7rem 0; }
        .sensor-badge { border-radius: 999px; padding: .2rem .55rem; font-size: .72rem; font-weight: 700; }
        .sensor-badge.normal { color: #bbf7d0; background: rgba(34, 197, 94, .18); }
        .sensor-badge.warning { color: #fef08a; background: rgba(250, 204, 21, .18); }
        .sensor-badge.critical { color: #fecaca; background: rgba(239, 68, 68, .2); }
        .sensor-badge.online { color: #bae6fd; background: rgba(14, 165, 233, .18); }
        .sensor-progress { height: 7px; overflow: hidden; border-radius: 999px; background: rgba(148,163,184,.2); margin-top: .35rem; }
        .sensor-progress > span { display: block; height: 100%; border-radius: inherit; background: #22c55e; }
        .sensor-card.warning .sensor-progress > span { background: #facc15; }
        .sensor-card.critical .sensor-progress > span { background: #ef4444; }
    </style>
    """, unsafe_allow_html=True)

    simulation_enabled = True
    refresh_seconds = 5
    if st_autorefresh is not None:
        st_autorefresh(
            interval=refresh_seconds * 1000,
            limit=None,
            key="monitoring_synthetic_refresh",
        )
    
    db = get_db()

    def to_float(value):
        return float(value) if value is not None else None

    def sensor_unit(sensor):
        """Retourne une unité exploitable même si les données importées contiennent None."""
        raw_unit = sensor.unit or (sensor.sensor_type.unit if sensor.sensor_type else "")
        if raw_unit and str(raw_unit).strip().lower() not in {"none", "null", "n/a"}:
            return str(raw_unit).strip()

        name = (sensor.name or sensor.sensor_code or "").lower()
        unit_rules = (
            (("temp",), "°C"),
            (("courant", "current", "amp"), "A"),
            (("tension", "voltage"), "kV"),
            (("vibration",), "mm/s"),
            (("pression", "pressure"), "bar"),
            (("vitesse", "speed", "rotation"), "tr/min"),
            (("fréquence", "frequence", "frequency"), "Hz"),
            (("débit", "debit", "flow"), "m³/h"),
        )
        for keywords, unit in unit_rules:
            if any(keyword in name for keyword in keywords):
                return unit
        return "u.a."

    def synthetic_profile(sensor, min_value, max_value):
        """Définit une plage nominale réaliste à partir du type de mesure."""
        name = (sensor.name or sensor.sensor_code or "").lower()
        profiles = (
            (("temp",), (45.0, 85.0, 1.2)),
            (("courant", "current", "amp"), (2600.0, 3400.0, 35.0)),
            (("tension", "voltage"), (18.0, 22.0, 0.18)),
            (("vibration",), (1.2, 4.5, 0.16)),
            (("pression", "pressure"), (90.0, 140.0, 1.5)),
            (("vitesse", "speed", "rotation"), (2950.0, 3050.0, 8.0)),
            (("fréquence", "frequence", "frequency"), (49.8, 50.2, 0.025)),
            (("débit", "debit", "flow"), (350.0, 650.0, 8.0)),
        )
        for keywords, profile in profiles:
            if any(keyword in name for keyword in keywords):
                return profile

        low = min_value if min_value is not None else 0.0
        high = max_value if max_value is not None and max_value > low else low + 100.0
        margin = (high - low) * 0.2
        return low + margin, high - margin, max((high - low) * 0.015, 0.01)

    def synthetic_thresholds(sensor, min_value, max_value):
        """Corrige en simulation les seuils génériques 0–100 issus de l'ancien import."""
        name = (sensor.name or sensor.sensor_code or "").lower()
        threshold_rules = (
            (("temp",), (20.0, 120.0)),
            (("courant", "current", "amp"), (1000.0, 5000.0)),
            (("tension", "voltage"), (10.0, 25.0)),
            (("vibration",), (0.0, 8.0)),
            (("pression", "pressure"), (50.0, 250.0)),
            (("vitesse", "speed", "rotation"), (2000.0, 4000.0)),
            (("fréquence", "frequence", "frequency"), (49.5, 50.5)),
            (("débit", "debit", "flow"), (100.0, 1000.0)),
        )
        for keywords, thresholds in threshold_rules:
            if any(keyword in name for keyword in keywords):
                return thresholds
        return min_value, max_value

    def synthetic_value(sensor, timestamp, min_value, max_value):
        """Produit une valeur stable pour un intervalle, avec tendance et bruit déterministes."""
        low, high, noise = synthetic_profile(sensor, min_value, max_value)
        center = (low + high) / 2
        amplitude = max((high - low) * 0.18, noise)
        sensor_key = str(sensor.id)
        phase_seed = int(hashlib.sha256(sensor_key.encode("utf-8")).hexdigest()[:8], 16)
        bucket = int(timestamp.timestamp() // max(refresh_seconds, 1))
        noise_seed = int(
            hashlib.sha256(f"{sensor_key}:{bucket}".encode("utf-8")).hexdigest()[:8],
            16,
        )
        rng = np.random.default_rng(noise_seed)
        phase = (phase_seed % 360) * np.pi / 180
        cycle = np.sin(bucket / 12 + phase) + 0.35 * np.sin(bucket / 31 + phase / 2)
        value = center + amplitude * cycle + rng.normal(0, noise)
        return round(float(np.clip(value, low, high)), 2)

    def sensor_status(value, min_value, max_value):
        if value is None:
            return "unknown", "Aucune donnee"
        if max_value is not None and value > max_value:
            return "critical", "Critique"
        if min_value is not None and value < min_value:
            return "critical", "Critique"
        utilization = sensor_utilization(value, min_value, max_value)
        if utilization is not None and utilization >= 80:
            return "warning", "Attention"
        return "normal", "Normal"

    def sensor_utilization(value, min_value, max_value):
        if value is None or min_value is None or max_value is None or max_value <= min_value:
            return None
        return (value - min_value) / (max_value - min_value) * 100

    def format_number(value):
        if value is None:
            return "N/A"
        formatted = f"{value:.2f}".rstrip("0").rstrip(".")
        return formatted

    def format_delta(delta, unit):
        if delta is None:
            return "Δ N/A"
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        magnitude = f"{abs(delta):.2f}".rstrip("0")
        if magnitude.endswith("."):
            magnitude += "0"
        sign = "+" if delta >= 0 else "-"
        return f"{arrow} Δ {sign}{magnitude} {unit}"

    def status_badge(status_key, status_label):
        icon = {"normal": "🟢", "warning": "🟡", "critical": "🔴", "unknown": "⚪"}.get(status_key, "⚪")
        return f"{icon} {status_label}"

    try:
        equipment_list = (
            db.query(Equipment)
            .filter(Equipment.is_active.is_(True))
            .order_by(Equipment.equipment_code)
            .all()
        )
        equipment_options = {eq.equipment_code: eq for eq in equipment_list}

        if not equipment_options:
            st.warning("Aucun Equipement disponible")
            return

        selected_equipment = readonly_choice(
            "Selectionner un Equipement",
            options=list(equipment_options.keys()),
            key="monitoring_equipment_choice",
            format_func=lambda code: f"{code} - {equipment_options[code].name}"
        )

        equipment = equipment_options[selected_equipment]
        sensors = (
            db.query(Sensor)
            .options(joinedload(Sensor.sensor_type))
            .filter(Sensor.equipment_id == equipment.id, Sensor.is_active.is_(True))
            .order_by(Sensor.name)
            .all()
        )

        ranked_readings = (
            db.query(
                SensorReading.id.label("reading_id"),
                SensorReading.sensor_id.label("sensor_id"),
                func.row_number()
                .over(
                    partition_by=SensorReading.sensor_id,
                    order_by=SensorReading.timestamp.desc().nullslast(),
                )
                .label("rank"),
            )
            .filter(SensorReading.sensor_id.in_([sensor.id for sensor in sensors]))
            .subquery()
        )
        reading_rows = (
            db.query(SensorReading, ranked_readings.c.rank)
            .join(ranked_readings, SensorReading.id == ranked_readings.c.reading_id)
            .filter(ranked_readings.c.rank <= 2)
            .all()
        )
        readings_by_sensor = {}
        for reading, rank in reading_rows:
            readings_by_sensor.setdefault(reading.sensor_id, {})[rank] = reading

        st.subheader(f"{equipment.name} ({equipment.location or 'Site non renseigne'})")

        latest_rows = []
        critical_count = 0
        warning_count = 0
        simulation_now = datetime.now(ZoneInfo("Africa/Casablanca"))

        for sensor in sensors:
            sensor_readings = readings_by_sensor.get(sensor.id, {})
            latest = sensor_readings.get(1)
            previous = sensor_readings.get(2)
            min_value = to_float(sensor.min_value)
            max_value = to_float(sensor.max_value)
            if simulation_enabled:
                min_value, max_value = synthetic_thresholds(sensor, min_value, max_value)
                value = synthetic_value(sensor, simulation_now, min_value, max_value)
                previous_value = synthetic_value(
                    sensor,
                    simulation_now - timedelta(seconds=refresh_seconds),
                    min_value,
                    max_value,
                )
                reading_timestamp = simulation_now
            else:
                value = to_float(latest.value) if latest else None
                previous_value = to_float(previous.value) if previous else None
                reading_timestamp = latest.timestamp if latest else None
            status_key, status_label = sensor_status(value, min_value, max_value)
            utilization = sensor_utilization(value, min_value, max_value)
            unit = sensor_unit(sensor)

            if status_key == "critical":
                critical_count += 1
            elif status_key == "warning":
                warning_count += 1

            latest_rows.append({
                "Capteur": sensor.name or sensor.sensor_code,
                "Valeur": value,
                "Unité": unit,
                "Min": min_value,
                "Max": max_value,
                "Statut": status_label,
                "status_key": status_key,
                "Utilisation (%)": utilization,
                "Horodatage": reading_timestamp,
                "Delta": None if value is None or previous_value is None else value - previous_value,
                "sensor_id": sensor.id,
                "sensor": sensor,
            })

        active_alerts = (
            db.query(Alert)
            .filter(Alert.equipment_id == equipment.id, Alert.status == "active")
            .count()
        )
        global_status = "Critique" if critical_count else "Attention" if warning_count or active_alerts else "Normal"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capteurs actifs", len(sensors))
        col2.metric("Etat global", global_status)
        col3.metric("Alertes actives", active_alerts)
        col4.metric("Capteurs hors seuil", critical_count + warning_count)
        st.caption(f"🕒 Dernière mise à jour : **{simulation_now:%H:%M:%S}**")

        st.divider()

        if not latest_rows:
            st.info("Aucun capteur actif pour cet Equipement.")
            return

        metric_cols = st.columns(min(4, len(latest_rows)))
        for idx, row in enumerate(latest_rows[:8]):
            with metric_cols[idx % len(metric_cols)]:
                utilization = row["Utilisation (%)"]
                progress = max(0, min(100, utilization or 0))
                utilization_text = "N/A" if utilization is None else f"{utilization:.0f} %"
                range_text = (
                    "Non définie"
                    if row["Min"] is None or row["Max"] is None
                    else f"{format_number(row['Min'])} – {format_number(row['Max'])} {row['Unité']}"
                )
                st.markdown(
                    f"""
                    <div class="sensor-card {row['status_key']}">
                        <div class="sensor-card-title">{html.escape(str(row['Capteur']))}</div>
                        <div class="sensor-card-value">{format_number(row['Valeur'])} {html.escape(row['Unité'])}</div>
                        <div class="sensor-badges">
                            <span class="sensor-badge {row['status_key']}">{status_badge(row['status_key'], row['Statut'])}</span>
                            <span class="sensor-badge online">● Capteur actif / En ligne</span>
                        </div>
                        <div class="sensor-card-meta">Plage normale : {range_text}</div>
                        <div class="sensor-card-meta">Utilisation : <strong>{utilization_text}</strong></div>
                        <div class="sensor-progress"><span style="width:{progress:.1f}%"></span></div>
                        <div class="sensor-card-meta">{html.escape(format_delta(row['Delta'], row['Unité']))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()
        st.subheader("Dernieres mesures")
        display_df = pd.DataFrame([
            {
                "Capteur": row["Capteur"],
                "Valeur": f"{format_number(row['Valeur'])} {row['Unité']}",
                "Plage normale": (
                    "N/A"
                    if row["Min"] is None or row["Max"] is None
                    else f"{format_number(row['Min'])} – {format_number(row['Max'])} {row['Unité']}"
                ),
                "Utilisation (%)": (
                    None if row["Utilisation (%)"] is None else round(row["Utilisation (%)"], 1)
                ),
                "Statut": status_badge(row["status_key"], row["Statut"]),
                "Horodatage": (
                    row["Horodatage"].strftime("%d/%m/%Y %H:%M:%S")
                    if row["Horodatage"] is not None else "N/A"
                ),
                "Delta": format_delta(row["Delta"], row["Unité"]),
            }
            for row in latest_rows
        ])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        selected_sensor_name = readonly_choice(
            "Historique capteur",
            options=[row["Capteur"] for row in latest_rows],
            key="monitoring_sensor_choice",
        )
        selected_row = next(row for row in latest_rows if row["Capteur"] == selected_sensor_name)
        history_limit = st.slider("Nombre de points", min_value=20, max_value=500, value=120, step=20)

        if simulation_enabled:
            history_df = pd.DataFrame([
                {
                    "timestamp": simulation_now - timedelta(seconds=refresh_seconds * offset),
                    "value": synthetic_value(
                        selected_row["sensor"],
                        simulation_now - timedelta(seconds=refresh_seconds * offset),
                        selected_row["Min"],
                        selected_row["Max"],
                    ),
                }
                for offset in reversed(range(history_limit))
            ])
        else:
            history = (
                db.query(SensorReading)
                .filter(SensorReading.sensor_id == selected_row["sensor_id"])
                .order_by(SensorReading.timestamp.desc())
                .limit(history_limit)
                .all()
            )
            history_df = pd.DataFrame([
                {"timestamp": reading.timestamp, "value": float(reading.value or 0)}
                for reading in reversed(history)
            ])

        if not history_df.empty:
            fig = px.line(
                history_df,
                x="timestamp",
                y="value",
                title=f"Historique - {selected_sensor_name}",
                labels={"timestamp": "Temps", "value": f"Valeur ({selected_row['Unité']})"},
            )
            min_threshold = selected_row["Min"]
            max_threshold = selected_row["Max"]
            if min_threshold is not None and max_threshold is not None:
                fig.add_hrect(
                    y0=min_threshold,
                    y1=max_threshold,
                    fillcolor="rgba(34, 197, 94, 0.10)",
                    line_width=0,
                    layer="below",
                    annotation_text="Zone normale",
                    annotation_position="top left",
                )
            if min_threshold is not None:
                fig.add_hline(
                    y=min_threshold,
                    line_dash="dash",
                    line_color="#f59e0b",
                    annotation_text="Seuil minimal",
                    annotation_position="bottom right",
                )
            if max_threshold is not None:
                fig.add_hline(
                    y=max_threshold,
                    line_dash="dash",
                    line_color="#ef4444",
                    annotation_text="Seuil maximal",
                    annotation_position="top right",
                )
            last_point = history_df.iloc[-1]
            fig.add_trace(go.Scatter(
                x=[last_point["timestamp"]],
                y=[last_point["value"]],
                mode="markers",
                name="Dernière mesure",
                marker={"size": 11, "color": "#38bdf8", "line": {"width": 2, "color": "#f8fafc"}},
                hovertemplate=f"Dernière mesure<br>%{{x}}<br>%{{y:.2f}} {selected_row['Unité']}<extra></extra>",
            ))
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, key=f"monitoring_history_{selected_row['sensor_id']}")

            values = history_df["value"].astype(float)
            stat_col1, stat_col2, stat_col3 = st.columns(3)
            stat_col1.metric("Minimum observé", f"{format_number(values.min())} {selected_row['Unité']}")
            stat_col2.metric("Maximum observé", f"{format_number(values.max())} {selected_row['Unité']}")
            stat_col3.metric("Moyenne", f"{format_number(values.mean())} {selected_row['Unité']}")

            below_min = min_threshold is not None and bool((values < min_threshold).any())
            above_max = max_threshold is not None and bool((values > max_threshold).any())
            if below_min or above_max:
                st.error(
                    "Certaines mesures dépassent les limites normales. Une anomalie potentielle "
                    "a été détectée. Une vérification de l’équipement est recommandée."
                )
            elif selected_row["status_key"] == "warning":
                st.warning(
                    "Les mesures restent dans les limites, mais se rapprochent du seuil maximal. "
                    "Une surveillance renforcée est recommandée."
                )
            else:
                st.success(
                    "Les mesures restent dans les limites normales. Aucune anomalie détectée. "
                    "Aucune intervention recommandée."
                )
        else:
            st.info("Aucun historique disponible pour ce capteur.")

    finally:
        db.close()

# ============================================================
# PAGE: PReDICTIONS & ANOMALIES
# ============================================================

def page_predictions():
    """Page des predictions RUL et anomalies"""

    if st_autorefresh is not None:
        st_autorefresh(interval=15_000, key="predictions_realtime_refresh")

    st.title("Prédictions et anomalies")
    
    db = get_db()
    
    def severity_rank(severity):
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)

    def estimate_rul_from_alerts(equipment):
        alerts = (
            db.query(Alert)
            .filter(Alert.equipment_id == equipment.id, Alert.status == "active")
            .all()
        )
        worst = max([severity_rank(alert.severity) for alert in alerts], default=0)
        if worst >= 4:
            return 72, 0.82, "Critique"
        if worst == 3:
            return 240, 0.78, "Risque eleve"
        if worst == 2:
            return 720, 0.72, "Surveillance"
        if worst == 1:
            return 1440, 0.68, "Stable"
        return 2160, 0.62, "Normal"

    def update_realtime_rul_predictions() -> tuple[bool, datetime | None]:
        """Simuler un instant capteur courant puis recalculer le RUL avec XGBoost."""
        now = datetime.now(ZoneInfo("Africa/Casablanca"))
        previous_cycle = st.session_state.get("last_realtime_rul_cycle")
        if previous_cycle and (now - previous_cycle).total_seconds() < 30:
            return True, previous_cycle

        model_manager = st.session_state.ml_manager
        if not model_manager.rul_model.is_fitted:
            model_manager.load_models()
        if not model_manager.rul_model.is_fitted:
            return False, None

        sensors = (
            db.query(Sensor)
            .options(joinedload(Sensor.equipment))
            .filter(Sensor.is_active.is_(True))
            .all()
        )
        current_rows = []
        for sensor in sensors:
            if sensor.equipment is None:
                continue
            previous = (
                db.query(SensorReading)
                .filter(SensorReading.sensor_id == sensor.id)
                .order_by(SensorReading.timestamp.desc().nullslast())
                .first()
            )
            if previous is None or previous.value is None:
                continue

            previous_value = float(previous.value)
            noise = max(abs(previous_value) * 0.0025, 0.01)
            value = previous_value + float(np.random.normal(0, noise))
            min_value = float(sensor.min_value) if sensor.min_value is not None else None
            max_value = float(sensor.max_value) if sensor.max_value is not None else None
            if min_value is not None:
                value = max(min_value, value)
            if max_value is not None:
                value = min(max_value, value)
            status = (
                "anomaly"
                if (min_value is not None and value <= min_value)
                or (max_value is not None and value >= max_value)
                else "normal"
            )
            reading = SensorReading(
                sensor_id=sensor.id,
                value=round(value, 4),
                timestamp=now,
                status=status,
            )
            db.add(reading)
            current_rows.append({
                "equipment_id": str(sensor.equipment.id),
                "sensor_name": sensor.name or sensor.sensor_code or "Capteur",
                "value": value,
                "timestamp": now,
                "status": status,
            })

        if not current_rows:
            db.rollback()
            return False, None

        predictions = model_manager.predict_rul(current_rows)
        for equipment_id, rul_hours in predictions.items():
            db.add(RULPrediction(
                equipment_id=uuid.UUID(str(equipment_id)),
                predicted_rul_hours=max(0, int(rul_hours)),
                prediction_date=now,
            ))
        db.commit()
        st.session_state.last_realtime_rul_cycle = now
        return bool(predictions), now

    try:
        tab1, tab2 = st.tabs(["Prédictions RUL", "Anomalies détectées"])

        with tab1:
            st.subheader("Remaining Useful Life (RUL)")

            realtime_ok, realtime_at = update_realtime_rul_predictions()
            if not realtime_ok:
                st.warning("Le modèle RUL temps réel n'est pas disponible. Les dernières prédictions enregistrées sont affichées.")

            equipment_list = (
                db.query(Equipment)
                .filter(Equipment.is_active == True)
                .order_by(Equipment.equipment_code)
                .all()
            )

            latest_predictions = []
            for equipment in equipment_list:
                predictions = (
                    db.query(RULPrediction)
                    .filter(RULPrediction.equipment_id == equipment.id)
                    .order_by(RULPrediction.prediction_date.desc().nullslast())
                    .limit(2)
                    .all()
                )
                prediction = predictions[0] if predictions else None

                if prediction:
                    rul_hours = prediction.predicted_rul_hours or 0
                    confidence = 0.87
                    source = "Modele ML"
                    prediction_date = prediction.prediction_date
                    if len(predictions) > 1:
                        previous_hours = predictions[1].predicted_rul_hours or rul_hours
                        trend_hours = int(rul_hours) - int(previous_hours)
                    else:
                        trend_hours = 0
                else:
                    rul_hours, confidence, risk = estimate_rul_from_alerts(equipment)
                    source = "Estimation alertes"
                    prediction_date = datetime.utcnow()
                    trend_hours = 0

                rul_days = round(int(rul_hours) / 24, 1)
                risk = "Critique" if rul_days < 15 else "Attention" if rul_days < 30 else "Normal"
                trend = (
                    f"↓ {abs(trend_hours) / 24:.1f} j"
                    if trend_hours < 0
                    else f"↑ {trend_hours / 24:.1f} j"
                    if trend_hours > 0
                    else "Stable"
                )

                latest_predictions.append({
                    "Équipement": equipment.equipment_code,
                    "Nom": equipment.name,
                    "Type": equipment.equipment_type.name if equipment.equipment_type else "Autre",
                    "RUL heures": int(rul_hours),
                    "RUL jours": rul_days,
                    "Confiance": confidence,
                    "Risque": risk,
                    "État du modèle": "Opérationnel" if source == "Modele ML" else "Estimation disponible",
                    "Tendance": trend,
                    "Date prediction": prediction_date,
                })

            if latest_predictions:
                rul_df = pd.DataFrame(latest_predictions)
                risk_order = {"Critique": 0, "Attention": 1, "Normal": 2}
                rul_df["Priorité"] = rul_df["Risque"].map(risk_order)
                rul_df = rul_df.sort_values(["Priorité", "RUL jours", "Équipement"])

                total_equipment = len(rul_df)
                critical_count = int((rul_df["Risque"] == "Critique").sum())
                attention_count = int((rul_df["Risque"] == "Attention").sum())
                average_rul = float(rul_df["RUL jours"].mean())
                availability = ((total_equipment - critical_count) / total_equipment * 100) if total_equipment else 0
                latest_date = pd.to_datetime(rul_df["Date prediction"], utc=True, errors="coerce").max()
                latest_label = (
                    latest_date.tz_convert("Africa/Casablanca").strftime("%d/%m/%Y à %H:%M:%S")
                    if pd.notna(latest_date)
                    else "Indisponible"
                )

                kpi_cols = st.columns(4)
                kpi_cols[0].metric("Équipements surveillés", total_equipment)
                kpi_cols[1].metric("RUL critique", critical_count)
                kpi_cols[2].metric("RUL moyen", f"{average_rul:.0f} jours")
                kpi_cols[3].metric("Disponibilité", f"{availability:.0f} %")

                st.markdown("#### Équipements prioritaires")
                summary = rul_df.head(min(4, len(rul_df)))
                cols = st.columns(len(summary))
                risk_icons = {"Critique": "🔴", "Attention": "🟠", "Normal": "🟢"}
                risk_colors = {"Critique": "#ef4444", "Attention": "#f59e0b", "Normal": "#22c55e"}

                for idx, (_, row) in enumerate(summary.iterrows()):
                    with cols[idx]:
                        update_label = (
                            pd.to_datetime(row["Date prediction"], utc=True)
                            .tz_convert("Africa/Casablanca")
                            .strftime("%H:%M")
                        )
                        st.markdown(
                            f"""
                            <div style="border:1px solid rgba(148,163,184,.22);
                                        border-top:4px solid {risk_colors[row['Risque']]};
                                        border-radius:12px;padding:1rem;background:rgba(15,23,42,.78);
                                        min-height:185px">
                                <div style="color:#cbd5e1;font-size:.82rem">{html.escape(str(row['Nom']))}</div>
                                <div style="font-weight:800;font-size:1rem">{html.escape(str(row['Équipement']))}</div>
                                <div style="font-size:2rem;font-weight:900;margin:.35rem 0">{row['RUL jours']:g} jours</div>
                                <div style="color:{risk_colors[row['Risque']]};font-weight:800">
                                    {risk_icons[row['Risque']]} {row['Risque']}
                                </div>
                                <div style="color:#cbd5e1;font-size:.8rem;margin-top:.45rem">
                                    Confiance : {row['Confiance']:.0%} · {row['Tendance']}<br>
                                    Dernière MAJ : {update_label}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                st.divider()
                st.markdown("#### Comparaison du RUL")
                chart_df = rul_df.sort_values("RUL jours", ascending=False)
                fig = px.bar(
                    chart_df,
                    x="RUL jours",
                    y="Équipement",
                    color="Risque",
                    orientation="h",
                    text="RUL jours",
                    color_discrete_map={
                        "Critique": "#ef4444",
                        "Attention": "#f59e0b",
                        "Normal": "#22c55e",
                    },
                    labels={"RUL jours": "Durée de vie restante (jours)"},
                )
                fig.update_traces(texttemplate="%{text:g} j", textposition="outside")
                fig.add_vline(
                    x=15,
                    line_dash="dash",
                    line_color="#ef4444",
                    annotation_text="Seuil critique : 15 jours",
                    annotation_position="top",
                )
                fig.update_layout(
                    template="plotly_dark",
                    legend_title_text="Niveau de risque",
                    margin=dict(l=20, r=30, t=45, b=20),
                    yaxis_title=None,
                )
                st.plotly_chart(fig, use_container_width=True, key="predictions_rul_chart")

                st.markdown("#### Détail des prédictions")
                filter_col, type_col = st.columns(2)
                with filter_col:
                    risk_filter = st.radio(
                        "Niveau de risque",
                        options=["Tous", "Critique", "Attention", "Normal"],
                        index=0,
                        horizontal=True,
                        key="rul_risk_filter",
                    )
                with type_col:
                    type_options = ["Tous"] + sorted(rul_df["Type"].dropna().unique().tolist())
                    equipment_type_filter = st.selectbox(
                        "Type d'équipement",
                        options=type_options,
                        key="rul_equipment_type_filter",
                    )

                filtered_df = rul_df.copy()
                if risk_filter and risk_filter != "Tous":
                    filtered_df = filtered_df[filtered_df["Risque"] == risk_filter]
                if equipment_type_filter != "Tous":
                    filtered_df = filtered_df[filtered_df["Type"] == equipment_type_filter]

                table_df = filtered_df.copy()
                table_df["Statut"] = table_df["Risque"].map({
                    "Critique": "🔴 Critique",
                    "Attention": "🟠 Attention",
                    "Normal": "🟢 Normal",
                })
                table_df["Dernière mise à jour"] = pd.to_datetime(
                    table_df["Date prediction"], utc=True, errors="coerce"
                ).dt.tz_convert("Africa/Casablanca").dt.strftime("%d/%m/%Y %H:%M")
                table_df["Confiance"] = table_df["Confiance"] * 100
                table_df = table_df[[
                    "Équipement", "Nom", "Type", "RUL jours", "Statut",
                    "Tendance", "Confiance", "État du modèle", "Dernière mise à jour",
                ]]
                st.dataframe(
                    table_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "RUL jours": st.column_config.NumberColumn("RUL", format="%.1f jours"),
                        "Confiance": st.column_config.ProgressColumn(
                            "Confiance",
                            format="%.0f %%",
                            min_value=0,
                            max_value=100,
                        ),
                    },
                )

            else:
                st.info("Aucun Equipement disponible pour calculer le RUL.")

        with tab2:
            st.subheader("Anomalies détectées")
            st.caption("Surveillance intelligente des anomalies issues du modèle ML")

            severity_labels = {
                "critical": "Critique",
                "high": "Élevée",
                "medium": "Moyenne",
                "low": "Faible",
            }
            severity_badges = {
                "critical": "🔴 Critique",
                "high": "🟠 Élevée",
                "medium": "🟡 Moyenne",
                "low": "🟢 Faible",
            }
            severity_colors = {
                "Critique": "#ef4444",
                "Élevée": "#f97316",
                "Moyenne": "#eab308",
                "Faible": "#22c55e",
            }
            type_labels = {
                "Anomalie ML": "Détection ML",
                "ml_anomaly": "Détection ML",
                "anomaly": "Détection ML",
                "threshold": "Dépassement de seuil",
            }

            anomaly_rows = []

            anomalies = (
                db.query(Anomaly)
                .order_by(Anomaly.detection_timestamp.desc().nullslast())
                .limit(100)
                .all()
            )
            for anomaly in anomalies:
                sensor = anomaly.sensor
                equipment = sensor.equipment if sensor else None
                score = float(anomaly.anomaly_score or 0)
                severity = "critical" if score >= 0.85 else "high" if score >= 0.60 else "medium" if score >= 0.30 else "low"
                anomaly_rows.append({
                    "Identifiant": str(anomaly.id),
                    "Origine": "anomaly",
                    "Type": "Anomalie ML",
                    "Équipement": equipment.equipment_code if equipment else "",
                    "Nom équipement": equipment.name if equipment else "Équipement inconnu",
                    "Capteur": sensor.name if sensor else "",
                    "Severite": severity,
                    "Score": score,
                    "Description": anomaly.anomaly_type or "Anomalie detectee",
                    "Date": anomaly.detection_timestamp,
                    "État brut": "acknowledged" if anomaly.acknowledged_by else "active",
                })

            ensure_severity_example_alerts(db)

            alert_anomalies = (
                db.query(Alert)
                .join(Equipment, Alert.equipment_id == Equipment.id)
                .filter(Alert.alert_type.in_(["threshold", "ml_anomaly", "anomaly"]))
                .order_by(Alert.created_at.desc().nullslast())
                .limit(100)
                .all()
            )
            for alert in alert_anomalies:
                example_definition = next(
                    (
                        definition
                        for definition in SEVERITY_EXAMPLE_ALERTS.values()
                        if definition["title"] == alert.title
                    ),
                    None,
                )
                anomaly_rows.append({
                    "Identifiant": str(alert.id),
                    "Origine": "alert",
                    "Type": alert.alert_type,
                    "Équipement": alert.equipment.equipment_code if alert.equipment else "",
                    "Nom équipement": alert.equipment.name if alert.equipment else "Équipement inconnu",
                    "Capteur": alert.title,
                    "Severite": alert.severity or "low",
                    "Score": example_definition["score"] if example_definition else None,
                    "Description": alert.message,
                    "Date": alert.created_at,
                    "État brut": alert.status or "active",
                })

            if anomaly_rows:
                anomalies_df = pd.DataFrame(anomaly_rows)
                anomalies_df["Date"] = pd.to_datetime(
                    anomalies_df["Date"], utc=True, errors="coerce"
                )
                anomalies_df["Sévérité"] = anomalies_df["Severite"].map(severity_labels).fillna("Faible")
                anomalies_df["Type affiché"] = anomalies_df["Type"].map(type_labels).fillna("Détection ML")

                with st.expander("Filtres", expanded=False):
                    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
                    with filter_col1:
                        severity_filter = st.multiselect(
                            "Sévérité",
                            options=list(severity_labels.values()),
                            default=list(severity_labels.values()),
                            key="anomaly_severity_filter",
                        )
                    with filter_col2:
                        equipment_options = ["Tous"] + sorted(
                            value for value in anomalies_df["Équipement"].dropna().unique() if value
                        )
                        equipment_filter = st.selectbox(
                            "Équipement",
                            options=equipment_options,
                            key="anomaly_equipment_filter",
                        )
                    with filter_col3:
                        period_filter = st.selectbox(
                            "Période",
                            options=["Toutes", "Aujourd'hui", "24 dernières heures", "7 jours", "30 jours"],
                            key="anomaly_period_filter",
                        )
                    with filter_col4:
                        state_filter = st.selectbox(
                            "État",
                            options=["Tous", "À traiter", "En cours", "Acquittée", "Résolue"],
                            key="anomaly_state_filter",
                        )

                filtered_df = anomalies_df[anomalies_df["Sévérité"].isin(severity_filter)].copy()
                if equipment_filter != "Tous":
                    filtered_df = filtered_df[filtered_df["Équipement"] == equipment_filter]

                now_utc = pd.Timestamp.now(tz="UTC")
                period_starts = {
                    "Aujourd'hui": now_utc.normalize(),
                    "24 dernières heures": now_utc - pd.Timedelta(hours=24),
                    "7 jours": now_utc - pd.Timedelta(days=7),
                    "30 jours": now_utc - pd.Timedelta(days=30),
                }
                if period_filter in period_starts:
                    filtered_df = filtered_df[filtered_df["Date"] >= period_starts[period_filter]]
                state_values = {
                    "À traiter": ["active", "open"],
                    "En cours": ["in_progress"],
                    "Acquittée": ["acknowledged"],
                    "Résolue": ["resolved"],
                }
                if state_filter in state_values:
                    filtered_df = filtered_df[filtered_df["État brut"].isin(state_values[state_filter])]

                if not filtered_df.empty:
                    total_anomalies = len(filtered_df)
                    critical_anomalies = int((filtered_df["Severite"] == "critical").sum())
                    impacted_equipment = int(
                        filtered_df.loc[filtered_df["Équipement"] != "", "Équipement"].nunique()
                    )
                    last_detection = filtered_df["Date"].max()
                    last_detection_label = (
                        last_detection.tz_convert("Africa/Casablanca").strftime("%H:%M")
                        if pd.notna(last_detection)
                        else "—"
                    )

                    kpi_items = [
                        ("◎", total_anomalies, "Anomalies détectées", "#38bdf8"),
                        ("!", critical_anomalies, "Critiques", "#ef4444"),
                        ("⚙", impacted_equipment, "Équipements concernés", "#a78bfa"),
                        ("◷", last_detection_label, "Dernière détection", "#2dd4bf"),
                    ]
                    kpi_cols = st.columns(4)
                    for kpi_col, (icon, value, label, accent) in zip(kpi_cols, kpi_items):
                        with kpi_col:
                            st.markdown(
                                f"""
                                <div style="border:1px solid rgba(148,163,184,.20);border-radius:14px;
                                            padding:1rem 1.05rem;background:rgba(15,23,42,.72);
                                            box-shadow:0 10px 25px rgba(2,6,23,.16);min-height:112px">
                                    <div style="display:flex;align-items:center;gap:.5rem;color:{accent};
                                                font-size:.9rem;font-weight:850">
                                        <span style="display:inline-grid;place-items:center;width:28px;height:28px;
                                                     border-radius:8px;background:{accent}1f">{icon}</span>
                                        {html.escape(label)}
                                    </div>
                                    <div style="font-size:1.9rem;font-weight:900;color:#f8fafc;
                                                margin-top:.45rem;line-height:1">{html.escape(str(value))}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    complete_counts = pd.DataFrame({
                        "Sévérité": ["Critique", "Élevée", "Moyenne", "Faible"],
                    })
                    counts = filtered_df["Sévérité"].value_counts()
                    complete_counts["Nombre"] = (
                        complete_counts["Sévérité"].map(counts).fillna(0).astype(int)
                    )
                    severity_fig = px.bar(
                        complete_counts,
                        x="Nombre",
                        y="Sévérité",
                        color="Sévérité",
                        text="Nombre",
                        orientation="h",
                        title="Répartition par sévérité",
                        color_discrete_map=severity_colors,
                        category_orders={
                            "Sévérité": ["Faible", "Moyenne", "Élevée", "Critique"]
                        },
                    )
                    severity_fig.update_traces(textposition="outside")
                    severity_fig.update_layout(
                        template="plotly_dark",
                        height=245,
                        showlegend=False,
                        xaxis_title=None,
                        yaxis_title=None,
                        margin=dict(l=20, r=30, t=45, b=15),
                    )
                    equipment_counts = (
                        filtered_df.loc[filtered_df["Équipement"] != ""]
                        .groupby(["Équipement", "Nom équipement"])
                        .size()
                        .sort_values(ascending=False)
                        .head(5)
                        .reset_index(name="Nombre")
                    )
                    equipment_counts["Libellé"] = equipment_counts.apply(
                        lambda row: f"{row['Nom équipement']} · {row['Équipement']}", axis=1
                    )
                    equipment_fig = px.bar(
                        equipment_counts.sort_values("Nombre"),
                        x="Nombre",
                        y="Libellé",
                        orientation="h",
                        text="Nombre",
                        title="Équipements les plus concernés",
                        color_discrete_sequence=["#38bdf8"],
                    )
                    equipment_fig.update_traces(textposition="outside")
                    equipment_fig.update_layout(
                        template="plotly_dark", height=245, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        margin=dict(l=20, r=30, t=45, b=15),
                    )
                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        st.plotly_chart(
                            severity_fig, use_container_width=True,
                            key="predictions_anomaly_distribution_chart",
                        )
                    with chart_col2:
                        st.plotly_chart(
                            equipment_fig, use_container_width=True,
                            key="predictions_equipment_distribution_chart",
                        )

                    st.markdown("#### Anomalies récentes")
                    export_df = filtered_df.copy()
                    export_df["Sévérité"] = export_df["Severite"].map(severity_badges)
                    export_df["État"] = export_df["État brut"].map({
                        "active": "🔴 Non traitée",
                        "open": "🔴 Non traitée",
                        "in_progress": "🟡 En cours",
                        "acknowledged": "🟢 Acquittée",
                        "resolved": "🟢 Résolue",
                    }).fillna("🟡 En cours")
                    export_df["Description courte"] = export_df["Description"].fillna("").apply(
                        lambda value: value if len(str(value)) <= 70 else f"{str(value)[:67]}..."
                    )
                    export_df["Date locale"] = export_df["Date"].dt.tz_convert(
                        "Africa/Casablanca"
                    ).dt.strftime("%d/%m/%Y %H:%M")
                    display_df = export_df[[
                        "Équipement", "Capteur", "Sévérité", "État", "Date locale",
                    ]].rename(columns={
                        "Capteur": "Anomalie",
                        "Date locale": "Détection",
                    })
                    display_df["Action"] = "Sélectionner"
                    st.download_button(
                        "⬇️ Exporter en CSV",
                        data=display_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"anomalies_{datetime.now():%Y%m%d_%H%M}.csv",
                        mime="text/csv",
                    )
                    st.caption("Sélectionnez une ligne pour consulter le diagnostic complet.")
                    anomaly_selection = st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key="anomaly_recent_table",
                    )
                    selected_rows = anomaly_selection.selection.rows
                    if selected_rows:
                        selected_position = selected_rows[0]
                        selected_anomaly = export_df.iloc[selected_position]
                        with st.expander("Détail de l'anomalie sélectionnée", expanded=True):
                            detail_col1, detail_col2 = st.columns(2)
                            detail_col1.markdown(
                                f"**Équipement**  \n{selected_anomaly['Nom équipement']} · "
                                f"{selected_anomaly['Équipement']}"
                            )
                            detail_col2.markdown(
                                f"**Origine**  \n{selected_anomaly['Type affiché']} · "
                                f"{selected_anomaly['Détection'] if 'Détection' in selected_anomaly else selected_anomaly['Date locale']}"
                            )
                            st.markdown(f"**Diagnostic**  \n{selected_anomaly['Description']}")
                            if selected_anomaly["Severite"] == "critical":
                                st.warning("Action recommandée : inspection immédiate de l'équipement.")

                else:
                    st.success("Aucune anomalie détectée pour les filtres sélectionnés.")
            else:
                st.success("Aucune anomalie détectée.")

    finally:
        db.close()

# ============================================================
# PAGE: EVALUATION ML
# ============================================================

def render_ml_evaluation_charts(model_manager, readings_df):
    """Affiche les diagnostics scientifiques issus des sorties reelles des modeles."""
    st.subheader("Diagnostics scientifiques")
    dark_layout = dict(template="plotly_dark", margin=dict(l=20, r=20, t=55, b=20))

    rul_eval = getattr(model_manager.rul_model, "evaluation_data", None)
    if rul_eval and len(rul_eval.get("y_test", [])):
        y_test = np.asarray(rul_eval["y_test"], dtype=float).reshape(-1)
        y_pred = np.asarray(rul_eval["y_pred"], dtype=float).reshape(-1)
        errors = y_test - y_pred
        n = min(len(y_test), len(y_pred))
        y_test, y_pred, errors = y_test[:n], y_pred[:n], errors[:n]
        x_index = np.arange(n)

        if rul_eval.get("target_is_proxy"):
            st.warning(
                "Le projet ne stocke pas de RUL reel mesure. Les courbes comparent donc "
                "les predictions au proxy de cible existant, sur un jeu de test separe (20 %)."
            )

        left, right = st.columns(2)
        with left:
            fig = go.Figure()
            fig.add_scatter(x=x_index, y=y_test, mode="lines+markers", name="RUL cible (proxy)")
            fig.add_scatter(x=x_index, y=y_pred, mode="lines+markers", name="RUL predit")
            fig.update_layout(title="RUL cible vs RUL predit", xaxis_title="Echantillon test", yaxis_title="RUL (heures)", **dark_layout)
            st.plotly_chart(fig, use_container_width=True, key="ml_rul_actual_predicted_lines")
        with right:
            low = float(np.nanmin(np.r_[y_test, y_pred])); high = float(np.nanmax(np.r_[y_test, y_pred]))
            fig = go.Figure()
            fig.add_scatter(x=y_test, y=y_pred, mode="markers", name="Predictions")
            fig.add_scatter(x=[low, high], y=[low, high], mode="lines", name="Ideal y = x", line=dict(dash="dash", color="#f8fafc"))
            fig.update_layout(title="Concordance du RUL", xaxis_title="RUL cible (heures)", yaxis_title="RUL predit (heures)", **dark_layout)
            st.plotly_chart(fig, use_container_width=True, key="ml_rul_scatter")

        left, right = st.columns(2)
        with left:
            fig = px.histogram(x=errors, nbins=min(30, max(5, n)), labels={"x": "Erreur (heures)", "y": "Frequence"}, title="Distribution des erreurs RUL")
            fig.add_vline(x=0, line_dash="dash", line_color="#f8fafc")
            fig.update_layout(**dark_layout)
            st.plotly_chart(fig, use_container_width=True, key="ml_rul_errors")
            st.caption(f"Erreur moyenne : {np.mean(errors):.2f} h · Ecart-type : {np.std(errors):.2f} h")
        with right:
            threshold = st.number_input("Seuil d'alerte RUL (heures)", min_value=0.0, value=20.0, step=1.0, key="ml_rul_alert_threshold")
            timestamps = pd.to_datetime(rul_eval.get("timestamps", []), utc=True, errors="coerce")
            x_axis = timestamps if len(timestamps) == n and not pd.isna(timestamps).all() else x_index
            critical = y_pred < threshold
            fig = go.Figure()
            fig.add_scatter(x=x_axis, y=y_pred, mode="lines+markers", name="RUL predit")
            fig.add_scatter(x=np.asarray(x_axis)[critical], y=y_pred[critical], mode="markers", name="Sous le seuil", marker=dict(color="#ef4444", size=10, symbol="diamond"))
            fig.add_hline(y=threshold, line_dash="dash", line_color="#f59e0b", annotation_text="Seuil")
            fig.update_layout(title="Evolution du RUL sur le jeu de test", xaxis_title="Temps / echantillon", yaxis_title="RUL (heures)", **dark_layout)
            st.plotly_chart(fig, use_container_width=True, key="ml_rul_timeline")
    else:
        st.info("Reentrainez les modeles pour produire les graphiques RUL sur le jeu de test separe.")

    if readings_df.empty or not model_manager.anomaly_model.is_fitted:
        st.info("Donnees ou modele Isolation Forest indisponibles pour les graphiques d'anomalies.")
        return

    valid = readings_df.dropna(subset=["value"]).copy()
    if valid.empty:
        st.info("Aucune valeur capteur exploitable pour evaluer les anomalies.")
        return
    X = valid[["value"]].to_numpy(dtype=float)
    scaled = model_manager.anomaly_model.scaler.transform(X)
    labels = model_manager.anomaly_model.model.predict(scaled)
    raw_scores = model_manager.anomaly_model.model.score_samples(scaled)
    decision_threshold = float(model_manager.anomaly_model.model.offset_)
    valid["ml_label"] = labels
    valid["anomaly_score_raw"] = raw_scores
    valid["Classe"] = np.where(labels == -1, "Anomalie", "Normal")

    left, right = st.columns(2)
    with left:
        counts = valid["Classe"].value_counts().rename_axis("Classe").reset_index(name="Nombre")
        fig = px.bar(counts, x="Classe", y="Nombre", color="Classe", title="Predictions Isolation Forest", color_discrete_map={"Normal": "#38bdf8", "Anomalie": "#ef4444"})
        fig.update_layout(**dark_layout)
        st.plotly_chart(fig, use_container_width=True, key="ml_iforest_counts")
    with right:
        fig = px.histogram(valid, x="anomaly_score_raw", color="Classe", barmode="overlay", opacity=.7, title="Distribution des scores Isolation Forest", color_discrete_map={"Normal": "#38bdf8", "Anomalie": "#ef4444"})
        fig.add_vline(x=decision_threshold, line_dash="dash", line_color="#f59e0b", annotation_text=f"Seuil {decision_threshold:.3f}")
        fig.update_layout(xaxis_title="score_samples (plus faible = plus anormal)", **dark_layout)
        st.plotly_chart(fig, use_container_width=True, key="ml_iforest_scores")

    sensors = sorted(valid["sensor_name"].dropna().astype(str).unique())
    selected = st.selectbox("Capteur pour l'evolution temporelle", sensors, key="ml_anomaly_sensor") if sensors else None
    timeline = valid[valid["sensor_name"].astype(str) == selected].sort_values("timestamp") if selected else valid.sort_values("timestamp")
    if timeline.empty:
        st.info("Aucune mesure disponible pour le capteur selectionne.")
    else:
        fig = px.scatter(timeline, x="timestamp", y="value", color="Classe", symbol="Classe", hover_data=["equipment_code", "anomaly_score_raw"], title=f"Evolution temporelle des anomalies — {selected or 'tous capteurs'}", color_discrete_map={"Normal": "#38bdf8", "Anomalie": "#ef4444"})
        fig.update_traces(marker=dict(size=8))
        fig.update_layout(xaxis_title="Temps", yaxis_title="Valeur mesuree", **dark_layout)
        st.plotly_chart(fig, use_container_width=True, key="ml_anomaly_timeline")

def page_ml_evaluation():
    """Page d'evaluation des modeles ML pour la soutenance."""

    st.title("Évaluation des modèles IA")
    st.caption("Synthèse des performances principales utilisées par la plateforme.")

    db = get_db()
    try:
        latest_readings = (
            db.query(SensorReading)
            .order_by(SensorReading.timestamp.desc().nullslast())
            .limit(5000)
            .all()
        )
        reading_rows = []
        for reading in latest_readings:
            sensor = reading.sensor
            equipment = sensor.equipment if sensor else None
            reading_rows.append({
                "equipment_id": str(equipment.id) if equipment else "",
                "equipment_code": equipment.equipment_code if equipment else "Inconnu",
                "sensor_name": (sensor.name or sensor.sensor_code) if sensor else "Inconnu",
                "value": float(reading.value or 0),
                "timestamp": reading.timestamp or datetime.utcnow(),
                "status": reading.status or "normal",
            })

        model_manager = st.session_state.ml_manager
        if not model_manager.anomaly_model.is_fitted and not model_manager.rul_model.is_fitted:
            model_manager.load_models()

        if st.button(
            "Actualiser l’évaluation",
            type="primary",
            disabled=not reading_rows,
            key="ml_simple_refresh_button",
        ):
            equipment_data = [
                {
                    "id": str(equipment.id),
                    "name": equipment.name,
                    "type": equipment.equipment_type.name if equipment.equipment_type else "",
                }
                for equipment in db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
            ]
            with st.spinner("Calcul des indicateurs principaux..."):
                st.session_state.ml_eval_metrics = model_manager.train_all_models(
                    reading_rows,
                    equipment_data,
                )
                rag_started_at = time.time()
                try:
                    rag_response = st.session_state.chatbot.query(
                        "Que faire si une vibration turbine est élevée ?"
                    )
                    st.session_state.ml_rag_metrics = {
                        "response_time": time.time() - rag_started_at,
                        "confidence": rag_response.get("confidence"),
                        "sources_count": len(rag_response.get("sources", [])),
                    }
                except Exception:
                    logger.exception("Évaluation rapide du RAG indisponible")
            st.success("Indicateurs actualisés.")

        metrics = st.session_state.get("ml_eval_metrics", {})
        anomaly_metrics = metrics.get("anomaly_detection", {})
        rul_metrics = metrics.get("rul_prediction", {})
        rag_metrics = st.session_state.get("ml_rag_metrics", {})

        if not anomaly_metrics and reading_rows and model_manager.anomaly_model.is_fitted:
            try:
                values = np.asarray([[row["value"]] for row in reading_rows], dtype=float)
                labels, _ = model_manager.anomaly_model.predict(values)
                detected_count = int(np.sum(np.asarray(labels) == -1))
                anomaly_metrics = {
                    "samples": len(values),
                    "anomalies_detected": detected_count,
                    "anomaly_ratio": detected_count / len(values),
                }
            except Exception:
                anomaly_metrics = {}

        rul_eval = getattr(model_manager.rul_model, "evaluation_data", None)
        if not rul_metrics and rul_eval and len(rul_eval.get("y_test", [])):
            y_test = np.asarray(rul_eval["y_test"], dtype=float)
            y_pred = np.asarray(rul_eval["y_pred"], dtype=float)
            residual = float(np.sum((y_test - y_pred) ** 2))
            total_variance = float(np.sum((y_test - np.mean(y_test)) ** 2))
            rul_metrics = {
                "samples": len(y_test),
                "features": len(model_manager.rul_model.feature_names or []),
                "mae": float(np.mean(np.abs(y_test - y_pred))),
                "r2_score": 1 - residual / total_variance if total_variance else float("nan"),
            }

        st.markdown("### Détection d’anomalies")
        iso_cols = st.columns(5)
        iso_cols[0].metric("Modèle", "Isolation Forest")
        iso_cols[1].metric("Échantillons", anomaly_metrics.get("samples", len(reading_rows)))
        iso_cols[2].metric("Anomalies", anomaly_metrics.get("anomalies_detected", "N/D"))
        iso_cols[3].metric(
            "Taux d’anomalies",
            f"{anomaly_metrics.get('anomaly_ratio', 0):.1%}"
            if anomaly_metrics.get("anomaly_ratio") is not None else "N/D",
        )
        iso_cols[4].metric(
            "Statut",
            "✅ Opérationnel" if model_manager.anomaly_model.is_fitted else "⚠️ À entraîner",
        )

        st.markdown("### Prédiction de la durée de vie")
        rul_cols = st.columns(6)
        rul_cols[0].metric("Modèle", "XGBoost")
        rul_cols[1].metric("Échantillons", rul_metrics.get("samples", "N/D"))
        rul_cols[2].metric(
            "MAE",
            f"{rul_metrics['mae']:.1f} h" if rul_metrics.get("mae") is not None else "N/D",
        )
        rul_cols[3].metric(
            "R²",
            f"{rul_metrics['r2_score']:.3f}"
            if rul_metrics.get("r2_score") is not None else "N/D",
        )
        rul_cols[4].metric("Variables", rul_metrics.get("features", "N/D"))
        rul_cols[5].metric(
            "Statut",
            "✅ Validé" if model_manager.rul_model.is_fitted else "⚠️ À entraîner",
        )

        st.markdown("### Assistant documentaire")
        rag_cols = st.columns(5)
        rag_cols[0].metric("Système", "RAG")
        rag_cols[1].metric(
            "Temps de réponse",
            f"{rag_metrics['response_time']:.2f} s"
            if rag_metrics.get("response_time") is not None else "N/D",
        )
        rag_cols[2].metric(
            "Confiance",
            f"{rag_metrics['confidence']:.0%}"
            if rag_metrics.get("confidence") is not None else "N/D",
        )
        rag_cols[3].metric("Sources", rag_metrics.get("sources_count", "N/D"))
        rag_cols[4].metric("Statut", "✅ Fonctionnel")

        if rul_eval and len(rul_eval.get("y_test", [])):
            y_test = np.asarray(rul_eval["y_test"], dtype=float)
            y_pred = np.asarray(rul_eval["y_pred"], dtype=float)
            low = float(np.nanmin(np.r_[y_test, y_pred]))
            high = float(np.nanmax(np.r_[y_test, y_pred]))
            fig = go.Figure()
            fig.add_scatter(
                x=y_test,
                y=y_pred,
                mode="markers",
                name="Prédictions",
                marker=dict(color="#38bdf8", size=8),
            )
            fig.add_scatter(
                x=[low, high],
                y=[low, high],
                mode="lines",
                name="Référence idéale",
                line=dict(dash="dash", color="#22c55e"),
            )
            fig.update_layout(
                title="Concordance du RUL prédit",
                xaxis_title="RUL de référence (heures)",
                yaxis_title="RUL prédit (heures)",
                template="plotly_dark",
                height=360,
                margin=dict(l=20, r=20, t=55, b=20),
            )
            st.plotly_chart(fig, use_container_width=True, key="ml_simple_rul_chart")
        else:
            st.info(
                "Actualisez l’évaluation pour afficher le graphique de concordance du RUL."
            )
    except Exception as e:
        st.warning(f"Évaluation momentanément indisponible : {str(e)}")
    finally:
        db.close()
    return

    st.title("🧪 Évaluation ML")
    st.caption("Qualite des donnees, entrainement des modeles et indicateurs de performance.")

    db = get_db()

    def reading_to_row(reading):
        sensor = reading.sensor
        equipment = sensor.equipment if sensor else None
        return {
            "equipment_id": str(equipment.id) if equipment else "",
            "equipment_code": equipment.equipment_code if equipment else "Inconnu",
            "sensor_name": sensor.name or sensor.sensor_code if sensor else "Inconnu",
            "value": float(reading.value or 0),
            "timestamp": reading.timestamp or datetime.utcnow(),
            "status": reading.status or "normal",
        }

    try:
        total_readings = db.query(SensorReading).count()
        total_anomalies = db.query(Anomaly).count()
        total_predictions = db.query(RULPrediction).count()
        active_alerts = db.query(Alert).filter(Alert.status == "active").count()
        active_anomaly_alerts = (
            db.query(Alert)
            .filter(Alert.status == "active", Alert.alert_type.in_(["threshold", "ml_anomaly", "anomaly"]))
            .count()
        )

        latest_readings = (
            db.query(SensorReading)
            .order_by(SensorReading.timestamp.desc().nullslast())
            .limit(5000)
            .all()
        )
        reading_rows = [reading_to_row(reading) for reading in latest_readings]
        readings_df = pd.DataFrame(reading_rows)

        model_manager = st.session_state.ml_manager
        if not model_manager.anomaly_model.is_fitted and not model_manager.rul_model.is_fitted:
            model_manager.load_models()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Lectures capteurs", total_readings)
        col2.metric("Anomalies referencees", total_anomalies)
        col3.metric("Predictions RUL", total_predictions)
        col4.metric("Alertes actives", active_alerts)

        st.divider()

        status_col1, status_col2, status_col3 = st.columns(3)
        status_col1.metric(
            "Modele anomalies",
            "Pret" if model_manager.anomaly_model.is_fitted else "Non entraine",
        )
        status_col2.metric(
            "Modele RUL",
            "Pret" if model_manager.rul_model.is_fitted else "Non entraine",
        )
        status_col3.metric(
            "Echantillon evaluation",
            len(reading_rows),
            help="Dernieres lectures utilisees pour entrainer ou evaluer rapidement les modeles.",
        )

        if st.button("Entrainer / reevaluer les modeles", type="primary", disabled=not reading_rows, key="ml_train_models_button"):
            equipment_data = [
                {
                    "id": str(equipment.id),
                    "name": equipment.name,
                    "type": equipment.equipment_type.name if equipment.equipment_type else "",
                }
                for equipment in db.query(Equipment).filter(Equipment.is_active == True).all()
            ]

            with st.spinner("Entrainement des modeles sur les donnees disponibles..."):
                metrics = model_manager.train_all_models(reading_rows, equipment_data)
                st.session_state.ml_eval_metrics = metrics

            st.success("Evaluation ML mise a jour.")

        metrics = st.session_state.get("ml_eval_metrics")
        anomaly_metrics = metrics.get("anomaly_detection", {}) if metrics else {}
        rul_metrics = metrics.get("rul_prediction", {}) if metrics else {}

        anomaly_score_mean = None
        if reading_rows and model_manager.anomaly_model.is_fitted:
            try:
                anomaly_predictions = model_manager.predict_anomalies(reading_rows)
                anomaly_scores = [
                    item.get("anomaly_score")
                    for item in anomaly_predictions.values()
                    if isinstance(item.get("anomaly_score"), (int, float))
                ]
                if anomaly_scores:
                    anomaly_score_mean = sum(anomaly_scores) / len(anomaly_scores)
            except Exception:
                anomaly_score_mean = None

        st.subheader("Resultats d'evaluation")
        card1, card2 = st.columns(2)

        with card1:
            st.markdown("#### Evaluation Isolation Forest")
            iso_cols = st.columns(2)
            iso_cols[0].metric("Samples", anomaly_metrics.get("samples", len(reading_rows) if reading_rows else "N/A"))
            iso_cols[1].metric("Anomalies detectees", anomaly_metrics.get("anomalies_detected", "N/A"))
            iso_cols[0].metric(
                "Ratio anomalies",
                f"{anomaly_metrics.get('anomaly_ratio', 0):.1%}"
                if "anomaly_ratio" in anomaly_metrics else "N/A",
            )
            iso_cols[1].metric(
                "Contamination",
                f"{float(anomaly_metrics.get('contamination')):.1%}"
                if anomaly_metrics.get("contamination") is not None else "N/A",
            )
            st.metric("Score moyen", f"{anomaly_score_mean:.2f}" if anomaly_score_mean is not None else "N/A")

        with card2:
            st.markdown("#### Evaluation RUL XGBoost")
            rul_cols = st.columns(2)
            rul_cols[0].metric("Samples", rul_metrics.get("samples", "N/A"))
            rul_cols[1].metric("Features", rul_metrics.get("features", "N/A"))
            rul_cols[0].metric(
                "MAE",
                f"{rul_metrics.get('mae', 0):.1f} h" if "mae" in rul_metrics else "N/A",
            )
            rul_cols[1].metric(
                "R2 Score",
                f"{rul_metrics.get('r2_score', 0):.3f}" if "r2_score" in rul_metrics else "N/A",
            )
            if rul_metrics.get("status") == "insufficient_data":
                st.warning("Le modele RUL demande plus de donnees historiques pour produire une evaluation fiable.")

        card3, card4 = st.columns(2)

        with card3:
            st.markdown("#### Cycle automatique des alertes")
            if st.button("Executer le cycle d'alertes", key="ml_run_alert_cycle_button"):
                with st.spinner("Evaluation du cycle d'alertes..."):
                    st.session_state.ml_alert_cycle_metrics = run_auto_alert_cycle(db=db)
            alert_cycle_metrics = st.session_state.get("ml_alert_cycle_metrics", {})
            alert_cols = st.columns(3)
            alert_cols[0].metric("Lectures evaluees", alert_cycle_metrics.get("evaluated_readings", "N/A"))
            alert_cols[1].metric("Alertes creees", alert_cycle_metrics.get("created_alerts", "N/A"))
            alert_cols[2].metric("Doublons ignores", alert_cycle_metrics.get("skipped_duplicates", "N/A"))

        with card4:
            st.markdown("#### Performance RAG")
            if st.button("Tester le chatbot", key="ml_test_rag_button"):
                with st.spinner("Evaluation rapide du chatbot RAG..."):
                    rag_response = st.session_state.chatbot.query("Que faire si une vibration turbine est elevee ?")
                    st.session_state.ml_rag_metrics = {
                        "response_time": rag_response.get("response_time"),
                        "confidence": rag_response.get("confidence"),
                        "sources_count": len(rag_response.get("sources", [])),
                    }
            rag_metrics = st.session_state.get("ml_rag_metrics", {})
            rag_cols = st.columns(3)
            rag_cols[0].metric(
                "Temps reponse",
                f"{rag_metrics.get('response_time', 0):.2f} s"
                if rag_metrics.get("response_time") is not None else "N/A",
            )
            rag_cols[1].metric(
                "Confiance",
                f"{rag_metrics.get('confidence', 0):.0%}"
                if rag_metrics.get("confidence") is not None else "N/A",
            )
            rag_cols[2].metric("Sources retrouvees", rag_metrics.get("sources_count", "N/A"))

        render_ml_evaluation_charts(model_manager, readings_df)

        st.divider()

        if readings_df.empty:
            st.info("Aucune lecture capteur disponible pour l'evaluation.")
            return

        readings_df["timestamp"] = pd.to_datetime(readings_df["timestamp"], utc=True, errors="coerce")
        readings_df = readings_df.dropna(subset=["timestamp"])
        if readings_df.empty:
            st.info("Les lectures existent, mais aucune date valide n'est disponible pour l'evaluation.")
            return
        readings_df["date"] = readings_df["timestamp"].dt.date

        tab1, tab2, tab3 = st.tabs(["Qualite donnees", "Anomalies", "RUL"])

        with tab1:
            st.subheader("Couverture des donnees")
            coverage_df = (
                readings_df.groupby("equipment_code")
                .agg(
                    lectures=("value", "count"),
                    capteurs=("sensor_name", "nunique"),
                    debut=("timestamp", "min"),
                    fin=("timestamp", "max"),
                )
                .reset_index()
                .sort_values("lectures", ascending=False)
            )

            fig = px.bar(
                coverage_df.head(15),
                x="equipment_code",
                y="lectures",
                color="capteurs",
                title="Lectures disponibles par equipement",
                labels={"equipment_code": "Équipement", "lectures": "Lectures", "capteurs": "Capteurs"},
            )
            st.plotly_chart(fig, use_container_width=True, key="ml_coverage_chart")
            st.dataframe(coverage_df, use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("Distribution des anomalies")
            status_counts = readings_df["status"].fillna("unknown").value_counts().reset_index()
            status_counts.columns = ["Statut", "Nombre"]

            col_a, col_b = st.columns(2)
            with col_a:
                fig = px.pie(status_counts, values="Nombre", names="Statut", hole=0.45)
                st.plotly_chart(fig, use_container_width=True, key="ml_status_pie_chart")
            with col_b:
                anomaly_rate = (readings_df["status"] == "anomaly").mean()
                st.metric("Taux d'anomalies capteurs", f"{anomaly_rate:.2%}")
                st.metric("Anomalies table metier", total_anomalies)
                st.metric("Alertes anomalies actives", active_anomaly_alerts)

            daily_df = (
                readings_df.assign(is_anomaly=readings_df["status"] == "anomaly")
                .groupby("date")
                .agg(lectures=("value", "count"), anomalies=("is_anomaly", "sum"))
                .reset_index()
            )
            if not daily_df.empty:
                fig = px.line(
                    daily_df,
                    x="date",
                    y=["lectures", "anomalies"],
                    title="Evolution quotidienne lectures vs anomalies",
                    labels={"date": "Date", "value": "Nombre"},
                )
                st.plotly_chart(fig, use_container_width=True, key="ml_daily_anomalies_chart")

        with tab3:
            st.subheader("Predictions RUL en base")
            predictions = (
                db.query(RULPrediction)
                .order_by(RULPrediction.prediction_date.desc().nullslast())
                .all()
            )
            prediction_rows = []
            for prediction in predictions:
                prediction_rows.append({
                    "Équipement": prediction.equipment.equipment_code if prediction.equipment else "",
                    "Nom": prediction.equipment.name if prediction.equipment else "",
                    "RUL heures": prediction.predicted_rul_hours,
                    "RUL jours": round((prediction.predicted_rul_hours or 0) / 24, 1),
                    "Date prediction": prediction.prediction_date,
                })

            if prediction_rows:
                prediction_df = pd.DataFrame(prediction_rows)
                fig = px.bar(
                    prediction_df.sort_values("RUL heures"),
                    x="Équipement",
                    y="RUL jours",
                    title="RUL predit par equipement",
                    labels={"RUL jours": "Jours restants"},
                )
                st.plotly_chart(fig, use_container_width=True, key="ml_rul_database_chart")
                st.dataframe(prediction_df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune prediction RUL stockee. Utilisez l'entrainement ou la page Predictions pour alimenter cette analyse.")

    except Exception as e:
        st.warning(f"Erreur lors du chargement de l'evaluation ML: {str(e)}")
    finally:
        db.close()

# ============================================================
# PAGE: CHATBOT RAG
# ============================================================

CHATBOT_SUGGESTIONS = [
    {
        "category": "Alertes",
        "question": "Que faire si une alerte critique apparait ?",
        "answer": (
            "Commencez par identifier l'equipement et le capteur concernes, puis verifiez la derniere valeur mesuree "
            "et son evolution. Si la derive est confirmee, reduisez la charge si possible, acquittez l'alerte, "
            "creez un ordre de maintenance et planifiez une inspection prioritaire. Pour une alerte critique, "
            "evitez de la fermer avant qu'une action terrain soit realisee ou documentee."
        ),
    },
    {
        "category": "Turbine",
        "question": "Que faire si la vibration turbine depasse 8 mm/s ?",
        "answer": (
            "Une vibration turbine superieure a 8 mm/s doit etre traitee comme un signal serieux. Verifiez les roulements, "
            "l'alignement rotor, l'equilibrage mecanique et la temperature associee. Reduisez temporairement la charge "
            "si la vibration continue d'augmenter, puis ouvrez une inspection mecanique avec priorite elevee."
        ),
    },
    {
        "category": "RUL",
        "question": "Comment interpreter le RUL d'un equipement ?",
        "answer": (
            "Le RUL estime la duree de vie restante avant degradation ou intervention probable. Un RUL faible signifie "
            "qu'il faut rapprocher l'inspection, verifier les tendances capteurs et preparer les pieces necessaires. "
            "Il ne remplace pas le diagnostic terrain: il sert a prioriser les equipements et anticiper les arrets."
        ),
    },
    {
        "category": "Chaudiere",
        "question": "Quels capteurs surveiller pour une chaudiere ?",
        "answer": (
            "Sur une chaudiere, surveillez surtout la temperature foyer, la pression vapeur, le debit d'eau d'alimentation, "
            "les variations de pression et les signes de fuite vapeur. Une temperature excessive ou une baisse du debit "
            "d'eau peut indiquer un probleme d'echange thermique, de circulation ou d'encrassement."
        ),
    },
    {
        "category": "Alternateur",
        "question": "Que verifier si l'alternateur chauffe ?",
        "answer": (
            "Verifiez le refroidissement du stator, l'Etat des paliers, les vibrations, les connexions electriques et la charge. "
            "Si la temperature continue de monter, reduisez la charge, controlez la ventilation/refroidissement et planifiez "
            "une inspection electrique avant tout retour a pleine puissance."
        ),
    },
    {
        "category": "Maintenance",
        "question": "Comment prioriser les interventions de maintenance ?",
        "answer": (
            "Priorisez selon la severite de l'alerte, la criticite de l'Equipement, la tendance des capteurs, le RUL estime "
            "et l'impact production. Les alertes critiques sur turbine, chaudiere, alternateur ou condenseur passent avant "
            "les anomalies isolees non confirmees."
        ),
    },
    {
        "category": "Condenseur",
        "question": "Que verifier si le condenseur perd le vide ?",
        "answer": (
            "Controlez les pompes de circulation, l'encrassement des tubes, la temperature de sortie d'eau et les entrees d'air parasites. "
            "Une perte de vide peut reduire le rendement et augmenter la charge thermique; il faut donc inspecter rapidement "
            "le circuit de refroidissement."
        ),
    },
    {
        "category": "Utilisation",
        "question": "Comment creer un ordre de maintenance depuis une alerte ?",
        "answer": (
            "Ouvrez la page Maintenance, consultez les alertes actives, puis utilisez l'action de traitement disponible pour creer "
            "ou suivre un ordre. Renseignez l'Equipement, la priorite, la description du probleme et l'action recommandee. "
            "Apres intervention, mettez a jour le statut pour garder l'historique exploitable."
        ),
    },
]

CHATBOT_CATEGORY_ICONS = {
    "Alertes": "⚠️",
    "Turbine": "⚙️",
    "RUL": "📈",
    "Chaudiere": "🔥",
    "Alternateur": "🔋",
    "Maintenance": "📋",
    "Condenseur": "💧",
    "Utilisation": "🛠️",
}


def get_chatbot_suggested_answer(question: str) -> str | None:
    normalized_question = (question or "").strip().lower()
    for item in CHATBOT_SUGGESTIONS:
        if normalized_question == item["question"].strip().lower():
            return item["answer"]
    return None


def _chatbot_model_label(chatbot: RAGChatbot) -> str:
    """Retourner un nom de modele lisible par un utilisateur non technique."""
    if chatbot.llm_provider != "groq":
        return "Moteur RAG local"
    model = (getattr(chatbot, "model", "") or "Modèle Groq").replace("-", " ")
    return model.title().replace("Llama 3.1", "Llama 3.1").replace("Llama 3.3", "Llama 3.3")


def _chatbot_sources(raw_sources: str | None) -> list[dict]:
    """Décoder sans risque les sources RAG enregistrées avec une réponse."""
    if not raw_sources:
        return []
    try:
        sources = json.loads(raw_sources)
        return sources if isinstance(sources, list) else []
    except (TypeError, ValueError):
        return []


def _chatbot_platform_context(question: str) -> dict | None:
    """Lire les dernières données métier lorsque la question vise l'état réel de la plateforme."""
    normalized = RAGChatbot._normalize(question)
    wants_rul = "rul" in normalized or "duree de vie" in normalized
    wants_alert = "alerte" in normalized
    wants_anomaly = "anomal" in normalized or "risque" in normalized
    if not any((wants_rul, wants_alert, wants_anomaly)):
        return None

    equipment_terms = ("turbine", "chaudiere", "alternateur", "condenseur", "pompe", "compresseur")
    requested_equipment = next((term for term in equipment_terms if term in normalized), None)
    db = get_db()
    try:
        equipment_query = db.query(Equipment).options(joinedload(Equipment.equipment_type))
        equipment_rows = equipment_query.filter(Equipment.is_active.is_(True)).all()
        if requested_equipment:
            equipment_rows = [
                item for item in equipment_rows
                if requested_equipment in RAGChatbot._normalize(
                    f"{item.name} {item.equipment_code} "
                    f"{item.equipment_type.name if item.equipment_type else ''}"
                )
            ]
        equipment_ids = [item.id for item in equipment_rows]
        context = {"equipment_filter": requested_equipment or "tous", "records": []}

        if wants_rul:
            predictions = (
                db.query(RULPrediction)
                .options(joinedload(RULPrediction.equipment))
                .filter(RULPrediction.equipment_id.in_(equipment_ids))
                .order_by(RULPrediction.prediction_date.desc())
                .all()
            ) if equipment_ids else []
            latest_by_equipment = {}
            for prediction in predictions:
                latest_by_equipment.setdefault(prediction.equipment_id, prediction)
            for prediction in latest_by_equipment.values():
                hours = prediction.predicted_rul_hours
                context["records"].append({
                    "type": "RUL",
                    "equipment": prediction.equipment.name,
                    "equipment_code": prediction.equipment.equipment_code,
                    "predicted_rul_hours": hours,
                    "predicted_rul_days": round(hours / 24, 1) if hours is not None else None,
                    "prediction_date": prediction.prediction_date,
                })

        if wants_alert:
            alerts = (
                db.query(Alert)
                .options(joinedload(Alert.equipment))
                .filter(Alert.equipment_id.in_(equipment_ids), Alert.status == "active")
                .order_by(Alert.created_at.desc())
                .limit(10)
                .all()
            ) if equipment_ids else []
            context["records"].extend({
                "type": "alerte",
                "equipment": alert.equipment.name if alert.equipment else "Inconnu",
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity,
                "created_at": alert.created_at,
            } for alert in alerts)

        if wants_anomaly:
            anomalies = (
                db.query(Anomaly)
                .options(joinedload(Anomaly.sensor).joinedload(Sensor.equipment))
                .join(Sensor, Anomaly.sensor_id == Sensor.id)
                .filter(Sensor.equipment_id.in_(equipment_ids))
                .order_by(Anomaly.detection_timestamp.desc())
                .limit(10)
                .all()
            ) if equipment_ids else []
            context["records"].extend({
                "type": "anomalie",
                "equipment": anomaly.sensor.equipment.name,
                "sensor": anomaly.sensor.name,
                "anomaly_type": anomaly.anomaly_type,
                "score": float(anomaly.anomaly_score) if anomaly.anomaly_score is not None else None,
                "detected_at": anomaly.detection_timestamp,
            } for anomaly in anomalies)

        summary_lines = []
        for record in context["records"]:
            if record["type"] == "RUL":
                summary_lines.append(
                    f"{record['equipment']} ({record['equipment_code']}) : RUL estimé à "
                    f"{record['predicted_rul_hours']} h, soit {record['predicted_rul_days']} jours "
                    f"(prédiction du {record['prediction_date']})."
                )
            elif record["type"] == "alerte":
                summary_lines.append(
                    f"Alerte {record['severity']} sur {record['equipment']} : {record['title']} "
                    f"({record['created_at']})."
                )
            elif record["type"] == "anomalie":
                summary_lines.append(
                    f"Anomalie {record['anomaly_type']} sur {record['equipment']} / {record['sensor']} "
                    f"avec un score de {record['score']} ({record['detected_at']})."
                )
        context["summary"] = "\n\n".join(summary_lines) or (
            "Aucune donnée correspondante n'est actuellement disponible dans la plateforme."
        )
        return context
    except Exception:
        logger.exception("Impossible de construire le contexte plateforme du chatbot")
        return {"records": [], "summary": "Les données de la plateforme sont temporairement indisponibles."}
    finally:
        db.close()


def _conversation_period(updated_at: datetime | None) -> str:
    """Regrouper les discussions recentes avec des reperes simples."""
    if updated_at is None:
        return "Plus ancien"
    today = datetime.utcnow().date()
    conversation_date = updated_at.date()
    if conversation_date == today:
        return "Aujourd'hui"
    if conversation_date == today - timedelta(days=1):
        return "Hier"
    return "Plus ancien"


def list_chat_conversations(user_id: str) -> list[dict]:
    """Lister les discussions et rattacher l'ancien historique si necessaire."""
    db = get_db()
    try:
        parsed_user_id = uuid.UUID(user_id)
        legacy_entries = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == parsed_user_id,
                ChatHistory.conversation_id.is_(None),
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        if legacy_entries:
            first_question = (legacy_entries[0].message or "Ancienne discussion").strip()
            legacy_conversation = ChatConversation(
                user_id=parsed_user_id,
                title=first_question[:55],
                created_at=legacy_entries[0].created_at,
                updated_at=legacy_entries[-1].created_at,
            )
            db.add(legacy_conversation)
            db.flush()
            for entry in legacy_entries:
                entry.conversation_id = legacy_conversation.id
            db.commit()

        conversations = (
            db.query(ChatConversation)
            .filter(ChatConversation.user_id == parsed_user_id)
            .order_by(ChatConversation.updated_at.desc())
            .all()
        )
        return [
            {"id": str(item.id), "title": item.title, "updated_at": item.updated_at}
            for item in conversations
        ]
    except Exception:
        db.rollback()
        logger.exception("Impossible de lister les discussions du chatbot")
        return []
    finally:
        db.close()


def load_chat_history(user_id: str, conversation_id: str) -> list[dict]:
    """Charger les messages d'une discussion appartenant a l'utilisateur."""
    db = get_db()
    try:
        entries = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == uuid.UUID(user_id),
                ChatHistory.conversation_id == uuid.UUID(conversation_id),
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        messages = []
        for entry in entries:
            response_text = entry.response or ""
            stored_sources = (
                []
                if response_text.startswith("Le service conversationnel est temporairement indisponible")
                else _chatbot_sources(entry.sources_json)
            )
            messages.extend([
                {"role": "user", "content": entry.message or ""},
                {
                    "role": "assistant",
                    "content": response_text,
                    "sources": stored_sources,
                },
            ])
        return messages
    except Exception:
        logger.exception("Impossible de charger la discussion du chatbot")
        return []
    finally:
        db.close()


def delete_chat_conversation(user_id: str, conversation_id: str) -> bool:
    """Supprimer une discussion et tous ses messages."""
    db = get_db()
    try:
        conversation = (
            db.query(ChatConversation)
            .filter(
                ChatConversation.id == uuid.UUID(conversation_id),
                ChatConversation.user_id == uuid.UUID(user_id),
            )
            .first()
        )
        if conversation is None:
            return False
        db.delete(conversation)
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("Impossible de supprimer la discussion")
        return False
    finally:
        db.close()


def _render_chatbot(discussion_container):
    """Afficher le panneau des discussions et le contenu du chatbot."""

    st.markdown("""
    <style>
        .rag-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: .25rem .1rem .8rem;
            margin: 0 0 1rem;
            border-bottom: 1px solid rgba(148, 163, 184, .16);
        }
        .rag-hero h1 { margin: 0; font-size: 1.25rem; }
        .rag-hero p { margin: .2rem 0 0; color: #94a3b8; font-size: .82rem; }
        .rag-status {
            display: inline-flex;
            align-items: center;
            gap: .4rem;
            padding: .28rem .6rem;
            color: #86efac;
            font-size: .74rem;
            font-weight: 650;
        }
        .rag-welcome { margin: 2.4rem 0 1.3rem; text-align: center; }
        .rag-welcome strong { font-size: 1.4rem; }
        div[class*="st-key-chat_suggestion_"] button {
            min-height: 58px;
            justify-content: flex-start;
            padding: .8rem 1rem;
            text-align: left;
            border-color: rgba(148, 163, 184, .2);
            border-radius: 14px;
            background: rgba(15, 23, 42, .58);
        }
        div[class*="st-key-chat_suggestion_"] button:hover {
            border-color: rgba(56, 189, 248, .58);
            background: rgba(56, 189, 248, .09);
            transform: translateY(-1px);
        }
    </style>
    """, unsafe_allow_html=True)

    hero_available = st.session_state.chatbot.llm_provider == "groq"
    hero_status = "● Disponible" if hero_available else "● Indisponible"
    st.markdown(f"""
        <div class="rag-hero">
            <div>
                <h1>✦ Assistant IA ONEE</h1>
                <p>Votre copilote pour la maintenance prédictive</p>
            </div>
            <span class="rag-status">{hero_status}</span>
        </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.chatbot.vectorstore:
        with st.spinner("Chargement de la base de connaissances..."):
            db = get_db()
            try:
                loaded_count = st.session_state.chatbot.load_knowledge_base_from_db(db)
            finally:
                db.close()

            if not loaded_count:
                kb = generate_default_knowledge_base()
                st.session_state.chatbot.add_knowledge_base(kb)
    
    current_user_id = st.session_state.user["id"]
    conversations = list_chat_conversations(current_user_id)
    llm_available = st.session_state.chatbot.llm_provider == "groq"
    
    if st.session_state.chatbot.llm_provider == "local":
        if os.getenv("GROQ_API_KEY"):
            st.warning("La clé Groq configurée est absente, invalide ou encore une valeur d'exemple. Configurez une clé valide puis redémarrez l'application.")
        else:
            st.info("Aucune clé Groq configurée. Le service conversationnel est indisponible.")

    if st.session_state.get("chat_conversations_user_id") != current_user_id:
        st.session_state.chat_conversations_user_id = current_user_id
        # Ne pas selectionner automatiquement la derniere conversation.
        st.session_state.active_chat_conversation_id = None

    with discussion_container:
        st.markdown("### Discussions")
        st.caption("Vos conversations")
        if st.button(
            "➕ Nouvelle discussion",
            use_container_width=True,
            key="chat_new_conversation_button",
        ):
            st.session_state.active_chat_conversation_id = None
            st.session_state.chat_history = []
            st.rerun()

        active_conversation_id = st.session_state.get("active_chat_conversation_id")
        recent_conversations = conversations[:5]
        if active_conversation_id and not any(
            item["id"] == active_conversation_id for item in recent_conversations
        ):
            active_item = next(
                (item for item in conversations if item["id"] == active_conversation_id),
                None,
            )
            if active_item:
                recent_conversations = [active_item] + recent_conversations[:4]

        def render_conversation_button(conversation: dict, key_prefix: str = "recent") -> None:
            is_active = conversation["id"] == active_conversation_id
            label = f"{'●' if is_active else '💬'} {conversation['title']}"
            if st.button(
                label,
                use_container_width=True,
                key=f"chat_conversation_{key_prefix}_{conversation['id']}",
                disabled=is_active,
            ):
                st.session_state.active_chat_conversation_id = conversation["id"]
                st.session_state.chat_history = load_chat_history(
                    current_user_id,
                    conversation["id"],
                )
                st.rerun()

        for conversation in recent_conversations:
            render_conversation_button(conversation)

        if len(conversations) > 5:
            recent_ids = {item["id"] for item in recent_conversations}
            with st.expander(f"Voir toutes les discussions ({len(conversations)})"):
                for conversation in conversations:
                    if conversation["id"] not in recent_ids:
                        render_conversation_button(conversation, key_prefix="all")

        if active_conversation_id:
            st.divider()
            if st.button(
                "🗑️ Supprimer la discussion",
                key="chat_delete_conversation_button",
                use_container_width=True,
            ):
                if delete_chat_conversation(current_user_id, active_conversation_id):
                    st.session_state.active_chat_conversation_id = None
                    st.session_state.chat_history = []
                    st.session_state.pop("chat_history_cache_key", None)
                    st.rerun()
                else:
                    st.error("La suppression de la discussion a échoué.")

    active_conversation_id = st.session_state.get("active_chat_conversation_id")
    history_cache_key = f"{current_user_id}:{active_conversation_id}"
    if st.session_state.get("chat_history_cache_key") != history_cache_key:
        st.session_state.chat_history = (
            load_chat_history(current_user_id, active_conversation_id)
            if active_conversation_id
            else []
        )
        st.session_state.chat_history_cache_key = history_cache_key

    if not st.session_state.chat_history:
        st.markdown(
            '<div class="rag-welcome"><strong>Bonjour 👋 Comment puis-je vous assister ?</strong></div>',
            unsafe_allow_html=True,
        )
        st.caption("Suggestions")
        featured_categories = {"Alertes", "RUL", "Turbine", "Maintenance"}
        featured_suggestions = [
            item for item in CHATBOT_SUGGESTIONS if item["category"] in featured_categories
        ][:4]
        suggestion_cols = st.columns(2)
        for index, item in enumerate(featured_suggestions):
            icon = CHATBOT_CATEGORY_ICONS.get(item["category"], "💬")
            label = f"{icon}  {item['question']}"
            if suggestion_cols[index % 2].button(
                label,
                key=f"chat_suggestion_{index}",
                use_container_width=True,
            ):
                st.session_state.pending_chat_question = item["question"]
                st.rerun()

    st.divider()
    
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.chat_message("user").write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                if isinstance(message.get("response_time"), (int, float)):
                    st.caption(f"Temps de réponse : {message['response_time']:.2f} s")
    
    # Réserver la zone du nouvel échange avant le champ de saisie afin que
    # celui-ci reste toujours sous la conversation pendant le streaming.
    live_exchange = st.container()
    pending_question = st.session_state.pop("pending_chat_question", None)
    typed_question = st.chat_input(
        "Posez votre question… Ex. : Pourquoi cette alerte est-elle critique ? Quel est le RUL de la turbine ?"
    )
    question = pending_question or typed_question
    
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with live_exchange:
            st.chat_message("user").write(question)

            import time
            start_time = time.time()
            streamed_text = ""
            with st.chat_message("assistant"):
                answer_placeholder = st.empty()

                def render_token(token: str) -> None:
                    nonlocal streamed_text
                    streamed_text += token
                    answer_placeholder.markdown(streamed_text + "▌")

                platform_context = _chatbot_platform_context(question)
                response = st.session_state.chatbot.query(
                    question,
                    chat_history=st.session_state.chat_history[:-1],
                    platform_context=platform_context,
                    on_token=render_token,
                )
                elapsed = time.time() - start_time
                st.session_state.chatbot_last_response_time = elapsed

                answer = response.get("answer", "Pas de réponse générée")
                answer_placeholder.markdown(answer)
                service_unavailable = answer.startswith("Le service conversationnel est temporairement indisponible")
                response_sources = [] if service_unavailable else response.get("sources", [])
                st.caption(f"Temps de réponse : {elapsed:.2f} s")

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "sources": response_sources,
            "response_time": elapsed,
        })

        db = get_db()
        new_conversation_id = None
        try:
            if active_conversation_id:
                conversation = (
                    db.query(ChatConversation)
                    .filter(
                        ChatConversation.id == uuid.UUID(active_conversation_id),
                        ChatConversation.user_id == uuid.UUID(current_user_id),
                    )
                    .first()
                )
            else:
                conversation = ChatConversation(
                    user_id=uuid.UUID(current_user_id),
                    title=question.strip()[:55] or "Nouvelle discussion",
                )
                db.add(conversation)
                db.flush()
                active_conversation_id = str(conversation.id)
                new_conversation_id = active_conversation_id

            if conversation is None:
                raise ValueError("Discussion introuvable pour cet utilisateur")

            conversation.updated_at = datetime.utcnow()
            db.add(ChatHistory(
                user_id=uuid.UUID(current_user_id),
                conversation_id=conversation.id,
                message=question,
                response=answer,
                sources_json=json.dumps(response_sources, ensure_ascii=False),
            ))
            db.commit()
            if new_conversation_id:
                st.session_state.active_chat_conversation_id = new_conversation_id
        except Exception:
            db.rollback()
            logger.exception("Impossible d'enregistrer l'historique chatbot")
        finally:
            db.close()
        
        st.rerun()


def page_chatbot():
    """Page du chatbot avec un second menu lateral dedie aux discussions."""
    discussion_column, chatbot_column = st.columns(
        [1, 5],
        gap="large",
    )
    with chatbot_column:
        _render_chatbot(discussion_column)


# ============================================================
# PAGE: GESTION MAINTENANCE
# ============================================================

def page_maintenance():
    """Page de gestion des ordres de maintenance"""
    
    st.title("🔧 Gestion de la maintenance")
    can_edit = can_manage_maintenance()
    if not can_edit:
        st.info("Mode consultation : seuls les administrateurs, ingénieurs et techniciens peuvent traiter la maintenance.")

    db = get_db()

    try:
        ensure_severity_example_alerts(db)
        tab1, tab2, tab3 = st.tabs(["Alertes", "Interventions", "Historique"])

        with tab1:
            st.subheader("Alertes actives")
            alerts = (
                db.query(Alert)
                .options(joinedload(Alert.equipment))
                .filter(Alert.status == "active")
                .order_by(Alert.created_at.desc().nullslast())
                .all()
            )

            critical_count = sum(alert.severity == "critical" for alert in alerts)

            kpi_cols = st.columns(2)
            for column, value, label, color in (
                (kpi_cols[0], len(alerts), "À traiter", "#38bdf8"),
                (kpi_cols[1], critical_count, "Critiques", "#ef4444"),
            ):
                with column:
                    st.markdown(
                        f"""<div style="border:1px solid rgba(148,163,184,.2);border-top:3px solid {color};
                        border-radius:12px;padding:1rem 1.2rem;background:rgba(15,23,42,.72)">
                        <div style="font-size:1.8rem;font-weight:900">{value}</div>
                        <div style="color:#cbd5e1;font-weight:700">{label}</div></div>""",
                        unsafe_allow_html=True,
                    )
            st.caption("Analysez chaque alerte : acquittez-la si aucune action terrain n’est requise, sinon créez une intervention.")

            alert_filter_col1, alert_filter_col2 = st.columns(2)
            with alert_filter_col1:
                severity_filter = st.selectbox(
                    "Sévérité",
                    options=["Toutes", "Critique", "Élevée", "Moyenne", "Faible"],
                    key="maintenance_severity_filter",
                )
            with alert_filter_col2:
                alert_equipment_options = ["Tous"] + sorted({
                    alert.equipment.equipment_code
                    for alert in alerts if alert.equipment and alert.equipment.equipment_code
                })
                alert_equipment_filter = st.selectbox(
                    "Équipement",
                    options=alert_equipment_options,
                    key="maintenance_alert_equipment_filter",
                )

            severity_labels = {
                "critical": ("🔴", "Critique", "#ef4444", "Immédiate", "2 heures"),
                "high": ("🟠", "Élevée", "#f97316", "Haute", "8 heures"),
                "medium": ("🟡", "Moyenne", "#eab308", "Moyenne", "24 heures"),
                "low": ("🟢", "Faible", "#22c55e", "Faible", "72 heures"),
            }

            def alert_type_icon(alert):
                content = f"{alert.title} {alert.message}".lower()
                if any(word in content for word in ("temp", "chauff", "therm")):
                    return "🌡️"
                if any(word in content for word in ("vibr", "roulement")):
                    return "📳"
                if any(word in content for word in ("pression", "débit", "debit")):
                    return "💨"
                if any(word in content for word in ("courant", "tension", "électr", "electr")):
                    return "⚡"
                return "⚠️"

            def elapsed_label(created_at):
                if not created_at:
                    return "date inconnue"
                created = pd.Timestamp(created_at)
                if created.tzinfo is None:
                    created = created.tz_localize("UTC")
                elapsed_seconds = max(
                    0,
                    int((pd.Timestamp.now(tz="UTC") - created.tz_convert("UTC")).total_seconds()),
                )
                if elapsed_seconds < 60:
                    return "moins d’une minute"
                if elapsed_seconds < 3600:
                    return f"{elapsed_seconds // 60} min"
                if elapsed_seconds < 86400:
                    return f"{elapsed_seconds // 3600} h"
                return f"{elapsed_seconds // 86400} j"

            filtered_alerts = []
            for alert in alerts:
                severity_name = severity_labels.get(
                    alert.severity,
                    severity_labels["low"],
                )[1]
                if severity_filter != "Toutes" and severity_name != severity_filter:
                    continue
                if (
                    alert_equipment_filter != "Tous"
                    and (
                        not alert.equipment
                        or alert.equipment.equipment_code != alert_equipment_filter
                    )
                ):
                    continue
                filtered_alerts.append(alert)

            if not alerts:
                st.success("Aucune alerte active à traiter.")
            elif not filtered_alerts:
                st.info("Aucune alerte ne correspond aux filtres sélectionnés.")
            else:
                for alert in filtered_alerts:
                    equipment_name = alert.equipment.name if alert.equipment else "Équipement inconnu"
                    equipment_code = (
                        alert.equipment.equipment_code if alert.equipment else "Non renseigné"
                    )
                    icon, severity_name, severity_color, priority, intervention_delay = (
                        severity_labels.get(alert.severity, severity_labels["low"])
                    )
                    created_label = (
                        pd.Timestamp(alert.created_at)
                        .tz_localize("UTC")
                        .tz_convert("Africa/Casablanca")
                        .strftime("%d/%m/%Y %H:%M")
                        if alert.created_at and pd.Timestamp(alert.created_at).tzinfo is None
                        else pd.Timestamp(alert.created_at)
                        .tz_convert("Africa/Casablanca")
                        .strftime("%d/%m/%Y %H:%M")
                        if alert.created_at
                        else "Date inconnue"
                    )
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="border:1px solid rgba(148,163,184,.22);
                                        border-left:5px solid {severity_color};
                                        border-radius:12px;padding:1.3rem 1.4rem;
                                        background:rgba(15,23,42,.72);line-height:1.55">
                                <div style="font-size:1.08rem;font-weight:850">
                                    {alert_type_icon(alert)} {html.escape(alert.title)}
                                </div>
                                <div style="color:#cbd5e1;font-size:.82rem;margin:.6rem 0">
                                    <b>Équipement :</b> {html.escape(equipment_name)} ({html.escape(equipment_code)})
                                    &nbsp;·&nbsp; <b>Sévérité :</b>
                                    <span style="color:{severity_color};font-weight:800">
                                        {icon} {severity_name}
                                    </span>
                                    &nbsp;·&nbsp; <b>Détectée il y a :</b> {elapsed_label(alert.created_at)}
                                </div>
                                <div style="color:#f8fafc;margin-top:.85rem">
                                    {html.escape(alert.message or "Aucune description disponible.")}
                                </div>
                                <div style="color:#94a3b8;font-size:.78rem;margin-top:.85rem">
                                    <span style="border:1px solid {severity_color};color:{severity_color};
                                                 border-radius:999px;padding:.18rem .55rem;font-weight:800">
                                        {icon} Priorité {priority}
                                    </span>
                                    &nbsp;·&nbsp; Intervention recommandée sous {intervention_delay}
                                    &nbsp;·&nbsp; {created_label}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        col1, col2 = st.columns([2, 1])
                        if col1.button(
                            "🔧 Créer une intervention",
                            key=f"create_order_{alert.id}",
                            disabled=not can_edit,
                            use_container_width=True,
                            type="primary",
                        ):
                            creator = (
                                db.query(User)
                                .filter(User.id == uuid.UUID(st.session_state.user["id"]))
                                .first()
                            )
                            order_count = db.query(MaintenanceOrder).count() + 1
                            order = MaintenanceOrder(
                                equipment_id=alert.equipment_id,
                                created_by=creator.id if creator else None,
                                order_number=f"OM-{order_count:04d}",
                                title=f"Intervention — {alert.title}",
                                description=alert.message,
                                priority=(
                                    "high"
                                    if alert.severity in {"critical", "high"}
                                    else "medium"
                                    if alert.severity == "medium"
                                    else "low"
                                ),
                                status="new",
                                created_at=datetime.utcnow(),
                            )
                            alert.status = "acknowledged"
                            alert.acknowledged_by = creator.id if creator else None
                            db.add(order)
                            db.commit()
                            st.success(f"Intervention {order.order_number} créée.")
                            st.rerun()

                        if col2.button(
                            "✓ Acquitter sans intervention",
                            key=f"close_{alert.id}",
                            disabled=not can_edit,
                            use_container_width=True,
                        ):
                            alert.status = "acknowledged"
                            alert.acknowledged_by = uuid.UUID(st.session_state.user["id"])
                            db.commit()
                            st.success("Alerte acquittée sans intervention.")
                            st.rerun()
                        st.write("")

        with tab2:
            st.subheader("Interventions de maintenance")
            orders = (
                db.query(MaintenanceOrder)
                .options(
                    joinedload(MaintenanceOrder.equipment),
                    joinedload(MaintenanceOrder.assigned_user),
                    joinedload(MaintenanceOrder.creator),
                )
                .order_by(MaintenanceOrder.created_at.desc().nullslast())
                .all()
            )

            order_search = st.text_input(
                "Rechercher",
                placeholder="Numéro, équipement ou technicien...",
                key="maintenance_order_search",
            )
            normalized_order_search = order_search.strip().lower()
            filtered_orders = [
                order for order in orders
                if not normalized_order_search
                or normalized_order_search in (
                    f"{order.order_number} {order.title} {order.description or ''} "
                    f"{order.equipment.equipment_code if order.equipment else ''} "
                    f"{order.assigned_user.full_name if order.assigned_user else ''}"
                ).lower()
            ]
            order_status_labels = {
                "new": "🔵 À traiter",
                "in_progress": "🟡 En cours",
                "completed": "🟢 Terminée",
            }
            order_priority_labels = {
                "high": "🔴 Haute",
                "medium": "🟠 Moyenne",
                "low": "🟢 Faible",
            }
            maintenance_role_labels = {
                "engineer": "Ingénieur",
                "technician": "Technicien",
                # Le rôle historique `viewer` correspond au profil technicien
                # de consultation dans les données existantes.
                "viewer": "Technicien",
            }

            def maintenance_responsible_label(user):
                if not user:
                    return "Non assigné"
                return maintenance_role_labels.get(user.role, "Responsable maintenance")

            if filtered_orders:
                rows = []
                for order in filtered_orders:
                    rows.append({
                        "N°": order.order_number,
                        "Équipement": order.equipment.equipment_code if order.equipment else "",
                        "Motif": (order.title or "Intervention").replace("Intervention — ", ""),
                        "Priorité": order_priority_labels.get(
                            order.priority or "medium",
                            "🟠 Moyenne",
                        ),
                        "Responsable": (
                            maintenance_responsible_label(order.assigned_user)
                        ),
                        "Statut": order_status_labels.get(
                            order.status or "new",
                            "🔵 À traiter",
                        ),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                with st.container():
                    selected_order_id = st.selectbox(
                        "Intervention sélectionnée",
                        options=[str(order.id) for order in filtered_orders],
                        format_func=lambda order_id: next(
                            f"{order.order_number} — {order.equipment.equipment_code if order.equipment else ''}"
                            for order in filtered_orders if str(order.id) == order_id
                        ),
                        key="selected_maintenance_order",
                    )
                selected_order = next(
                    order for order in filtered_orders if str(order.id) == selected_order_id
                )
                selected_equipment_name = (
                    selected_order.equipment.name if selected_order.equipment else "Équipement inconnu"
                )
                selected_reason = (selected_order.title or "Intervention").replace("Intervention — ", "")
                selected_priority = order_priority_labels.get(selected_order.priority or "medium", "🟠 Moyenne")
                selected_responsible = (
                    maintenance_responsible_label(selected_order.assigned_user)
                )
                selected_status = order_status_labels.get(selected_order.status or "new", "🔵 À traiter")
                st.markdown(
                    f"""
                    <div style="border:1px solid rgba(148,163,184,.22);border-radius:12px;
                                padding:1.2rem 1.35rem;background:rgba(15,23,42,.72);margin:.5rem 0 1rem">
                        <div style="font-size:1.1rem;font-weight:900;margin-bottom:.9rem">🔧 {html.escape(selected_order.order_number)} — {html.escape(selected_equipment_name)}</div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem 1.5rem;color:#cbd5e1">
                            <div><small>Motif</small><br><b style="color:#f8fafc">{html.escape(selected_reason)}</b></div>
                            <div><small>Priorité</small><br><b>{selected_priority}</b></div>
                            <div><small>Responsable</small><br><b style="color:#f8fafc">{html.escape(selected_responsible)}</b></div>
                            <div><small>Statut actuel</small><br><b>{selected_status}</b></div>
                        </div>
                        <div style="margin-top:1rem;color:#94a3b8"><small>Recommandation</small><br>
                            <span style="color:#e2e8f0">{html.escape(selected_order.description or 'Consulter et diagnostiquer l’équipement avant intervention.')}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if selected_order.status == "completed":
                    st.success("✅ Intervention terminée")
                else:
                    if selected_order.assigned_to is None:
                        available_staff = (
                            db.query(User)
                            .filter(
                                User.role.in_(["engineer", "technician", "viewer"]),
                                User.is_active.is_(True),
                            )
                            .order_by(User.full_name, User.username)
                            .all()
                        )
                        staff_by_role = {}
                        for staff_member in available_staff:
                            assignment_role = (
                                "technician"
                                if staff_member.role == "viewer"
                                else staff_member.role
                            )
                            staff_by_role.setdefault(assignment_role, staff_member)
                        available_roles = [
                            role for role in ("engineer", "technician")
                            if role in staff_by_role
                        ]
                        if available_roles:
                            assign_select_col, assign_button_col = st.columns([2, 1])
                            with assign_select_col:
                                selected_staff_role = st.selectbox(
                                    "Responsable",
                                    options=available_roles,
                                    format_func=lambda role: maintenance_role_labels[role],
                                    key=f"maintenance_engineer_{selected_order.id}",
                                )
                            with assign_button_col:
                                st.write("")
                                if st.button(
                                    "Assigner",
                                    use_container_width=True,
                                    type="primary",
                                    disabled=not can_edit,
                                    key=f"assign_maintenance_order_{selected_order.id}",
                                ):
                                    selected_order.assigned_to = staff_by_role[selected_staff_role].id
                                    db.commit()
                                    st.success("Responsable assigné à l’intervention.")
                                    st.rerun()
                        else:
                            st.warning("Aucun responsable de maintenance actif n’est disponible.")

                    action_col, spacer_col = st.columns([1, 2])
                    with action_col:
                        if selected_order.status == "new":
                            if st.button(
                                "▶ Démarrer l’intervention",
                                use_container_width=True,
                                disabled=(
                                    not can_edit
                                    or selected_order.assigned_to is None
                                ),
                                key="start_selected_maintenance_order",
                            ):
                                if selected_order.assigned_to is None:
                                    st.error("Assignez un responsable avant de démarrer l’intervention.")
                                else:
                                    selected_order.status = "in_progress"
                                    db.commit()
                                    st.rerun()
                        elif selected_order.status == "in_progress":
                            if st.button(
                                "✓ Terminer l’intervention",
                                use_container_width=True,
                                disabled=not can_edit,
                                key="complete_selected_maintenance_order",
                            ):
                                selected_order.status = "completed"
                                db.commit()
                                st.rerun()
            elif orders:
                st.info("Aucune intervention ne correspond à la recherche.")
            else:
                st.info("Aucune intervention enregistrée.")

        with tab3:
            st.subheader("Historique de maintenance")
            history_alerts = (
                db.query(Alert)
                .options(joinedload(Alert.equipment), joinedload(Alert.acknowledged_user))
                .filter(Alert.status.in_(["acknowledged", "closed"]))
                .order_by(Alert.created_at.desc().nullslast())
                .limit(100)
                .all()
            )
            completed_orders = (
                db.query(MaintenanceOrder)
                .options(
                    joinedload(MaintenanceOrder.equipment),
                    joinedload(MaintenanceOrder.assigned_user),
                    joinedload(MaintenanceOrder.creator),
                )
                .filter(MaintenanceOrder.status == "completed")
                .order_by(MaintenanceOrder.created_at.desc().nullslast())
                .limit(100)
                .all()
            )
            if history_alerts or completed_orders:
                search_col, period_col, equipment_col = st.columns([2, 1, 1])
                with search_col:
                    history_search = st.text_input(
                        "Rechercher",
                        placeholder="Événement, équipement ou responsable...",
                        key="maintenance_history_search",
                    )
                with period_col:
                    history_filter = st.selectbox(
                        "Filtre",
                        options=["Tous", "Alertes", "Interventions", "Aujourd’hui", "Cette semaine"],
                        key="maintenance_history_period_filter",
                    )
                equipment_options = ["Tous"] + sorted({
                    item.equipment.equipment_code
                    for item in [*history_alerts, *completed_orders]
                    if item.equipment and item.equipment.equipment_code
                })
                with equipment_col:
                    history_equipment = st.selectbox(
                        "Équipement",
                        options=equipment_options,
                        key="maintenance_history_equipment_filter",
                    )

                now_utc = pd.Timestamp.now(tz="UTC")
                normalized_history_search = history_search.strip().lower()
                severity_history_labels = {
                    "critical": "🔴 Critique",
                    "high": "🟠 Élevée",
                    "medium": "🟡 Moyenne",
                    "low": "🟢 Faible",
                }
                priority_history_labels = {
                    "high": "🔴 Haute",
                    "medium": "🟠 Moyenne",
                    "low": "🟢 Faible",
                }
                order_alert_titles = {
                    (order.title or "").replace("Intervention — ", "")
                    for order in db.query(MaintenanceOrder).all()
                }
                history_events = []
                for alert in history_alerts:
                    responsible = (
                        alert.acknowledged_user.full_name
                        if alert.acknowledged_user else "Non renseigné"
                    )
                    history_events.append({
                        "kind": "Alerte",
                        "date": alert.created_at,
                        "equipment": alert.equipment.equipment_code if alert.equipment else "",
                        "event": f"Alerte — {alert.title}",
                        "level": severity_history_labels.get(alert.severity, "⚪ Inconnue"),
                        "action": (
                            "Intervention créée" if alert.title in order_alert_titles
                            else "Acquittée sans intervention"
                        ),
                        "responsible": responsible,
                    })
                for order in completed_orders:
                    history_events.append({
                        "kind": "Intervention",
                        "date": order.created_at,
                        "equipment": order.equipment.equipment_code if order.equipment else "",
                        "event": order.order_number,
                        "level": priority_history_labels.get(order.priority or "medium", "🟠 Moyenne"),
                        "action": "Intervention terminée",
                        "responsible": (
                            order.assigned_user.full_name if order.assigned_user
                            else order.creator.full_name if order.creator
                            else "Non assigné"
                        ),
                    })

                filtered_events = []
                for event in history_events:
                    event_date = pd.Timestamp(event["date"]) if event["date"] else None
                    if event_date is not None and event_date.tzinfo is None:
                        event_date = event_date.tz_localize("UTC")
                    searchable = f"{event['event']} {event['equipment']} {event['responsible']}".lower()
                    if normalized_history_search and normalized_history_search not in searchable:
                        continue
                    if history_equipment != "Tous" and event["equipment"] != history_equipment:
                        continue
                    if history_filter == "Alertes" and event["kind"] != "Alerte":
                        continue
                    if history_filter == "Interventions" and event["kind"] != "Intervention":
                        continue
                    if history_filter == "Aujourd’hui" and (event_date is None or event_date < now_utc.normalize()):
                        continue
                    if history_filter == "Cette semaine" and (event_date is None or event_date < now_utc - pd.Timedelta(days=7)):
                        continue
                    event["sort_date"] = event_date
                    filtered_events.append(event)

                filtered_events.sort(
                    key=lambda event: event["sort_date"] if event["sort_date"] is not None else pd.Timestamp.min.tz_localize("UTC"),
                    reverse=True,
                )
                history_rows = [{
                    "Date": (
                        event["sort_date"].tz_convert("Africa/Casablanca").strftime("%d/%m/%Y %H:%M")
                        if event["sort_date"] is not None else "Date inconnue"
                    ),
                    "Équipement": event["equipment"],
                    "Événement": event["event"],
                    "Sévérité / Priorité": event["level"],
                    "Action": event["action"],
                    "Responsable": event["responsible"],
                } for event in filtered_events]
                if history_rows:
                    st.dataframe(
                        pd.DataFrame(history_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Aucun événement ne correspond aux filtres sélectionnés.")
            else:
                st.info("Aucun événement de maintenance dans l’historique.")

    finally:
        db.close()

# ============================================================
# PAGE: SETTINGS
# ============================================================

def page_settings():
    """Page des parametres"""
    
    st.title("⚙️ Paramètres")
    
    user = st.session_state.user
    st.subheader("Profil utilisateur")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.text_input("Nom", value=user["full_name"], disabled=True)
    with col2:
        st.text_input("Email", value=user['email'], disabled=True)
    with col3:
        st.text_input("Rôle", value=user['role'].upper(), disabled=True)
    
    st.divider()
    st.subheader("Statistiques système")

    db = get_db()
    try:
        stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
        stats_col1.metric("Utilisateurs", db.query(User).count())
        stats_col2.metric("Équipements", db.query(Equipment).filter(Equipment.is_active == True).count())
        stats_col3.metric("Lectures", db.query(SensorReading).count())
        stats_col4.metric("Alertes actives", db.query(Alert).filter(Alert.status == "active").count())
    finally:
        db.close()

    if user["role"] == "admin":
        st.divider()
        st.subheader("Gestion des utilisateurs")
        with st.expander("➕ Créer un compte utilisateur", expanded=False):
            with st.form("admin_create_user_form", clear_on_submit=True):
                create_col1, create_col2 = st.columns(2)
                with create_col1:
                    new_full_name = st.text_input("Nom complet")
                    new_username = st.text_input("Nom d’utilisateur")
                    new_email = st.text_input(
                        "Email professionnel",
                        placeholder="prenom.nom@onee.ma",
                    )
                with create_col2:
                    new_department = st.selectbox(
                        "Département",
                        [
                            "Production",
                            "Maintenance",
                            "Exploitation",
                            "Instrumentation",
                            "Électricité",
                            "Informatique",
                        ],
                    )
                    new_role = st.selectbox(
                        "Rôle",
                        ["viewer", "technician", "engineer", "admin"],
                        format_func=lambda value: {
                            "viewer": "Consultation",
                            "technician": "Technicien",
                            "engineer": "Ingénieur",
                            "admin": "Administrateur",
                        }[value],
                    )
                    temporary_password = st.text_input(
                        "Mot de passe temporaire",
                        type="password",
                    )

                create_submitted = st.form_submit_button(
                    "Créer le compte",
                    type="primary",
                    use_container_width=True,
                )
                if create_submitted:
                    required_values = [
                        new_full_name,
                        new_username,
                        new_email,
                        temporary_password,
                    ]
                    if not all(value.strip() for value in required_values):
                        st.error("Tous les champs obligatoires doivent être renseignés.")
                    elif not new_email.strip().lower().endswith("@onee.ma"):
                        st.error("Utilisez une adresse professionnelle se terminant par @onee.ma.")
                    else:
                        password_errors = validate_password_strength(
                            temporary_password,
                            new_username,
                            new_email,
                            new_full_name,
                        )
                        if password_errors:
                            st.error("Mot de passe temporaire trop faible : " + ", ".join(password_errors) + ".")
                        else:
                            creation_db = get_db()
                            try:
                                created_user = register_user(
                                    creation_db,
                                    new_username.strip(),
                                    new_email.strip().lower(),
                                    temporary_password,
                                    new_full_name.strip(),
                                    new_department,
                                )
                                if created_user:
                                    created_user.role = new_role
                                    created_user.must_change_password = True
                                    creation_db.commit()
                                    st.success(
                                        f"Compte « {new_username.strip()} » créé. "
                                        "Transmettez les identifiants temporaires par le canal interne prévu."
                                    )
                                else:
                                    st.error("Ce nom d’utilisateur ou cet email est déjà utilisé.")
                            finally:
                                creation_db.close()

        db = get_db()
        try:
            users = (
                db.query(User)
                .filter(User.archived_at.is_(None))
                .order_by(User.username)
                .all()
            )
            user_rows = [{
                "Nom d’utilisateur": item.username,
                "Email": item.email,
                "Nom": item.full_name,
                "Rôle": item.role,
                "Statut": "🟢 Actif" if item.is_active else "🔴 Désactivé",
                "Dernière connexion": (
                    pd.Timestamp(item.last_login)
                    .tz_localize("UTC")
                    .tz_convert("Africa/Casablanca")
                    .strftime("%d/%m/%Y %H:%M")
                    if item.last_login and pd.Timestamp(item.last_login).tzinfo is None
                    else pd.Timestamp(item.last_login)
                    .tz_convert("Africa/Casablanca")
                    .strftime("%d/%m/%Y %H:%M")
                    if item.last_login
                    else "Jamais"
                ),
            } for item in users]
            st.dataframe(pd.DataFrame(user_rows), use_container_width=True, hide_index=True)

            user_options = {str(item.id): item.username for item in users}
            departments = [
                "Production",
                "Maintenance",
                "Exploitation",
                "Instrumentation",
                "Électricité",
                "Informatique",
            ]
            role_labels = {
                "viewer": "Consultation",
                "technician": "Technicien",
                "engineer": "Ingénieur",
                "admin": "Administrateur",
            }

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                with st.expander("✏️ Modifier un utilisateur", expanded=False):
                    edited_user_id = st.selectbox(
                        "Utilisateur à modifier",
                        options=list(user_options),
                        format_func=lambda value: user_options[value],
                        key="admin_edit_user_id",
                    )
                    edited_user = next(
                        item for item in users if str(item.id) == edited_user_id
                    )
                    with st.form("admin_edit_user_form"):
                        edited_full_name = st.text_input(
                            "Nom complet",
                            value=edited_user.full_name or "",
                        )
                        edited_email = st.text_input(
                            "Email professionnel",
                            value=edited_user.email,
                        )
                        edited_department = st.selectbox(
                            "Département",
                            departments,
                            index=(
                                departments.index(edited_user.department)
                                if edited_user.department in departments
                                else 0
                            ),
                        )
                        edited_role = st.selectbox(
                            "Rôle",
                            list(role_labels),
                            index=(
                                list(role_labels).index(edited_user.role)
                                if edited_user.role in role_labels
                                else 0
                            ),
                            format_func=lambda value: role_labels[value],
                        )
                        edited_active = st.checkbox(
                            "Compte actif",
                            value=bool(edited_user.is_active),
                        )
                        edit_submitted = st.form_submit_button(
                            "Enregistrer les modifications",
                            type="primary",
                            use_container_width=True,
                        )

                        if edit_submitted:
                            normalized_email = edited_email.strip().lower()
                            is_current_user = edited_user_id == str(user["id"])
                            duplicate_email = (
                                db.query(User)
                                .filter(
                                    func.lower(User.email) == normalized_email,
                                    User.id != edited_user.id,
                                )
                                .first()
                            )
                            if not edited_full_name.strip() or not normalized_email:
                                st.error("Le nom et l’email sont obligatoires.")
                            elif not normalized_email.endswith("@onee.ma"):
                                st.error("L’email professionnel doit se terminer par @onee.ma.")
                            elif duplicate_email:
                                st.error("Cette adresse email est déjà utilisée.")
                            elif is_current_user and (edited_role != "admin" or not edited_active):
                                st.error("Vous ne pouvez pas retirer vos propres droits administrateur ni désactiver votre compte.")
                            else:
                                edited_user.full_name = edited_full_name.strip()
                                edited_user.email = normalized_email
                                edited_user.department = edited_department
                                edited_user.role = edited_role
                                edited_user.is_active = edited_active
                                edited_user.updated_at = datetime.utcnow()
                                db.commit()
                                if is_current_user:
                                    st.session_state.user["full_name"] = edited_user.full_name
                                    st.session_state.user["email"] = edited_user.email
                                st.success(f"Le compte « {edited_user.username} » a été modifié.")
                                st.rerun()

            with action_col2:
                with st.expander("🗄️ Archiver un utilisateur", expanded=False):
                    archivable_user_options = {
                        str(item.id): item.username
                        for item in users
                        if str(item.id) != str(user["id"])
                    }
                    if not archivable_user_options:
                        st.info("Aucun autre compte à archiver.")
                    else:
                        deleted_user_id = st.selectbox(
                            "Utilisateur à archiver",
                            options=list(archivable_user_options),
                            format_func=lambda value: archivable_user_options[value],
                            key="admin_delete_user_id",
                        )
                        deleted_username = archivable_user_options[deleted_user_id]
                        st.warning(
                            "L’archivage désactive la connexion tout en conservant les ordres, "
                            "alertes et historiques nécessaires à la traçabilité."
                        )
                        with st.form("admin_delete_user_form"):
                            delete_confirmation = st.text_input(
                                f"Écrivez « {deleted_username} » pour confirmer",
                            )
                            delete_submitted = st.form_submit_button(
                                "Archiver le compte",
                                use_container_width=True,
                            )

                            if delete_submitted:
                                if delete_confirmation.strip() != deleted_username:
                                    st.error("Le nom d’utilisateur saisi ne correspond pas.")
                                else:
                                    user_to_archive = (
                                        db.query(User)
                                        .filter(
                                            User.id == uuid.UUID(deleted_user_id),
                                            User.archived_at.is_(None),
                                        )
                                        .first()
                                    )
                                    if user_to_archive is None:
                                        st.error("Ce compte est déjà archivé ou n’existe plus.")
                                    else:
                                        archived_at = datetime.utcnow()
                                        user_to_archive.is_active = False
                                        user_to_archive.archived_at = archived_at
                                        user_to_archive.updated_at = archived_at
                                        db.commit()
                                        st.success(
                                            f"Le compte « {deleted_username} » a été archivé. "
                                            "Son historique est conservé."
                                        )
                                        st.rerun()
        finally:
            db.close()

# ============================================================
# NAVIGATION PRINCIPALE
# ============================================================

def main():
    """Application principale"""
    
    if not st.session_state.authenticated:
        page_auth_final()
    elif st.session_state.user.get("must_change_password", False):
        page_force_password_change()
    else:
        def get_url_page():
            try:
                return get_query_param("page", "dashboard")
            except Exception:
                return "dashboard"

        def set_url_page(slug):
            try:
                set_query_params(page=slug, sid=st.session_state.get("sid"))
            except Exception:
                pass

        page_options = [
            "Tableau de bord",
            "Supervision",
            "Prédictions",
            "Assistant IA",
            "Maintenance",
            "Paramètres",
        ]
        page_slugs = {
            "Tableau de bord": "dashboard",
            "Supervision": "monitoring",
            "Prédictions": "predictions",
            "Assistant IA": "chatbot",
            "Maintenance": "maintenance",
            "Paramètres": "settings",
        }
        slug_to_page = {slug: page for page, slug in page_slugs.items()}
        requested_slug = get_url_page()
        default_page = slug_to_page.get(requested_slug, "Tableau de bord")
        default_index = page_options.index(default_page)

        with st.sidebar:
            user = st.session_state.user
            st.markdown(f"""
                <div class="sidebar-brand">
                    <p class="sidebar-brand-title">ONEE</p>
                    <div class="sidebar-brand-subtitle">Maintenance prédictive</div>
                </div>
                <div class="sidebar-user">👤 {user['full_name']} · {user['role']}</div>
            """, unsafe_allow_html=True)
            st.title("🏭 ONEE")
            st.caption(f" {st.session_state.user['full_name']}")
            st.divider()
            
            page = st.radio(
                "Navigation",
                options=page_options,
                index=default_index,
                label_visibility="collapsed",
                key="navigation_page",
            )

            if get_url_page() != page_slugs[page]:
                set_url_page(page_slugs[page])
            
            st.divider()
            
            if st.button("🚪 Déconnexion", use_container_width=True, key="sidebar_logout_button"):
                logout_user()
                st.rerun()
        
        selected_slug = page_slugs[page]

        if selected_slug == "dashboard":
            page_dashboard()
        elif selected_slug == "monitoring":
            page_monitoring()
        elif selected_slug == "predictions":
            page_predictions()
        elif selected_slug == "chatbot":
            page_chatbot()
        elif selected_slug == "maintenance":
            page_maintenance()
        elif selected_slug == "settings":
            page_settings()
            return

if __name__ == "__main__":
    main()
