class_name GatilhosAnimacao
extends RefCounted
## Traducao unica entre os eventos que a timeline conhece e o contrato do Atelie.

## O catalogo usa o vocabulario cru da timeline. Nao ha traducao paralela.
const GATILHOS := ["acerto", "adrenalina", "agarrado", "agarrao", "agarrao_desfecho", "area", "arma_puxada", "atacando", "aterrissagem", "atordoado", "beam", "bloqueando", "bloqueio", "bola_x", "buff", "canal", "canalizando", "choque", "combo", "congelado", "corrida", "cura", "dano", "dash", "desvio", "dormindo", "escudo_quebrou", "esquiva", "explosao", "expr", "golpe_fase", "hitstop", "intangivel", "invencivel", "knockback", "ko", "lancado", "morto", "movimento", "no_ar", "obstaculo", "ocioso", "oculto", "orbe", "parede", "parry", "poeira", "portal", "primeiro_sangue", "projetil", "projetil_arma", "projetil_fim", "pulo", "recuperacao", "skill", "status", "summon", "super_armor", "tempo_parado", "transformacao", "transformado", "trap", "wall_splat"]


static func da_timeline(evento: Dictionary, amostra: Dictionary = {}) -> String:
	var tipo := str(evento.get("tipo", ""))
	if tipo == "movimento":
		return str(evento.get("gatilho", "ocioso"))
	if int(amostra.get("golpe_fase", 0)) > 0:
		return "golpe_fase"
	return tipo if tipo in GATILHOS else "ocioso"


static func reconhece(gatilho: String) -> bool:
	return gatilho in GATILHOS
