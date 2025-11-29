# app.py — Panel de Control Dental — ✅ Render + PostgreSQL Listo
import os
import logging
from datetime import datetime
import urllib.parse
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash
)
from extensions.database import db
from models.reservas import Reserva

# === 🔐 Configuración segura desde variables de entorno ===
logging.basicConfig(level=logging.INFO)

# Validación estricta: falla si falta algo crítico
required_vars = ["SECRET_KEY", "DATABASE_URL", "ADMIN_PIN"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"❌ FATAL: Variable de entorno '{var}' no definida. Configúrala en Render.")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# === Inicialización ===
db.init_app(app)

# === Seguridad ===
ADMIN_PIN = os.getenv("ADMIN_PIN")  # Ya validado arriba

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# === Funciones auxiliares ===
def hay_solapamiento(fecha, hora, exclude_id=None):
    query = Reserva.query.filter_by(fecha=fecha, hora=hora)
    if exclude_id:
        query = query.filter(Reserva.id != exclude_id)
    return query.filter(
        Reserva.estado.in_(["autorizada", "pendiente"])
    ).first() is not None

def enviar_whatsapp_notificacion(reserva):
    if not reserva.telefono:
        return
    
    telefono = reserva.telefono.replace(' ', '').replace('-', '')
    if telefono.startswith('9') and len(telefono) == 9:
        telefono = '51' + telefono
    
    mensaje = (
        f"✅ ¡Hola {reserva.nombre}! Tu cita en *Clínica Dental* ha sido autorizada.\n\n"
        f"📅 Fecha: {reserva.fecha.strftime('%d/%m/%Y')}\n"
        f"⏰ Hora: {reserva.hora.strftime('%H:%M')}\n"
        f"🦷 Servicio: {reserva.servicio}\n\n"
        f"¡Te esperamos! 🌟\n"
        f"📍 Av. Salaverry 1234, Lima"
    )
    
    url = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"
    logging.info(f"📲 WhatsApp para {reserva.nombre}: {url}")

# === Crear tablas al iniciar ===
with app.app_context():
    try:
        db.create_all()
        logging.info("✅ Tablas creadas o ya existen.")
    except Exception as e:
        logging.error(f"❌ Error al inicializar DB: {e}")
        raise

# === Rutas públicas ===
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
            fecha = request.form["fecha"]
            hora = request.form["hora"]
            mensaje = request.form.get("mensaje", "").strip()

            nueva = Reserva(
                nombre=nombre,
                telefono=telefono,
                servicio=servicio,
                fecha=fecha,
                hora=hora,
                mensaje=mensaje
            )

            db.session.add(nueva)
            db.session.commit()
            logging.info(f"✅ Reserva guardada: ID {nueva.id}")
            return redirect(url_for("reserva_exitosa"))

        except Exception as e:
            db.session.rollback()
            logging.error(f"❌ Error al guardar: {e}")
            return "Error interno. Inténtelo más tarde.", 500

    return render_template("reservar.html")

@app.route("/reserva_exitosa")
def reserva_exitosa():
    return render_template("reserva_exitosa.html")

@app.route("/health")
def health_check():
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "msg": str(e)}, 500

# === Autenticación ===
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if pin == ADMIN_PIN:
            session["logged_in"] = True
            flash("✅ Bienvenida al panel de control", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("❌ PIN incorrecto", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# === Panel de control ===
@app.route("/admin")
@login_required
def admin_panel():
    reservas = Reserva.query.order_by(
        Reserva.fecha.asc(),
        Reserva.hora.asc()
    ).all()
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
    except Exception as e:
        logging.error(f"❌ Error notificación: {e}")
        flash(f"✅ {r.nombre} autorizado (sin notificación)", "warning")
    
    return redirect(url_for("admin_panel"))

@app.route("/admin/atender/<int:id>")
@login_required
def atender(id):
    r = Reserva.query.get_or_404(id)
    if r.estado not in ["pendiente", "autorizada"]:
        flash("⚠️ Solo se pueden marcar como atendidas reservas pendientes/autorizadas", "warning")
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
    reservas_pasadas = Reserva.query.order_by(
        Reserva.creado_en.desc()
    ).limit(20).all()
    
    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip()
            telefono = request.form["telefono"].strip()
            servicio = request.form["servicio"].strip()
            fecha = request.form["fecha"]
            hora = request.form["hora"]
            mensaje = request.form.get("mensaje", "").strip()

            if hay_solapamiento(fecha, hora):
                flash(f"⚠️ Horario ocupado: {fecha} {hora}", "error")
                return render_template(
                    "admin_agregar.html", 
                    reservas_pasadas=reservas_pasadas,
                    datos=request.form
                )

            nueva = Reserva(
                nombre=nombre,
                telefono=telefono,
                servicio=servicio,
                fecha=fecha,
                hora=hora,
                mensaje=mensaje,
                estado="autorizada"
            )
            db.session.add(nueva)
            db.session.commit()
            flash(f"➕ {nombre} agregado exitosamente", "success")
            return redirect(url_for("admin_panel"))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"❌ Error al agregar: {e}")
            flash("Error al agregar paciente", "error")

    return render_template("admin_agregar.html", reservas_pasadas=reservas_pasadas)

# === Ejecución ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)