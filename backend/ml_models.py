"""
Modèles de Machine Learning pour détection d'anomalies et prédiction RUL
Utilise scikit-learn, XGBoost et TensorFlow
"""
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Optional
from pathlib import Path
import logging

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
import joblib

logger = logging.getLogger(__name__)

# Répertoire pour sauvegarder les modèles
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def _repair_sklearn_tree_compat(estimator) -> None:
    """Patch old sklearn tree estimators loaded with newer sklearn releases."""
    visited = set()

    def repair(obj) -> None:
        if obj is None:
            return

        obj_id = id(obj)
        if obj_id in visited:
            return
        visited.add(obj_id)

        if obj.__class__.__name__ == "ExtraTreeRegressor" and not hasattr(obj, "monotonic_cst"):
            obj.monotonic_cst = None

        estimators = getattr(obj, "estimators_", None)
        if estimators is not None:
            for child in np.ravel(estimators):
                repair(child)

        for attr_name in ("estimator_", "base_estimator_"):
            repair(getattr(obj, attr_name, None))

    repair(estimator)


def _repair_xgboost_compat(model) -> None:
    """Patch old XGBoost sklearn wrappers loaded with newer XGBoost releases."""
    if model is not None and model.__class__.__name__.startswith("XGB") and not hasattr(model, "feature_weights"):
        model.feature_weights = None

# ============================================================
# MODÈLE 1: DÉTECTION D'ANOMALIES (Isolation Forest)
# ============================================================

