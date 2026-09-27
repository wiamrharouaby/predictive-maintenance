"""
Générateur de données synthétiques réalistes pour capteurs de centrale thermique
Simule 10 équipements avec 5 capteurs chacun sur 3 mois
"""
import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class ThermalPowerPlantDataGenerator:
    """Génère des données synthétiques réalistes pour une centrale thermique"""
    
    def __init__(self, seed: int = 42):
        """Initialiser le générateur"""
        random.seed(seed)
        np.random.seed(seed)
        
        self.equipment_configs = self._create_equipment_configs()
        self.start_date = datetime.utcnow() - timedelta(days=90)  # 3 mois d'historique
        
    def _create_equipment_configs(self) -> Dict:
        """Créer les configurations d'équipements réalistes"""
        return {
            # Turbines
            "TURB-01": {
                "type": "Turbine",
                "name": "Turbine Haute Pression 1",
                "location": "Hall A",
                "power": "50 MW",
                "sensors": {
                    "temperature": {"nominal": 380, "range": (350, 410), "noise": 2},
                    "pressure": {"nominal": 120, "range": (100, 140), "noise": 3},
                    "vibration": {"nominal": 5, "range": (2, 15), "noise": 0.5},
                    "speed": {"nominal": 3000, "range": (2800, 3200), "noise": 10},
                }
            },
            "TURB-02": {
                "type": "Turbine",
                "name": "Turbine Basse Pression 1",
                "location": "Hall A",
                "power": "30 MW",
                "sensors": {
                    "temperature": {"nominal": 320, "range": (300, 340), "noise": 2},
                    "pressure": {"nominal": 30, "range": (20, 40), "noise": 1},
                    "vibration": {"nominal": 4, "range": (1, 12), "noise": 0.4},
                    "speed": {"nominal": 1500, "range": (1400, 1600), "noise": 5},
                }
            },
            # Chaudières
            "CHAUD-01": {
                "type": "Chaudière",
                "name": "Chaudière de Récupération 1",
                "location": "Hall B",
                "power": "200 MW",
                "sensors": {
                    "temperature": {"nominal": 450, "range": (400, 500), "noise": 5},
                    "pressure": {"nominal": 180, "range": (150, 210), "noise": 5},
                    "flow_rate": {"nominal": 800, "range": (600, 1000), "noise": 20},
                    "vibration": {"nominal": 3, "range": (0.5, 10), "noise": 0.3},
                }
            },
            "CHAUD-02": {
                "type": "Chaudière",
                "name": "Chaudière de Récupération 2",
                "location": "Hall B",
                "power": "200 MW",
                "sensors": {
                    "temperature": {"nominal": 440, "range": (390, 490), "noise": 5},
                    "pressure": {"nominal": 175, "range": (145, 205), "noise": 5},
                    "flow_rate": {"nominal": 780, "range": (580, 980), "noise": 20},
                    "vibration": {"nominal": 3.2, "range": (0.5, 10), "noise": 0.3},
                }
            },
            # Alternateurs
            "ALT-01": {
                "type": "Alternateur",
                "name": "Alternateur 1",
                "location": "Hall C",
                "power": "80 MW",
                "sensors": {
                    "temperature": {"nominal": 60, "range": (40, 80), "noise": 1},
                    "current": {"nominal": 3000, "range": (2500, 3500), "noise": 50},
                    "vibration": {"nominal": 2, "range": (0.2, 8), "noise": 0.2},
                    "frequency": {"nominal": 50, "range": (49.5, 50.5), "noise": 0.05},
                }
            },
            "ALT-02": {
                "type": "Alternateur",
                "name": "Alternateur 2",
                "location": "Hall C",
                "power": "80 MW",
                "sensors": {
                    "temperature": {"nominal": 58, "range": (38, 78), "noise": 1},
                    "current": {"nominal": 2950, "range": (2450, 3450), "noise": 50},
                    "vibration": {"nominal": 2.1, "range": (0.2, 8), "noise": 0.2},
                    "frequency": {"nominal": 50, "range": (49.5, 50.5), "noise": 0.05},
                }
            },
            # Compresseurs
            "COMP-01": {
                "type": "Compresseur",
                "name": "Compresseur Air 1",
                "location": "Hall D",
                "power": "20 MW",
                "sensors": {
                    "temperature": {"nominal": 75, "range": (50, 100), "noise": 2},
                    "pressure": {"nominal": 8, "range": (6, 10), "noise": 0.3},
                    "vibration": {"nominal": 6, "range": (2, 14), "noise": 0.8},
                    "speed": {"nominal": 4500, "range": (4000, 5000), "noise": 50},
                }
            },
            # Pompes
            "PUMP-01": {
                "type": "Pompe",
                "name": "Pompe Circulation Eau 1",
                "location": "Hall E",
                "power": "5 MW",
                "sensors": {
                    "temperature": {"nominal": 65, "range": (50, 80), "noise": 1},
                    "pressure_inlet": {"nominal": 2, "range": (1, 3), "noise": 0.2},
                    "pressure_outlet": {"nominal": 18, "range": (16, 20), "noise": 0.5},
                    "vibration": {"nominal": 3, "range": (0.5, 8), "noise": 0.3},
                }
            },
            # Échangeurs
            "EXCH-01": {
                "type": "Échangeur",
                "name": "Échangeur Thermique 1",
                "location": "Hall F",
                "power": "100 MW",
                "sensors": {
                    "temperature_in": {"nominal": 350, "range": (320, 380), "noise": 3},
                    "temperature_out": {"nominal": 200, "range": (170, 230), "noise": 3},
                    "pressure_drop": {"nominal": 5, "range": (3, 8), "noise": 0.5},
                    "flow_rate": {"nominal": 500, "range": (400, 600), "noise": 15},
                }
            },
        }
    
    def generate_reading(
        self,
        timestamp: datetime,
        equipment_id: str,
        sensor_type: str,
        config: Dict
    ) -> float:
        """Générer une lecture avec variations réalistes"""
        
        nominal = config["nominal"]
        range_min, range_max = config["range"]
        noise = config["noise"]
        
        # Patterns cycliques réalistes (variations quotidiennes)
        hour_of_day = timestamp.hour
        hour_factor = 0.02 * np.sin(2 * np.pi * hour_of_day / 24)
        
        # Trend légèrement croissant (dégradation avec le temps)
        days_elapsed = (timestamp - self.start_date).days
        degradation = 0.001 * days_elapsed
        
        # Ajouter du bruit aléatoire
        random_noise = np.random.normal(0, noise)
        
        # Valeur finale avec tous les facteurs
        value = nominal * (1 + hour_factor + degradation + random_noise / nominal)
        
        # Clamp dans la plage valide
        value = max(range_min, min(range_max, value))
        
        return round(value, 2)
    
    def generate_sensor_readings(
        self,
        equipment_id: str,
        num_days: int = 90,
        interval_minutes: int = 15
    ) -> List[Tuple]:
        """Générer des lectures pour un équipement sur plusieurs jours"""
        
        readings = []
        equipment_config = self.equipment_configs.get(equipment_id)
        
        if not equipment_config:
            return readings
        
        current_time = self.start_date
        end_time = self.start_date + timedelta(days=num_days)
        
        while current_time < end_time:
            for sensor_name, sensor_config in equipment_config["sensors"].items():
                reading_value = self.generate_reading(
                    current_time,
                    equipment_id,
                    sensor_name,
                    sensor_config
                )
                
                readings.append({
                    "equipment_id": equipment_id,
                    "sensor_name": sensor_name,
                    "value": reading_value,
                    "timestamp": current_time,
                    "status": "normal"
                })
            
            current_time += timedelta(minutes=interval_minutes)
        
        return readings
    
    def generate_anomalies(
        self,
        equipment_id: str,
        readings: List[Dict],
        anomaly_probability: float = 0.05
    ) -> List[Dict]:
        """Générer des anomalies détectées"""
        
        anomalies = []
        equipment_config = self.equipment_configs.get(equipment_id)
        
        if not equipment_config:
            return anomalies
        
        for i, reading in enumerate(readings):
            if random.random() < anomaly_probability:
                sensor_type = reading["sensor_name"]
                sensor_config = equipment_config["sensors"].get(sensor_type)
                
                if sensor_config:
                    # Calculer un score d'anomalie basé sur la déviation
                    nominal = sensor_config["nominal"]
                    actual = reading["value"]
                    deviation = abs(actual - nominal) / nominal
                    
                    anomaly_score = min(0.99, deviation)
                    
                    # Déterminer la sévérité
                    if anomaly_score > 0.2:
                        severity = "critical"
                    elif anomaly_score > 0.15:
                        severity = "high"
                    elif anomaly_score > 0.1:
                        severity = "medium"
                    else:
                        severity = "low"
                    
                    anomalies.append({
                        "sensor_name": sensor_type,
                        "equipment_id": equipment_id,
                        "anomaly_type": "univariate",
                        "anomaly_score": round(anomaly_score, 4),
                        "detection_timestamp": reading["timestamp"],
                        "actual_value": reading["value"],
                        "threshold_value": nominal,
                        "severity": severity,
                        "description": f"Déviation détectée pour {sensor_type}"
                    })
        
        return anomalies
    
    def generate_all_data(self, num_days: int = 90) -> Dict:
        """Générer toutes les données synthétiques"""
        
        all_data = {
            "equipment": [],
            "sensors": [],
            "readings": [],
            "anomalies": []
        }
        
        logger.info(f"Génération de données pour {len(self.equipment_configs)} équipements...")
        
        sensor_counter = 0
        for equipment_code, equipment_config in self.equipment_configs.items():
            
            # Ajouter l'équipement
            all_data["equipment"].append({
                "code": equipment_code,
                "name": equipment_config["name"],
                "type": equipment_config["type"],
                "location": equipment_config["location"],
                "power": equipment_config["power"]
            })
            
            # Ajouter les capteurs
            sensor_names = []
            for sensor_name in equipment_config["sensors"].keys():
                sensor_counter += 1
                sensor_code = f"SENS-{sensor_counter:04d}"
                sensor_names.append(sensor_name)
                
                all_data["sensors"].append({
                    "code": sensor_code,
                    "name": sensor_name,
                    "equipment_code": equipment_code,
                    "type": sensor_name.lower()
                })
            
            # Générer les lectures
            logger.info(f"  Génération des lectures pour {equipment_code}...")
            readings = self.generate_sensor_readings(equipment_code, num_days)
            all_data["readings"].extend(readings)
            
            # Générer les anomalies
            anomalies = self.generate_anomalies(equipment_code, readings)
            all_data["anomalies"].extend(anomalies)
        
        logger.info(f"✓ Données générées: {len(all_data['equipment'])} équipements, "
                   f"{len(all_data['sensors'])} capteurs, "
                   f"{len(all_data['readings'])} lectures, "
                   f"{len(all_data['anomalies'])} anomalies")
        
        return all_data
    
    @staticmethod
    def get_equipment_summary() -> str:
        """Obtenir un résumé des équipements configurés"""
        generator = ThermalPowerPlantDataGenerator()
        summary = "Équipements configurés pour la génération de données:\n"
        summary += "=" * 60 + "\n"
        
        for code, config in generator.equipment_configs.items():
            summary += f"{code}: {config['name']} ({config['type']}) - {len(config['sensors'])} capteurs\n"
        
        return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test du générateur
    print(ThermalPowerPlantDataGenerator.get_equipment_summary())
    
    generator = ThermalPowerPlantDataGenerator()
    data = generator.generate_all_data(num_days=7)  # Test sur 7 jours
    
    print(f"\nRésumé des données générées:")
    print(f"  Équipements: {len(data['equipment'])}")
    print(f"  Capteurs: {len(data['sensors'])}")
    print(f"  Lectures: {len(data['readings'])}")
    print(f"  Anomalies: {len(data['anomalies'])}")
