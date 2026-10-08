extends SceneTree

const Tocador := preload("res://nucleo/tocador_folha.gd")
const Gatilhos := preload("res://nucleo/gatilhos_animacao.gd")

func _init() -> void:
	var tocador := Tocador.new()
	assert(tocador.gatilho_animacao == "")
	assert(Gatilhos.da_timeline({"tipo": "acerto"}) == "acerto")
	assert(Gatilhos.da_timeline({"tipo": "ko"}) == "ko")
	assert(Gatilhos.da_timeline({}, {"golpe_fase": 2}) == "golpe_fase")
	assert(Gatilhos.reconhece("ocioso"))
	quit()
