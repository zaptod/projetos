extends SceneTree
## Verificacao minima das regras sem arte propria da E3.

func _init() -> void:
	var gatilhos = preload("res://nucleo/gatilhos_animacao.gd")
	assert(gatilhos.da_timeline({"tipo": "ko"}) == "ko")
	print("testes do palco: 0 falha(s)")
	quit()
