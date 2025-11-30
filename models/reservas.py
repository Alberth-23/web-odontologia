# models/reservas.py
from datetime import datetime
from extensions.database import db


class Reserva(db.Model):
    __tablename__ = "reservas"

    # bigserial en Postgres → BigInteger en SQLAlchemy
    id = db.Column(db.BigInteger, primary_key=True)

    # Coincidir tamaños con la tabla
    nombre = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(30))  # en la tabla NO es NOT NULL
    servicio = db.Column(db.String(100), nullable=False)

    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)

    mensaje = db.Column(db.Text)

    # En la tabla: NOT NULL DEFAULT 'pendiente'
    estado = db.Column(db.String(20), nullable=False, default="pendiente")

    # timestamptz en Postgres
    creado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,  # también podrías usar server_default=db.func.now()
    )

    def __repr__(self):
        return f"<Reserva {self.id}: {self.nombre} - {self.estado}>"