class AnomalyDetectionModel:
    """Modèle de détection d'anomalies utilisant Isolation Forest"""
    
    def __init__(self, contamination: float = 0.05):
        """Initialiser le modèle"""
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.model_name = "anomaly_detection"
        self.evaluation_data = None
        
    def train(self, X_train: np.ndarray) -> Dict:
        """Entraîner le modèle sur les données"""
        
        logger.info("Entraînement du modèle de détection d'anomalies...")
        
        # Normaliser les données
        X_scaled = self.scaler.fit_transform(X_train)
        
        # Entraîner Isolation Forest
        self.model.fit(X_scaled)
        self.is_fitted = True
        
        # Calcul des métriques
        predictions = self.model.predict(X_scaled)
        raw_scores = self.model.score_samples(X_scaled)
        self.evaluation_data = {
            "labels": predictions.copy(),
            "scores": raw_scores.copy(),
            "decision_threshold": float(self.model.offset_),
        }
        anomaly_count = sum(predictions == -1)
        anomaly_ratio = anomaly_count / len(predictions)
        
        metrics = {
            "samples": len(X_train),
            "anomalies_detected": int(anomaly_count),
            "anomaly_ratio": float(anomaly_ratio),
            "contamination": self.model.contamination
        }
        
        logger.info(f"✓ Modèle entraîné: {anomaly_count} anomalies sur {len(X_train)} samples")
        return metrics
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Prédire les anomalies et retourner les scores"""
        
        if not self.is_fitted:
            raise ValueError("Le modèle doit d'abord être entraîné")
        
        X_scaled = self.scaler.transform(X)
        
        # Prédictions (-1 = anomalie, 1 = normal)
        predictions = self.model.predict(X_scaled)
        
        # Scores d'anomalie (négatifs pour les anomalies)
        scores = self.model.score_samples(X_scaled)
        
        # Normaliser les scores en [0, 1]
        normalized_scores = 1 / (1 + np.exp(scores))  # Sigmoïde
        
        return predictions, normalized_scores
    
    def save(self) -> bool:
        """Sauvegarder le modèle"""
        try:
            model_path = MODELS_DIR / f"{self.model_name}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'timestamp': datetime.utcnow().isoformat()
                }, f)
            logger.info(f"✓ Modèle sauvegardé: {model_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Erreur sauvegarde modèle: {e}")
            return False
    
    def load(self) -> bool:
        """Charger le modèle"""
        try:
            model_path = MODELS_DIR / f"{self.model_name}.pkl"
            if not model_path.exists():
                logger.warning(f"Modèle non trouvé: {model_path}")
                return False
            
            with open(model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.scaler = data['scaler']
                _repair_sklearn_tree_compat(self.model)
                self.is_fitted = True
            
            logger.info(f"✓ Modèle chargé: {model_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Erreur chargement modèle: {e}")
            return False


# ============================================================
# MODÈLE 2: PRÉDICTION RUL (Remaining Useful Life)
# ============================================================

class RULPredictionModel:
    """Modèle de prédiction RUL utilisant XGBoost"""
    
    def __init__(self):
        """Initialiser le modèle"""
        self.model = XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            objective='reg:squarederror'
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.model_name = "rul_prediction"
        self.feature_names = None
        self.evaluation_data = None
        
    def create_features(self, readings_df: pd.DataFrame) -> pd.DataFrame:
        """Créer des features pour le RUL à partir des lectures de capteurs"""
        
        features = []
        
        # Grouper par équipement et fenêtre temporelle
        equipment_groups = readings_df.groupby('equipment_id')
        
        for equipment_id, eq_data in equipment_groups:
            
            # Fenêtres de 24h
            eq_data = eq_data.copy()
            eq_data['timestamp'] = pd.to_datetime(eq_data['timestamp'], utc=True, errors='coerce')
            eq_data = eq_data.dropna(subset=['timestamp']).sort_values('timestamp')
            eq_data['date'] = eq_data['timestamp'].dt.date
            
            for date, day_data in eq_data.groupby('date'):
                if len(day_data) > 0:
                    # Statistiques des capteurs
                    feature_dict = {
                        'equipment_id': equipment_id,
                        'timestamp': day_data['timestamp'].max(),
                        'sensor_count': day_data['sensor_name'].nunique(),
                        'mean_value': day_data['value'].mean(),
                        'std_value': day_data['value'].std(),
                        'max_value': day_data['value'].max(),
                        'min_value': day_data['value'].min(),
                        'anomaly_count': (day_data['status'] == 'anomaly').sum()
                    }
                    features.append(feature_dict)
        
        return pd.DataFrame(features)
    
    def train(self, readings_df: pd.DataFrame, equipment_df: pd.DataFrame) -> Dict:
        """Entraîner le modèle"""
        
        logger.info("Entraînement du modèle RUL...")
        
        # Créer les features
        features_df = self.create_features(readings_df)
        # mean_value sert actuellement a construire le proxy RUL historique :
        # l'exclure des variables explicatives evite une fuite cible -> feature.
        self.feature_names = [
            col for col in features_df.columns
            if col not in ['equipment_id', 'timestamp', 'mean_value']
        ]
        
        if len(features_df) < 10:
            logger.warning("Pas assez de données pour entraîner le RUL")
            return {"status": "insufficient_data"}
        
        X = features_df[self.feature_names].fillna(0).values
        
        # Créer les targets (RUL simulation)
        # Plus de déviation = moins de vie utile restante
        y = 8760 - (features_df['mean_value'].fillna(0).to_numpy() * 100)
        y = np.maximum(y, 100)  # RUL minimum = 100 heures
        
        # Normaliser et entraîner
        indices = np.arange(len(X))
        X_train, X_test, y_train, y_test, _, test_indices = train_test_split(
            X, y, indices, test_size=0.2, random_state=42
        )
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model.fit(X_train_scaled, y_train)
        self.is_fitted = True
        
        # Métriques
        from sklearn.metrics import mean_absolute_error, r2_score
        predictions = self.model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions) if len(y_test) >= 2 else float("nan")
        self.evaluation_data = {
            "y_test": np.asarray(y_test, dtype=float),
            "y_pred": np.asarray(predictions, dtype=float),
            "errors": np.asarray(y_test - predictions, dtype=float),
            "timestamps": features_df.iloc[test_indices]["timestamp"].to_numpy(),
            "target_is_proxy": True,
        }
        
        metrics = {
            "samples": len(X),
            "features": len(self.feature_names),
            "mae": float(mae),
            "r2_score": float(r2),
            "test_samples": len(y_test),
            "target_is_proxy": True,
        }
        
        logger.info(f"✓ Modèle RUL entraîné: MAE={mae:.2f}h, R²={r2:.4f}")
        return metrics
    
    def predict(self, readings_df: pd.DataFrame) -> Dict[str, float]:
        """Prédire le RUL pour les équipements"""
        
        if not self.is_fitted:
            raise ValueError("Le modèle doit d'abord être entraîné")
        
        features_df = self.create_features(readings_df)
        X = features_df[self.feature_names].fillna(0).values
        
        if len(X) == 0:
            return {}
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        # Associer les prédictions aux équipements
        results = {}
        for idx, row in features_df.iterrows():
            equipment_id = row['equipment_id']
            rul_hours = max(0, int(predictions[idx]))
            
            if equipment_id not in results:
                results[equipment_id] = rul_hours
            else:
                results[equipment_id] = min(results[equipment_id], rul_hours)
        
        return results
    
    def save(self) -> bool:
        """Sauvegarder le modèle"""
        try:
            model_path = MODELS_DIR / f"{self.model_name}.pkl"
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'timestamp': datetime.utcnow().isoformat()
            }, model_path)
            logger.info(f"✓ Modèle RUL sauvegardé: {model_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Erreur sauvegarde RUL: {e}")
            return False
    
    def load(self) -> bool:
        """Charger le modèle"""
        try:
            model_path = MODELS_DIR / f"{self.model_name}.pkl"
            if not model_path.exists():
                logger.warning(f"Modèle non trouvé: {model_path}")
                return False
            
            data = joblib.load(model_path)
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_names = data['feature_names']
            _repair_sklearn_tree_compat(self.model)
            _repair_xgboost_compat(self.model)
            self.is_fitted = True
            
            logger.info(f"✓ Modèle RUL chargé: {model_path}")
            return True
        except Exception as e:
            logger.error(f"✗ Erreur chargement RUL: {e}")
            return False


# ============================================================
# CLASSE UTILITAIRE: ML Pipeline Manager
# ============================================================

class MLPipelineManager:
    """Gestionnaire des modèles ML"""
    
    def __init__(self):
        """Initialiser le pipeline"""
        self.anomaly_model = AnomalyDetectionModel()
        self.rul_model = RULPredictionModel()
        
    def train_all_models(
        self,
        readings_data: List[Dict],
        equipment_data: List[Dict]
    ) -> Dict:
        """Entraîner tous les modèles"""
        
        logger.info("Entraînement de tous les modèles ML...")
        
        # Convertir en DataFrames
        readings_df = pd.DataFrame(readings_data)
        equipment_df = pd.DataFrame(equipment_data)
        
        # Entraîner le modèle d'anomalies
        if len(readings_df) > 0:
            X = readings_df[['value']].fillna(0).values
            anomaly_metrics = self.anomaly_model.train(X)
        else:
            anomaly_metrics = {"error": "No data"}
        
        # Entraîner le modèle RUL
        rul_metrics = self.rul_model.train(readings_df, equipment_df)
        
        # Sauvegarder les modèles
        self.anomaly_model.save()
        self.rul_model.save()
        
        return {
            "anomaly_detection": anomaly_metrics,
            "rul_prediction": rul_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def predict_anomalies(self, readings_data: List[Dict]) -> Dict:
        """Prédire les anomalies"""
        
        if not readings_data:
            return {}
        
        readings_df = pd.DataFrame(readings_data)
        X = readings_df[['value']].fillna(0).values
        
        predictions, scores = self.anomaly_model.predict(X)
        
        results = {}
        for idx, score in enumerate(scores):
            reading = readings_data[idx]
            results[f"{reading['equipment_id']}_{reading['sensor_name']}"] = {
                "anomaly_score": float(score),
                "is_anomaly": bool(predictions[idx] == -1),
                "timestamp": reading['timestamp'].isoformat() if hasattr(reading['timestamp'], 'isoformat') else str(reading['timestamp'])
            }
        
        return results
    
    def predict_rul(self, readings_data: List[Dict]) -> Dict:
        """Prédire le RUL"""
        
        if not readings_data:
            return {}
        
        readings_df = pd.DataFrame(readings_data)
        return self.rul_model.predict(readings_df)
    
    def load_models(self) -> bool:
        """Charger les modèles sauvegardés"""
        
        anomaly_loaded = self.anomaly_model.load()
        rul_loaded = self.rul_model.load()
        
        return anomaly_loaded or rul_loaded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test des modèles
    print("Test des modèles ML...")
    
    # Données de test
    test_readings = [
        {"equipment_id": "TURB-01", "sensor_name": "temperature", "value": 380 + np.random.randn(), "timestamp": datetime.utcnow()}
        for _ in range(100)
    ]
    test_equipment = [
        {"id": "TURB-01", "name": "Turbine 1", "type": "Turbine"}
    ]
    
    manager = MLPipelineManager()
    metrics = manager.train_all_models(test_readings, test_equipment)
    print(f"\nMétriques: {metrics}")
