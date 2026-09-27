"""
Modèles SQLAlchemy pour la base de données PostgreSQL
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, Numeric, Date, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


# =========================
# USER
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="viewer")
    department = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    must_change_password = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_login = Column(DateTime(timezone=True))

    # Maintenance Orders (2 FK => IMPORTANT: foreign_keys obligatoires)
    assigned_orders = relationship(
        "MaintenanceOrder",
        foreign_keys="MaintenanceOrder.assigned_to",
        back_populates="assigned_user"
    )

    created_orders = relationship(
        "MaintenanceOrder",
        foreign_keys="MaintenanceOrder.created_by",
        back_populates="creator"
    )

    # Anomalies
    acknowledged_anomalies = relationship(
        "Anomaly",
        foreign_keys="Anomaly.acknowledged_by",
        back_populates="acknowledged_user"
    )

    # Alerts
    acknowledged_alerts = relationship(
        "Alert",
        foreign_keys="Alert.acknowledged_by",
        back_populates="acknowledged_user"
    )

    # Chat
    chat_history = relationship("ChatHistory", back_populates="user")
    chat_conversations = relationship(
        "ChatConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# =========================
# EQUIPMENT TYPE
# =========================
class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="equipment_type")
    knowledge_base = relationship("KnowledgeBase", back_populates="equipment_type")


# =========================
# EQUIPMENT
# =========================
class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_type_id = Column(UUID(as_uuid=True), ForeignKey("equipment_types.id"))

    equipment_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(String(255))

    manufacturer = Column(String(100))
    model = Column(String(100))
    installation_date = Column(Date)

    nominal_power = Column(String(50))
    description = Column(Text)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    equipment_type = relationship("EquipmentType", back_populates="equipment")

    sensors = relationship("Sensor", back_populates="equipment", cascade="all, delete-orphan")
    maintenance_orders = relationship("MaintenanceOrder", back_populates="equipment")
    alerts = relationship("Alert", back_populates="equipment")
    rul_predictions = relationship("RULPrediction", back_populates="equipment")


# =========================
# SENSOR TYPE
# =========================
class SensorType(Base):
    __tablename__ = "sensor_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    unit = Column(String(50))

    min_value = Column(Numeric(10, 2))
    max_value = Column(Numeric(10, 2))

    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    sensors = relationship("Sensor", back_populates="sensor_type")


# =========================
# SENSOR
# =========================
class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id"))
    sensor_type_id = Column(UUID(as_uuid=True), ForeignKey("sensor_types.id"))

    sensor_code = Column(String(50), unique=True)
    name = Column(String(255))

    unit = Column(String(50))
    min_value = Column(Numeric(15, 4))
    max_value = Column(Numeric(15, 4))

    installation_date = Column(Date)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="sensors")
    sensor_type = relationship("SensorType", back_populates="sensors")

    readings = relationship("SensorReading", back_populates="sensor", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="sensor")


# =========================
# SENSOR READING
# =========================
class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id"))

    value = Column(Numeric(15, 4))
    timestamp = Column(DateTime(timezone=True))

    status = Column(String(20), default="normal")

    sensor = relationship("Sensor", back_populates="readings")


# =========================
# ANOMALY
# =========================
class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id"))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    anomaly_type = Column(String(50))
    anomaly_score = Column(Numeric(5, 4))
    detection_timestamp = Column(DateTime(timezone=True))

    sensor = relationship("Sensor", back_populates="anomalies")

    acknowledged_user = relationship(
        "User",
        foreign_keys=[acknowledged_by],
        back_populates="acknowledged_anomalies"
    )


# =========================
# MAINTENANCE ORDER
# =========================
class MaintenanceOrder(Base):
    __tablename__ = "maintenance_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id"))

    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    order_number = Column(String(50), unique=True)
    title = Column(String(255))
    description = Column(Text)
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="new")

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="maintenance_orders")

    assigned_user = relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_orders"
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_orders"
    )


# =========================
# ALERT
# =========================
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id"))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    title = Column(String(255))
    message = Column(Text)

    alert_type = Column(String(50))
    severity = Column(String(20))
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="alerts")

    acknowledged_user = relationship(
        "User",
        foreign_keys=[acknowledged_by],
        back_populates="acknowledged_alerts"
    )


# =========================
# CHAT HISTORY (MANQUAIT ❗)
# =========================
class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="chat_conversations")
    messages = relationship(
        "ChatHistory",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatHistory.created_at",
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    message = Column(Text)
    response = Column(Text)
    sources_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="chat_history")
    conversation = relationship("ChatConversation", back_populates="messages")


# =========================
# RUL PREDICTION (si utilisé)
# =========================
class RULPrediction(Base):
    __tablename__ = "rul_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id"))

    predicted_rul_hours = Column(Integer)
    prediction_date = Column(DateTime(timezone=True))

    equipment = relationship("Equipment", back_populates="rul_predictions")


# =========================
# KNOWLEDGE BASE (si utilisé)
# =========================
class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    document_title = Column(String(255))
    content = Column(Text)

    equipment_type_id = Column(UUID(as_uuid=True), ForeignKey("equipment_types.id"))

    equipment_type = relationship("EquipmentType", back_populates="knowledge_base")


Index("idx_equipment_active_type", Equipment.is_active, Equipment.equipment_type_id)
Index("idx_sensors_equipment_active", Sensor.equipment_id, Sensor.is_active)
Index("idx_sensor_readings_sensor_timestamp", SensorReading.sensor_id, SensorReading.timestamp.desc())
Index("idx_alerts_status_created", Alert.status, Alert.created_at.desc())
Index("idx_alerts_equipment_status", Alert.equipment_id, Alert.status)
Index("idx_anomalies_ack_timestamp", Anomaly.acknowledged_by, Anomaly.detection_timestamp.desc())
Index("idx_maintenance_orders_created", MaintenanceOrder.created_at.desc())
Index("idx_rul_predictions_equipment_date", RULPrediction.equipment_id, RULPrediction.prediction_date.desc())
