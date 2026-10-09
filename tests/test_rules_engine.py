from src.rules_engine import (
    clasificar_mensaje,
    extraer_monto_deuda,
    extraer_tipo_deuda,
    load_rules,
    tiene_interes_consejero,
)


def test_escalar_por_palabra_de_riesgo():
    decision, razon = clasificar_mensaje("Me llego una demanda por mi tarjeta")
    assert decision == "escalar_humano"
    assert "demanda" in razon


def test_ignorar_por_baja():
    decision, _ = clasificar_mensaje("No me interesa, quitame de esta lista")
    assert decision == "ignorar"


def test_responder_mensaje_normal():
    decision, _ = clasificar_mensaje("Hola, tengo una deuda de tarjeta de credito de 3500000")
    assert decision == "responder"


def test_escalar_por_monto_muy_alto():
    decision, razon = clasificar_mensaje("Debo 900000000 de hipoteca")
    assert decision == "escalar_humano"
    assert "umbral automático" in razon


def test_escalar_por_monto_muy_bajo():
    decision, razon = clasificar_mensaje("Debo 50000 de tarjeta")
    assert decision == "escalar_humano"
    assert "umbral mínimo" in razon


def test_extraer_monto_deuda():
    assert extraer_monto_deuda("tengo una deuda de 3500000 en tarjeta") == 3500000
    assert extraer_monto_deuda("tengo una deuda de 3.500.000 en tarjeta") == 3500000
    assert extraer_monto_deuda("hola, quiero informacion") is None


def test_extraer_tipo_deuda():
    rules = load_rules()
    assert extraer_tipo_deuda("debo de mi tarjeta de credito", rules) == "tarjeta_credito"
    assert extraer_tipo_deuda("debo la hipoteca de la casa", rules) == "hipotecario"
    assert extraer_tipo_deuda("no especifico nada", rules) == "no_especificado"


def test_interes_consejero():
    rules = load_rules()
    assert tiene_interes_consejero("quiero hablar con un consejero", rules) is True
    assert tiene_interes_consejero("solo pregunto algo random", rules) is False
