"""
Generation automatique des alertes de maintenance predictive.

Le worker combine deux sources:
- modele ML Isolation Forest quand un modele entraine est disponible;
- regles de seuils capteur en fallback, pour rester operationnel en demo.
"""
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.database import SessionLocal
from backend.ml_models import MLPipelineManager
from backend.models import Alert, Equipment, Sensor, SensorReading

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover - dependance optionnelle au runtime
    BackgroundScheduler = None


DEFAULT_INTERVAL_MINUTES = int(os.getenv("AUTO_ALERT_INTERVAL_MINUTES", "5"))
DEFAULT_LOOKBACK_MINUTES = int(os.getenv("AUTO_ALERT_LOOKBACK_MINUTES", "30"))

_scheduler = None
_ml_manager: Optional[MLPipelineManager] = None


def start_auto_alert_scheduler(interval_minutes: int = DEFAULT_INTERVAL_MINUTES):
    """Demarre APScheduler une seule fois et retourne l'instance."""
    global _scheduler

    if os.getenv("AUTO_ALERTS_ENABLED", "true").lower() in {"0", "false", "no"}:
        logger.info("Auto-alertes desactivees par AUTO_ALERTS_ENABLED")
        return None

    if BackgroundScheduler is None:
        logger.warning("APScheduler non installe: scheduler auto-alertes non demarre")
        return None

    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_auto_alert_cycle,
        trigger="interval",
        minutes=interval_minutes,
        id="auto_alert_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.utcnow(),
    )
    _scheduler.start()
    logger.info("Scheduler auto-alertes demarre: intervalle=%s min", interval_minutes)
    return _scheduler


def stop_auto_alert_scheduler() -> None:
    """Arrete le scheduler si actif."""
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler auto-alertes arrete")
    _scheduler = None


def run_auto_alert_cycle(
    db: Optional[Session] = None,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
) -> Dict[str, int]:
    """Execute une detection et cree les alertes manquantes."""
    owns_session = db is None
    db = db or SessionLocal()

    try:
        readings = _get_latest_readings(db, lookback_minutes=lookback_minutes)
        ml_predictions = _predict_with_ml(readings)

        created = 0
        skipped_duplicates = 0
        evaluated = 0

        for item in readings:
            evaluated += 1
            rule_event = _evaluate_thresholds(item)
            ml_event = _evaluate_ml_prediction(item, ml_predictions)
            event = _pick_strongest_event(rule_event, ml_event)

            if not event:
                continue

            if _has_open_duplicate(db, item["equipment"].id, event["alert_type"], item["sensor"].id):
                skipped_duplicates += 1
                continue

            db.add(_build_alert(item, event))
            created += 1

        db.commit()

        result = {
            "evaluated_readings": evaluated,
            "created_alerts": created,
            "skipped_duplicates": skipped_duplicates,
        }
        logger.info("Cycle auto-alertes termine: %s", result)
        return result

    except Exception:
        db.rollback()
        logger.exception("Erreur pendant le cycle auto-alertes")
        return {"evaluated_readings": 0, "created_alerts": 0, "skipped_duplicates": 0}
    finally:
        if owns_session:
            db.close()


def _get_latest_readings(db: Session, lookback_minutes: int) -> List[Dict]:
    cutoff = datetime.utcnow() - timedelta(minutes=lookback_minutes)

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
        .subquery()
    )

    rows = (
        db.query(Sensor, SensorReading)
        .join(Equipment, Sensor.equipment_id == Equipment.id)
        .join(ranked_readings, ranked_readings.c.sensor_id == Sensor.id)
        .join(SensorReading, SensorReading.id == ranked_readings.c.reading_id)
        .options(joinedload(Sensor.equipment))
        .filter(
            Sensor.is_active.is_(True),
            Equipment.is_active.is_(True),
            ranked_readings.c.rank == 1,
        )
        .all()
    )

    items = []
    for sensor, reading in rows:
        items.append(
            {
                "sensor": sensor,
                "equipment": sensor.equipment,
                "reading": reading,
                "value": float(reading.value or 0),
                "is_stale": bool(reading.timestamp and reading.timestamp.replace(tzinfo=None) < cutoff),
            }
        )

    return items


