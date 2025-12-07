import os
from datetime import datetime, date, time
from types import SimpleNamespace
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy

# ==============================
# CARGA DE VARIABLES DE ENTORNO
# ==============================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Si no está python-dotenv, simplemente se ignora y se usan
    # las variables de entorno del sistema.
    pass

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-unsafe"  # solo para desarrollo si olvidas ponerla
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///odontologia_dev.db"
)
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")

# ==============================
# INICIALIZACIÓN DE FLASK
# ==============================
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ==============================
# MODELOS
# ==============================
class Reserva(db.Model):
    __tablename__ = "reservas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(50), nullable=False)
    servicio = db.Column(db.String(120), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    mensaje = db.Column(db.Text, default="")
    estado = db.Column(db.String(20), default="pendiente")  # pendiente, autorizada, atendida, cancelada
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==============================
# HELPERS
# ==============================
def admin_required(view_func):
    """Protege rutas solo para staff logueado."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Debes iniciar sesión para acceder al panel.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_year():
    """Añade 'year' a todos los templates."""
    return {"year": datetime.utcnow().year}


# ==============================
# RUTAS PÚBLICAS
# ==============================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/servicios")
def servicios():
    return render_template("servicios.html")


@app.route("/equipo")
def equipo():
    return render_template("equipo.html")


@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    if request.method == "POST":
        form = request.form

        nombre = form.get("nombre", "").strip()
        correo = form.get("correo", "").strip()
        telefono = form.get("telefono", "").strip()
        servicio = form.get("servicio", "").strip()
        fecha_str = form.get("fecha", "").strip()
        hora_str = form.get("hora", "").strip()
        mensaje = form.get("mensaje", "").strip()

        # Validación básica
        if not (nombre and correo and telefono and servicio and fecha_str and hora_str):
            # Si el POST viene del fetch, basta devolver 400
            return "Faltan datos", 400

        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hora_obj = datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            return "Fecha u hora inválidas", 400

        # Crear reserva pendiente
        reserva = Reserva(
            nombre=nombre,
            correo=correo,
            telefono=telefono,
            servicio=servicio,
            fecha=fecha_obj,
            hora=hora_obj,
            mensaje=mensaje,
            estado="pendiente",
        )
        db.session.add(reserva)
        db.session.commit()

        # El JS en reservar.html usa fetch y luego redirige a /reserva_exitosa si response.ok
        return "OK", 200

    # GET
    return render_template("reservar.html")


@app.route("/reserva_exitosa")
def reserva_exitosa():
    return render_template("reserva_exitosa.html")


@app.route("/contacto", methods=["GET", "POST"])
def contacto():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip()
        telefono = request.form.get("telefono", "").strip()
        asunto = request.form.get("asunto", "").strip()
        mensaje = request.form.get("mensaje", "").strip()

        # Aquí podrías enviar correo, guardar en DB, etc.
        # Por ahora solo mostramos un mensaje.
        if nombre and correo and mensaje:
            flash("Mensaje enviado correctamente. Te contactaremos pronto.", "success")
        else:
            flash("Por favor completa al menos nombre, correo y mensaje.", "error")

        return redirect(url_for("contacto"))

    return render_template("contacto.html")


# ==============================
# LOGIN STAFF
# ==============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if pin == ADMIN_PIN:
            session["is_admin"] = True
            flash("Acceso concedido al panel de control.", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("PIN incorrecto.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("index"))


# ==============================
# PANEL ADMIN
# ==============================
@app.route("/admin")
@app.route("/admin_panel")
@admin_required
def admin_panel():
    reservas = Reserva.query.order_by(Reserva.fecha.asc(), Reserva.hora.asc()).all()
    return render_template("admin_panel.html", reservas=reservas)


@app.route("/admin/agregar", methods=["GET", "POST"])
@admin_required
def admin_agregar():
    reservas_pasadas = (
        Reserva.query.order_by(Reserva.created_at.desc()).limit(20).all()
    )

    if request.method == "POST":
        form = request.form
        nombre = form.get("nombre", "").strip()
        telefono = form.get("telefono", "").strip()
        servicio = form.get("servicio", "").strip()
        fecha_str = form.get("fecha", "").strip()
        hora_str = form.get("hora", "").strip()
        mensaje = form.get("mensaje", "").strip()

        # Para repoblar el formulario en caso de error
        datos = SimpleNamespace(
            nombre=nombre,
            telefono=telefono,
            servicio=servicio,
            fecha=fecha_str,
            hora=hora_str,
            mensaje=mensaje,
        )

        # Validación básica
        if not (nombre and telefono and servicio and fecha_str and hora_str):
            flash("Por favor completa todos los campos obligatorios.", "error")
            return render_template(
                "admin_agregar.html",
                reservas_pasadas=reservas_pasadas,
                datos=datos,
            )

        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hora_obj = datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            flash("Fecha u hora inválidas.", "error")
            return render_template(
                "admin_agregar.html",
                reservas_pasadas=reservas_pasadas,
                datos=datos,
            )

        # Verificar colisión de horario (no canceladas)
        choque = Reserva.query.filter_by(fecha=fecha_obj, hora=hora_obj).filter(
            Reserva.estado != "cancelada"
        ).first()

        if choque:
            flash(
                f"El horario {fecha_str} {hora_str} ya está ocupado por {choque.nombre}.",
                "error",
            )
            return render_template(
                "admin_agregar.html",
                reservas_pasadas=reservas_pasadas,
                datos=datos,
            )

        # Crear reserva ya autorizada
        reserva = Reserva(
            nombre=nombre,
            correo="",  # si la cita es telefónica, puede ir vacío
            telefono=telefono,
            servicio=servicio,
            fecha=fecha_obj,
            hora=hora_obj,
            mensaje=mensaje,
            estado="autorizada",
        )
        db.session.add(reserva)
        db.session.commit()

        flash("Paciente registrado y cita autorizada correctamente.", "success")
        return redirect(url_for("admin_panel"))

    # GET
    return render_template(
        "admin_agregar.html",
        reservas_pasadas=reservas_pasadas,
        datos=None,
    )


# ==============================
# ACCIONES SOBRE RESERVAS
# ==============================
@app.route("/autorizar/<int:id>")
@admin_required
def autorizar(id):
    reserva = Reserva.query.get_or_404(id)
    reserva.estado = "autorizada"
    db.session.commit()
    flash(f"Cita de {reserva.nombre} autorizada.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/atender/<int:id>")
@admin_required
def atender(id):
    reserva = Reserva.query.get_or_404(id)
    reserva.estado = "atendida"
    db.session.commit()
    flash(f"Cita de {reserva.nombre} marcada como atendida.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/cancelar/<int:id>")
@admin_required
def cancelar(id):
    reserva = Reserva.query.get_or_404(id)
    reserva.estado = "cancelada"
    db.session.commit()
    flash(f"Cita de {reserva.nombre} cancelada.", "warning")
    return redirect(url_for("admin_panel"))


@app.route("/eliminar/<int:id>")
@admin_required
def eliminar(id):
    reserva = Reserva.query.get_or_404(id)
    db.session.delete(reserva)
    db.session.commit()
    flash(f"Registro de {reserva.nombre} eliminado permanentemente.", "danger")
    return redirect(url_for("admin_panel"))


# ==============================
# CLI / MAIN
# ==============================
if __name__ == "__main__":
    # Crear tablas si no existen (solo desarrollo)
    with app.app_context():
        db.create_all()
    app.run(debug=True)