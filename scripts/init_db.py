#!/usr/bin/env python3
"""
Script pour initialiser la base de données PostgreSQL
Crée toutes les tables et les données initiales
"""

import os
import sys
import logging
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import inspect
from backend.database import engine, SessionLocal, Base
from backend.models import (
    User, EquipmentType, SensorType
)
from backend.auth import hash_password

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# INIT DB
# ============================================================

def init_database():
    """Initialiser la base de données"""

    load_dotenv(override=True)

    logger.info("=" * 60)
    logger.info("INITIALISATION BASE DE DONNÉES PFE MAINTENANCE")
    logger.info("=" * 60)

    try:
        # Connexion + création tables
        with engine.connect() as connection:
            logger.info("✓ Connexion PostgreSQL réussie")

            Base.metadata.create_all(bind=engine)
            logger.info("✓ Tables créées avec succès")

            inspector = inspect(engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ {len(tables)} tables détectées")

    except Exception as e:
        logger.error(f"✗ Erreur création tables: {e}")
        return False

    # ============================================================
    # INSERT DATA
    # ============================================================

    try:
        db = SessionLocal()

        # ========================================================
        # EQUIPMENT TYPES
        # ========================================================
        if db.query(EquipmentType).count() == 0:
            logger.info("Insertion types équipements...")

            equipment_types_data = [
                {"name": "Turbine", "description": "Turbine vapeur haute pression"},
                {"name": "Chaudière", "description": "Chaudière de récupération de chaleur"},
                {"name": "Alternateur", "description": "Alternateur synchrone de puissance"},
                {"name": "Compresseur", "description": "Compresseur à air"},
                {"name": "Pompe", "description": "Pompe de circulation d'eau"},
                {"name": "Échangeur", "description": "Échangeur thermique"},
            ]

            for item in equipment_types_data:
                db.add(EquipmentType(**item))

            db.commit()
            logger.info("✓ Equipment types insérés")
        else:
            logger.info("✓ Equipment types déjà présents")

        # ========================================================
        # SENSOR TYPES
        # ========================================================
        if db.query(SensorType).count() == 0:
            logger.info("Insertion types capteurs...")

            sensor_types_data = [
                {"name": "Température", "unit": "°C", "min_value": -50, "max_value": 150, "description": "Capteur de température"},
                {"name": "Pression", "unit": "bar", "min_value": 0, "max_value": 500, "description": "Capteur de pression"},
                {"name": "Vibration", "unit": "mm/s", "min_value": 0, "max_value": 50, "description": "Capteur de vibration"},
                {"name": "Courant", "unit": "A", "min_value": 0, "max_value": 5000, "description": "Capteur électrique"},
                {"name": "Débit", "unit": "m³/h", "min_value": 0, "max_value": 10000, "description": "Capteur débit"},
                {"name": "Vitesse", "unit": "rpm", "min_value": 0, "max_value": 10000, "description": "Rotation"},
                {"name": "Humidité", "unit": "%", "min_value": 0, "max_value": 100, "description": "Humidité"},
                {"name": "Puissance", "unit": "MW", "min_value": 0, "max_value": 500, "description": "Puissance"},
            ]

            for item in sensor_types_data:
                db.add(SensorType(**item))

            db.commit()
            logger.info("✓ Sensor types insérés")
        else:
            logger.info("✓ Sensor types déjà présents")

        # ========================================================
        # USERS
        # ========================================================
        admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
        engineer_password = os.getenv("DEFAULT_ENGINEER_PASSWORD")
        if db.query(User).count() == 0 and admin_password and engineer_password:
            logger.info("Création utilisateurs...")

            admin_user = User(
                username="admin",
                email="admin@onee.ma",
                password_hash=hash_password(admin_password),
                full_name="Administrateur",
                role="admin",
                department="IT",
                is_active=True
            )

            engineer_user = User(
                username="engineer",
                email="engineer@onee.ma",
                password_hash=hash_password(engineer_password),
                full_name="Ingénieur Maintenance",
                role="engineer",
                department="Maintenance",
                is_active=True
            )

            db.add(admin_user)
            db.add(engineer_user)

            db.commit()
            logger.info("✓ Users créés")
        else:
            logger.info("✓ Users déjà présents")

        db.close()

    except Exception as e:
        logger.error(f"✗ Erreur insertion données: {e}")
        return False

    # ============================================================
    # FIN
    # ============================================================

    logger.info("=" * 60)
    logger.info("✓ INITIALISATION TERMINÉE")
    logger.info("=" * 60)

    logger.info("\nUtilisateurs test:")
    logger.info("  identifiants fournis uniquement par variables d'environnement")
    logger.info("\n⚠️ Change les mots de passe en production!")

    return True


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
