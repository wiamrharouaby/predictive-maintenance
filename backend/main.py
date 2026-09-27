"""
API FastAPI principale pour le système de maintenance prédictive
"""
import os
import logging
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta

from backend.database import get_db, test_connection, init_db
from backend.models import (
    User, Equipment, Sensor, SensorReading, Anomaly,
    Alert, MaintenanceOrder, RULPrediction
)
from backend.auth import (
    authenticate_user, 
    create_user_token,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    get_current_user,
    CurrentUser,
    decode_token
)
from backend.auto_alerts import (
    start_auto_alert_scheduler, stop_auto_alert_scheduler, run_auto_alert_cycle
)

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cors_origins():
    """Lire les origines CORS depuis l'environnement."""
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

# Créer l'app FastAPI
app = FastAPI(
    title="PFE Maintenance Prédictive API",
    description="API pour système de maintenance prédictive ONEE",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# DÉPENDANCES
# ============================================================

def get_token_from_header(authorization: str = Header(None)) -> str:
    """Extraire le token du header Authorization"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format de token invalide"
        )
    
    return parts[1]

async def get_current_user_dependency(
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> CurrentUser:
    """Dépendance pour obtenir l'utilisateur actuel"""
    current_user = get_current_user(token, db)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré"
        )
    return current_user

# ============================================================
# ENDPOINTS: AUTHENTIFICATION
# ============================================================

@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """Authentifier un utilisateur et retourner un token"""
    user = authenticate_user(db, request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )
    
    return create_user_token(user)

