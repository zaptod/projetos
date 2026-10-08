class_name GatilhosAnimacao
extends RefCounted
## Traducao unica entre os eventos que a timeline conhece e o contrato do Atelie.

const POR_EVENTO := {
	"acerto": "acerto_recebido", "dano": "acerto_recebido", "ko": "ko",
	"skill": "golpe", "cura": "vida_baixa", "bloqueio": "acerto_recebido",
	"parry": "acerto_recebido", "esquiva": "golpe", "dash": "golpe",
}


static func da_timeline(evento: Dictionary, amostra: Dictionary = {}) -> String:
	var tipo := str(evento.get("tipo", ""))
	if tipo == "movimento":
		return str(evento.get("gatilho", "ocioso"))
	if POR_EVENTO.has(tipo):
		return POR_EVENTO[tipo]
	if int(amostra.get("golpe_fase", 0)) > 0:
		return "golpe"
	if float(amostra.get("hp", 1.0)) <= 0.25:
		return "vida_baixa"
	return "ocioso"
