import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import Alert, Equipment


ALERT_TITLE = "Vibration critique détectée — Turbine Nord"
ALERT_MESSAGE = (
    "Le modèle ML a détecté un niveau vibratoire critique sur le rotor. "
    "Réduire la charge et contrôler immédiatement les paliers, l’alignement et l’état du rotor."
)
ALERT_TYPE = "anomaly"
ALERT_SEVERITY = "critical"
ALERT_STATUS = "active"


db = SessionLocal()

try:
    equipment = db.query(Equipment).first()

    if not equipment:
        print("Aucun équipement trouvé! Créez d'abord les données.")
        exit(1)

    existing_alert = (
        db.query(Alert)
        .filter(
            Alert.equipment_id == equipment.id,
            Alert.title == ALERT_TITLE,
            Alert.status == ALERT_STATUS,
        )
        .first()
    )

    if existing_alert:
        print("Cette alerte existe déjà, aucune nouvelle alerte créée.")
        print(f"   ID: {existing_alert.id}")
        print(f"   Équipement: {equipment.name}")
        print(f"   Titre: {existing_alert.title}")
        print(f"   Sévérité: {existing_alert.severity}")
        print(f"   Status: {existing_alert.status}")
        print("\nRechargez le dashboard Streamlit pour la voir.")
        exit(0)

    alert = Alert(
        id=uuid.uuid4(),
        equipment_id=equipment.id,
        title=ALERT_TITLE,
        message=ALERT_MESSAGE,
        alert_type=ALERT_TYPE,
        severity=ALERT_SEVERITY,
        status=ALERT_STATUS,
        created_at=datetime.utcnow(),
    )

    db.add(alert)
    db.commit()

    print("Alerte test créée avec succès!")
    print(f"   ID: {alert.id}")
    print(f"   Équipement: {equipment.name}")
    print(f"   Titre: {alert.title}")
    print(f"   Sévérité: {alert.severity}")
    print(f"   Status: {alert.status}")
    print("\nRechargez maintenant le dashboard Streamlit pour voir l'alerte!")

except Exception as e:
    print(f"Erreur: {e}")
    db.rollback()
finally:
    db.close()
