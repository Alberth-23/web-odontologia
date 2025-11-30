# app.py — Panel de Control Dental — Flask + Supabase/PostgreSQL + Render

import os
import logging
import urllib.parse
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

# ──────────────────────────────────────────────────────────────────────────────
# Cargar .env automáticamente en desarrollo (si python-dotenv está instalado)
# ──────────────────────────────────────────────────────────────────────────────
if os.getenv("FLASK_ENV") != "production":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # En producción o si no está instalada la librería, simplemente se ignora
        pass

from extensions.database import db
from models.reservas import Reserva

# ──────────────────────────────────────────────────────────────────────────────
# Logging básico
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuración de Flask y base de datos
# ──────────────────────────────────────────────────────────────────────────────

required_vars = ["SECRET_KEY", "DATABASE_URL", "ADMIN_PIN"]
missing_vars = [v for v in required_vars if not os.getenv(v)]
if missing_vars:
    raise RuntimeError(
        f"❌ FALTAN variables de entorno: {', '.join(missing_vars)}. "
        "Defínelas en Render (Settings → Environment) o en tu .env local."
    )

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

raw_db_url = os.getenv("DATABASE_URL")

# Normalizar por si viene como postgres:// (Supabase a veces lo hace)
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

ADMIN_PIN = os.getenv("ADMIN_PIN")

# Crear tablas si no existen (no borra nada, solo asegura estructura)
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Tablas creadas o ya existían.")
    except Exception:
        logger.exception("❌ Error al inicializar la base de datos")
        raise

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────

def login_required(view_func):
    """Protege rutas del panel de admin."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def hay_solapamiento(fecha, hora, exclude_id=None):
    """
    Devuelve True si ya existe una reserva en esa fecha y hora
    con estado pendiente/autorizada.
    """
    query = Reserva.query.filter_by(fecha=fecha, hora=hora)
    if exclude_id:
        query = query.filter(Reserva.id != exclude_id)
    return query.filter(
        Reserva.estado.in_(("autorizada", "pendiente"))
    ).first() is not None


def enviar_whatsapp_notificacion(reserva: Reserva) -> None:
    """
    Construye la URL de WhatsApp para notificar al paciente.
    (Solo la deja en logs; no envía el mensaje automáticamente).
    """
    if not reserva.telefono:
        return

    telefono = reserva.telefono.replace(" ", "").replace("-", "")
    # Si es un móvil peruano de 9 dígitos sin prefijo, anteponer 51
    if telefono.startswith("9") and len(telefono) == 9:
        telefono = "51" + telefono

    mensaje = (
        f"✅ ¡Hola {reserva.nombre}! Tu cita en *Clínica Dental* ha sido autorizada.\n\n"
        f"📅 Fecha: {reserva.fecha.strftime('%d/%m/%Y')}\n"
        f"⏰ Hora: {reserva.hora.strftime('%H:%M')}\n"
        f"🦷 Servicio: {reserva.servicio}\n\n"
        f"¡Te esperamos!\n"
        f"📍 Av. Salaverry 1234, Lima"
    )

    url = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"
    logger.info("📲 URL WhatsApp para %s: %s", reserva.nombre, url)

# ──────────────────────────────────────────────────────────────────────────────
# Rutas públicas
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/servicios")
def servicios():
    return render_template("servicios.html")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html")


@app.route("/equipo")
def equipo():
    return render_template("equipo.html")


@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip()
            telefono = request.form["telefono"].strip()
            servicio = request.form["servicio"].strip()
            fecha_str = request.form["fecha"]
            hora_str = request.form["hora"]
            mensaje = request.form.get("mensaje", "").strip()

            # Convertir a tipos reales (Postgres: date, time)
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hora = datetime.strptime(hora_str, "%H:%M").time()

            nueva = Reserva(
                nombre=nombre,
                telefono=telefono,
                servicio=servicio,
                fecha=fecha,
                hora=hora,
                mensaje=mensaje,
            )

            db.session.add(nueva)
            db.session.commit()
            logger.info("✅ Reserva guardada con ID %s", nueva.id)
            return redirect(url_for("reserva_exitosa"))

        except Exception:
            db.session.rollback()
            logger.exception("❌ Error al guardar reserva desde página pública")
            return "Error interno. Inténtelo más tarde.", 500

    return render_template("reservar.html")


@app.route("/reserva_exitosa")
def reserva_exitosa():
    return render_template("reserva_exitosa.html")


@app.route("/health")
def health_check():
    """Comprobación simple para Render (status de la app y DB)."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception as e:
        logger.exception("❌ Error en healthcheck")
        return {"status": "error", "msg": str(e)}, 500

