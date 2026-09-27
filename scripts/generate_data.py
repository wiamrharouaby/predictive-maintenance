#!/usr/bin/env python3
"""
Script pour générer des données synthétiques réalistes pour le système de maintenance prédictive
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import random

# Ajouter le chemin du backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import SessionLocal, engine
from backend.models import Base, EquipmentType, Equipment, Sensor, SensorReading
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_synthetic_data():
    """Génère les données synthétiques pour le système ONEE"""
    
    logger.info("=" * 60)
    logger.info("GÉNÉRATION DES DONNÉES SYNTHÉTIQUES")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 1. Créer les types d'équipements
        logger.info("Création des types d'équipements...")
        
        equipment_types_data = [
            {"name": "Turbine", "description": "Turbine à vapeur de la centrale"},
            {"name": "Chaudière", "description": "Chaudière de production de vapeur"},
            {"name": "Alternateur", "description": "Alternateur de production d'électricité"},
            {"name": "Condenseur", "description": "Condenseur pour refroidissement"},
        ]
        
        equipment_types = {}
        for et_data in equipment_types_data:
            existing = db.query(EquipmentType).filter(EquipmentType.name == et_data["name"]).first()
            if not existing:
                et = EquipmentType(**et_data)
                db.add(et)
                logger.info(f"  ✓ Type '{et_data['name']}' créé")
            else:
                et = existing
                logger.info(f"  ✓ Type '{et_data['name']}' existe déjà")
            equipment_types[et_data["name"]] = et
        
        db.commit()
        logger.info("✓ Types d'équipements créés")
        
        # 2. Créer les équipements
        logger.info("Création des équipements...")
        
        equipment_data = [
            {"type": "Turbine", "name": "Turbine 1", "location": "Bloc A"},
            {"type": "Turbine", "name": "Turbine 2", "location": "Bloc B"},
            {"type": "Chaudière", "name": "Chaudière 1", "location": "Bloc A"},
            {"type": "Chaudière", "name": "Chaudière 2", "location": "Bloc B"},
            {"type": "Alternateur", "name": "Alternateur 1", "location": "Bloc A"},
            {"type": "Alternateur", "name": "Alternateur 2", "location": "Bloc B"},
            {"type": "Condenseur", "name": "Condenseur 1", "location": "Bloc A"},
        ]
        
        equipment_objects = {}
        for eq_data in equipment_data:
            existing = db.query(Equipment).filter(Equipment.name == eq_data["name"]).first()
            if not existing:
                eq = Equipment(
                    equipment_type_id=equipment_types[eq_data["type"]].id,
                    equipment_code=f"EQ-{eq_data['type'][:3].upper()}-{random.randint(1000, 9999)}",
                    name=eq_data["name"],
                    location=eq_data["location"],
                    manufacturer="ONEE Manufacturing",
                    model=f"Model-{random.randint(2000, 2025)}",
                    installation_date=(datetime.now() - timedelta(days=random.randint(365, 3650))).date(),
                    nominal_power="100 MW",
                    is_active=True
                )
                db.add(eq)
                logger.info(f"  ✓ Équipement '{eq_data['name']}' créé")
            else:
                eq = existing
                logger.info(f"  ✓ Équipement '{eq_data['name']}' existe déjà")
            equipment_objects[eq_data["name"]] = eq
        
        db.commit()
        logger.info("✓ Équipements créés")
        
        # Recharger les équipements avec leurs relations
        equipment_objects = {}
        for eq_data in equipment_data:
            eq = db.query(Equipment).filter(Equipment.name == eq_data["name"]).first()
            equipment_objects[eq_data["name"]] = eq
        
        # 3. Créer les capteurs
        logger.info("Création des capteurs...")
        
        sensor_templates = {
            "Turbine": [
                {"name": "Température Sortie Vapeur", "unit": "°C", "min_value": 300, "max_value": 600},
                {"name": "Pression Sortie Vapeur", "unit": "bar", "min_value": 1, "max_value": 300},
                {"name": "Vibration Rotor", "unit": "mm/s", "min_value": 0, "max_value": 10},
                {"name": "Vitesse Rotation", "unit": "RPM", "min_value": 2000, "max_value": 4000},
            ],
            "Chaudière": [
                {"name": "Température Foyer", "unit": "°C", "min_value": 800, "max_value": 1200},
                {"name": "Pression Vapeur", "unit": "bar", "min_value": 50, "max_value": 250},
                {"name": "Débit Eau Alimentation", "unit": "t/h", "min_value": 100, "max_value": 500},
                {"name": "Température Eau Retour", "unit": "°C", "min_value": 100, "max_value": 300},
            ],
            "Alternateur": [
                {"name": "Température Stator", "unit": "°C", "min_value": 20, "max_value": 120},
                {"name": "Vibration Palier", "unit": "mm/s", "min_value": 0, "max_value": 8},
                {"name": "Courant Sortie", "unit": "A", "min_value": 1000, "max_value": 5000},
                {"name": "Tension Sortie", "unit": "kV", "min_value": 10, "max_value": 25},
            ],
            "Condenseur": [
                {"name": "Température Entrée Eau", "unit": "°C", "min_value": 10, "max_value": 30},
                {"name": "Température Sortie Eau", "unit": "°C", "min_value": 20, "max_value": 40},
                {"name": "Débit Eau Circulation", "unit": "m³/h", "min_value": 1000, "max_value": 5000},
                {"name": "Vide Condenseur", "unit": "mbar", "min_value": 0, "max_value": 100},
            ],
        }
        
        # Obtenir ou créer les types de capteurs
        from backend.models import SensorType
        
        sensor_type_default = db.query(SensorType).filter(SensorType.name == "Analog").first()
        if not sensor_type_default:
            sensor_type_default = SensorType(
                name="Analog",
                description="Capteur analogique standard"
            )
            db.add(sensor_type_default)
            db.commit()
        
        sensor_objects = {}
        for eq_name, eq_obj in equipment_objects.items():
            eq_data = next((e for e in equipment_data if e["name"] == eq_name), None)
            if not eq_data:
                continue
            eq_type_name = eq_data["type"]
            sensors = sensor_templates.get(eq_type_name, [])
            
            for sensor_data in sensors:
                existing = db.query(Sensor).filter(
                    (Sensor.equipment_id == eq_obj.id) &
                    (Sensor.name == sensor_data["name"])
                ).first()
                
                if not existing:
                    sensor = Sensor(
                        equipment_id=eq_obj.id,
                        sensor_type_id=sensor_type_default.id,
                        sensor_code=f"SNS-{eq_obj.equipment_code}-{sensor_data['name'][:20].upper()}",
                        name=sensor_data["name"],
                        location_on_equipment=f"Loc-{eq_name}",
                        unit=sensor_data["unit"],
                        min_value=sensor_data["min_value"],
                        max_value=sensor_data["max_value"],
                        installation_date=datetime.now().date(),
                        is_active=True
                    )
                    db.add(sensor)
                    logger.info(f"  ✓ Capteur '{sensor_data['name']}' créé pour {eq_name}")
                else:
                    sensor = existing
                
                sensor_objects[f"{eq_name}_{sensor_data['name']}"] = sensor
        
        db.commit()
        logger.info("✓ Capteurs créés")
        
        # 4. Générer les lectures de capteurs (historique 3 mois)
        logger.info("Génération des lectures de capteurs (3 mois d'historique)...")
        
        now = datetime.now()
        start_date = now - timedelta(days=90)
        
        readings_count = 0
        for sensor_name, sensor in sensor_objects.items():
            # Générer 2 lectures par jour pendant 90 jours
            current_date = start_date
            
            # Vérifier si des lectures existent déjà
            existing_count = db.query(SensorReading).filter(
                SensorReading.sensor_id == sensor.id
            ).count()
            
            if existing_count == 0:
                while current_date <= now:
                    # 2 lectures par jour (matin et soir)
                    for _ in range(2):
                        # Générer une valeur avec une petite variation
                        base_value = float(sensor.min_value + sensor.max_value) / 2

                        variation = random.gauss(
                            0,
                            float(sensor.max_value - sensor.min_value) * 0.05
                        )

                        value = base_value + variation

                        value = max(float(sensor.min_value), min(float(sensor.max_value), value))
                        
                        # Ajouter quelques anomalies aléatoires
                        if random.random() < 0.02:  # 2% d'anomalies
                            value = random.uniform(
                                float(sensor.min_value) * 0.5,
                                float(sensor.max_value) * 1.5
                            )
                        
                        reading = SensorReading(
                           sensor_id=sensor.id,
                           value=round(value, 2),
                           timestamp=current_date + timedelta(
                               hours=random.randint(0, 23),
                               minutes=random.randint(0, 59)
                           ),
                           status="normal"
                        )
                        db.add(reading)
                        readings_count += 1
                    
                    current_date += timedelta(days=1)
        
        db.commit()
        logger.info(f"✓ {readings_count} lectures de capteurs créées")
        
        logger.info("=" * 60)
        logger.info("✓ GÉNÉRATION COMPLÈTE")
        logger.info("=" * 60)
        logger.info(f"✓ {len(equipment_objects)} équipements créés")
        logger.info(f"✓ {len(sensor_objects)} capteurs créés")
        logger.info(f"✓ {readings_count} lectures de capteurs créées")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    generate_synthetic_data()
