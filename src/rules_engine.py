"""Motor de reglas: clasifica mensajes entrantes usando rules/rules.yaml.

Las reglas se leen del archivo en cada llamada (hot-reload) para que se
puedan editar sin reiniciar el servidor ni tocar código.
"""
import re
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


def load_rules():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _contains_any(text, keywords):
    text_lower = text.lower()
    return next((kw for kw in keywords if kw.lower() in text_lower), None)


def extraer_monto_deuda(mensaje):
    """Busca el primer número con pinta de monto de dinero en el mensaje."""
    match = re.search(r"\d{1,3}(?:[.,]\d{3})+|\d{5,9}", mensaje)
    if not match:
        return None
    numero = match.group(0).replace(".", "").replace(",", "")
    try:
        return int(numero)
    except ValueError:
        return None


def extraer_tipo_deuda(mensaje, rules):
    mensaje_lower = mensaje.lower()
    for tipo, keywords in rules.get("palabras_tipo_deuda", {}).items():
        if any(kw in mensaje_lower for kw in keywords):
            return tipo
    return "no_especificado"


def tiene_interes_consejero(mensaje, rules):
    return _contains_any(mensaje, rules.get("consejero_interes_keywords", [])) is not None


def clasificar_mensaje(mensaje, rules=None):
    """Devuelve (decision, razon).

    decision in {"responder", "ignorar", "escalar_humano"}.
    El orden de evaluación es intencional: riesgo primero, salida después,
    umbrales de monto al final.
    """
    rules = rules or load_rules()

    kw_escalar = _contains_any(mensaje, rules.get("escalar_keywords", []))
    if kw_escalar:
        return "escalar_humano", f"Palabra de riesgo/ambigüedad detectada: '{kw_escalar}'"

    kw_ignorar = _contains_any(mensaje, rules.get("ignorar_keywords", []))
    if kw_ignorar:
        return "ignorar", f"Palabra de salida/no-interés detectada: '{kw_ignorar}'"

    monto = extraer_monto_deuda(mensaje)
    deuda_cfg = rules.get("deuda", {})
    if monto is not None:
        if monto < deuda_cfg.get("monto_minimo", 0):
            return "escalar_humano", f"Monto de deuda ({monto}) por debajo del umbral mínimo"
        if monto > deuda_cfg.get("monto_maximo_auto", float("inf")):
            return "escalar_humano", f"Monto de deuda ({monto}) por encima del umbral automático"

    return "responder", "Mensaje dentro de lo normal"