# ──────────────────────────────────────────────────────────────────────────────
# Autenticación
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if pin == ADMIN_PIN:
            session["logged_in"] = True
            flash("✅ Bienvenida al panel de control", "success")
            return redirect(url_for("admin_panel"))
        flash("❌ PIN incorrecto", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ──────────────────────────────────────────────────────────────────────────────
# Panel de control (admin)
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin_panel():
    reservas = (
        Reserva.query
        .order_by(Reserva.fecha.asc(), Reserva.hora.asc())
        .all()
    )
    return render_template("admin_panel.html", reservas=reservas)


@app.route("/admin/autorizar/<int:id>")
@login_required
def autorizar(id):
    r = Reserva.query.get_or_404(id)

    if r.estado != "pendiente":
        flash("⚠️ Solo se pueden autorizar reservas pendientes", "warning")
        return redirect(url_for("admin_panel"))

    if hay_solapamiento(r.fecha, r.hora, exclude_id=r.id):
        flash(f"⚠️ Horario ya ocupado: {r.fecha} {r.hora}", "error")
        return redirect(url_for("admin_panel"))

    r.estado = "autorizada"
    db.session.commit()

    try:
        enviar_whatsapp_notificacion(r)
        flash(f"✅ {r.nombre} autorizado y notificado", "success")
    except Exception:
        logger.exception("❌ Error enviando notificación de WhatsApp")
        flash(f"✅ {r.nombre} autorizado (sin notificación)", "warning")

    return redirect(url_for("admin_panel"))


@app.route("/admin/atender/<int:id>")
@login_required
def atender(id):
    r = Reserva.query.get_or_404(id)

    if r.estado not in ("pendiente", "autorizada"):
        flash(
            "⚠️ Solo se pueden marcar como atendidas "
            "reservas pendientes/autorizadas",
            "warning",
        )
        return redirect(url_for("admin_panel"))

    r.estado = "atendida"
    db.session.commit()
    flash(f"🦷 {r.nombre} marcado como atendido", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/cancelar/<int:id>")
@login_required
def cancelar(id):
    r = Reserva.query.get_or_404(id)
    r.estado = "cancelada"
    db.session.commit()
    flash(f"❌ {r.nombre} cancelado", "warning")
    return redirect(url_for("admin_panel"))


@app.route("/admin/eliminar/<int:id>")
@login_required
def eliminar(id):
    r = Reserva.query.get_or_404(id)
    nombre = r.nombre
    db.session.delete(r)
    db.session.commit()
    flash(f"🗑️ {nombre} eliminado permanentemente", "info")
    return redirect(url_for("admin_panel"))


@app.route("/admin/agregar", methods=["GET", "POST"])
@login_required
def admin_agregar():
    reservas_pasadas = (
        Reserva.query
        .order_by(Reserva.creado_en.desc())
        .limit(20)
        .all()
    )

    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip()
            telefono = request.form["telefono"].strip()
            servicio = request.form["servicio"].strip()
            fecha_str = request.form["fecha"]
            hora_str = request.form["hora"]
            mensaje = request.form.get("mensaje", "").strip()

            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hora = datetime.strptime(hora_str, "%H:%M").time()

            if hay_solapamiento(fecha, hora):
                flash(f"⚠️ Horario ocupado: {fecha} {hora}", "error")
                return render_template(
                    "admin_agregar.html",
                    reservas_pasadas=reservas_pasadas,
                    datos=request.form,
                )

            nueva = Reserva(
                nombre=nombre,
                telefono=telefono,
                servicio=servicio,
                fecha=fecha,
                hora=hora,
                mensaje=mensaje,
                estado="autorizada",
            )
            db.session.add(nueva)
            db.session.commit()
            flash(f"➕ {nombre} agregado exitosamente", "success")
            return redirect(url_for("admin_panel"))

        except Exception:
            db.session.rollback()
            logger.exception("❌ Error al agregar reserva desde panel admin")
            flash("Error al agregar paciente", "error")

    return render_template(
        "admin_agregar.html",
        reservas_pasadas=reservas_pasadas,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Ejecución local (en Render se usa gunicorn app:app)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.getenv("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)