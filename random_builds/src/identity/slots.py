"""Os tres artefatos de recompensa de uma geracao (secoes 4, 6 e 7).

    character           o personagem sozinho      IMAGEM  (PicassoIA)
    weapon              a arma sozinha            IMAGEM  (PicassoIA)
    character_weapon    os dois juntos            VIDEO   (Digen)

Por que dois viraram imagem: pedir tres videos e caro, lento e - o pior -
INCONSISTENTE. Em generation_00020 o mesmo personagem saiu de cabelo branco no
clipe dele e de cabelo preto no payoff, com os mesmos campos de identidade nos
dois prompts. Gerar o personagem UMA vez, como imagem, e mandar essa imagem
para o video resolve a inconsistencia na raiz e troca duas geracoes de video
por duas de imagem.

As imagens tem uso DUPLO: sao a referencia visual do video do Digen e sao o
conteudo das duas revelacoes do video da roleta (animadas, nunca paradas).

Os SLOTS nao mudaram de nome nem de quantidade de proposito: a fila, o status,
o edit_plan e os testes ja falam essa lingua. O que mudou foi a MIDIA e o
PROVEDOR de cada um.
"""
from __future__ import annotations

DREAMFACE = "dreamface"

CHARACTER = "character"
WEAPON = "weapon"
CHARACTER_WEAPON = "character_weapon"

# Passo INTERMEDIARIO, nao e cena: o Editor Pro do PicassoIA recebe as duas
# imagens e devolve UMA com o personagem segurando a arma. E ela que vai ao
# Digen como referencia do video — o composer de la aceita um arquivo so, e
# assim esse arquivo carrega as duas identidades ja compostas.
REFERENCIA = "character_weapon_ref"

# A ordem e a ordem do video: personagem, arma, os dois juntos.
SLOTS = (CHARACTER, WEAPON, CHARACTER_WEAPON)

# O que a FILA pode conter. Maior que SLOTS de proposito: a referencia e
# trabalho, mas nao e cena. Quem monta a timeline continua iterando SLOTS.
JOBS = (CHARACTER, WEAPON, REFERENCIA, CHARACTER_WEAPON)

IMAGEM, VIDEO = "imagem", "video"

# O que se PEDE ao provedor. Quem esta na tela e decidido pelo arquivo que
# existe no disco (uma geracao antiga tem mp4 no slot de personagem), nunca
# por esta tabela — ver `midia_do_arquivo`.
MIDIA = {CHARACTER: IMAGEM, WEAPON: IMAGEM, REFERENCIA: IMAGEM,
         CHARACTER_WEAPON: VIDEO}

PICASSO, DIGEN = "picasso", "digen"
PROVEDOR = {CHARACTER: PICASSO, WEAPON: PICASSO, REFERENCIA: PICASSO,
            CHARACTER_WEAPON: DIGEN}

# O payoff so pode ser gerado depois das duas imagens: sao elas que vao
# anexadas como referencia. Sem elas ele ainda sai, mas so com texto — e ai
# volta a ser o personagem sorteado de novo, que e o problema que a imagem
# veio resolver.
DEPENDE_DE = {
    REFERENCIA: (CHARACTER, WEAPON),
    # O payoff espera a REFERENCIA, nao as duas imagens: e ela que ele anexa.
    # Se ela falhar de vez, a dependencia conta como satisfeita e o video sai
    # so com texto — degradar e obrigatorio, travar nao.
    CHARACTER_WEAPON: (REFERENCIA,),
}

# Nomes canonicos dos entregaveis (secao 18). Ficam na raiz da geracao porque
# sao produto da build, nao arquivo interno.
ARQUIVO = {
    CHARACTER: "character_image.png",
    WEAPON: "weapon_image.png",
    REFERENCIA: "character_weapon_reference.png",
    CHARACTER_WEAPON: "character_weapon_video.mp4",
}

# Onde procurar o artefato de cada slot, em ordem: o nome canonico, as outras
# extensoes que o provedor pode entregar, e por ULTIMO os nomes .mp4 do formato
# anterior. Terminar em mp4 e o que faz uma geracao JA FEITA continuar sendo
# tratada como video e continuar tendo revelacao — sem isso toda build
# anterior a esta mudanca apareceria como "faltando" no status.
CANDIDATOS = {
    CHARACTER: ("character_image.png", "character_image.jpg",
                "character_image.webp", "character_video.mp4",
                "identity/digen.mp4"),
    WEAPON: ("weapon_image.png", "weapon_image.jpg", "weapon_image.webp",
             "weapon_video.mp4"),
    REFERENCIA: ("character_weapon_reference.png",),
    CHARACTER_WEAPON: ("character_weapon_video.mp4",),
}

EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".webp")
EXTENSOES_VIDEO = (".mp4", ".mov", ".webm", ".mkv")

SEPARADOR = "#"


def valido(slot: str) -> str:
    """Aceita qualquer JOB, nao so os tres de timeline."""
    if slot not in JOBS:
        raise ValueError(f"slot desconhecido: {slot!r} (esperado: {', '.join(JOBS)})")
    return slot


def job_id(generation_id: str, slot: str) -> str:
    return f"{generation_id}{SEPARADOR}{valido(slot)}"


def partes(job_id: str) -> tuple[str, str]:
    """`job_id` -> (generation_id, slot).

    Sem separador e job do formato antigo: um clipe so, que era o do
    personagem.
    """
    if SEPARADOR not in job_id:
        return job_id, CHARACTER
    generation_id, _, slot = job_id.partition(SEPARADOR)
    return generation_id, valido(slot)


def provedor(slot: str) -> str:
    return PROVEDOR[valido(slot)]


def midia(slot: str) -> str:
    return MIDIA[valido(slot)]


def depende_de(slot: str) -> tuple[str, ...]:
    return DEPENDE_DE.get(valido(slot), ())


def nomes_aceitos(slot: str) -> tuple[str, ...]:
    """Nome canonico primeiro, formatos anteriores depois."""
    return CANDIDATOS[valido(slot)]


def rotulo(slot: str) -> str:
    return {CHARACTER: "personagem", WEAPON: "arma",
            REFERENCIA: "personagem com a arma (imagem)",
            CHARACTER_WEAPON: "personagem + arma (video)"}[valido(slot)]
