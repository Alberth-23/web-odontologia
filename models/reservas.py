# models/reservas.py
from extensions.database import db
from datetime import datetime

class Reserva(db.Model):
    __tablename__ = "reservas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    servicio = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    mensaje = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ✅ NUEVOS CAMPOS PARA PANEL DE CONTROL
    estado = db.Column(db.String(20), default="pendiente")  # pendiente, autorizada, atendida, cancelada
    notas_internas = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Reserva {self.id}: {self.nombre} - {self.estado}>"