@app.get("/auth/me", response_model=UserResponse)
def get_me(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Obtenir les informations de l'utilisateur actuel"""
    user = db.query(User).filter(User.id == current_user.id).first()
    return user

@app.post("/auth/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Rafraîchir le token d'accès"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return create_user_token(user)

# ============================================================
# ENDPOINTS: HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    """Vérifier l'état de l'API"""
    return {
        "status": "ok",
        "database": "connected" if test_connection() else "disconnected"
    }

@app.get("/api/info")
def api_info():
    """Informations sur l'API"""
    return {
        "name": "PFE Maintenance Prédictive API",
        "version": "1.0.0",
        "description": "Système de maintenance prédictive pour ONEE",
        "endpoints": {
            "auth": ["/auth/login", "/auth/me", "/auth/refresh"],
            "equipment": ["/api/equipment"],
            "sensors": ["/api/sensors"],
            "readings": ["/api/readings"],
            "anomalies": ["/api/anomalies"],
            "predictions": ["/api/predictions"],
            "maintenance": ["/api/maintenance"]
        }
    }

# ============================================================
# ENDPOINTS PLACEHOLDER (à implémenter dans Phase 2)
# ============================================================

@app.get("/api/equipment")
def get_equipment(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer tous les équipements"""
    equipment = (
        db.query(Equipment)
        .options(joinedload(Equipment.equipment_type))
        .filter(Equipment.is_active.is_(True))
        .all()
    )
    return [
        {
            "id": str(item.id),
            "code": item.equipment_code,
            "name": item.name,
            "type": item.equipment_type.name if item.equipment_type else None,
            "location": item.location,
            "manufacturer": item.manufacturer,
            "model": item.model,
            "nominal_power": item.nominal_power,
        }
        for item in equipment
    ]

@app.get("/api/sensors")
def get_sensors(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer tous les capteurs"""
    sensors = (
        db.query(Sensor)
        .options(joinedload(Sensor.equipment))
        .filter(Sensor.is_active.is_(True))
        .all()
    )
    return [
        {
            "id": str(sensor.id),
            "equipment_id": str(sensor.equipment_id),
            "equipment_code": sensor.equipment.equipment_code if sensor.equipment else None,
            "code": sensor.sensor_code,
            "name": sensor.name,
            "unit": sensor.unit,
            "min_value": float(sensor.min_value) if sensor.min_value is not None else None,
            "max_value": float(sensor.max_value) if sensor.max_value is not None else None,
        }
        for sensor in sensors
    ]

@app.get("/api/readings")
def get_readings(
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer les lectures des capteurs"""
    limit = min(max(limit, 1), 1000)
    readings = (
        db.query(SensorReading)
        .options(joinedload(SensorReading.sensor).joinedload(Sensor.equipment))
        .order_by(SensorReading.timestamp.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(reading.id),
            "sensor_id": str(reading.sensor_id),
            "sensor": reading.sensor.name if reading.sensor else None,
            "equipment": reading.sensor.equipment.equipment_code if reading.sensor and reading.sensor.equipment else None,
            "value": float(reading.value) if reading.value is not None else None,
            "timestamp": reading.timestamp.isoformat() if reading.timestamp else None,
            "status": reading.status,
        }
        for reading in readings
    ]

@app.get("/api/anomalies")
def get_anomalies(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer les anomalies détectées"""
    anomalies = (
        db.query(Anomaly)
        .options(joinedload(Anomaly.sensor).joinedload(Sensor.equipment))
        .order_by(Anomaly.detection_timestamp.desc().nullslast())
        .limit(100)
        .all()
    )
    return [
        {
            "id": str(anomaly.id),
            "sensor": anomaly.sensor.name if anomaly.sensor else None,
            "equipment": anomaly.sensor.equipment.equipment_code if anomaly.sensor and anomaly.sensor.equipment else None,
            "type": anomaly.anomaly_type,
            "score": float(anomaly.anomaly_score) if anomaly.anomaly_score is not None else None,
            "timestamp": anomaly.detection_timestamp.isoformat() if anomaly.detection_timestamp else None,
        }
        for anomaly in anomalies
    ]

@app.get("/api/predictions")
def get_predictions(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer les prédictions RUL"""
    predictions = (
        db.query(RULPrediction)
        .options(joinedload(RULPrediction.equipment))
        .order_by(RULPrediction.prediction_date.desc().nullslast())
        .limit(1000)
        .all()
    )
    return [
        {
            "id": str(prediction.id),
            "equipment_id": str(prediction.equipment_id),
            "equipment": prediction.equipment.equipment_code if prediction.equipment else None,
            "rul_hours": prediction.predicted_rul_hours,
            "prediction_date": prediction.prediction_date.isoformat() if prediction.prediction_date else None,
        }
        for prediction in predictions
    ]

@app.get("/api/maintenance")
def get_maintenance_orders(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer les ordres de maintenance"""
    orders = (
        db.query(MaintenanceOrder)
        .options(
            joinedload(MaintenanceOrder.equipment),
            joinedload(MaintenanceOrder.assigned_user),
            joinedload(MaintenanceOrder.creator),
        )
        .order_by(MaintenanceOrder.created_at.desc().nullslast())
        .limit(1000)
        .all()
    )
    return [
        {
            "id": str(order.id),
            "order_number": order.order_number,
            "title": order.title,
            "equipment": order.equipment.equipment_code if order.equipment else None,
            "assigned_to": order.assigned_user.username if order.assigned_user else None,
            "created_by": order.creator.username if order.creator else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order in orders
    ]

@app.get("/api/alerts")
def get_alerts(
    status_filter: str = "active",
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Récupérer les alertes."""
    query = db.query(Alert)
    if status_filter != "all":
        query = query.filter(Alert.status == status_filter)
    alerts = (
        query.options(joinedload(Alert.equipment))
        .order_by(Alert.created_at.desc().nullslast())
        .limit(100)
        .all()
    )
    return [
        {
            "id": str(alert.id),
            "equipment": alert.equipment.equipment_code if alert.equipment else None,
            "title": alert.title,
            "message": alert.message,
            "type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }
        for alert in alerts
    ]

@app.post("/api/alerts/run-cycle")
def run_alert_cycle_endpoint(
    current_user: CurrentUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Déclencher manuellement un cycle d'auto-alertes."""
    if current_user.role not in {"admin", "engineer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    return run_auto_alert_cycle(db=db)

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# ============================================================
# STARTUP & SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():
    """Initialisation au démarrage"""
    logger.info("Démarrage de l'API...")
    init_db()
    logger.info("✓ Base de données initialisée")
    if test_connection():
        logger.info("✓ Base de données connectée")
    else:
        logger.error("✗ Impossible de se connecter à la base de données")

    start_auto_alert_scheduler()

@app.on_event("shutdown")
async def shutdown():
    stop_auto_alert_scheduler()
    """Nettoyage à l'arrêt"""
    logger.info("Arrêt de l'API...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
