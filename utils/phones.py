# utils/phones.py
import re

def normalizar_telefono_peru(telefono: str) -> str:
    """
    Normaliza un número de teléfono peruano a formato legible internacional (+51).
    
    Ejemplos:
      "947236123"          → "+51 947 236 123"
      "947 236 123"        → "+51 947 236 123"
      "+51947236123"       → "+51 947 236 123"
      "0947236123"         → "+51 947 236 123"
      "51947236123"        → "+51 947 236 123"
    
    Si no es un número válido, devuelve el original limpio.
    """
    if not telefono:
        return ""
    
    # Eliminar todo lo que no sea dígito
    digitos = re.sub(r'\D', '', telefono)
    
    # Caso 1: empieza con 0 y tiene 10 dígitos → quitar 0 inicial
    if digitos.startswith('0') and len(digitos) == 10:
        digitos = digitos[1:]  # → 9 dígitos
    
    # Caso 2: empieza con 51 y tiene 11 dígitos → quitar 51
    if digitos.startswith('51') and len(digitos) == 11:
        digitos = digitos[2:]  # → 9 dígitos
    
    # Ahora debe tener 9 dígitos y empezar con 9 (móvil peruano)
    if len(digitos) == 9 and digitos.startswith('9'):
        return f"+51 {digitos[:3]} {digitos[3:6]} {digitos[6:]}"
    
    # Si no cumple, devolver los dígitos limpios (o cadena vacía)
    return digitos if digitos else telefono.strip()