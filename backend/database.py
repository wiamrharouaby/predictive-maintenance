"""
Configuration de la connexion PostgreSQL et session SQLAlchemy
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

# URL de connexion PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/pfe_maintenance"
)


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _engine_options() -> dict:
    """Options SQLAlchemy adaptees a l'API et aux scripts locaux."""
    options = {
        "echo": _bool_env("SQL_ECHO"),
        "pool_pre_ping": True,
    }

    if _bool_env("DB_POOL_DISABLED"):
        options["poolclass"] = NullPool
        return options

    options.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        }
    )
    return options

# Créer l'engine
engine = create_engine(DATABASE_URL, **_engine_options())

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles ORM
Base = declarative_base()

def get_db():
    """Dépendance FastAPI pour obtenir une session DB"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialiser la base de données"""
    Base.metadata.create_all(bind=engine)
    # create_all ne modifie pas une table existante.
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE chat_history "
            "ADD COLUMN IF NOT EXISTS conversation_id UUID "
            "REFERENCES chat_conversations(id) ON DELETE CASCADE"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chat_history_conversation_id "
            "ON chat_history (conversation_id)"
        ))
        connection.execute(text(
            "ALTER TABLE chat_history "
            "ADD COLUMN IF NOT EXISTS sources_json TEXT"
        ))
        connection.execute(text(
            "ALTER TABLE maintenance_orders "
            "ADD COLUMN IF NOT EXISTS description TEXT"
        ))
        connection.execute(text(
            "ALTER TABLE maintenance_orders "
            "ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium'"
        ))
        connection.execute(text(
            "ALTER TABLE maintenance_orders "
            "ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'new'"
        ))
        connection.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        connection.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE"
        ))
    if os.getenv("SEED_DEFAULT_USERS", "false").lower() in {"1", "true", "yes"}:
        create_default_users()
    if os.getenv("SEED_DEMO_OPERATIONAL_DATA", "true").lower() in {"1", "true", "yes"}:
        seed_demo_operational_data()


def seed_demo_operational_data():
    """Alimenter idempotemment le corpus RAG et les RUL de demonstration."""
    from datetime import datetime
    from backend.models import Equipment, KnowledgeBase, RULPrediction
    from backend.rag_chatbot import generate_default_knowledge_base

    db = SessionLocal()
    try:
        existing_titles = {
            title for (title,) in db.query(KnowledgeBase.document_title).all()
        }
        for document in generate_default_knowledge_base():
            if document["document_title"] in existing_titles:
                continue
            db.add(KnowledgeBase(
                document_title=document["document_title"],
                content=document["content"],
            ))

        if db.query(RULPrediction).count() == 0:
            equipment = db.query(Equipment).order_by(Equipment.equipment_code).all()
            demo_rul_hours = [432, 960, 1440, 2160, 3120, 4080, 5040]
            for index, item in enumerate(equipment):
                db.add(RULPrediction(
                    equipment_id=item.id,
                    predicted_rul_hours=demo_rul_hours[index % len(demo_rul_hours)],
                    prediction_date=datetime.utcnow(),
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def create_default_users():
    """Créer les utilisateurs par défaut (admin et engineer)"""
    from backend.auth import hash_password
    from backend.models import User
    
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    engineer_password = os.getenv("DEFAULT_ENGINEER_PASSWORD")
    if not admin_password or not engineer_password:
        print("Utilisateurs par defaut ignores: mots de passe non configures")
        return

    db = SessionLocal()
    try:
        default_users = [
            {
                "username": "admin",
                "email": "admin@onee.ma",
                "password": admin_password,
                "full_name": "Administrator",
                "role": "admin",
            },
            {
                "username": "engineer",
                "email": "engineer@onee.ma",
                "password": engineer_password,
                "full_name": "Engineer User",
                "role": "engineer",
            },
        ]

        for item in default_users:
            existing = db.query(User).filter(User.username == item["username"]).first()
            if existing:
                print(f"Utilisateur {item['username']} déjà présent")
                continue

            db.add(User(
                username=item["username"],
                email=item["email"],
                password_hash=hash_password(item["password"]),
                full_name=item["full_name"],
                role=item["role"],
                is_active=True
            ))
            print(f"Utilisateur {item['username']} créé")
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠ Erreur lors de la création des utilisateurs par défaut: {e}")
    finally:
        db.close()

def test_connection():
    """Tester la connexion à la base de données"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✓ Connexion PostgreSQL réussie!")
            return True
    except Exception as e:
        print(f"✗ Erreur connexion PostgreSQL: {e}")
        return False