def _predict_with_ml(readings: List[Dict]) -> Dict:
    global _ml_manager

    if not readings:
        return {}

    if _ml_manager is None:
        _ml_manager = MLPipelineManager()
        _ml_manager.load_models()

    if not _ml_manager.anomaly_model.is_fitted:
        return {}

    payload = [
        {
            "equipment_id": str(item["equipment"].id),
            "sensor_name": item["sensor"].name or item["sensor"].sensor_code,
            "value": item["value"],
            "timestamp": item["reading"].timestamp or datetime.utcnow(),
        }
        for item in readings
    ]

    try:
        return _ml_manager.predict_anomalies(payload)
    except Exception:
        logger.exception("Prediction ML indisponible pour le cycle auto-alertes")
        return {}


def _evaluate_thresholds(item: Dict) -> Optional[Dict]:
    sensor = item["sensor"]
    value = item["value"]
    min_value = _to_float(sensor.min_value)
    max_value = _to_float(sensor.max_value)

    if min_value is None and max_value is None:
        return None

    deviation_ratio = 0.0
    direction = None
    threshold = None

    if max_value is not None and value > max_value:
        threshold = max_value
        direction = "au-dessus"
        deviation_ratio = (value - max_value) / max(abs(max_value), 1)
    elif min_value is not None and value < min_value:
        threshold = min_value
        direction = "en-dessous"
        deviation_ratio = (min_value - value) / max(abs(min_value), 1)
    else:
        return None

    severity = _severity_from_deviation(deviation_ratio)
    return {
        "alert_type": "threshold",
        "severity": severity,
        "score": min(0.99, max(0.1, deviation_ratio)),
        "title": f"{severity.upper()}: {sensor.name or sensor.sensor_code}",
        "message": (
            f"Lecture {value:.2f} {sensor.unit or ''} {direction} du seuil "
            f"{threshold:.2f} sur {item['equipment'].name}."
        ),
    }


def _evaluate_ml_prediction(item: Dict, predictions: Dict) -> Optional[Dict]:
    key = f"{item['equipment'].id}_{item['sensor'].name or item['sensor'].sensor_code}"
    prediction = predictions.get(key)

    if not prediction or not prediction.get("is_anomaly"):
        return None

    score = float(prediction.get("anomaly_score", 0.0))
    severity = _severity_from_score(score)
    sensor = item["sensor"]

    return {
        "alert_type": "ml_anomaly",
        "severity": severity,
        "score": score,
        "title": f"Anomalie ML {severity}: {sensor.name or sensor.sensor_code}",
        "message": (
            f"Anomalie detectee par le modele sur {item['equipment'].name}. "
            f"Capteur {sensor.name or sensor.sensor_code}: valeur {item['value']:.2f} "
            f"{sensor.unit or ''}, score {score:.2f}."
        ),
    }


def _pick_strongest_event(rule_event: Optional[Dict], ml_event: Optional[Dict]) -> Optional[Dict]:
    if rule_event and ml_event:
        return max([rule_event, ml_event], key=lambda event: _severity_rank(event["severity"]))
    return rule_event or ml_event


def _has_open_duplicate(db: Session, equipment_id, alert_type: str, sensor_id) -> bool:
    fingerprint = f"sensor={sensor_id}"
    return (
        db.query(Alert)
        .filter(
            Alert.equipment_id == equipment_id,
            Alert.alert_type == alert_type,
            Alert.status.in_(["active", "open", "acknowledged"]),
            Alert.message.contains(fingerprint),
        )
        .first()
        is not None
    )


def _build_alert(item: Dict, event: Dict) -> Alert:
    sensor = item["sensor"]
    fingerprint = f"sensor={sensor.id}"
    message = f"{event['message']} [{fingerprint}; score={event['score']:.2f}]"

    return Alert(
        equipment_id=item["equipment"].id,
        title=event["title"],
        message=message,
        alert_type=event["alert_type"],
        severity=event["severity"],
        status="active",
        created_at=datetime.utcnow(),
    )


def _severity_from_deviation(deviation_ratio: float) -> str:
    if deviation_ratio >= 0.20:
        return "critical"
    if deviation_ratio >= 0.10:
        return "high"
    if deviation_ratio >= 0.05:
        return "medium"
    return "low"


def _severity_from_score(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.60:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def _severity_rank(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
