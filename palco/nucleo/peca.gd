class_name PecaPalco
extends Node2D
## Base (opcional) das pecas da biblioteca.
##
## O palco instancia a cena da peca e, SE o script tiver estes metodos, chama:
##   configurar(dados, ctx)   uma vez, com o cabecalho (lutador, arma, objeto...)
##   atualizar(amostra, ctx)  a cada quadro, com os canais da timeline no quadro
##   evento(tipo, dados, ctx) quando um evento da luta cai nesta peca
##
## Uma peca SEM script tambem funciona (uma imagem, uma animacao): o palco poe
## posicao, rotacao e escala e procura um AnimationPlayer chamado "Anim". O
## contrato completo de cada categoria esta em docs/palco/COMO-EDITAR.md.
##
## `ctx` (Dictionary) traz: estilo (EstiloPalco), quadro, fps, t_jogo (s de
## jogo, congela no hitstop), dt_mundo (s de jogo andados desde o quadro
## anterior; 0 no corte e no hitstop), zoom (px de tela por px do mundo),
## px_por_m, palco (o no do palco), timeline e passo (o passo FRACIONARIO
## da timeline que este quadro mostra: a peca sem estado le dali para tras).

## Raio (px) com que a peca foi DESENHADA. O palco escala a peca para o raio
## real: um lutador com raio_ref 100 e raio 0,93 m aparece com escala 0,93.
@export var raio_ref: float = 100.0
## Comprimento (px) empunhadura -> ponta com que a ARMA foi desenhada, ao
## longo de +x. O palco escala para o comprimento honesto da hitbox.
@export var comprimento_ref: float = 100.0


func configurar(_dados: Dictionary, _ctx: Dictionary) -> void:
	pass


## Ponto no MUNDO (px, o mesmo espaco das posicoes que o palco atribui) ->
## coordenada local desta peca. Use isto, e nao to_local(): to_local fala em
## coordenadas de tela, que mudam com a camera.
func do_mundo(p: Vector2) -> Vector2:
	return (p - position).rotated(-rotation) / scale


func atualizar(_amostra: Dictionary, _ctx: Dictionary) -> void:
	pass


func evento(_tipo: String, _dados: Dictionary, _ctx: Dictionary) -> void:
	pass
