import pygame
import math
import random
import os
import tempfile
import threading
import logging
from collections.abc import Mapping

from neural_fights.data import database
from neural_fights.utils.config import (
    ALTURA,
    AMARELO_FAISCA,
    AZUL_MANA,
    BRANCO,
    COR_CORPO,
    COR_FUNDO,
    COR_GRID,
    COR_P1,
    COR_P2,
    COR_TEXTO_INFO,
    COR_TEXTO_TITULO,
    COR_UI_BG,
    FPS,
    LARGURA,
    PPM,
    SANGUE_ESCURO,
    VERMELHO_SANGUE,
)
from neural_fights.effects import (Particula, FloatingText, Decal, Shockwave, Câmera,
                     ImpactFlash, MagicClash, BlockEffect, DashTrail, HitSpark,
                     MovementAnimationManager, MovementType,  # v8.0 Movement Animations
                     AttackAnimationManager, calcular_knockback_com_forca, get_impact_tier,  # v8.0 Attack Animations
                     MagicVFXManager)  # v11.0 Magic VFX
from neural_fights.effects.audio import AudioManager  # v10.0 Sistema de Áudio
from neural_fights.core.entities import Lutador
from neural_fights.core.combat import criar_metadata_impacto
from neural_fights.core.physics import intersect_line_circle, colisao_linha_linha, normalizar_angulo
from neural_fights.core.hitbox import sistema_hitbox, verificar_hit, atualizar_debug, DEBUG_VISUAL
from neural_fights.core.arena import set_arena  # v9.0 Sistema de Arena
from neural_fights.ai import CombatChoreographer  # Sistema de Coreografia v5.0
from neural_fights.core.game_feel import GameFeelManager, HitStopManager  # Sistema de Game Feel v8.0
from neural_fights.core.match_series import BestOfSeries


DELETE_MATCH_CONFIG_ENV = "NEURAL_FIGHTS_DELETE_MATCH_CONFIG"
logger = logging.getLogger(__name__)


def _is_generated_match_config(path: str | None) -> bool:
    """Aceita cleanup somente para temporarios criados pelo runner visual."""

    if not path:
        return False
    resolved = os.path.realpath(os.path.abspath(path))
    temp_dir = os.path.realpath(tempfile.gettempdir())
    basename = os.path.basename(resolved)
    return (
        os.path.dirname(resolved) == temp_dir
        and basename.startswith("neural-fights-match-")
        and basename.endswith(".json")
    )


class _SilentAudioManager:
    """Adaptador nulo usado para manter chamadas de áudio fora do combate."""

    enabled = False
    sounds = {}

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class Simulador:
    """Motor de uma partida. Exclusivo por processo, por dependência real.

    Os lutadores e seus brains recebem áudio, arena e coreógrafo por injeção
    (``Lutador.configurar_contexto_partida``), então o domínio não alcança mais
    estado de módulo. O que continua global ao processo é infraestrutura que
    não admite duas cópias:

    * ``pygame.init()``/``pygame.quit()`` — SDL tem um subsistema por processo;
    * os managers com ``_instance`` de classe (áudio, VFX, animações, game
      feel, hit stop, coreografia), que este simulador reseta e assume;
    * a semente do ``random`` de módulo, salva e restaurada em ``close()``.

    Por isso o lock abaixo permanece: ele serializa construção, reload e
    encerramento para que um simulador nunca destrua a infraestrutura de
    outro. Paralelismo real de partidas é por processo — é o que o modo
    torneio já faz ao lançar cada luta via ``subprocess``.
    """

    _lifecycle_lock = threading.RLock()
    _active_owner_token = None

    @staticmethod
    def criar_match_config_padrao():
        """Cria uma luta válida em memória sem consultar/gravar estado runtime."""
        personagens = database.carregar_personagens()
        if len(personagens) < 2:
            raise RuntimeError(
                "São necessários pelo menos 2 personagens cadastrados "
                "para iniciar uma luta."
            )
        return {
            "p1_nome": personagens[0].nome,
            "p2_nome": personagens[1].nome,
            "cenario": "Arena",
            "best_of": 1,
            "portrait_mode": False,
        }

    def __init__(self, match_config=None, *, headless=False, seed=None):
        self._lifecycle_token = None
        self._random_state_before_seed = None
        self._closed = True
        owner_token = object()

        # A aquisição acontece antes de qualquer leitura ou inicialização. Isso
        # impede que duas construções concorrentes disputem os singletons.
        with Simulador._lifecycle_lock:
            if Simulador._active_owner_token is not None:
                raise RuntimeError(
                    "Já existe uma instância ativa de Simulador neste processo; "
                    "chame close() antes de criar outra."
                )
            Simulador._active_owner_token = owner_token
            self._lifecycle_token = owner_token
            self._closed = False

        try:
            self._inicializar(match_config, headless=headless, seed=seed)
        except BaseException as exc:
            try:
                self.close()
            except BaseException as cleanup_error:
                exc.add_note(f"Falha adicional ao limpar Simulador: {cleanup_error}")
            raise

    def _inicializar(self, match_config=None, *, headless=False, seed=None):
        if match_config is None:
            # Configurações visuais isoladas pertencem ao processo que as
            # consome. Removê-las logo após a leitura evita depender da vida
            # da interface que iniciou este subprocesso.
            isolated_config_path = None
            if os.environ.get(DELETE_MATCH_CONFIG_ENV) == "1":
                requested_cleanup = os.environ.get(database.MATCH_CONFIG_ENV)
                if _is_generated_match_config(requested_cleanup):
                    isolated_config_path = requested_cleanup
                elif requested_cleanup:
                    logger.warning(
                        "Cleanup recusado para match config nao temporaria: %s",
                        requested_cleanup,
                    )

            try:
                match_config = database.carregar_match_config()
            finally:
                if isolated_config_path:
                    try:
                        os.remove(os.path.abspath(isolated_config_path))
                    except FileNotFoundError:
                        pass
                    except OSError as exc:
                        # O processo pai ainda mantém um fallback após wait().
                        logger.warning(
                            "Nao foi possivel remover config temporaria: %s",
                            exc,
                        )
        elif not isinstance(match_config, Mapping):
            raise TypeError("match_config precisa ser um mapeamento")

        self.match_config = dict(match_config)
        self.headless = bool(headless)
        self.seed = seed
        self._rng_generation = 0
        if seed is not None:
            self._random_state_before_seed = random.getstate()
            random.seed(seed)

        best_of = self.match_config.get("best_of", 1)
        if isinstance(best_of, str) and best_of in {"1", "3", "5"}:
            best_of = int(best_of)
        self.best_of_series = BestOfSeries(best_of)
        if self.headless:
            pygame.font.init()
        else:
            pygame.init()
        
        # Carrega config primeiro para saber o modo de tela
        self.portrait_mode = self._check_portrait_mode()
        
        # Define dimensões da tela baseado no modo
        if self.portrait_mode:
            from neural_fights.utils.config import LARGURA_PORTRAIT, ALTURA_PORTRAIT
            self.screen_width = LARGURA_PORTRAIT
            self.screen_height = ALTURA_PORTRAIT
        else:
            self.screen_width = LARGURA
            self.screen_height = ALTURA
        
        if self.headless:
            self.tela = pygame.Surface((self.screen_width, self.screen_height))
        else:
            self.tela = pygame.display.set_mode((self.screen_width, self.screen_height))
            pygame.display.set_caption("Neural Fights - v9.0 ARENA EDITION")
        self.clock = pygame.time.Clock()
        self.rodando = True
        
        self.cam = Câmera(self.screen_width, self.screen_height)
        self.particulas = [] 
        self.decals = [] 
        self.textos = [] 
        self.shockwaves = [] 
        self.projeteis = []
        self.portais = []
        
        # === NOVOS EFEITOS v7.0 ===
        self.impact_flashes = []
        self.magic_clashes = []
        self.block_effects = []
        self.dash_trails = []
        self.hit_sparks = []

        self.paused = False
        self.show_hud = True
        self.show_analysis = False
        self.show_hitbox_debug = DEBUG_VISUAL  # Toggle com tecla H
        self.time_scale = 1.0
        self.slow_mo_timer = 0.0
        self.hit_stop_timer = 0.0 
        self.vencedor = None
        self.vencedor_round_side = None
        self.vencedor_serie_side = None
        self.empate_round = False
        self.round_finalizado = False
        self._slow_mo_ended = False
        self.rastros = {} 
        self.vida_visual_p1 = 100; self.vida_visual_p2 = 100
        
        # Sistema de Coreografia
        self.choreographer = None
        
        # === SISTEMA DE GAME FEEL v8.0 ===
        # Gerencia Hit Stop, Super Armor, Channeling e Camera Feel
        self.game_feel = None
        
        # === SISTEMA DE ARENA v9.0 ===
        self.arena = None
        
        # === SISTEMA DE ÁUDIO v10.0 ===
        self.audio = None
        
        self.recarregar_tudo()

    def _assert_active_owner(self):
        if (
            self._closed
            or self._lifecycle_token is None
            or Simulador._active_owner_token is not self._lifecycle_token
        ):
            raise RuntimeError("Esta instância de Simulador não está mais ativa")

    def _check_portrait_mode(self) -> bool:
        """Verifica se o modo retrato está ativado no config"""
        try:
            config = getattr(self, "match_config", None)
            if config is None:
                config = database.carregar_match_config()
            return bool(config.get("portrait_mode", False))
        except (OSError, ValueError, TypeError):
            return False

    def recarregar_tudo(self):
        # O lock também serializa reload e close: nenhum reset global pode
        # ocorrer enquanto a instância está sendo encerrada.
        with Simulador._lifecycle_lock:
            self._assert_active_owner()
            self._recarregar_tudo_owned()

    def _recarregar_tudo_owned(self):
        self.p1, self.p2, self.cenario, _ = self.carregar_luta_dados()
        self._configurar_partida_atual()

    def _configurar_partida_atual(self):
        """Reinicia entidades e managers para os lutadores ja atribuidos."""

        generation = self._rng_generation
        self._rng_generation += 1
        if self.seed is None:
            base_seed = random.getrandbits(128)
        else:
            base_seed = self.seed
        self.p1.configurar_rng_runtime(
            random.Random(f"neural-fights:{base_seed}:{generation}:p1")
        )
        self.p2.configurar_rng_runtime(
            random.Random(f"neural-fights:{base_seed}:{generation}:p2")
        )
        sistema_hitbox.limpar_historico()

        self.particulas = []; self.decals = []; self.textos = []; self.shockwaves = []; self.projeteis = []
        self.impact_flashes = []; self.magic_clashes = []; self.block_effects = []
        self.dash_trails = []; self.hit_sparks = []
        self.summons = []; self.traps = []; self.beams = []; self.areas = []; self.portais = []
        self.time_scale = 1.0; self.slow_mo_timer = 0.0; self.hit_stop_timer = 0.0
        self.vencedor = None; self.paused = False; self.rastros = {self.p1: [], self.p2: []}
        self.vencedor_round_side = None; self.empate_round = False; self.round_finalizado = False
        self.vencedor_serie_side = self.best_of_series.winner
        self._slow_mo_ended = False
        self.vida_visual_p1 = self.p1.vida_max
        self.vida_visual_p2 = self.p2.vida_max

        CombatChoreographer.reset()
        self.choreographer = CombatChoreographer.get_instance()
        self.choreographer.registrar_lutadores(self.p1, self.p2)

        GameFeelManager.reset()
        self.game_feel = GameFeelManager.get_instance()
        self.game_feel.set_camera(self.cam)
        self.game_feel.registrar_lutadores(self.p1, self.p2)

        MovementAnimationManager.reset()
        self.movement_anims = MovementAnimationManager.get_instance()
        self.movement_anims.set_ppm(PPM)

        AttackAnimationManager.reset()
        self.attack_anims = AttackAnimationManager()
        self.attack_anims.set_ppm(PPM)

        cenario_nome = getattr(self, 'cenario', 'Arena') or 'Arena'
        self.arena = set_arena(cenario_nome)
        self.cam.set_arena_bounds(
            self.arena.centro_x,
            self.arena.centro_y,
            self.arena.largura,
            self.arena.altura,
        )

        spawn1, spawn2 = self.arena.get_spawn_points()
        self.p1.pos[0], self.p1.pos[1] = spawn1
        self.p2.pos[0], self.p2.pos[1] = spawn2
        self._prev_z = {self.p1: 0, self.p2: 0}

        # Entidades também consultam o singleton diretamente. No headless,
        # todas recebem o mesmo adaptador nulo e nenhuma carga de áudio ocorre.
        AudioManager.reset()
        if self.headless:
            self.audio = _SilentAudioManager()
            AudioManager._instance = self.audio
        else:
            self.audio = AudioManager.get_instance()
        self._prev_stagger = {self.p1: False, self.p2: False}
        self._prev_dash = {self.p1: 0, self.p2: 0}

        # Os lutadores (e seus brains) recebem os colaboradores desta partida
        # em vez de alcançarem os singletons de módulo.
        for lutador in (self.p1, self.p2):
            lutador.configurar_contexto_partida(
                audio=self.audio,
                arena=self.arena,
                choreographer=self.choreographer,
            )

        MagicVFXManager.reset()
        self.magic_vfx = MagicVFXManager.get_instance()
        self.audio.play_special("arena_start", 0.8)

    def carregar_luta_dados(self):
        config = getattr(self, "match_config", None)
        if config is None:
            config = database.carregar_match_config()
        campos_ausentes = [
            campo for campo in ("p1_nome", "p2_nome") if not config.get(campo)
        ]
        if campos_ausentes:
            raise ValueError(
                "Configuração de luta sem campo(s): " + ", ".join(campos_ausentes)
            )

        todos = database.carregar_personagens()
        armas = database.carregar_armas()

        def montar(nome):
            p = next((x for x in todos if x.nome == nome), None)
            if p is None:
                raise ValueError(f"Personagem não encontrado na configuração: {nome}")
            # Always set arma_obj, even if None
            p.arma_obj = next((a for a in armas if a.nome == p.nome_arma), None) if p.nome_arma else None
            return p
        l1 = Lutador(montar(config["p1_nome"]), 5.0, 8.0)
        l2 = Lutador(montar(config["p2_nome"]), 19.0, 8.0)
        cenario = config.get("cenario", "Arena")
        portrait_mode = config.get("portrait_mode", False)
        return l1, l2, cenario, portrait_mode

    def _nome_do_slot(self, slot):
        lutador = self.p1 if slot == "p1" else self.p2
        return lutador.dados.nome

    def _finalizar_round(self, winner_slot=None):
        """Fecha e contabiliza um round uma única vez."""
        if not hasattr(self, "best_of_series"):
            self.best_of_series = BestOfSeries(1)
        if getattr(self, "round_finalizado", False):
            return False

        if winner_slot is None:
            registrado = self.best_of_series.record_draw()
        else:
            registrado = self.best_of_series.record_win(winner_slot)

        if not registrado:
            return False

        self.round_finalizado = True
        self.vencedor_round_side = winner_slot
        self.vencedor_serie_side = self.best_of_series.winner
        self.empate_round = winner_slot is None
        self.vencedor = (
            "EMPATE" if winner_slot is None else self._nome_do_slot(winner_slot)
        )
        self.ativar_slow_motion()
        return True

    def _detectar_resultado_round(self):
        """Detecta o resultado pelo estado real dos dois lutadores."""
        if getattr(self, "round_finalizado", False):
            return False

        p1_morto = bool(getattr(self.p1, "morto", False))
        p2_morto = bool(getattr(self.p2, "morto", False))

        if not p1_morto and not p2_morto:
            return False
        if p1_morto and p2_morto:
            return self._finalizar_round()
        return self._finalizar_round("p2" if p1_morto else "p1")

    def _reiniciar_round_ou_serie(self):
        """R avança o round ou inicia uma nova série após o campeão."""
        if self.best_of_series.finished:
            self.best_of_series.reset_series()
        else:
            self.best_of_series.reset_round()
        self.recarregar_tudo()

    def _atualizar_lutadores(self, dt):
        """Atualiza os dois slots antes de qualquer decisão sobre o round."""
        self.p1.update(dt, self.p2)
        self.p2.update(dt, self.p1)

    def processar_inputs(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.rodando = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: 
                    if self.audio: self.audio.play_ui("back")
                    self.rodando = False 
                if event.key == pygame.K_r: 
                    if self.audio: self.audio.play_ui("confirm")
                    self._reiniciar_round_ou_serie()
                if event.key == pygame.K_SPACE: 
                    if self.audio: self.audio.play_ui("select")
                    self.paused = not self.paused
                if event.key == pygame.K_g: 
                    if self.audio: self.audio.play_ui("select")
                    self.show_hud = not self.show_hud  # G para HUD
                if event.key == pygame.K_h: 
                    if self.audio: self.audio.play_ui("select")
                    self.show_hitbox_debug = not self.show_hitbox_debug  # H para HITBOX DEBUG
                if event.key == pygame.K_TAB: 
                    if self.audio: self.audio.play_ui("select")
                    self.show_analysis = not self.show_analysis
                if event.key == pygame.K_t: 
                    if self.audio: self.audio.play_ui("select")
                    self.time_scale = 0.2 if self.time_scale == 1.0 else 1.0
                if event.key == pygame.K_f: 
                    if self.audio: self.audio.play_ui("select")
                    self.time_scale = 3.0 if self.time_scale == 1.0 else 1.0
                if event.key == pygame.K_1: 
                    if self.audio: self.audio.play_ui("select")
                    self.cam.modo = "P1"
                if event.key == pygame.K_2: 
                    if self.audio: self.audio.play_ui("select")
                    self.cam.modo = "P2"
                if event.key == pygame.K_3: 
                    if self.audio: self.audio.play_ui("select")
                    self.cam.modo = "AUTO"
            if event.type == pygame.MOUSEWHEEL:
                self.cam.target_zoom += event.y * 0.1
                self.cam.target_zoom = max(0.5, min(self.cam.target_zoom, 3.0))

        keys = pygame.key.get_pressed()
        move_speed = 15 / self.cam.zoom
        if keys[pygame.K_w] or keys[pygame.K_UP]: self.cam.y -= move_speed; self.cam.modo = "MANUAL"
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: self.cam.y += move_speed; self.cam.modo = "MANUAL"
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: self.cam.x -= move_speed; self.cam.modo = "MANUAL"
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.cam.x += move_speed; self.cam.modo = "MANUAL"

    def _atualizar_visuais_round_finalizado(self, dt):
        """Mantém o impacto final animado sem reabrir dano, IA ou física."""
        if getattr(self, "cam", None):
            self.cam.atualizar(dt, self.p1, self.p2)
        atualizar_debug(dt)

        if getattr(self, "paused", False):
            return

        for texto in getattr(self, "textos", []):
            texto.update(dt)
        self.textos = [texto for texto in getattr(self, "textos", []) if texto.vida > 0]

        for onda in getattr(self, "shockwaves", []):
            onda.update(dt)
        self.shockwaves = [onda for onda in getattr(self, "shockwaves", []) if onda.vida > 0]

        for nome_lista in (
            "impact_flashes", "magic_clashes", "block_effects",
            "dash_trails", "hit_sparks",
        ):
            efeitos = getattr(self, nome_lista, [])
            for efeito in efeitos:
                efeito.update(dt)
            setattr(self, nome_lista, [efeito for efeito in efeitos if efeito.vida > 0])

        if getattr(self, "magic_vfx", None):
            self.magic_vfx.update(dt)
        if getattr(self, "movement_anims", None):
            self.movement_anims.update(dt)
        if getattr(self, "attack_anims", None):
            self.attack_anims.update(dt)

        if not hasattr(self, "decals"):
            self.decals = []
        for particula in getattr(self, "particulas", [])[:]:
            particula.atualizar(dt)
            if particula.vida <= 0:
                if particula.cor == VERMELHO_SANGUE and random.random() < 0.3:
                    self.decals.append(
                        Decal(particula.x, particula.y, particula.tamanho * 2, SANGUE_ESCURO)
                    )
                self.particulas.remove(particula)
        if len(getattr(self, "decals", [])) > 100:
            self.decals.pop(0)

    def _aplicar_resultado_periodico_area(self, area, resultado):
        """Aplica ticks/status depois do impacto inicial da mesma área."""

        alvo = resultado["alvo"]
        if resultado.get("dot_tick"):
            dano_dot = resultado.get("dano", 5)
            modificar_dano = getattr(area.dono, "get_dano_modificado", None)
            if callable(modificar_dano):
                dano_dot = modificar_dano(dano_dot)
            tipo_dot = resultado.get("tipo", "NORMAL")
            fonte_tick = resultado.get("fonte_impacto", object())
            metadata_tick = criar_metadata_impacto(
                area,
                dot_tick=True,
                elemento=resultado.get("elemento", area.elemento),
            )
            resolver_impacto = getattr(alvo, "resolver_impacto", None)
            if callable(resolver_impacto):
                impacto = resolver_impacto(
                    dano_dot,
                    0,
                    0,
                    tipo_dot,
                    atacante=area.dono,
                    fonte_impacto=fonte_tick,
                    ignorar_recuperacao_impacto=True,
                    gerar_recuperacao_impacto=False,
                    metadata_impacto=metadata_tick,
                )
                morreu = impacto.morreu
                dano_aplicado = impacto.dano
                impacto_aplicado = impacto.atingiu
            else:
                morreu = alvo.tomar_dano(
                    dano_dot,
                    0,
                    0,
                    tipo_dot,
                    atacante=area.dono,
                    fonte_impacto=fonte_tick,
                    ignorar_recuperacao_impacto=True,
                    gerar_recuperacao_impacto=False,
                    metadata_impacto=metadata_tick,
                )
                dano_aplicado = getattr(alvo, "ultimo_dano_recebido", dano_dot)
                impacto_aplicado = True
            if morreu:
                self.textos.append(FloatingText(
                    alvo.pos[0] * PPM,
                    alvo.pos[1] * PPM - 50,
                    "FATAL!",
                    VERMELHO_SANGUE,
                    40,
                ))
            elif impacto_aplicado:
                cor_dot = self._get_cor_efeito(
                    resultado.get("elemento") or tipo_dot
                )
                self.textos.append(FloatingText(
                    alvo.pos[0] * PPM,
                    alvo.pos[1] * PPM - 30,
                    int(dano_aplicado),
                    cor_dot,
                    14,
                ))
            return

        resolver_impacto = getattr(alvo, "resolver_impacto", None)
        if callable(resolver_impacto):
            resolver_impacto(
                0.0,
                0.0,
                0.0,
                resultado["efeito"],
                atacante=area.dono,
                fonte_impacto=resultado.get("fonte_impacto", object()),
                ignorar_recuperacao_impacto=True,
                gerar_recuperacao_impacto=False,
                metadata_impacto=criar_metadata_impacto(
                    area,
                    status_stack=True,
                ),
            )

    def update(self, dt):
        """Avança o mundo em passos limitados para preservar determinismo."""

        dt = float(dt)
        if not math.isfinite(dt):
            raise ValueError("dt da simulacao precisa ser finito")
        dt = max(0.0, dt)
        if dt == 0.0:
            return self._update_step(0.0)

        # 100 ms e o maior passo logico aceito pelo runtime. Esse limite
        # preserva expiracoes sem transformar um frame de 100 ms em duas
        # chamadas observaveis aos gerenciadores visuais.
        max_step = 0.1
        remaining = dt
        while remaining > 1e-12:
            step = min(max_step, remaining)
            self._update_step(step)
            remaining = max(0.0, remaining - step)
            if remaining <= 1e-12:
                remaining = 0.0

    def _update_step(self, dt):
        if getattr(self, "round_finalizado", False):
            self._atualizar_visuais_round_finalizado(dt)
            return
        if self._detectar_resultado_round():
            return

        self.cam.atualizar(dt, self.p1, self.p2)
        # Atualiza sistema de debug de hitbox
        atualizar_debug(dt)
        
        if self.paused: return

        for t in self.textos: t.update(dt)
        self.textos = [t for t in self.textos if t.vida > 0]
        for s in self.shockwaves: s.update(dt)
        self.shockwaves = [s for s in self.shockwaves if s.vida > 0]

        if self._processar_hit_stop(dt):
            return

        self._coletar_buffers_dos_lutadores(dt)
        self._atualizar_efeitos_visuais(dt)
        self._atualizar_projeteis(dt)
        self._atualizar_orbes_magicos(dt)
        self._atualizar_areas(dt)
        self._atualizar_beams(dt)
        self._atualizar_summons(dt)
        self._atualizar_traps(dt)
        self._atualizar_transformacoes(dt)
        self._atualizar_canalizacoes(dt)
        self._atualizar_animacoes(dt)

    def _processar_hit_stop(self, dt):
        """Aplica o hit stop do frame.

        Retorna ``True`` quando o frame foi consumido pelo hit stop e o
        restante do passo deve ser pulado.
        """
        # O Game Feel Manager pode zerar o dt durante hit stop
        dt_efetivo = dt
        if self.game_feel:
            dt_efetivo = self.game_feel.update(dt)
            # Durante hit stop, apenas efeitos visuais atualizam
            if dt_efetivo == 0:
                # Atualiza apenas efeitos visuais durante hit stop
                for ef in self.impact_flashes: ef.update(dt * 0.3)  # Slow mo nos efeitos
                for ef in self.hit_sparks: ef.update(dt * 0.3)
                return True
        else:
            # Fallback para sistema antigo de hit stop
            if self.hit_stop_timer > 0: 
                self.hit_stop_timer -= dt
                return True
        return False

    def _coletar_buffers_dos_lutadores(self, dt):
        """Move projeteis, areas, beams, summons, traps e portais dos lutadores
        para as listas do simulador e atualiza os portais ativos."""
        for p in [self.p1, self.p2]:
            # Projéteis
            if p.buffer_projeteis:
                self.projeteis.extend(p.buffer_projeteis)
                p.buffer_projeteis = []
            # Orbes mágicos
            if hasattr(p, 'buffer_orbes') and p.buffer_orbes:
                if not hasattr(self, 'orbes'):
                    self.orbes = []
                # Orbes ficam na lista do lutador para atualização de órbita
                # mas também precisamos processar colisões aqui
            # Áreas
            if hasattr(p, 'buffer_areas') and p.buffer_areas:
                if not hasattr(self, 'areas'):
                    self.areas = []
                self.areas.extend(p.buffer_areas)
                p.buffer_areas = []
            # Beams
            if hasattr(p, 'buffer_beams') and p.buffer_beams:
                if not hasattr(self, 'beams'):
                    self.beams = []
                self.beams.extend(p.buffer_beams)
                p.buffer_beams = []
            
            # === NOVOS TIPOS v2.0 ===
            # Summons (invocações)
            if hasattr(p, 'buffer_summons') and p.buffer_summons:
                if not hasattr(self, 'summons'):
                    self.summons = []
                # Spawn effect dramático para cada novo summon
                for summon in p.buffer_summons:
                    if hasattr(self, 'magic_vfx') and self.magic_vfx:
                        # Determina elemento pelo nome/cor do summon
                        elemento = "ARCANO"
                        nome = getattr(summon, 'nome', '').lower()
                        if any(w in nome for w in ["fogo", "fire", "chama"]):
                            elemento = "FOGO"
                        elif any(w in nome for w in ["gelo", "ice"]):
                            elemento = "GELO"
                        elif any(w in nome for w in ["raio", "light"]):
                            elemento = "RAIO"
                        elif any(w in nome for w in ["trevas", "shadow"]):
                            elemento = "TREVAS"
                        
                        self.magic_vfx.spawn_summon(summon.x * PPM, summon.y * PPM, elemento)
                
                self.summons.extend(p.buffer_summons)
                p.buffer_summons = []
            
            # Traps (armadilhas/estruturas)
            if hasattr(p, 'buffer_traps') and p.buffer_traps:
                if not hasattr(self, 'traps'):
                    self.traps = []
                self.traps.extend(p.buffer_traps)
                p.buffer_traps = []

            if hasattr(p, "buffer_portais") and p.buffer_portais:
                if not hasattr(self, "portais"):
                    self.portais = []
                self.portais.extend(p.buffer_portais)
                p.buffer_portais = []

        for portal in getattr(self, "portais", ()):
            portal.atualizar(
                dt,
                tuple(
                    lutador
                    for lutador in (self.p1, self.p2)
                    if not self._alvo_em_transicao_sombria(lutador)
                ),
            )
        self.portais = [
            portal for portal in getattr(self, "portais", ()) if portal.ativo
        ]

    def _atualizar_efeitos_visuais(self, dt):
        """Avanca os efeitos puramente visuais do frame e resolve clashes."""
        for ef in self.impact_flashes: ef.update(dt)
        self.impact_flashes = [ef for ef in self.impact_flashes if ef.vida > 0]
        for ef in self.magic_clashes: ef.update(dt)
        self.magic_clashes = [ef for ef in self.magic_clashes if ef.vida > 0]
        for ef in self.block_effects: ef.update(dt)
        self.block_effects = [ef for ef in self.block_effects if ef.vida > 0]
        for ef in self.dash_trails: ef.update(dt)
        self.dash_trails = [ef for ef in self.dash_trails if ef.vida > 0]
        for ef in self.hit_sparks: ef.update(dt)
        self.hit_sparks = [ef for ef in self.hit_sparks if ef.vida > 0]
        
        # === ATUALIZA MAGIC VFX v11.0 ===
        if hasattr(self, 'magic_vfx') and self.magic_vfx:
            self.magic_vfx.update(dt)

        # === CLASH DE PROJÉTEIS (v7.0) ===
        self._verificar_clash_projeteis()

    def _atualizar_projeteis(self, dt):
        """Move projeteis, resolve colisoes e aplica as mecanicas derivadas
        (split, ricochete, contagio, retorno)."""
        novos_projeteis = []  # Para projéteis criados por split/duplicação
        for proj in self.projeteis:
            origem_proj = (getattr(proj, "x", 0.0), getattr(proj, "y", 0.0))
            # Passa lista de alvos para suportar homing
            alvos = [
                alvo
                for alvo in (self.p1, self.p2)
                if not self._alvo_em_transicao_sombria(alvo)
            ]
            resultado = None
            
            # Verifica se o método atualizar aceita alvos
            if hasattr(proj, 'atualizar'):
                import inspect
                sig = inspect.signature(proj.atualizar)
                if len(sig.parameters) > 1:
                    resultado = proj.atualizar(dt, alvos)
                else:
                    proj.atualizar(dt)
            
            # Processa resultados especiais
            if resultado:
                if resultado.get("duplicar"):
                    novo = proj.criar_duplicata(resultado)
                    if novo is not None:
                        novos_projeteis.append(novo)
                
                elif resultado.get("split"):
                    # Split aleatório (Caos)
                    from neural_fights.core.combat import Projetil
                    for angulo_split in resultado.get(
                        "angulos",
                        (resultado["angulo"],),
                    ):
                        novo = Projetil(
                            proj.nome,
                            resultado["x"],
                            resultado["y"],
                            angulo_split,
                            proj.dono,
                            habilitar_split=False,
                        )
                        novo.dano = proj.dano * 0.5
                        novos_projeteis.append(novo)
                
                elif resultado.get("explodir"):
                    # Cria efeito de área na posição
                    from neural_fights.core.combat import AreaEffect
                    area = AreaEffect(proj.nome, resultado["x"], resultado["y"], proj.dono)
                    area.raio = resultado.get("raio", 2.0)
                    if hasattr(self, 'areas'):
                        self.areas.append(area)
                    # Efeitos visuais de explosão
                    self.impact_flashes.append(ImpactFlash(resultado["x"] * PPM, resultado["y"] * PPM, proj.cor, 2.0, "explosion"))
                    self.shockwaves.append(Shockwave(resultado["x"] * PPM, resultado["y"] * PPM, proj.cor, tamanho=2.5))
                    self._spawn_particulas_efeito(resultado["x"] * PPM, resultado["y"] * PPM, "EXPLOSAO")

            if self._resolver_colisao_projetil_traps(proj, *origem_proj):
                continue
            
            alvo = getattr(proj, "alvo_forcado", None)
            if alvo is None:
                if getattr(proj, "backfire", False):
                    alvos_projeteis = [proj.dono]
                elif getattr(proj, "perfura", False):
                    alvos_projeteis = self._obter_alvos_hostis(
                        proj.dono,
                        incluir_summons=True,
                    )
                else:
                    alvos_projeteis = [
                        self.p2 if proj.dono == self.p1 else self.p1
                    ]
            else:
                alvos_projeteis = [alvo]
            alvos_projeteis = [
                candidato
                for candidato in alvos_projeteis
                if not self._alvo_em_transicao_sombria(candidato)
            ]
            if not alvos_projeteis:
                continue
            alvo = alvos_projeteis[0]
            alvos_cone_secundarios = []
            colisao_cone = None
            if getattr(proj, "cone", False):
                alvos_no_cone = [
                    candidato
                    for candidato in self._obter_alvos_hostis(proj.dono)
                    if proj.colidir(candidato)
                ]
                colisao_cone = bool(alvos_no_cone)
                if alvos_no_cone:
                    alvo = alvos_no_cone[0]
                    alvos_cone_secundarios = alvos_no_cone[1:]
            elif getattr(proj, "perfura", False):
                alvos_perfurados_no_frame = [
                    candidato
                    for candidato in alvos_projeteis
                    if proj.colidir(candidato)
                    and proj.pode_atingir(candidato)
                ]
                colisao_cone = bool(alvos_perfurados_no_frame)
                if alvos_perfurados_no_frame:
                    alvo = alvos_perfurados_no_frame[0]
                    alvos_cone_secundarios = alvos_perfurados_no_frame[1:]
            
            # === SISTEMA DE BLOQUEIO/DESVIO v7.0 ===
            bloqueado = self._verificar_bloqueio_projetil(proj, alvo)
            if bloqueado:
                proj.ativo = False
                continue
            
            # Verifica colisão - ArmaProjetil tem método próprio
            colidiu = False
            if colisao_cone is not None:
                colidiu = colisao_cone
            elif hasattr(proj, 'colidir'):
                colidiu = proj.colidir(alvo)
            else:
                # Projéteis de skill (antigo)
                alvo_x, alvo_y = self._posicao_alvo_combate(alvo)
                dx = alvo_x - proj.x
                dy = alvo_y - proj.y
                dist = math.hypot(dx, dy)
                colidiu = dist < (alvo.raio_fisico + proj.raio) and proj.ativo
            
            if colidiu and proj.ativo:
                alvo_x, alvo_y = self._posicao_alvo_combate(alvo)
                refletir = getattr(alvo, "tentar_refletir_projetil", None)
                if callable(refletir) and refletir(proj):
                    continue
                # Nota: proj.ativo será setado false dentro do bloco se não for perfurante
                
                # === ÁUDIO v10.0 - SOM DE IMPACTO DE PROJÉTIL ===
                if self.audio:
                    # Determina tipo de projétil para som adequado
                    if hasattr(proj, 'tipo'):
                        tipo_proj = proj.tipo  # "faca", "flecha", "shuriken"
                    else:
                        tipo_proj = "energy"  # Projétil de skill
                    
                    listener_x = self.cam.x / PPM
                    self.audio.play_skill("PROJETIL", tipo_proj, proj.x, listener_x, phase="impact")
                
                # === EFEITOS DE IMPACTO MELHORADOS v11.0 DRAMATIC ===
                cor_impacto = proj.cor if hasattr(proj, 'cor') else BRANCO
                self.impact_flashes.append(ImpactFlash(proj.x * PPM, proj.y * PPM, cor_impacto, 1.2, "magic"))
                self.shockwaves.append(Shockwave(proj.x * PPM, proj.y * PPM, cor_impacto, tamanho=1.2))
                
                # Direção do impacto
                dx = alvo.pos[0] - proj.x
                dy = alvo.pos[1] - proj.y
                dist = math.hypot(dx, dy) or 1
                direcao_impacto = math.atan2(dy, dx)
                
                # Hit Sparks na direção do impacto
                self.hit_sparks.append(HitSpark(proj.x * PPM, proj.y * PPM, cor_impacto, direcao_impacto, 1.0))
                
                # === EXPLOSÃO DRAMÁTICA v11.0 ===
                if hasattr(self, 'magic_vfx') and self.magic_vfx:
                    # Determina elemento pelo nome/tipo do projétil
                    elemento = "DEFAULT"
                    tipo_proj_str = str(getattr(proj, 'tipo', '')).lower()
                    nome_skill = str(getattr(proj, 'nome', '')).lower()
                    
                    if any(w in nome_skill + tipo_proj_str for w in ["fogo", "fire", "chama", "meteoro"]):
                        elemento = "FOGO"
                    elif any(w in nome_skill + tipo_proj_str for w in ["gelo", "ice", "glacial"]):
                        elemento = "GELO"
                    elif any(w in nome_skill + tipo_proj_str for w in ["raio", "lightning", "thunder"]):
                        elemento = "RAIO"
                    elif any(w in nome_skill + tipo_proj_str for w in ["trevas", "shadow", "dark"]):
                        elemento = "TREVAS"
                    elif any(w in nome_skill + tipo_proj_str for w in ["luz", "light", "holy"]):
                        elemento = "LUZ"
                    
                    dano_proj = getattr(proj, 'dano', 10)
                    self.magic_vfx.spawn_explosion(
                        proj.x * PPM, proj.y * PPM, 
                        elemento=elemento, 
                        tamanho=0.6 + dano_proj * 0.02,
                        dano=dano_proj
                    )
                
                # === v11.0: VERIFICAÇÕES DE CONDIÇÃO ===
                bonus_condicao = 1.0
                if hasattr(proj, 'verificar_condicao'):
                    bonus_condicao = proj.verificar_condicao(alvo)
                
                # Aplica dano com efeito
                dano_base = proj.dono.get_dano_modificado(proj.dano) if hasattr(proj.dono, 'get_dano_modificado') else proj.dano
                dano_final = dano_base * bonus_condicao
                dano_final *= self._modificador_protecao_summon(alvo)
                tipo_efeito = proj.tipo_efeito if hasattr(proj, 'tipo_efeito') else "NORMAL"
                
                # Camera shake proporcional ao dano
                shake_intensity = min(15.0, 5.0 + dano_final * 0.3)
                self.cam.aplicar_shake(shake_intensity, 0.1)
                self.hit_stop_timer = 0.03  # Micro hit-stop
                
                # === v11.0: PERFURAÇÃO - não desativa projétil ===
                if hasattr(proj, 'perfura') and proj.perfura:
                    if id(alvo) not in proj.alvos_perfurados:
                        if hasattr(proj, 'pode_atingir') and not proj.pode_atingir(alvo):
                            continue
                    # Não desativa - continua voando
                else:
                    if getattr(proj, "iniciar_retorno", lambda: False)():
                        pass
                    elif getattr(proj, "explosion_timer", None) is not None:
                        proj.aguardando_explosao = True
                        proj.vel = 0.0
                    else:
                        proj.ativo = False
                
                kwargs_impacto = {
                    "atacante": proj.dono,
                    "fonte_impacto": getattr(proj, "fonte_impacto", proj),
                    "ignorar_invencibilidade": getattr(proj, "multi_shot", 1) > 1,
                    "duracao_efeito": (
                        getattr(proj, "delay_explosao", 0.0) or None
                        if tipo_efeito == "BOMBA_RELOGIO"
                        else getattr(proj, "duracao_efeito", None)
                    ),
                    "raio_efeito": (
                        getattr(proj, "raio_explosao", None)
                        if tipo_efeito == "BOMBA_RELOGIO"
                        else None
                    ),
                    "percentual_efeito": getattr(proj, "percentual_efeito", None),
                    "metadata_impacto": criar_metadata_impacto(proj),
                }
                resolver_impacto = getattr(alvo, "resolver_impacto", None)
                if callable(resolver_impacto):
                    impacto = resolver_impacto(
                        dano_final,
                        dx/dist,
                        dy/dist,
                        tipo_efeito,
                        **kwargs_impacto,
                    )
                    morreu = impacto.morreu
                    dano_aplicado = impacto.dano
                    impacto_aplicado = impacto.atingiu
                else:
                    vida_antes = float(getattr(alvo, "vida", 0.0))
                    resultado_dano = alvo.tomar_dano(dano_final)
                    dano_aplicado = max(
                        0.0,
                        vida_antes - float(getattr(alvo, "vida", vida_antes)),
                    )
                    impacto_aplicado = dano_aplicado > 0.0
                    morreu = bool(
                        isinstance(resultado_dano, Mapping)
                        and resultado_dano.get("morreu")
                    ) or not getattr(alvo, "ativo", True)
                if morreu:
                    self.textos.append(FloatingText(alvo_x*PPM, alvo_y*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                else:
                    # Texto especial para execução
                    if bonus_condicao >= 5.0:
                        self.textos.append(FloatingText(alvo_x*PPM, alvo_y*PPM - 50, "EXECUÇÃO!", (200, 50, 50), 32))
                    
                    # Cor do texto baseado no efeito ou tipo de projétil
                    if hasattr(proj, 'tipo') and proj.tipo in ["faca", "shuriken", "chakram", "flecha"]:
                        cor_txt = proj.cor if hasattr(proj, 'cor') else BRANCO
                    else:
                        cor_txt = self._get_cor_efeito(tipo_efeito)
                    self.textos.append(FloatingText(alvo_x*PPM, alvo_y*PPM - 30, int(dano_aplicado), cor_txt))
                    
                    # Partículas baseadas no efeito
                    self._spawn_particulas_efeito(alvo_x*PPM, alvo_y*PPM, tipo_efeito)
                
                # === v11.0: LIFESTEAL ===
                if hasattr(proj, 'lifesteal') and proj.lifesteal > 0:
                    cura = dano_aplicado * proj.lifesteal
                    cura_real = proj.dono.receber_cura(cura)
                    self.textos.append(FloatingText(proj.dono.pos[0]*PPM, proj.dono.pos[1]*PPM - 30, f"+{int(cura_real)}", (200, 100, 200), 16))
                
                # Efeito DRENAR recupera vida do atacante
                elif tipo_efeito == "DRENAR":
                    cura = dano_aplicado * 0.15
                    cura_real = proj.dono.receber_cura(cura)
                    self.textos.append(FloatingText(proj.dono.pos[0]*PPM, proj.dono.pos[1]*PPM - 30, f"+{int(cura_real)}", (100, 255, 150), 16))

                # Praga se propaga somente para outro lutador hostil disponível
                # dentro do raio, carregando o histórico para não reinfectar.
                criar_contagio = getattr(proj, "criar_contagio", None)
                if impacto_aplicado:
                    if callable(criar_contagio):
                        contagio = criar_contagio(
                            alvo,
                            self._obter_alvos_hostis(proj.dono),
                        )
                        if contagio is not None:
                            novos_projeteis.append(contagio)
                
                # === v11.0: EXPLOSÃO NO IMPACTO ===
                if (
                    hasattr(proj, 'raio_explosao')
                    and proj.raio_explosao > 0
                    and tipo_efeito != "BOMBA_RELOGIO"
                    and getattr(proj, "delay_explosao", 0.0) <= 0.0
                ):
                    from neural_fights.core.combat import AreaEffect
                    explosao = AreaEffect(proj.nome + " Explosão", proj.x, proj.y, proj.dono)
                    explosao.raio = proj.raio_explosao
                    explosao.raio_atual = explosao.raio
                    explosao.dano = proj.dano * 0.5  # Dano de área é 50% do projétil
                    explosao.tipo_efeito = tipo_efeito
                    explosao.fonte_impacto = object()
                    explosao.ignorar_invencibilidade = True
                    if hasattr(self, 'areas'):
                        self.areas.append(explosao)
                    self.impact_flashes.append(ImpactFlash(proj.x * PPM, proj.y * PPM, cor_impacto, 2.0, "explosion"))
                    self.shockwaves.append(Shockwave(proj.x * PPM, proj.y * PPM, cor_impacto, tamanho=2.5))
                    self._spawn_particulas_efeito(proj.x * PPM, proj.y * PPM, "EXPLOSAO")
                
                if getattr(proj, "remove_congelamento", False) and impacto_aplicado:
                    remover_congelamento = getattr(alvo, "remover_congelamento", None)
                    if callable(remover_congelamento):
                        remover_congelamento()

                # Um cone é uma única fonte capaz de atingir cada entidade no
                # volume uma vez. O cache de fonte fica por alvo, portanto não
                # impede os demais acertos e ainda bloqueia duplicatas.
                for alvo_cone in alvos_cone_secundarios:
                    bonus_cone = proj.verificar_condicao(alvo_cone)
                    dano_cone = proj.dono.get_dano_modificado(proj.dano)
                    dano_cone *= bonus_cone
                    origem_secundaria = getattr(
                        proj,
                        "origem_cone",
                        None,
                    ) or (proj.x, proj.y)
                    alvo_cone_x, alvo_cone_y = self._posicao_alvo_combate(alvo_cone)
                    dx_cone = alvo_cone_x - origem_secundaria[0]
                    dy_cone = alvo_cone_y - origem_secundaria[1]
                    dist_cone = math.hypot(dx_cone, dy_cone) or 1.0
                    resolver_secundario = getattr(
                        alvo_cone,
                        "resolver_impacto",
                        None,
                    )
                    if callable(resolver_secundario):
                        impacto_cone = resolver_secundario(
                            dano_cone,
                            dx_cone / dist_cone,
                            dy_cone / dist_cone,
                            proj.tipo_efeito,
                            atacante=proj.dono,
                            fonte_impacto=proj.fonte_impacto,
                            ignorar_invencibilidade=proj.multi_shot > 1,
                            metadata_impacto=criar_metadata_impacto(proj),
                        )
                        atingiu_secundario = impacto_cone.atingiu
                        dano_secundario = impacto_cone.dano
                    else:
                        vida_antes = float(getattr(alvo_cone, "vida", 0.0))
                        alvo_cone.tomar_dano(dano_cone)
                        dano_secundario = max(
                            0.0,
                            vida_antes - float(getattr(alvo_cone, "vida", vida_antes)),
                        )
                        atingiu_secundario = dano_secundario > 0.0
                    if atingiu_secundario:
                        self.textos.append(FloatingText(
                            alvo_cone_x * PPM,
                            alvo_cone_y * PPM - 30,
                            int(dano_secundario),
                            self._get_cor_efeito(proj.tipo_efeito),
                        ))
                        self._spawn_particulas_efeito(
                            alvo_cone_x * PPM,
                            alvo_cone_y * PPM,
                            proj.tipo_efeito,
                        )

        # Adiciona projéteis criados por split/duplicação/chain
        self.projeteis.extend(novos_projeteis)
        self.projeteis = [p for p in self.projeteis if p.ativo]

    def _atualizar_orbes_magicos(self, dt):
        """Resolve as colisoes dos orbes que orbitam cada lutador."""
        for p in [self.p1, self.p2]:
            if hasattr(p, 'buffer_orbes'):
                for orbe in p.buffer_orbes:
                    if orbe.ativo and orbe.estado == "disparando":
                        if self._resolver_colisao_projetil_traps(
                            orbe,
                            getattr(orbe, "prev_x", orbe.x),
                            getattr(orbe, "prev_y", orbe.y),
                        ):
                            continue
                        alvo = self.p2 if orbe.dono == self.p1 else self.p1
                        if self._alvo_em_transicao_sombria(alvo):
                            continue
                        if orbe.colidir(alvo):
                            refletir = getattr(alvo, "tentar_refletir_projetil", None)
                            if callable(refletir) and refletir(orbe):
                                continue
                            orbe.ativo = False
                            
                            # === ÁUDIO v10.0 - SOM DE ORBE MÁGICO ===
                            if self.audio:
                                listener_x = self.cam.x / PPM
                                self.audio.play_skill("PROJETIL", "orbe_magico", orbe.x, listener_x, phase="impact")
                            
                            # Shockwave mágico
                            self.shockwaves.append(Shockwave(orbe.x * PPM, orbe.y * PPM, orbe.cor, tamanho=1.5))
                            
                            # Direção do impacto
                            dx = alvo.pos[0] - orbe.x
                            dy = alvo.pos[1] - orbe.y
                            dist = math.hypot(dx, dy) or 1
                            
                            # Aplica dano mágico
                            dano_final = orbe.dono.get_dano_modificado(orbe.dano) if hasattr(orbe.dono, 'get_dano_modificado') else orbe.dano
                            
                            morreu = alvo.tomar_dano(
                                dano_final,
                                dx/dist,
                                dy/dist,
                                "NORMAL",
                                atacante=orbe.dono,
                                fonte_impacto=orbe,
                                metadata_impacto=criar_metadata_impacto(orbe),
                            )
                            dano_aplicado = getattr(alvo, "ultimo_dano_recebido", dano_final)
                            if morreu:
                                self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                            else:
                                # Texto mágico colorido
                                self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 30, int(dano_aplicado), orbe.cor))
                                # Partículas mágicas
                                self._spawn_particulas_efeito(alvo.pos[0]*PPM, alvo.pos[1]*PPM, "NORMAL")

    def _atualizar_areas(self, dt):
        """Atualiza areas de efeito e aplica dano/status por tick."""
        if hasattr(self, 'areas'):
            novas_areas = []  # Para ondas adicionais, meteoros, etc.
            for area in self.areas:
                resultados_periodicos = []
                # Passa lista de alvos para suportar pull, vortex, etc.
                alvos_area = [
                    alvo
                    for alvo in (self.p1, self.p2)
                    if not self._alvo_em_transicao_sombria(alvo)
                ]
                resultado = None
                
                # Verifica se o método atualizar aceita alvos
                if hasattr(area, 'atualizar'):
                    import inspect
                    sig = inspect.signature(area.atualizar)
                    if len(sig.parameters) > 1:
                        resultado = area.atualizar(dt, alvos_area)
                    else:
                        area.atualizar(dt)
                
                # Processa resultados especiais
                if resultado:
                    for res in resultado:
                        if res.get("nova_onda"):
                            # Cada pulso é uma área de impacto isolada, mas
                            # preserva o contrato da skill original.
                            from neural_fights.core.combat import AreaEffect

                            nova = AreaEffect(
                                area.nome,
                                res["x"],
                                res["y"],
                                area.dono,
                                subefeito=True,
                            )
                            nova.ondas = 1
                            nova.onda_atual = 1
                            nova.meteoros = 0
                            nova.pilares = 0
                            nova.pilares_spawned = True
                            nova.delay = 0.0
                            nova.delay_total = 0.0
                            nova.ativado = True
                            nova.raio = res.get("raio", area.raio * 1.5)
                            nova.raio_atual = nova.raio
                            nova.dano = res.get("dano", area.dano * 0.7)
                            nova.dano_por_segundo = 0.0
                            nova.tipo_efeito = area.tipo_efeito
                            nova.efeito2 = area.efeito2
                            nova.ground = area.ground
                            nova.fonte_impacto = res.get("fonte_impacto", object())
                            nova.ignorar_invencibilidade = True
                            novas_areas.append(nova)
                        
                        elif res.get("meteoro"):
                            # Cria meteoro caindo
                            from neural_fights.core.combat import AreaEffect
                            meteoro = AreaEffect(
                                area.nome,
                                res["x"],
                                res["y"],
                                area.dono,
                                subefeito=True,
                            )
                            meteoro.ondas = 1
                            meteoro.onda_atual = 1
                            meteoro.meteoros = 0
                            meteoro.pilares = 0
                            meteoro.pilares_spawned = True
                            meteoro.delay = 0.0
                            meteoro.delay_total = 0.0
                            meteoro.ativado = True
                            meteoro.raio = res.get("raio", area.raio_meteoro)
                            meteoro.raio_atual = meteoro.raio
                            meteoro.dano = res.get("dano", area.dano_meteoro)
                            meteoro.dano_por_segundo = 0.0
                            meteoro.tipo_efeito = area.tipo_efeito
                            meteoro.efeito2 = area.efeito2
                            meteoro.elemento = area.elemento
                            meteoro.ground = area.ground
                            meteoro.fonte_impacto = res.get("fonte_impacto", object())
                            meteoro.ignorar_invencibilidade = True
                            novas_areas.append(meteoro)
                            # Efeito visual
                            self.impact_flashes.append(ImpactFlash(res["x"] * PPM, res["y"] * PPM, (255, 100, 50), 2.0, "explosion"))
                            self.shockwaves.append(Shockwave(res["x"] * PPM, res["y"] * PPM, (255, 100, 50), tamanho=2.5))
                            self._spawn_particulas_efeito(res["x"] * PPM, res["y"] * PPM, "FOGO")

                        elif res.get("pilar"):
                            from neural_fights.core.combat import AreaEffect

                            pilar = AreaEffect(
                                area.nome,
                                res["x"],
                                res["y"],
                                area.dono,
                                subefeito=True,
                            )
                            pilar.pilares = 0
                            pilar.pilares_spawned = True
                            pilar.posicoes_pilares = []
                            pilar.delay = 0.0
                            pilar.ativado = True
                            pilar.ativo = True
                            pilar.raio = res["raio"]
                            pilar.raio_atual = res["raio"]
                            pilar.dano = res["dano"]
                            pilar.tipo_efeito = area.tipo_efeito
                            pilar.elemento = area.elemento
                            pilar.ground = area.ground
                            pilar.fonte_impacto = area.fonte_impacto
                            novas_areas.append(pilar)
                            self.impact_flashes.append(
                                ImpactFlash(
                                    res["x"] * PPM,
                                    res["y"] * PPM,
                                    area.cor,
                                    1.5,
                                    "magic",
                                )
                            )
                        
                        elif res.get("pull"):
                            # Aplica força de puxão no alvo
                            alvo = res["alvo"]
                            forca = res.get("forca", 5.0)
                            dx = area.x - alvo.pos[0]
                            dy = area.y - alvo.pos[1]
                            dist = math.hypot(dx, dy) or 1
                            # Aplica velocidade em direção ao centro
                            if hasattr(alvo, 'vel'):
                                alvo.vel[0] += (dx / dist) * forca * dt
                                alvo.vel[1] += (dy / dist) * forca * dt
                        
                        elif res.get("dot_tick") or res.get("status_stack"):
                            resultados_periodicos.append(res)
                
                if (
                    area.ativo
                    or getattr(area, "teve_tempo_ativo_no_frame", False)
                ) and getattr(area, 'ativado', True):
                    # Verifica colisão com alvos
                    for alvo in [self.p1, self.p2]:
                        if (
                            (alvo == area.dono and not area.afeta_caster)
                            or alvo in area.alvos_atingidos
                            or self._alvo_em_transicao_sombria(alvo)
                        ):
                            continue
                        imune_ground = getattr(alvo, "esta_imune_ground", None)
                        if area.ground and callable(imune_ground) and imune_ground():
                            continue
                        alvo_x, alvo_y = self._posicao_alvo_combate(alvo)
                        dx = alvo_x - area.x
                        dy = alvo_y - area.y
                        dist = math.hypot(dx, dy)
                        if self._area_colide_alvo(area, alvo):
                            area.alvos_atingidos.add(alvo)
                            
                            # === ÁUDIO v10.0 - SOM DE ÁREA ===
                            if self.audio:
                                listener_x = self.cam.x / PPM
                                skill_name = getattr(area, 'nome_skill', '')
                                self.audio.play_skill("AREA", skill_name, area.x, listener_x, phase="impact")
                            
                            if getattr(area, "dano_precalculado", False):
                                dano = area.dano
                            else:
                                dano = area.dono.get_dano_modificado(area.dano) if hasattr(area.dono, 'get_dano_modificado') else area.dano
                            condicao_cumprida, bonus_condicao = area.verificar_condicao(alvo)
                            dano *= bonus_condicao
                            tipo_impacto = area.sortear_efeito_principal()
                            kwargs_impacto = {
                                "atacante": area.dono,
                                "fonte_impacto": area.fonte_impacto,
                                "metadata_impacto": criar_metadata_impacto(area),
                                "ignorar_invencibilidade": getattr(
                                    area,
                                    "ignorar_invencibilidade",
                                    False,
                                ),
                                "duracao_efeito": (
                                    area.duracao_charme or None
                                    if tipo_impacto == "CHARME"
                                    else area.duracao_stop or None
                                    if tipo_impacto == "TEMPO_PARADO"
                                    else None
                                ),
                            }
                            resolver_impacto = getattr(alvo, "resolver_impacto", None)
                            if callable(resolver_impacto):
                                impacto = resolver_impacto(
                                    dano,
                                    dx/(dist or 1),
                                    dy/(dist or 1),
                                    tipo_impacto,
                                    **kwargs_impacto,
                                )
                                morreu = impacto.morreu
                                dano_aplicado = impacto.dano
                                impacto_aplicado = impacto.atingiu
                            else:
                                morreu = alvo.tomar_dano(
                                    dano,
                                    dx/(dist or 1),
                                    dy/(dist or 1),
                                    tipo_impacto,
                                    **kwargs_impacto,
                                )
                                dano_aplicado = getattr(alvo, "ultimo_dano_recebido", dano)
                                impacto_aplicado = getattr(alvo, 'invencivel_timer', 0.0) > 0.0
                            # tomar_dano já aplica o efeito principal. Aqui entram
                            # apenas os metadados adicionais da área e efeito2,
                            # desde que o impacto não tenha sido negado.
                            if impacto_aplicado:
                                area.aplicar_efeitos_alvo(
                                    alvo,
                                    aplicar_efeito_principal=False,
                                )
                                if area.lifesteal > 0.0 and dano_aplicado > 0.0:
                                    receber_cura = getattr(
                                        area.dono,
                                        "receber_cura",
                                        None,
                                    )
                                    if callable(receber_cura):
                                        cura_real = receber_cura(
                                            dano_aplicado * area.lifesteal
                                        )
                                        if cura_real > 0.0:
                                            self.textos.append(FloatingText(
                                                area.dono.pos[0] * PPM,
                                                area.dono.pos[1] * PPM - 30,
                                                f"+{int(cura_real)}",
                                                (200, 100, 200),
                                                16,
                                            ))
                                if area.remove_congelamento and condicao_cumprida:
                                    remover_congelamento = getattr(
                                        alvo,
                                        "remover_congelamento",
                                        None,
                                    )
                                    if callable(remover_congelamento) and remover_congelamento():
                                        self.textos.append(FloatingText(
                                            alvo.pos[0] * PPM,
                                            alvo.pos[1] * PPM - 60,
                                            "SHATTER!",
                                            (180, 220, 255),
                                            24,
                                        ))
                                if area.forca_empurrao > 0 and hasattr(alvo, "vel"):
                                    alvo.vel[0] += dx / (dist or 1) * area.forca_empurrao
                                    alvo.vel[1] += dy / (dist or 1) * area.forca_empurrao
                            if morreu:
                                self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                            elif impacto_aplicado:
                                cor_txt = self._get_cor_efeito(tipo_impacto)
                                self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 30, int(dano_aplicado), cor_txt))

                for res in resultados_periodicos:
                    self._aplicar_resultado_periodico_area(area, res)
            
            # Adiciona novas áreas criadas por ondas/meteoros
            self.areas.extend(novas_areas)
            self.areas = [a for a in self.areas if a.ativo]

    def _atualizar_beams(self, dt):
        """Atualiza beams instantaneos e encadeamentos."""
        if hasattr(self, 'beams'):
            novos_beams = []
            for beam in self.beams:
                beam.atualizar(dt)
                if beam.ativo and not beam.hit_aplicado:
                    alvo = getattr(beam, "alvo_forcado", None)
                    if alvo is None:
                        alvo = self.p2 if beam.dono == self.p1 else self.p1
                    if self._alvo_em_transicao_sombria(alvo):
                        continue
                    # Verifica se beam cruza com alvo
                    if self._beam_colide_alvo(beam, alvo):
                        beam.hit_aplicado = True
                        
                        # === ÁUDIO v10.0 - SOM DE BEAM ===
                        if self.audio:
                            listener_x = self.cam.x / PPM
                            skill_name = getattr(beam, 'nome', '')
                            self.audio.play_skill("BEAM", skill_name, beam.dono.pos[0], listener_x, phase="impact")

                        dano = beam.dono.get_dano_modificado(beam.dano) if hasattr(beam.dono, 'get_dano_modificado') else beam.dano
                        pos_alvo = self._posicao_alvo_combate(alvo)
                        dx = pos_alvo[0] - beam.x1
                        dy = pos_alvo[1] - beam.y1
                        dist = math.hypot(dx, dy) or 1
                        resolver_impacto = getattr(alvo, "resolver_impacto", None)
                        if callable(resolver_impacto):
                            impacto = resolver_impacto(
                                dano,
                                dx/dist,
                                dy/dist,
                                beam.tipo_efeito,
                                atacante=beam.dono,
                                fonte_impacto=beam,
                                metadata_impacto=criar_metadata_impacto(beam),
                            )
                            morreu = impacto.morreu
                            dano_aplicado = impacto.dano
                            impacto_aplicado = impacto.atingiu
                        else:
                            alvo.tomar_dano(dano)
                            morreu = not getattr(alvo, "ativo", True)
                            dano_aplicado = dano
                            impacto_aplicado = True
                        if morreu:
                            self.textos.append(FloatingText(pos_alvo[0]*PPM, pos_alvo[1]*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                        elif impacto_aplicado:
                            self.textos.append(FloatingText(pos_alvo[0]*PPM, pos_alvo[1]*PPM - 30, int(dano_aplicado), (255, 255, 100)))
                            self.cam.aplicar_shake(8.0, 0.1)
                        if impacto_aplicado:
                            salto = beam.criar_salto(
                                alvo,
                                self._obter_alvos_hostis(
                                    beam.dono,
                                    incluir_summons=True,
                                ),
                            )
                            if salto is not None:
                                novos_beams.append(salto)
            self.beams.extend(novos_beams)
            self.beams = [b for b in self.beams if b.ativo]

    def _atualizar_summons(self, dt):
        """Atualiza invocacoes e resolve seus ataques."""
        if hasattr(self, 'summons'):
            for summon in self.summons:
                alvos = [
                    alvo
                    for alvo in (self.p1, self.p2)
                    if not self._alvo_em_transicao_sombria(alvo)
                ]
                resultados = summon.atualizar(dt, alvos)
                
                for res in resultados:
                    if res.get("tipo") == "ataque":
                        alvo = res["alvo"]
                        dano = res["dano"]
                        if not res.get("dano_precalculado", False):
                            modificar = getattr(
                                summon.dono,
                                "get_dano_modificado",
                                None,
                            )
                            if callable(modificar):
                                dano = modificar(dano)
                        morreu = alvo.tomar_dano(
                            dano,
                            0,
                            0,
                            summon.tipo_efeito,
                            atacante=summon.dono,
                            fonte_impacto=res.get("fonte_impacto", object()),
                            metadata_impacto=criar_metadata_impacto(summon),
                        )
                        dano_aplicado = getattr(alvo, "ultimo_dano_recebido", dano)
                        if morreu:
                            self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                        else:
                            self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 30, int(dano_aplicado), summon.cor))
                    
                    elif res.get("tipo") == "aura":
                        alvo = res["alvo"]
                        dano = res["dano"]
                        modificar = getattr(
                            summon.dono,
                            "get_dano_modificado",
                            None,
                        )
                        if callable(modificar):
                            dano = modificar(dano)
                        alvo.tomar_dano(
                            dano,
                            0,
                            0,
                            summon.tipo_efeito,
                            atacante=summon.dono,
                            fonte_impacto=res.get("fonte_impacto", object()),
                            ignorar_recuperacao_impacto=True,
                            gerar_recuperacao_impacto=False,
                            metadata_impacto=criar_metadata_impacto(summon),
                        )
                    
                    elif res.get("revive"):
                        # Fenix reviveu!
                        self.textos.append(FloatingText(res["x"]*PPM, res["y"]*PPM - 30, "REVIVE!", (255, 200, 50), 28))
                        self._spawn_particulas_efeito(res["x"]*PPM, res["y"]*PPM, "FOGO")
            
            self.summons = [s for s in self.summons if s.ativo]

    def _atualizar_traps(self, dt):
        """Atualiza armadilhas e estruturas posicionadas na arena."""
        if hasattr(self, 'traps'):
            for trap in self.traps:
                trap.atualizar(dt)
                
                # Verifica colisão com lutadores
                if trap.bloqueia_movimento:
                    for lutador in [self.p1, self.p2]:
                        if lutador == trap.dono:
                            continue
                        if self._alvo_em_transicao_sombria(lutador):
                            continue
                        imune_ground = getattr(lutador, "esta_imune_ground", None)
                        if trap.ground and callable(imune_ground) and imune_ground():
                            continue
                        if trap.colidir_ponto(lutador.pos[0], lutador.pos[1]):
                            # Empurra para fora
                            dx = lutador.pos[0] - trap.x
                            dy = lutador.pos[1] - trap.y
                            dist = math.hypot(dx, dy) or 1
                            lutador.pos[0] = trap.x + (dx / dist) * (trap.largura / 2 + 0.5)
                            lutador.pos[1] = trap.y + (dy / dist) * (trap.altura / 2 + 0.5)
                            
                            # Dano de contato
                            if trap.dano_contato > 0:
                                dano_trap = trap.dano_contato * dt
                                modificar = getattr(
                                    trap.dono,
                                    "get_dano_modificado",
                                    None,
                                )
                                if callable(modificar):
                                    dano_trap = modificar(dano_trap)
                                lutador.tomar_dano(
                                    dano_trap,
                                    0,
                                    0,
                                    trap.efeito_contato or "NORMAL",
                                    atacante=trap.dono,
                                    fonte_impacto=object(),
                                    ignorar_recuperacao_impacto=True,
                                    gerar_recuperacao_impacto=False,
                                    metadata_impacto=criar_metadata_impacto(trap),
                                )
            
            self.traps = [t for t in self.traps if t.ativo]

    def _atualizar_transformacoes(self, dt):
        """Atualiza transformacoes ativas dos lutadores."""
        for lutador in [self.p1, self.p2]:
            if hasattr(lutador, 'transformacao_ativa') and lutador.transformacao_ativa:
                transform = lutador.transformacao_ativa
                alvos = [
                    alvo
                    for alvo in (self.p1, self.p2)
                    if not self._alvo_em_transicao_sombria(alvo)
                ]
                resultados = transform.atualizar(dt, alvos)
                
                for res in resultados:
                    if res.get("tipo") == "contato":
                        alvo = res["alvo"]
                        dano = res["dano"]
                        modificar = getattr(
                            lutador,
                            "get_dano_modificado",
                            None,
                        )
                        if callable(modificar):
                            dano = modificar(dano)
                        alvo.tomar_dano(
                            dano,
                            0,
                            0,
                            "NORMAL",
                            atacante=lutador,
                            fonte_impacto=res.get("fonte_impacto", object()),
                            ignorar_recuperacao_impacto=True,
                            gerar_recuperacao_impacto=False,
                            metadata_impacto=criar_metadata_impacto(transform),
                        )
                    elif res.get("tipo") == "slow":
                        alvo = res["alvo"]
                        fator = max(0.01, res["fator"])
                        alvo._aplicar_efeito_status(
                            "LENTO",
                            duracao=res.get("duracao", 0.2),
                            intensidade=0.5 / fator,
                        )
                
                if not transform.ativo:
                    lutador.transformacao_ativa = None

    def _atualizar_canalizacoes(self, dt):
        """Avanca canalizacoes, aplica seus efeitos e sincroniza a vida visual."""
        for lutador in [self.p1, self.p2]:
            if hasattr(lutador, 'channel_ativo') and lutador.channel_ativo:
                channel = lutador.channel_ativo
                alvos = [
                    alvo
                    for alvo in (self.p1, self.p2)
                    if not self._alvo_em_transicao_sombria(alvo)
                ]
                resultados = channel.atualizar(dt, alvos)
                
                for res in resultados:
                    if res.get("tipo") == "cura":
                        valor = res["valor"]
                        self.textos.append(FloatingText(lutador.pos[0]*PPM, lutador.pos[1]*PPM - 30, f"+{int(valor)}", (100, 255, 150), 14))
                    
                    elif res.get("tipo") == "impacto":
                        impacto = res.get("impacto")
                        if impacto is None or not impacto.atingiu:
                            continue
                        alvo = res["alvo"]
                        if impacto.morreu:
                            self.textos.append(FloatingText(
                                alvo.pos[0] * PPM,
                                alvo.pos[1] * PPM - 50,
                                "FATAL!",
                                VERMELHO_SANGUE,
                                40,
                            ))
                        else:
                            cor = self._get_cor_efeito(res.get("efeito", "NORMAL"))
                            self.textos.append(FloatingText(
                                alvo.pos[0] * PPM,
                                alvo.pos[1] * PPM - 30,
                                int(impacto.dano),
                                cor,
                                12,
                            ))

                    elif res.get("tipo") == "dano":
                        alvo = res["alvo"]
                        dano = res["dano"]
                        efeito = res.get("efeito", "NORMAL")
                        
                        morreu = alvo.tomar_dano(
                            dano, 0, 0, efeito, atacante=lutador
                        )
                        dano_aplicado = getattr(alvo, "ultimo_dano_recebido", dano)
                        if morreu:
                            self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 50, "FATAL!", VERMELHO_SANGUE, 40))
                        else:
                            cor = self._get_cor_efeito(efeito)
                            self.textos.append(FloatingText(alvo.pos[0]*PPM, alvo.pos[1]*PPM - 30, int(dano_aplicado), cor, 12))
                
                if not channel.ativo:
                    lutador.channel_ativo = None

        legacy_finished = (
            not hasattr(self, "round_finalizado")
            and bool(getattr(self, "vencedor", None))
        )
        if not getattr(self, "round_finalizado", False) and not legacy_finished:
            # Atualiza Sistema de Coreografia v5.0
            if self.choreographer:
                momento_anterior = self.choreographer.momento_atual
                self.choreographer.update(dt)
                
                # === SWORD CLASH v6.1 - Detecta início do momento CLASH ===
                if self.choreographer.momento_atual == "CLASH" and momento_anterior != "CLASH":
                    self._executar_sword_clash()
            
            self._atualizar_lutadores(dt)
            
            # === ATUALIZA COOLDOWNS DE SOM DE PAREDE ===
            if hasattr(self, '_wall_sound_cooldown'):
                for lutador_id in list(self._wall_sound_cooldown.keys()):
                    self._wall_sound_cooldown[lutador_id] = max(0, self._wall_sound_cooldown[lutador_id] - dt)
            
            # === APLICA LIMITES DA ARENA v9.0 ===
            if self.arena:
                # Aplica colisão com paredes para ambos os lutadores
                # Retorna intensidade do impacto (0.0 se apenas deslizando)
                p1_impacto = (
                    0.0
                    if self._alvo_em_transicao_sombria(self.p1)
                    else self.arena.aplicar_limites(self.p1, dt)
                )
                p2_impacto = (
                    0.0
                    if self._alvo_em_transicao_sombria(self.p2)
                    else self.arena.aplicar_limites(self.p2, dt)
                )
                
                # Debug apenas para impactos reais
                if p1_impacto > 0 or p2_impacto > 0:
                    logger.debug(
                        "Colisao: p1_impacto=%.1f p2_impacto=%.1f",
                        p1_impacto,
                        p2_impacto,
                    )
                
                # Efeitos visuais de colisão com parede (apenas impactos reais)
                if p1_impacto > 0:
                    self._criar_efeito_colisao_parede(self.p1, p1_impacto)
                if p2_impacto > 0:
                    self._criar_efeito_colisao_parede(self.p2, p2_impacto)
                
                # Limpa colisões antigas da arena
                self.arena.limpar_colisoes()
            
            self.resolver_fisica_corpos(dt)
            self.verificar_colisoes_combate()
            if self._detectar_resultado_round():
                return
            self.atualizar_rastros()
            self.vida_visual_p1 += (self.p1.vida - self.vida_visual_p1) * 5 * dt
            self.vida_visual_p2 += (self.p2.vida - self.vida_visual_p2) * 5 * dt
            
            # === DETECTA EVENTOS DE MOVIMENTO v8.0 ===
            self._detectar_eventos_movimento()

    def _atualizar_animacoes(self, dt):
        """Dispara animacoes de movimento/ataque e mantem os decals sob limite."""
        if self.movement_anims:
            self.movement_anims.update(dt)
        
        # === ATUALIZA ANIMAÇÕES DE ATAQUE v8.0 IMPACT EDITION ===
        if self.attack_anims:
            self.attack_anims.update(dt)
        
        for p in self.particulas[:]:
            p.atualizar(dt)
            if p.vida <= 0: 
                if p.cor == VERMELHO_SANGUE and random.random() < 0.3:
                    self.decals.append(Decal(p.x, p.y, p.tamanho * 2, SANGUE_ESCURO))
                self.particulas.remove(p)
        if len(self.decals) > 100: self.decals.pop(0)


    def _criar_efeito_colisao_parede(self, lutador, intensidade_colisao: float):
        """
        Cria efeitos visuais e sonoros quando lutador colide com parede da arena.
        
        Args:
            lutador: O lutador que colidiu
            intensidade_colisao: Intensidade do impacto (velocidade perpendicular à parede)
                                 Valores típicos: 2-5 leve, 5-10 médio, 10-20+ forte
        
        BUGFIX v2.0:
        - Threshold de som reduzido de 8 → 3 (impactos leves também tocam)
        - Fallback para 'wall_hit' caso wall_impact_light/heavy não existam
        - Cooldown reduzido de 0.3s → 0.2s para ser mais responsivo
        - Limiar de efeitos visuais reduzido de 5 → 2 (mais responsivo)
        """
        # Limiar mínimo para processar a colisão (muito leve = deslizamento)
        if intensidade_colisao < 2:
            return
        
        # === COOLDOWN DE SOM POR LUTADOR ===
        lutador_id = id(lutador)
        if not hasattr(self, '_wall_sound_cooldown'):
            self._wall_sound_cooldown = {}
        
        sound_on_cooldown = self._wall_sound_cooldown.get(lutador_id, 0) > 0
        
        # === ÁUDIO - BUGFIX: threshold reduzido + fallback de som ===
        # BUG ANTERIOR: threshold de 8 era alto demais, maioria dos impactos eram silenciosos
        # CORREÇÃO: qualquer impacto >= 3 toca som; usa fallback se sons específicos não carregados
        if self.audio and self.audio.enabled and intensidade_colisao >= 2 and not sound_on_cooldown:
            # Volume: intensidade 3 = 0.3, intensidade 15+ = 1.0
            volume = 0.3 + (intensidade_colisao - 3) * 0.058
            volume = max(0.3, min(1.0, volume))
            
            # Tenta tocar som específico, com fallback em cadeia
            som_tocado = False
            if intensidade_colisao > 12:
                # Impacto muito forte
                for nome_som in ["wall_impact_heavy", "wall_impact_light", "wall_hit"]:
                    if nome_som in self.audio.sounds:
                        self.audio.play(nome_som, volume=volume)
                        som_tocado = True
                        break
            elif intensidade_colisao > 5:
                # Impacto médio
                for nome_som in ["wall_impact_light", "wall_hit", "wall_impact_heavy"]:
                    if nome_som in self.audio.sounds:
                        self.audio.play(nome_som, volume=volume * 0.8)
                        som_tocado = True
                        break
            else:
                # Impacto leve
                for nome_som in ["wall_hit", "wall_impact_light"]:
                    if nome_som in self.audio.sounds:
                        self.audio.play(nome_som, volume=volume * 0.55)
                        som_tocado = True
                        break
            
            if som_tocado:
                # Cooldown reduzido: 0.2s (era 0.3s)
                self._wall_sound_cooldown[lutador_id] = 0.2
                logger.debug(
                    "Audio de parede: intensidade=%.1f volume=%.2f",
                    intensidade_colisao,
                    volume,
                )
            else:
                logger.debug(
                    "Audio de parede indisponivel: intensidade=%.1f",
                    intensidade_colisao,
                )
        
        # Só cria efeitos visuais se intensidade suficiente
        if intensidade_colisao < 5:
            return
        
        # Intensidade normalizada para efeitos visuais (0.0 a 1.0)
        intensidade = min(1.0, intensidade_colisao / 15)
        
        # Partículas de poeira/impacto
        x_px = lutador.pos[0] * PPM
        y_px = lutador.pos[1] * PPM
        cor_parede = self.arena.config.cor_borda if self.arena else (100, 100, 120)
        
        num_particulas = int(5 + intensidade * 10)
        for _ in range(num_particulas):
            angulo = random.uniform(0, math.pi * 2)
            vel = random.uniform(30, 80) * intensidade
            # Particula(x, y, cor, vel_x, vel_y, tamanho, vida_util)
            self.particulas.append(Particula(
                x_px + random.uniform(-15, 15),
                y_px + random.uniform(-15, 15),
                cor_parede,
                math.cos(angulo) * vel,
                math.sin(angulo) * vel,
                random.uniform(3, 6),
                random.uniform(0.2, 0.5)
            ))
        
        # Shake da câmera proporcional à intensidade
        if intensidade > 0.5:
            self.cam.aplicar_shake(intensidade * 8, 0.1)
        
        # Flash de impacto se muito forte
        if intensidade > 0.7:
            self.impact_flashes.append(ImpactFlash(x_px, y_px, cor_parede, intensidade * 0.8, "physical"))

    def _get_cor_efeito(self, efeito):
        """Retorna cor do texto baseado no tipo de efeito - v2.0 COLOSSAL"""
        cores = {
            # Base
            "NORMAL": BRANCO,
            # Fogo
            "FOGO": (255, 100, 0),
            "QUEIMAR": (255, 150, 50),
            "QUEIMANDO": (255, 120, 20),
            # Gelo
            "GELO": (150, 220, 255),
            "CONGELAR": (100, 200, 255),
            "CONGELADO": (180, 230, 255),
            "LENTO": (150, 200, 255),
            # Natureza/Veneno
            "VENENO": (100, 255, 100),
            "ENVENENADO": (80, 220, 80),
            "NATUREZA": (100, 200, 50),
            # Sangue
            "SANGRAMENTO": (180, 0, 30),
            "SANGRANDO": (200, 30, 30),
            "SANGUE": (180, 0, 50),
            # Raio
            "RAIO": (255, 255, 100),
            "PARALISIA": (255, 255, 150),
            # Trevas
            "TREVAS": (150, 0, 200),
            "DRENAR": (80, 0, 120),
            "MALDITO": (100, 0, 150),
            "NECROSE": (50, 50, 50),
            # Luz
            "LUZ": (255, 255, 220),
            "CEGO": (255, 255, 200),
            # Arcano
            "ARCANO": (150, 100, 255),
            "SILENCIADO": (180, 150, 255),
            # Tempo
            "TEMPO": (200, 180, 255),
            "TEMPO_PARADO": (220, 200, 255),
            # Gravitação
            "GRAVITACAO": (100, 50, 150),
            "PUXADO": (120, 70, 180),
            "VORTEX": (80, 30, 130),
            # Caos
            "CAOS": (255, 100, 200),
            # CC
            "ATORDOAR": (255, 255, 150),
            "ATORDOADO": (255, 255, 100),
            "ENRAIZADO": (139, 90, 43),
            "MEDO": (150, 0, 150),
            "CHARME": (255, 150, 200),
            "SONO": (100, 100, 200),
            "KNOCK_UP": (200, 200, 255),
            # Debuffs
            "FRACO": (150, 150, 150),
            "VULNERAVEL": (255, 150, 150),
            "EXAUSTO": (100, 100, 100),
            "MARCADO": (255, 200, 50),
            "EXPOSTO": (255, 180, 100),
            "CORROENDO": (150, 100, 50),
            # Buffs
            "ACELERADO": (255, 200, 100),
            "FORTALECIDO": (255, 150, 50),
            "BLINDADO": (200, 200, 200),
            "REGENERANDO": (100, 255, 100),
            "ESCUDO_MAGICO": (150, 150, 255),
            "FURIA": (255, 50, 50),
            "INVISIVEL": (200, 200, 200),
            "INTANGIVEL": (180, 180, 255),
            "DETERMINADO": (255, 200, 100),
            "ABENÇOADO": (255, 255, 200),
            "IMORTAL": (255, 215, 0),
            # Especiais
            "EMPURRAO": (200, 200, 255),
            "EXPLOSAO": (255, 200, 50),
            "BOMBA_RELOGIO": (255, 150, 0),
            "POSSESSO": (100, 0, 100),
            "LINK_ALMA": (255, 100, 255),
            "ESPELHADO": (200, 200, 255),
            "PERFURAR": (200, 200, 200),
        }
        return cores.get(efeito, BRANCO)
    
    def _spawn_particulas_efeito(self, x, y, efeito):
        """Spawna partículas específicas do efeito - v2.0 COLOSSAL"""
        cores_part = {
            # Fogo
            "QUEIMAR": (255, 100, 0),
            "QUEIMANDO": (255, 120, 20),
            "FOGO": (255, 150, 50),
            # Gelo
            "CONGELAR": (150, 220, 255),
            "CONGELADO": (180, 240, 255),
            "LENTO": (150, 200, 255),
            "GELO": (100, 200, 255),
            # Natureza/Veneno
            "VENENO": (100, 255, 100),
            "ENVENENADO": (80, 220, 80),
            "NATUREZA": (100, 200, 50),
            # Sangue
            "SANGRAMENTO": VERMELHO_SANGUE,
            "SANGRANDO": (200, 30, 30),
            "SANGUE": (180, 0, 50),
            # Raio
            "RAIO": (255, 255, 100),
            "PARALISIA": (255, 255, 150),
            # Trevas
            "TREVAS": (100, 0, 150),
            "DRENAR": (80, 0, 120),
            "MALDITO": (100, 0, 150),
            "NECROSE": (50, 50, 50),
            # Luz
            "LUZ": (255, 255, 220),
            "CEGO": (255, 255, 200),
            # Arcano
            "ARCANO": (150, 100, 255),
            "SILENCIADO": (180, 150, 255),
            # Tempo
            "TEMPO": (200, 180, 255),
            "TEMPO_PARADO": (220, 200, 255),
            # Gravitação
            "GRAVITACAO": (100, 50, 150),
            "PUXADO": (120, 70, 180),
            "VORTEX": (80, 30, 130),
            # Caos
            "CAOS": (255, 100, 200),
            # CC
            "ATORDOAR": (255, 255, 100),
            "ATORDOADO": (255, 255, 100),
            "ENRAIZADO": (139, 90, 43),
            "KNOCK_UP": (200, 200, 255),
            # Especiais
            "EXPLOSAO": (255, 200, 50),
            "BOMBA_RELOGIO": (255, 150, 0),
        }
        cor = cores_part.get(efeito)
        if cor:
            # Quantidade de partículas varia por tipo
            qtd = 8
            if efeito in ["EXPLOSAO", "FOGO", "QUEIMANDO"]:
                qtd = 15
            elif efeito in ["RAIO", "PARALISIA"]:
                qtd = 12
            elif efeito in ["VORTEX", "GRAVITACAO"]:
                qtd = 20
            elif efeito in ["CAOS"]:
                qtd = 18
            
            for _ in range(qtd):
                vx = random.uniform(-8, 8)
                vy = random.uniform(-8, 8)
                tamanho = random.randint(3, 7)
                vida = random.uniform(0.4, 0.8)
                self.particulas.append(Particula(x, y, cor, vx, vy, tamanho, vida))
    
    @staticmethod
    def _alvo_em_transicao_sombria(alvo):
        """Indica que o alvo está fora do espaço físico durante um portal."""

        verificar = getattr(alvo, "em_transicao_sombria", None)
        return bool(callable(verificar) and verificar())

    @staticmethod
    def _posicao_alvo_combate(alvo):
        pos = getattr(alvo, "pos", None)
        if pos is not None and len(pos) >= 2:
            return float(pos[0]), float(pos[1])
        return float(alvo.x), float(alvo.y)

    @classmethod
    def _area_colide_alvo(cls, area, alvo):
        """Aceita volumes circulares e o corredor varrido por um dash."""

        alvo_x, alvo_y = cls._posicao_alvo_combate(alvo)
        raio_alvo = float(getattr(alvo, "raio_fisico", 0.5))
        segmento = getattr(area, "segmento_impacto", None)
        if segmento is not None:
            raio = raio_alvo + float(getattr(area, "raio_segmento", 0.5))
            if intersect_line_circle(segmento[0], segmento[1], (alvo_x, alvo_y), raio):
                return True
            # ``intersect_line_circle`` não considera um segmento degenerado.
            if segmento[0] == segmento[1]:
                return math.hypot(
                    alvo_x - segmento[0][0],
                    alvo_y - segmento[0][1],
                ) <= raio
            return False
        return math.hypot(alvo_x - area.x, alvo_y - area.y) < (
            area.raio_atual + raio_alvo
        )

    def _obter_alvos_hostis(self, dono, incluir_summons=False):
        """Lista alvos disponíveis para chain/contágio sem duplicar entidades."""
        candidatos = [self.p1, self.p2]
        candidatos.extend(getattr(self, "alvos_adicionais", ()))
        if incluir_summons:
            candidatos.extend(getattr(self, "summons", ()))

        hostis = []
        vistos = set()
        for candidato in candidatos:
            if candidato is None or candidato is dono or id(candidato) in vistos:
                continue
            if getattr(candidato, "morto", False) or not getattr(candidato, "ativo", True):
                continue
            if self._alvo_em_transicao_sombria(candidato):
                continue
            if getattr(candidato, "dono", None) is dono:
                continue
            vistos.add(id(candidato))
            hostis.append(candidato)
        return hostis

    def _modificador_protecao_summon(self, alvo):
        """Retorna a maior proteção explícita de uma invocação aliada."""

        reducao = 0.0
        for summon in getattr(self, "summons", ()):
            protege = getattr(summon, "protege", None)
            if callable(protege) and protege(alvo):
                reducao = max(
                    reducao,
                    float(getattr(summon, "reducao_dano_protegido", 0.0)),
                )
        return max(0.0, min(1.0, 1.0 - reducao))

    def _beam_colide_alvo(self, beam, alvo):
        """Verifica se um beam colide com um alvo"""
        # Usa colisão linha-círculo
        from neural_fights.core.physics import colisao_linha_circulo
        pt1 = (beam.x1 * PPM, beam.y1 * PPM)
        pt2 = (beam.x2 * PPM, beam.y2 * PPM)
        alvo_x, alvo_y = self._posicao_alvo_combate(alvo)
        centro = (alvo_x * PPM, alvo_y * PPM)
        raio = getattr(alvo, "raio_fisico", 0.5) * PPM
        return colisao_linha_circulo(pt1, pt2, centro, raio)

    # =========================================================================
    # SISTEMA DE DETECÇÃO DE EVENTOS DE MOVIMENTO v8.0
    # =========================================================================
    
    def _detectar_eventos_movimento(self):
        """
        Detecta eventos de movimento para disparar animações apropriadas.
        
        Eventos detectados:
        - Aterrissagem (z era > 0, agora é 0)
        - Pulo (z era 0, agora > 0)
        - Dash (dash_timer aumentou)
        - Knockback (velocidade alta após tomar dano)
        - Recuperação de stagger (stun_timer zerou)
        - Corrida rápida (velocidade alta contínua)
        """
        for lutador in [self.p1, self.p2]:
            if lutador.morto:
                continue
            
            z_atual = getattr(lutador, 'z', 0)
            z_anterior = self._prev_z.get(lutador, 0)
            
            # Posição X para sons posicionais
            pos_x = lutador.pos[0]
            listener_x = (self.p1.pos[0] + self.p2.pos[0]) / 2  # Centro entre lutadores
            
            # === ATERRISSAGEM ===
            # Detecta quando z cai para o chão (aterrissando)
            # Trigger mais cedo: quando z cai de qualquer altura para perto do chão
            if z_anterior > 0.15 and z_atual <= 0.05:
                # Som de aterrissagem
                if self.audio:
                    self.audio.play_movement("land", pos_x, listener_x)
                    logger.debug(
                        "Aterrissagem de %s: z %.2f -> %.2f",
                        lutador.dados.nome,
                        z_anterior,
                        z_atual,
                    )
                # Efeito visual (se disponível)
                if self.movement_anims:
                    vel_queda = abs(getattr(lutador, 'vel_z', 0))
                    self.movement_anims.criar_landing_effect(lutador, vel_queda + 5)
            
            # === PULO ===
            # Detecta quando z começa a subir do chão (iniciando pulo)
            # Threshold baixo: vel_z ~10 * dt ~0.017 = ~0.17 de aumento por frame
            elif z_anterior <= 0.05 and z_atual > 0.1:
                # Som de pulo
                if self.audio:
                    self.audio.play_movement("jump", pos_x, listener_x)
                    logger.debug(
                        "Pulo de %s: z %.2f -> %.2f",
                        lutador.dados.nome,
                        z_anterior,
                        z_atual,
                    )
                # Efeito visual (se disponível)
                if self.movement_anims:
                    self.movement_anims.criar_jump_effect(lutador)
            
            # === DASH ===
            dash_atual = getattr(lutador, 'dash_timer', 0)
            dash_anterior = self._prev_dash.get(lutador, 0)
            
            if dash_atual > dash_anterior and dash_atual > 0.1:
                # Novo dash detectado
                direcao = math.radians(lutador.angulo_olhar)
                
                # Som de dash
                if self.audio:
                    self.audio.play_skill("DASH", "", pos_x, listener_x, phase="cast")
                
                # Efeito visual (se disponível)
                if self.movement_anims:
                    # Determina tipo de dash baseado na ação
                    acao = getattr(lutador.brain, 'acao_atual', "")
                    if acao in ["RECUAR", "FUGIR"]:
                        tipo = MovementType.DASH_BACKWARD
                    elif acao in ["CIRCULAR", "FLANQUEAR"]:
                        tipo = MovementType.DASH_LATERAL
                    else:
                        tipo = MovementType.DASH_FORWARD
                    self.movement_anims.criar_dash_effect(lutador, direcao, tipo)
            
            # === RECUPERAÇÃO DE STAGGER ===
            stagger_atual = getattr(lutador, 'stun_timer', 0) > 0
            stagger_anterior = self._prev_stagger.get(lutador, False)
            
            if stagger_anterior and not stagger_atual:
                # Acabou de se recuperar - efeito visual
                if self.movement_anims:
                    self.movement_anims.criar_recovery_effect(lutador)
            
            # === CORRIDA RÁPIDA ===
            vel_magnitude = math.hypot(lutador.vel[0], lutador.vel[1])
            if vel_magnitude > 12.0 and z_atual <= 0.1 and self.movement_anims:
                # Correndo rápido no chão
                if random.random() < 0.15:  # Não spammar efeitos
                    direcao = math.atan2(lutador.vel[1], lutador.vel[0])
                    self.movement_anims.criar_sprint_effect(lutador, direcao)
            
            # Atualiza estados anteriores
            self._prev_z[lutador] = z_atual
            self._prev_stagger[lutador] = stagger_atual
            self._prev_dash[lutador] = dash_atual
    
    def _criar_knockback_visual(self, lutador, direcao: float, intensidade: float):
        """
        Cria efeitos visuais de knockback.
        Chamado quando um personagem leva um golpe forte.
        """
        if self.movement_anims:
            self.movement_anims.criar_knockback_effect(lutador, direcao, intensidade)

    # =========================================================================
    # SISTEMA DE CLASH DE PROJÉTEIS v7.0
    # =========================================================================
    
    def _verificar_clash_projeteis(self):
        """Verifica colisão entre projéteis de diferentes donos"""
        projs_p1 = [p for p in self.projeteis if p.dono == self.p1 and p.ativo]
        projs_p2 = [p for p in self.projeteis if p.dono == self.p2 and p.ativo]
        
        # Também checa orbes mágicos
        orbes_p1 = []
        orbes_p2 = []
        if hasattr(self.p1, 'buffer_orbes'):
            orbes_p1 = [o for o in self.p1.buffer_orbes if o.ativo and o.estado == "disparando"]
        if hasattr(self.p2, 'buffer_orbes'):
            orbes_p2 = [o for o in self.p2.buffer_orbes if o.ativo and o.estado == "disparando"]
        
        # Combina projéteis e orbes
        todos_p1 = projs_p1 + orbes_p1
        todos_p2 = projs_p2 + orbes_p2
        
        for p1 in todos_p1:
            for p2 in todos_p2:
                if not (getattr(p1, 'ativo', True) and getattr(p2, 'ativo', True)):
                    continue
                
                # Distância entre projéteis
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = math.hypot(dx, dy)
                
                # Raio de colisão (soma dos raios)
                r1 = getattr(p1, 'raio', 0.2)
                r2 = getattr(p2, 'raio', 0.2)
                
                if dist < r1 + r2 + 0.3:  # Margem extra para visual
                    # CLASH DETECTADO!
                    self._executar_clash_magico(p1, p2)
    
    def _executar_clash_magico(self, proj1, proj2):
        """Executa efeito de clash entre dois projéteis/magias"""
        # Desativa ambos
        proj1.ativo = False
        proj2.ativo = False
        
        # Ponto médio do clash
        mx = (proj1.x + proj2.x) / 2
        my = (proj1.y + proj2.y) / 2
        
        # Cores dos projéteis
        cor1 = getattr(proj1, 'cor', (255, 100, 100))
        cor2 = getattr(proj2, 'cor', (100, 100, 255))
        
        # Cria efeito de clash mágico
        self.magic_clashes.append(MagicClash(mx * PPM, my * PPM, cor1, cor2, tamanho=1.5))
        
        # Flash de impacto duplo
        self.impact_flashes.append(ImpactFlash(mx * PPM, my * PPM, cor1, 1.5, "clash"))
        
        # Shockwave grande
        self.shockwaves.append(Shockwave(mx * PPM, my * PPM, BRANCO, tamanho=2.0))
        
        # Texto de CLASH
        self.textos.append(FloatingText(mx * PPM, my * PPM - 40, "CLASH!", AMARELO_FAISCA, 35))
        
        # SOM DE CLASH
        listener_x = (self.p1.pos[0] + self.p2.pos[0]) / 2
        self.audio.play_positional("clash_magic", mx, listener_x, volume=1.0)
        
        # Camera shake e hit stop dramáticos
        self.cam.aplicar_shake(25.0, 0.25)
        self.hit_stop_timer = 0.15
        
        # Partículas extras
        for _ in range(30):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(80, 200)
            cor = random.choice([cor1, cor2])
            self.particulas.append(Particula(
                mx * PPM, my * PPM, cor,
                math.cos(ang) * vel / 60, math.sin(ang) * vel / 60,
                random.randint(4, 8), 0.4
            ))
    
    def _executar_sword_clash(self):
        """Executa efeito de clash de espadas entre dois lutadores (momento cinematográfico)"""
        if not self.p1 or not self.p2:
            return
        
        # === CANCELA OS ATAQUES DE AMBOS (evita que alguém tome dano) ===
        self.p1.atacando = False
        self.p2.atacando = False
        self.p1.timer_animacao = 0
        self.p2.timer_animacao = 0
        # Reseta cooldown de ataque para que possam atacar novamente após o clash
        self.p1.cooldown_ataque = 0.3
        self.p2.cooldown_ataque = 0.3
        # Limpa alvos atingidos para evitar hits fantasmas
        self.p1.alvos_atingidos_neste_ataque.clear()
        self.p2.alvos_atingidos_neste_ataque.clear()
        
        # Ponto médio do clash (entre os dois lutadores)
        mx = (self.p1.pos[0] + self.p2.pos[0]) / 2
        my = (self.p1.pos[1] + self.p2.pos[1]) / 2
        
        # Cores das armas/lutadores
        cor1 = self.p1.dados.cor if hasattr(self.p1, 'dados') and hasattr(self.p1.dados, 'cor') else (255, 180, 80)
        cor2 = self.p2.dados.cor if hasattr(self.p2, 'dados') and hasattr(self.p2.dados, 'cor') else (80, 180, 255)
        
        # === EFEITOS VISUAIS ===
        # Flash de impacto principal
        self.impact_flashes.append(ImpactFlash(mx * PPM, my * PPM, AMARELO_FAISCA, 2.0, "clash"))
        
        # Shockwave dramático
        self.shockwaves.append(Shockwave(mx * PPM, my * PPM, BRANCO, tamanho=2.5))
        
        # Texto épico
        textos_clash = ["CLASH!", "CLANG!", "⚔ CLASH ⚔", "STEEL!", "IMPACTO!"]
        texto = random.choice(textos_clash)
        self.textos.append(FloatingText(mx * PPM, my * PPM - 50, texto, AMARELO_FAISCA, 40))
        
        if self.audio:
            self.audio.play("clash_swords", volume=1.0)
        
        # === CAMERA SHAKE E HIT STOP DRAMÁTICOS ===
        self.cam.aplicar_shake(20.0, 0.3)
        self.hit_stop_timer = 0.2  # Pausa dramática
        
        # === PARTÍCULAS DE FAÍSCAS ===
        for _ in range(40):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(100, 250)
            cor = random.choice([AMARELO_FAISCA, BRANCO, cor1, cor2, (255, 200, 100)])
            self.particulas.append(Particula(
                mx * PPM, my * PPM, cor,
                math.cos(ang) * vel / 60, math.sin(ang) * vel / 60,
                random.randint(3, 7), random.uniform(0.3, 0.6)
            ))
        
        # === EFEITO ADICIONAL - Hit Sparks nas armas ===
        # Direção aleatória para as faíscas
        direcao_faiscas = random.uniform(0, math.pi * 2)
        self.hit_sparks.append(HitSpark(mx * PPM, my * PPM, AMARELO_FAISCA, direcao_faiscas, 1.5))
        
        logger.debug("Clash de espadas em (%.1f, %.1f)", mx, my)
    
    # =========================================================================
    # SISTEMA DE BLOQUEIO E DESVIO v7.0
    # =========================================================================
    
    def _resolver_colisao_projetil_traps(self, proj, origem_x, origem_y):
        """Bloqueia e danifica estruturas antes de atingir um lutador."""

        if not getattr(proj, "ativo", True) or getattr(proj, "cone", False):
            return False
        destino_x = getattr(proj, "x", origem_x)
        destino_y = getattr(proj, "y", origem_y)
        for trap in getattr(self, "traps", ()):
            if (
                not getattr(trap, "ativo", False)
                or not getattr(trap, "bloqueia_projeteis", False)
                or getattr(trap, "dono", None) is getattr(proj, "dono", None)
            ):
                continue
            colidir_segmento = getattr(trap, "colidir_segmento", None)
            colidiu = (
                colidir_segmento(
                    origem_x,
                    origem_y,
                    destino_x,
                    destino_y,
                    getattr(proj, "raio", 0.0),
                )
                if callable(colidir_segmento)
                else trap.colidir_ponto(destino_x, destino_y)
            )
            if not colidiu:
                continue

            dano = max(0.0, float(getattr(proj, "dano", 0.0)))
            dono = getattr(proj, "dono", None)
            if callable(getattr(dono, "get_dano_modificado", None)):
                dano = dono.get_dano_modificado(dano)
            trap.tomar_dano(dano)
            proj.ativo = False
            return True
        return False

    def _verificar_bloqueio_projetil(self, proj, alvo):
        """Verifica se o alvo pode bloquear ou desviar do projétil"""
        if not proj.ativo:
            return False
        # Invocações não executam ações defensivas nem possuem equipamento.
        if not hasattr(alvo, "dados"):
            return False
        
        # Distância do projétil ao alvo
        dx = alvo.pos[0] - proj.x
        dy = alvo.pos[1] - proj.y
        dist = math.hypot(dx, dy)
        
        # Só verifica se projétil está perto
        if dist > alvo.raio_fisico + 1.5:
            return False
        
        # === BLOQUEIO COM ESCUDO ORBITAL ===
        if alvo.dados.arma_obj and "Orbital" in alvo.dados.arma_obj.tipo:
            escudo_info = alvo.get_escudo_info()
            if escudo_info:
                # Verifica se projétil está na área do escudo
                escudo_pos, escudo_raio, escudo_ang, escudo_arco = escudo_info
                dx_e = proj.x * PPM - escudo_pos[0]
                dy_e = proj.y * PPM - escudo_pos[1]
                dist_escudo = math.hypot(dx_e, dy_e)
                
                if dist_escudo < escudo_raio + proj.raio * PPM:
                    # Verifica ângulo
                    ang_proj = math.degrees(math.atan2(dy_e, dx_e))
                    diff_ang = abs(normalizar_angulo(ang_proj - escudo_ang))
                    
                    if diff_ang <= escudo_arco / 2:
                        # BLOQUEADO!
                        self._efeito_bloqueio(proj, alvo, escudo_pos)
                        return True
        
        # === DESVIO COM DASH ===
        if hasattr(alvo, 'dash_timer') and alvo.dash_timer > 0:
            # Durante dash, chance de desviar
            if dist < alvo.raio_fisico + 0.5:
                # Dash evasivo bem-sucedido!
                self._efeito_desvio_dash(proj, alvo)
                return True
        
        # === BLOQUEIO DURANTE ATAQUE (timing perfeito) ===
        if alvo.atacando and alvo.timer_animacao > 0.15:  # Frame inicial do ataque
            if alvo.dados.arma_obj and "Reta" in alvo.dados.arma_obj.tipo:
                # Verifica se arma intercepta projétil
                linha_arma = alvo.get_pos_ponteira_arma()
                if linha_arma:
                    from neural_fights.core.physics import colisao_linha_circulo
                    if colisao_linha_circulo(linha_arma[0], linha_arma[1], 
                                            (proj.x * PPM, proj.y * PPM), 
                                            proj.raio * PPM + 5):
                        # PARRY!
                        self._efeito_parry(proj, alvo)
                        return True
        
        return False
    
    def _efeito_bloqueio(self, proj, bloqueador, pos_escudo):
        """Efeito visual de bloqueio"""
        # === ÁUDIO v10.0 - SOM DE BLOQUEIO ===
        if self.audio:
            self.audio.play_special("shield_block", volume=0.7)
        
        # Direção do impacto
        ang = math.atan2(proj.y * PPM - pos_escudo[1], proj.x * PPM - pos_escudo[0])
        
        # Cor do bloqueador
        cor = (bloqueador.dados.cor_r, bloqueador.dados.cor_g, bloqueador.dados.cor_b)
        
        # Efeito de bloqueio
        self.block_effects.append(BlockEffect(proj.x * PPM, proj.y * PPM, cor, ang))
        
        # Texto
        self.textos.append(FloatingText(proj.x * PPM, proj.y * PPM - 30, "BLOCK!", (100, 200, 255), 22))
        
        # Partículas metálicas
        for _ in range(12):
            vx = math.cos(ang + random.uniform(-0.5, 0.5)) * random.uniform(3, 8)
            vy = math.sin(ang + random.uniform(-0.5, 0.5)) * random.uniform(3, 8)
            self.particulas.append(Particula(proj.x * PPM, proj.y * PPM, AMARELO_FAISCA, vx, vy, 3, 0.3))
        
        # Shake leve
        self.cam.aplicar_shake(8.0, 0.1)
        self.hit_stop_timer = 0.05
    
    def _efeito_desvio_dash(self, proj, desviador):
        """Efeito visual de desvio com dash"""
        # Trail do dash
        if hasattr(desviador, 'pos_historico') and len(desviador.pos_historico) > 2:
            posicoes = [(p[0] * PPM, p[1] * PPM) for p in desviador.pos_historico[-8:]]
            cor = (desviador.dados.cor_r, desviador.dados.cor_g, desviador.dados.cor_b)
            self.dash_trails.append(DashTrail(posicoes, cor))
        
        # Texto
        self.textos.append(FloatingText(desviador.pos[0] * PPM, desviador.pos[1] * PPM - 50, "DODGE!", (150, 255, 150), 24))
        
        # Pequeno slow-mo para drama
        self.time_scale = 0.5
        self.slow_mo_timer = 0.3
    
    def _efeito_parry(self, proj, parryer):
        """Efeito visual de parry (defesa com ataque)"""
        # Flash de impacto especial
        self.impact_flashes.append(ImpactFlash(proj.x * PPM, proj.y * PPM, AMARELO_FAISCA, 1.8, "clash"))
        
        # Texto PARRY!
        self.textos.append(FloatingText(proj.x * PPM, proj.y * PPM - 40, "PARRY!", AMARELO_FAISCA, 28))
        
        # Shockwave dourada
        self.shockwaves.append(Shockwave(proj.x * PPM, proj.y * PPM, AMARELO_FAISCA, tamanho=1.5))
        
        # Hit sparks dramáticas
        ang = math.atan2(proj.y - parryer.pos[1], proj.x - parryer.pos[0])
        self.hit_sparks.append(HitSpark(proj.x * PPM, proj.y * PPM, AMARELO_FAISCA, ang, 1.5))
        
        # Camera e timing
        self.cam.aplicar_shake(15.0, 0.15)
        self.hit_stop_timer = 0.1

    def atualizar_rastros(self):
        for p in [self.p1, self.p2]:
            if p.morto: self.rastros[p] = []; continue
            if p.atacando and p.dados.arma_obj and "Reta" in p.dados.arma_obj.tipo:
                coords = p.get_pos_ponteira_arma()
                if coords: self.rastros[p].append((coords[1], coords[0]))
            else: self.rastros[p] = []
            if len(self.rastros[p]) > 10: self.rastros[p].pop(0)

    def resolver_fisica_corpos(self, dt):
        """Resolve colisão física entre os dois lutadores impedindo sobreposição"""
        p1, p2 = self.p1, self.p2
        if (
            p1.morto
            or p2.morto
            or self._alvo_em_transicao_sombria(p1)
            or self._alvo_em_transicao_sombria(p2)
        ):
            return
        
        # Múltiplas iterações para garantir separação completa
        for _ in range(3):
            # Calcula distância entre centros
            dx = p2.pos[0] - p1.pos[0]
            dy = p2.pos[1] - p1.pos[1]
            dist = math.hypot(dx, dy)
            
            # Soma dos raios (distância mínima permitida)
            soma_raios = p1.raio_fisico + p2.raio_fisico
            
            # Só processa se estiverem se sobrepondo E na mesma altura (Z)
            if dist >= soma_raios or abs(p1.z - p2.z) >= 1.0:
                break  # Não há sobreposição, sai do loop
                
            # Calcula penetração (quanto estão se sobrepondo)
            penetracao = soma_raios - dist
            
            # Vetor normal de separação (de p1 para p2)
            if dist > 0.001:
                nx, ny = dx / dist, dy / dist
            else:
                # Se estiverem exatamente no mesmo ponto, escolhe direção aleatória
                ang = random.uniform(0, math.pi * 2)
                nx, ny = math.cos(ang), math.sin(ang)
            
            # === SEPARAÇÃO FÍSICA INSTANTÂNEA ===
            # Move cada corpo para fora da sobreposição (metade para cada lado)
            separacao = (penetracao / 2.0) + 0.02  # Margem de segurança
            
            p1.pos[0] -= nx * separacao
            p1.pos[1] -= ny * separacao
            p2.pos[0] += nx * separacao
            p2.pos[1] += ny * separacao
        
        # === VELOCIDADE DE REPULSÃO (aplica uma vez) ===
        # Recalcula distância após separação
        dx = p2.pos[0] - p1.pos[0]
        dy = p2.pos[1] - p1.pos[1]
        dist = math.hypot(dx, dy)
        
        # Se ainda estiverem muito próximos, aplica repulsão
        if dist < soma_raios * 1.2 and dist > 0.001:
            nx, ny = dx / dist, dy / dist
            fator_repulsao = 6.0
            p1.vel[0] -= nx * fator_repulsao
            p1.vel[1] -= ny * fator_repulsao
            p2.vel[0] += nx * fator_repulsao
            p2.vel[1] += ny * fator_repulsao

    def verificar_colisoes_combate(self):
        if (
            self._alvo_em_transicao_sombria(self.p1)
            or self._alvo_em_transicao_sombria(self.p2)
        ):
            return
        if (
            not self.p1.morto
            and not self.p2.morto
            and self.p1.dados.arma_obj
            and self.p2.dados.arma_obj
        ):
            if self.checar_clash_geral(self.p1, self.p2):
                self.efeito_clash(self.p1, self.p2); return 
        self.checar_ataque(self.p1, self.p2)
        self.checar_ataque(self.p2, self.p1)

    def efeito_clash(self, p1, p2):
        """Efeito visual dramático quando armas colidem"""
        mx = (p1.pos[0] + p2.pos[0]) / 2 * PPM
        my = (p1.pos[1] + p2.pos[1]) / 2 * PPM
        
        # === PARTÍCULAS DE FAÍSCA EM TODAS DIREÇÕES ===
        for _ in range(35):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(80, 180)
            vx = math.cos(ang) * vel / 60
            vy = math.sin(ang) * vel / 60
            self.particulas.append(Particula(mx, my, AMARELO_FAISCA, vx, vy, random.randint(3, 7), 0.5))
        
        # Cores das armas para o efeito
        cor1 = (p1.dados.arma_obj.r, p1.dados.arma_obj.g, p1.dados.arma_obj.b) if hasattr(p1.dados.arma_obj, 'r') else (255, 255, 255)
        cor2 = (p2.dados.arma_obj.r, p2.dados.arma_obj.g, p2.dados.arma_obj.b) if hasattr(p2.dados.arma_obj, 'r') else (255, 255, 255)
        
        # === EFEITOS VISUAIS ESPECIAIS ===
        self.magic_clashes.append(MagicClash(mx, my, cor1, cor2, tamanho=1.2))
        self.impact_flashes.append(ImpactFlash(mx, my, AMARELO_FAISCA, 1.5, "clash"))
        
        # Hit sparks em ambas direções
        ang_p1_p2 = math.atan2(p2.pos[1] - p1.pos[1], p2.pos[0] - p1.pos[0])
        self.hit_sparks.append(HitSpark(mx, my, cor1, ang_p1_p2, 1.5))
        self.hit_sparks.append(HitSpark(mx, my, cor2, ang_p1_p2 + math.pi, 1.5))
        
        # Empurra ambos para trás
        vec_x = p1.pos[0] - p2.pos[0]
        vec_y = p1.pos[1] - p2.pos[1]
        mag = math.hypot(vec_x, vec_y) or 1
        p1.tomar_clash(vec_x/mag, vec_y/mag)
        p2.tomar_clash(-vec_x/mag, -vec_y/mag)
        
        # === EFEITOS DE CÂMERA DRAMÁTICOS ===
        self.cam.aplicar_shake(25.0, 0.25)
        self.cam.zoom_punch(0.15, 0.15)
        self.hit_stop_timer = 0.15  # Pausa dramática
        
        # Shockwave grande
        self.shockwaves.append(Shockwave(mx, my, BRANCO, 1.5))
        
        # Texto CLASH! maior
        self.textos.append(FloatingText(mx, my - 60, "CLASH!", AMARELO_FAISCA, 38))

    def checar_clash_geral(self, p1, p2):
        if "Reta" in p1.dados.arma_obj.tipo and "Reta" in p2.dados.arma_obj.tipo:
            l1 = p1.get_pos_ponteira_arma(); l2 = p2.get_pos_ponteira_arma()
            if l1 and l2: return colisao_linha_linha(l1[0], l1[1], l2[0], l2[1])
        if "Reta" in p1.dados.arma_obj.tipo and "Orbital" in p2.dados.arma_obj.tipo:
            return self.checar_clash_espada_escudo(p1, p2)
        if "Orbital" in p1.dados.arma_obj.tipo and "Reta" in p2.dados.arma_obj.tipo:
            return self.checar_clash_espada_escudo(p2, p1)
        return False

    def checar_clash_espada_escudo(self, atacante, escudeiro):
        linha = atacante.get_pos_ponteira_arma()
        info = escudeiro.get_escudo_info()
        if not linha or not info: return False
        pts = intersect_line_circle(linha[0], linha[1], info[0], info[1])
        if not pts: return False
        for px, py in pts:
            dx = px - info[0][0]; dy = py - info[0][1]
            ang = math.degrees(math.atan2(dy, dx))
            diff = normalizar_angulo(ang - info[2])
            if abs(diff) <= info[3] / 2: return True
        return False

    def checar_ataque(self, atacante, defensor):
        """
        Verifica ataque usando o novo sistema de hitbox com debug.
        
        === INTEGRAÇÃO GAME FEEL v8.0 ===
        - Hit Stop proporcional à classe (Força > Ágil)
        - Super Armor para tanks/berserkers
        - Camera shake baseado em INTENSIDADE, não velocidade
        
        === v10.1: PREVENÇÃO DE MULTI-HIT ===
        - Cada ataque só pode acertar cada alvo UMA vez
        - Evita o bug de múltiplos hits durante um único swing
        """
        
        pode_causar_dano = getattr(atacante, "pode_causar_dano", None)
        if callable(pode_causar_dano) and not pode_causar_dano(defensor):
            return False

        # Armas ranged e mágicas NÃO usam hitbox direta
        # Elas causam dano apenas via projéteis/orbes
        arma = atacante.dados.arma_obj
        if arma and arma.tipo in ["Arremesso", "Arco", "Mágica"]:
            return False  # Dano é feito pelos projéteis/orbes, não pela hitbox
        
        # === v10.1: VERIFICA SE JÁ ACERTOU ESTE ALVO NESTE ATAQUE ===
        defensor_id = id(defensor)
        if hasattr(atacante, 'alvos_atingidos_neste_ataque'):
            if defensor_id in atacante.alvos_atingidos_neste_ataque:
                # Já acertou este alvo neste ataque, ignora
                return False
        
        # Usa o novo sistema modular para armas melee
        acertou, motivo = verificar_hit(atacante, defensor)
        
        if acertou:
            # === v10.1: MARCA ALVO COMO ATINGIDO NESTE ATAQUE ===
            if hasattr(atacante, 'alvos_atingidos_neste_ataque'):
                atacante.alvos_atingidos_neste_ataque.add(defensor_id)
            
            dx, dy = int(defensor.pos[0] * PPM), int(defensor.pos[1] * PPM)
            vx = defensor.pos[0] - atacante.pos[0]
            vy = defensor.pos[1] - atacante.pos[1]
            mag = math.hypot(vx, vy) or 1
            
            # Usa o novo sistema de dano modificado
            dano_base = arma.dano * (atacante.dados.forca / 2.0)
            dano, is_critico = (
                atacante.calcular_dano_ataque(dano_base, defensor)
                if hasattr(atacante, "calcular_dano_ataque")
                else (dano_base, False)
            )
            if dano <= 0:
                return False

            # O vetor base é calculado uma única vez. Game Feel pode reduzi-lo
            # (inclusive a zero) e o resultado passa a ser a fonte de verdade.
            direcao_impacto = math.atan2(vy, vx)
            pos_impacto = (dx / PPM, dy / PPM)
            knockback_final = calcular_knockback_com_forca(
                atacante,
                defensor,
                direcao_impacto,
                dano,
            )
            
            # === ÁUDIO v10.0 - SOM DE ATAQUE (baseado no dano) ===
            tipo_ataque = arma.tipo if arma else "SOCO"
            if self.audio:
                listener_x = self.cam.x / PPM
                self.audio.play_attack(tipo_ataque, atacante.pos[0], listener_x, damage=dano, is_critical=is_critico)
            
            # Notifica Sistema de Coreografia v5.0
            if self.choreographer:
                self.choreographer.registrar_hit(atacante, defensor)
            
            # === GAME FEEL v8.0 - DETERMINA TIPO DE GOLPE ===
            classe_atacante = getattr(atacante, 'classe_nome', "Guerreiro")
            
            # Classes de FORÇA têm golpes PESADOS
            if any(c in classe_atacante for c in ["Berserker", "Guerreiro", "Cavaleiro", "Gladiador"]):
                tipo_golpe = "PESADO" if dano > 20 else "MEDIO"
                if dano > 35 or is_critico:
                    tipo_golpe = "DEVASTADOR"
            # Classes ÁGEIS têm golpes LEVES (mantém fluidez)
            elif any(c in classe_atacante for c in ["Assassino", "Ninja", "Ladino"]):
                tipo_golpe = "LEVE"
                if is_critico:  # Críticos de assassino são DEVASTADORES
                    tipo_golpe = "DEVASTADOR"
            # Híbridos e outros
            else:
                tipo_golpe = "MEDIO"
                if dano > 25:
                    tipo_golpe = "PESADO"
            
            # === GAME FEEL - VERIFICA SUPER ARMOR DO DEFENSOR ===
            resultado_hit = None
            if self.game_feel:
                # Calcula progresso da animação de ataque do defensor (para super armor)
                progresso_anim = 0.0
                if hasattr(defensor, 'timer_animacao') and defensor.atacando:
                    progresso_anim = 1.0 - (defensor.timer_animacao / 0.25)
                
                # Verifica super armor
                self.game_feel.verificar_super_armor(
                    defensor, progresso_anim, 
                    getattr(defensor.brain, 'acao_atual', "")
                )
                
                # Processa hit através do Game Feel Manager
                resultado_hit = self.game_feel.processar_hit(
                    atacante=atacante,
                    alvo=defensor,
                    dano=dano,
                    posicao=(dx, dy),
                    tipo_golpe=tipo_golpe,
                    is_critico=is_critico,
                    knockback=knockback_final,
                )
                
                # Usa valores processados pelo Game Feel
                dano = resultado_hit["dano_final"]
                knockback_final = resultado_hit["knockback"]
            
            forca_atacante = atacante.dados.forca

            # A entidade continua decidindo se o impacto é aceito (i-frame,
            # esquiva, escudo etc.), mas não volta a escalar o knockback.
            fonte_melee = (
                "ataque_corpo_a_corpo",
                id(atacante),
                getattr(atacante, "ataque_id", 0),
            )
            metadata_melee = {
                "eh_corpo_a_corpo": True,
                "tipo_fonte": "ataque_corpo_a_corpo",
                "eh_skill": False,
                "eh_projetil": False,
            }
            resolver_impacto = getattr(defensor, "resolver_impacto", None)
            if callable(resolver_impacto):
                impacto = resolver_impacto(
                    dano,
                    0.0,
                    0.0,
                    "NORMAL",
                    atacante=atacante,
                    fonte_impacto=fonte_melee,
                    metadata_impacto=metadata_melee,
                )
                morreu = impacto.morreu
                dano_aplicado = impacto.dano
                impacto_aplicado = impacto.atingiu and dano_aplicado > 0.0
            else:
                morreu = defensor.tomar_dano(
                    dano,
                    0.0,
                    0.0,
                    "NORMAL",
                    atacante=atacante,
                    fonte_impacto=fonte_melee,
                    metadata_impacto=metadata_melee,
                )
                dano_aplicado = getattr(defensor, "ultimo_dano_recebido", dano)
                resultado_impacto = getattr(defensor, "ultimo_resultado_impacto", None)
                impacto_aplicado = (
                    getattr(resultado_impacto, "atingiu", dano_aplicado > 0.0)
                    and dano_aplicado > 0.0
                )

            if not impacto_aplicado:
                return False

            kb_x, kb_y = knockback_final
            defensor.vel[0] += kb_x
            defensor.vel[1] += kb_y
            magnitude_knockback = math.hypot(kb_x, kb_y)
            direcao_vfx = (
                math.atan2(kb_y, kb_x)
                if magnitude_knockback > 1e-9
                else direcao_impacto
            )

            # === FEEDBACK VISUAL DE SUPER ARMOR ===
            if resultado_hit and resultado_hit["super_armor_ativa"]:
                self.textos.append(FloatingText(dx, dy - 60, "ARMOR!", (255, 200, 50), 22))
                for _ in range(8):
                    ang = random.uniform(0, math.pi * 2)
                    vel = random.uniform(3, 8)
                    self.particulas.append(Particula(
                        dx, dy, (255, 200, 100),
                        math.cos(ang) * vel, math.sin(ang) * vel,
                        random.randint(4, 8), 0.4
                    ))

            # === EFEITOS DE IMPACTO MELHORADOS v8.0 IMPACT EDITION ===
            self.hit_sparks.append(HitSpark(dx, dy, AMARELO_FAISCA, direcao_vfx, 1.2))
            cor_arma = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else BRANCO
            self.impact_flashes.append(ImpactFlash(dx, dy, cor_arma, 1.0, "normal"))

            if self.attack_anims:
                impact_result = self.attack_anims.criar_attack_impact(
                    atacante=atacante,
                    alvo=defensor,
                    dano=dano_aplicado,
                    posicao=pos_impacto,
                    direcao=direcao_vfx,
                    tipo_dano="physical",
                    is_critico=is_critico
                )

                if not self.game_feel:
                    self.cam.aplicar_shake(impact_result['shake_intensity'], impact_result['shake_duration'])
                    if impact_result['zoom_punch'] > 0:
                        self.cam.zoom_punch(impact_result['zoom_punch'], 0.15)

            if morreu:
                # === ÁUDIO v10.0 - SOM DE MORTE ===
                if self.audio:
                    self.audio.play_special("ko", volume=1.0)
                
                # === MORTE - EFEITOS MÁXIMOS ===
                self.spawn_particulas(dx, dy, vx/mag, vy/mag, VERMELHO_SANGUE, 50)
                
                # Knockback visual épico na morte
                if magnitude_knockback > 1e-9:
                    self._criar_knockback_visual(
                        defensor,
                        direcao_vfx,
                        magnitude_knockback * 1.5,
                    )
                
                # Game Feel já processou camera shake para morte
                if not self.game_feel:
                    self.cam.aplicar_shake(35.0, 0.5)
                    self.cam.zoom_punch(0.3, 0.2)
                    self.hit_stop_timer = 0.4
                else:
                    # Efeitos adicionais de morte
                    self.cam.zoom_punch(0.35, 0.25)
                
                self.shockwaves.append(Shockwave(dx, dy, VERMELHO_SANGUE, 2.0))
                self.textos.append(FloatingText(dx, dy - 50, "FATAL!", VERMELHO_SANGUE, 45))
                return True
            else:
                # === ÁUDIO v10.0 - SOM DE IMPACTO ===
                if self.audio:
                    listener_x = self.cam.x / PPM
                    is_counter = resultado_hit and resultado_hit.get("counter_hit", False)
                    self.audio.play_impact(dano_aplicado, defensor.pos[0], listener_x, is_critico, is_counter)
                
                # === HIT NORMAL - EFEITOS PROPORCIONAIS AO DANO E FORÇA ===
                # Knockback visual proporcional ao dano
                if magnitude_knockback > 1e-9 and (dano_aplicado > 8 or forca_atacante > 12):
                    self._criar_knockback_visual(
                        defensor,
                        direcao_vfx,
                        magnitude_knockback,
                    )
                
                # Partículas proporcionais
                qtd_part = max(5, min(25, int(dano_aplicado / 3)))
                self.spawn_particulas(dx, dy, vx/mag, vy/mag, VERMELHO_SANGUE, qtd_part)
                
                # Se Game Feel está gerenciando shake/hitstop, não duplicamos
                if not self.game_feel:
                    shake_intensity = min(20.0, 5.0 + dano_aplicado * 0.3)
                    self.cam.aplicar_shake(shake_intensity, 0.12)
                    self.hit_stop_timer = min(0.1, 0.02 + dano_aplicado * 0.002)
                    if dano_aplicado > 15:
                        self.cam.zoom_punch(0.08, 0.1)
                
                # Shockwave para ataques fortes
                tier = get_impact_tier(forca_atacante)
                if dano_aplicado > 10 or forca_atacante >= 14:
                    self.shockwaves.append(Shockwave(dx, dy, BRANCO, 0.6 * tier['shockwave_size']))
                
                # === TEXTO DE DANO ESTILIZADO ===
                if is_critico:
                    cor_txt = (255, 50, 50)  # Vermelho intenso - crítico
                    tamanho_txt = 32
                    self.textos.append(FloatingText(dx, dy - 50, "CRÍTICO!", (255, 200, 0), 24))
                elif dano_aplicado > 25:
                    cor_txt = (255, 100, 100)  # Vermelho claro - dano alto
                    tamanho_txt = 28
                elif dano_aplicado > 15:
                    cor_txt = (255, 200, 100)  # Laranja - dano médio
                    tamanho_txt = 24
                else:
                    cor_txt = BRANCO
                    tamanho_txt = 20
                
                self.textos.append(FloatingText(dx, dy - 30, int(dano_aplicado), cor_txt, tamanho_txt))
        return False

    def spawn_particulas(self, x, y, dir_x, dir_y, cor, qtd):
        for _ in range(qtd):
            vx = dir_x * random.uniform(2, 12) + random.uniform(-4, 4)
            vy = dir_y * random.uniform(2, 12) + random.uniform(-4, 4)
            self.particulas.append(Particula(x*PPM, y*PPM, cor, vx, vy, random.randint(3, 8)))

    def ativar_slow_motion(self):
        self.time_scale = 0.2; self.slow_mo_timer = 2.0
        # Som de slow motion
        if getattr(self, "audio", None):
            self.audio.play_special("slowmo_start", 0.6)

    def desenhar(self):
        self.tela.fill(COR_FUNDO)
        
        # === DESENHA ARENA v9.0 (ANTES DE TUDO) ===
        if self.arena:
            self.arena.desenhar(self.tela, self.cam)
        else:
            # Fallback: grid antigo se não houver arena
            self.desenhar_grid()
        
        for d in self.decals: d.draw(self.tela, self.cam)
        
        # === DESENHA ÁREAS COM EFEITOS DRAMÁTICOS v11.0 ===
        if hasattr(self, 'areas'):
            for area in self.areas:
                if area.ativo:
                    ax, ay = self.cam.converter(area.x * PPM, area.y * PPM)
                    obter_raio_visual = getattr(area, "get_raio_visual", None)
                    raio_visual = (
                        obter_raio_visual()
                        if callable(obter_raio_visual)
                        else area.raio_atual
                    )
                    ar = self.cam.converter_tam(raio_visual * PPM)
                    if ar > 0:
                        # Pulso baseado no tempo
                        pulse_time = pygame.time.get_ticks() / 1000.0
                        pulse = 0.85 + 0.15 * math.sin(pulse_time * 6)
                        ar_pulsing = int(ar * pulse)
                        
                        # Múltiplas camadas para glow dramático
                        # Camada externa (glow)
                        s_glow = pygame.Surface((ar*4, ar*4), pygame.SRCALPHA)
                        glow_alpha = int(30 + 20 * math.sin(pulse_time * 4))
                        pygame.draw.circle(s_glow, (*area.cor[:3], glow_alpha), (ar*2, ar*2), ar*2)
                        self.tela.blit(s_glow, (ax - ar*2, ay - ar*2))
                        
                        # Camada média
                        s = pygame.Surface((ar*2, ar*2), pygame.SRCALPHA)
                        cor_com_alpha = (*area.cor[:3], min(255, area.alpha // 3))
                        pygame.draw.circle(s, cor_com_alpha, (ar, ar), ar_pulsing)
                        self.tela.blit(s, (ax - ar, ay - ar))
                        
                        # Anéis pulsantes (2-3 anéis)
                        for i in range(3):
                            ring_phase = pulse_time * (3 + i) + i * 0.5
                            ring_pulse = 0.5 + 0.5 * ((ring_phase % 1.0))
                            ring_r = int(ar * ring_pulse)
                            if ring_r > 2 and ring_r < ar:
                                ring_alpha = int(150 * (1 - ring_pulse))
                                s_ring = pygame.Surface((ring_r*2+4, ring_r*2+4), pygame.SRCALPHA)
                                pygame.draw.circle(s_ring, (*area.cor[:3], ring_alpha), (ring_r+2, ring_r+2), ring_r, 2)
                                self.tela.blit(s_ring, (ax - ring_r - 2, ay - ring_r - 2))
                        
                        # Borda principal (brilhante)
                        pygame.draw.circle(self.tela, area.cor, (ax, ay), ar_pulsing, 3)
                        # Core brilhante
                        inner_r = int(ar * 0.3)
                        if inner_r > 2:
                            s_core = pygame.Surface((inner_r*2+4, inner_r*2+4), pygame.SRCALPHA)
                            pygame.draw.circle(s_core, (255, 255, 255, 80), (inner_r+2, inner_r+2), inner_r)
                            self.tela.blit(s_core, (ax - inner_r - 2, ay - inner_r - 2))
        
        # Portais precisam ser visiveis nas duas extremidades do teleporte.
        for portal in getattr(self, "portais", ()):
            if not portal.ativo:
                continue
            ponto_a = self.cam.converter(
                portal.ponto_a[0] * PPM,
                portal.ponto_a[1] * PPM,
            )
            ponto_b = self.cam.converter(
                portal.ponto_b[0] * PPM,
                portal.ponto_b[1] * PPM,
            )
            raio = max(3, self.cam.converter_tam(portal.raio * PPM))
            pulso = 0.85 + 0.15 * math.sin(pygame.time.get_ticks() / 120.0)
            raio_pulso = max(3, int(raio * pulso))
            pygame.draw.line(self.tela, portal.cor, ponto_a, ponto_b, 1)
            for centro in (ponto_a, ponto_b):
                pygame.draw.circle(self.tela, portal.cor, centro, raio_pulso, 3)
                pygame.draw.circle(self.tela, BRANCO, centro, max(2, raio_pulso // 2), 1)

        # === DESENHA BEAMS COM EFEITOS DRAMÁTICOS v11.0 ===
        if hasattr(self, 'beams'):
            pulse_time = pygame.time.get_ticks() / 1000.0
            for beam in self.beams:
                if beam.ativo:
                    # Desenha segmentos zigzag
                    pts_screen = []
                    for bx, by in beam.segments:
                        sx, sy = self.cam.converter(bx * PPM, by * PPM)
                        pts_screen.append((sx, sy))
                    if len(pts_screen) >= 2:
                        pulse = 0.8 + 0.4 * abs(math.sin(pulse_time * 12))
                        largura_efetiva = int(beam.largura * pulse)
                        
                        # Calcula bounding box para surface
                        min_x = min(p[0] for p in pts_screen) - largura_efetiva - 10
                        min_y = min(p[1] for p in pts_screen) - largura_efetiva - 10
                        max_x = max(p[0] for p in pts_screen) + largura_efetiva + 10
                        max_y = max(p[1] for p in pts_screen) + largura_efetiva + 10
                        
                        w = int(max_x - min_x + 1)
                        h = int(max_y - min_y + 1)
                        
                        if w > 0 and h > 0:
                            s = pygame.Surface((w, h), pygame.SRCALPHA)
                            local_pts = [(int(p[0] - min_x), int(p[1] - min_y)) for p in pts_screen]
                            
                            # Glow externo (muito largo, semi-transparente)
                            glow_alpha = int(60 + 30 * math.sin(pulse_time * 8))
                            pygame.draw.lines(s, (*beam.cor[:3], glow_alpha), False, local_pts, largura_efetiva + 12)
                            
                            # Glow médio
                            pygame.draw.lines(s, (*beam.cor[:3], 150), False, local_pts, largura_efetiva + 6)
                            
                            # Beam principal colorido
                            pygame.draw.lines(s, beam.cor, False, local_pts, largura_efetiva)
                            
                            # Core brilhante branco
                            core_largura = max(2, largura_efetiva // 2)
                            pygame.draw.lines(s, (255, 255, 255), False, local_pts, core_largura)
                            
                            self.tela.blit(s, (min_x, min_y))
                        
                        # Partículas ao longo do beam
                        if random.random() < 0.3:
                            idx = random.randint(0, len(pts_screen) - 1)
                            px, py = pts_screen[idx]
                            # Particula(x, y, cor, vel_x, vel_y, tamanho, vida_util)
                            self.particulas.append(Particula(
                                px + random.uniform(-10, 10),
                                py + random.uniform(-10, 10),
                                beam.cor,
                                random.uniform(-30, 30),  # vel_x
                                random.uniform(-30, 30),  # vel_y
                                random.uniform(3, 6),     # tamanho
                                0.3                       # vida_util
                            ))
        
        for p in self.particulas:
            sx, sy = self.cam.converter(p.x, p.y); tam = self.cam.converter_tam(p.tamanho)
            # Desenha partícula com glow
            if tam > 2:
                s = pygame.Surface((int(tam*2)+4, int(tam*2)+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*p.cor, 100), (int(tam)+2, int(tam)+2), int(tam))
                pygame.draw.circle(s, p.cor, (int(tam)+2, int(tam)+2), max(1, int(tam*0.6)))
                self.tela.blit(s, (sx - int(tam) - 2, sy - int(tam) - 2))
            else:
                pygame.draw.rect(self.tela, p.cor, (sx, sy, max(1, int(tam)), max(1, int(tam))))
        
        # === DESENHA SUMMONS (Invocações) v11.0 DRAMATIC ===
        if hasattr(self, 'summons') and self.summons:
            pulse_time = pygame.time.get_ticks() / 1000.0
            for summon in self.summons:
                if summon.ativo:
                    sx, sy = self.cam.converter(summon.x * PPM, summon.y * PPM)
                    raio = self.cam.converter_tam(0.8 * PPM)  # Tamanho visual do summon
                    
                    # Círculo mágico no chão (rotacionando)
                    rotacao = pulse_time * 2
                    circle_r = int(raio * 1.5)
                    s_circle = pygame.Surface((circle_r*2+4, circle_r*2+4), pygame.SRCALPHA)
                    pygame.draw.circle(s_circle, (*summon.cor, 60), (circle_r+2, circle_r+2), circle_r, 2)
                    # Runas (linhas radiais)
                    for i in range(8):
                        ang = rotacao + i * (math.pi / 4)
                        inner = circle_r * 0.6
                        outer = circle_r
                        x1 = circle_r + 2 + math.cos(ang) * inner
                        y1 = circle_r + 2 + math.sin(ang) * inner
                        x2 = circle_r + 2 + math.cos(ang) * outer
                        y2 = circle_r + 2 + math.sin(ang) * outer
                        pygame.draw.line(s_circle, (*summon.cor, 100), (int(x1), int(y1)), (int(x2), int(y2)), 2)
                    self.tela.blit(s_circle, (sx - circle_r - 2, sy - circle_r - 2))
                    
                    # Sombra
                    pygame.draw.ellipse(self.tela, (30, 30, 30), (sx - raio, sy + raio//2, raio*2, raio//2))
                    
                    # Glow exterior pulsante
                    glow_pulse = 0.8 + 0.4 * math.sin(pulse_time * 5 + summon.vida_timer)
                    s = pygame.Surface((int(raio*4), int(raio*4)), pygame.SRCALPHA)
                    glow_alpha = int((60 + 40 * math.sin(summon.vida_timer * 3)) * glow_pulse)
                    pygame.draw.circle(s, (*summon.cor, glow_alpha), (int(raio*2), int(raio*2)), int(raio * 1.8 * glow_pulse))
                    self.tela.blit(s, (sx - raio*2, sy - raio*2))
                    
                    # Corpo do summon (baseado na cor da skill) com gradiente
                    pygame.draw.circle(self.tela, summon.cor, (int(sx), int(sy)), int(raio))
                    pygame.draw.circle(self.tela, tuple(min(255, c + 50) for c in summon.cor), (int(sx), int(sy)), int(raio * 0.7))
                    
                    # Core brilhante
                    pygame.draw.circle(self.tela, BRANCO, (int(sx), int(sy)), max(1, int(raio * 0.35)))
                    
                    # Barra de vida do summon
                    vida_pct = summon.vida / summon.vida_max
                    barra_w = raio * 2
                    pygame.draw.rect(self.tela, (50, 50, 50), (sx - raio, sy - raio - 10, barra_w, 5))
                    pygame.draw.rect(self.tela, summon.cor, (sx - raio, sy - raio - 10, barra_w * vida_pct, 5))
                    
                    # Nome do summon
                    font = pygame.font.Font(None, 16)
                    nome_txt = font.render(summon.nome, True, summon.cor)
                    self.tela.blit(nome_txt, (sx - nome_txt.get_width()//2, sy - raio - 22))
        
        # === DESENHA TRAPS (Armadilhas) v2.0 ===
        if hasattr(self, 'traps'):
            for trap in self.traps:
                if trap.ativo:
                    tx, ty = self.cam.converter(trap.x * PPM, trap.y * PPM)
                    traio = self.cam.converter_tam(trap.raio * PPM)
                    
                    # Desenha armadilha como hexágono ou círculo
                    if trap.bloqueia_movimento:
                        # Estrutura sólida - hexágono
                        pts = []
                        for i in range(6):
                            ang = i * (math.pi / 3) + trap.angulo
                            pts.append((tx + math.cos(ang) * traio, ty + math.sin(ang) * traio))
                        pygame.draw.polygon(self.tela, trap.cor, pts)
                        pygame.draw.polygon(self.tela, BRANCO, pts, 2)
                    else:
                        # Armadilha no chão - círculo com padrão
                        s = pygame.Surface((traio*2, traio*2), pygame.SRCALPHA)
                        pygame.draw.circle(s, (*trap.cor, 150), (traio, traio), traio)
                        self.tela.blit(s, (tx - traio, ty - traio))
                        # Marcas de perigo
                        pygame.draw.circle(self.tela, trap.cor, (int(tx), int(ty)), int(traio), 2)
                        pygame.draw.circle(self.tela, trap.cor, (int(tx), int(ty)), int(traio * 0.5), 1)
        
        # === DESENHA MARCAS NO CHÃO (CRATERAS, RACHADURAS) - v8.0 IMPACT ===
        if hasattr(self, 'attack_anims') and self.attack_anims:
            self.attack_anims.draw_ground(self.tela, self.cam)
        
        lutadores = [self.p1, self.p2]
        lutadores.sort(key=lambda p: 0 if p.morto else 1)
        for l in lutadores: self.desenhar_lutador(l)
        
        # === DESENHA PROJÉTEIS COM TRAIL DRAMÁTICO v11.0 ===
        pulse_time = pygame.time.get_ticks() / 1000.0
        for proj in self.projeteis:
            if getattr(proj, "cone", False):
                origem_x, origem_y = proj.origem_cone
                pontos = [self.cam.converter(origem_x * PPM, origem_y * PPM)]
                angulo_inicial = proj.angulo - proj.angulo_cone / 2.0
                segmentos = max(3, int(proj.angulo_cone / 10.0))
                for indice in range(segmentos + 1):
                    angulo = math.radians(
                        angulo_inicial + proj.angulo_cone * indice / segmentos
                    )
                    x = origem_x + math.cos(angulo) * proj.alcance_cone
                    y = origem_y + math.sin(angulo) * proj.alcance_cone
                    pontos.append(self.cam.converter(x * PPM, y * PPM))
                pygame.draw.polygon(self.tela, proj.cor, pontos, 2)
                continue

            # Trail dramático com glow
            if hasattr(proj, 'trail') and len(proj.trail) > 1:
                cor_trail = proj.cor if hasattr(proj, 'cor') else BRANCO
                
                for i in range(1, len(proj.trail)):
                    t = i / len(proj.trail)
                    alpha = int(255 * t * 0.7)
                    largura = max(1, int(proj.raio * PPM * self.cam.zoom * t))
                    
                    p1 = self.cam.converter(proj.trail[i-1][0] * PPM, proj.trail[i-1][1] * PPM)
                    p2 = self.cam.converter(proj.trail[i][0] * PPM, proj.trail[i][1] * PPM)
                    
                    # Glow do trail (mais largo, semi-transparente)
                    if largura > 2:
                        s = pygame.Surface((abs(int(p2[0]-p1[0]))+largura*4, abs(int(p2[1]-p1[1]))+largura*4), pygame.SRCALPHA)
                        offset_x = min(p1[0], p2[0]) - largura*2
                        offset_y = min(p1[1], p2[1]) - largura*2
                        local_p1 = (p1[0] - offset_x, p1[1] - offset_y)
                        local_p2 = (p2[0] - offset_x, p2[1] - offset_y)
                        pygame.draw.line(s, (*cor_trail[:3], alpha // 2), local_p1, local_p2, largura * 2)
                        pygame.draw.line(s, (*cor_trail[:3], alpha), local_p1, local_p2, largura)
                        self.tela.blit(s, (offset_x, offset_y))
                    else:
                        pygame.draw.line(self.tela, cor_trail, p1, p2, largura)
            
            # Projétil principal - desenho baseado no tipo
            px, py = self.cam.converter(proj.x * PPM, proj.y * PPM)
            pr = self.cam.converter_tam(proj.raio * PPM)
            cor = proj.cor if hasattr(proj, 'cor') else BRANCO
            
            # Glow do projétil
            glow_pulse = 0.8 + 0.4 * math.sin(pulse_time * 10 + id(proj) % 100)
            glow_r = int(pr * 2 * glow_pulse)
            if glow_r > 3:
                s = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*cor[:3], 60), (glow_r+2, glow_r+2), glow_r)
                self.tela.blit(s, (px - glow_r - 2, py - glow_r - 2))
            
            tipo_proj = getattr(proj, 'tipo', 'skill')
            ang_visual = getattr(proj, 'angulo_visual', proj.angulo) if hasattr(proj, 'angulo') else 0
            rad = math.radians(ang_visual)
            
            if tipo_proj == "faca":
                # Desenha faca (triângulo alongado)
                tam = max(pr * 2, 8)
                pts = [
                    (px + math.cos(rad) * tam, py + math.sin(rad) * tam),  # Ponta
                    (px + math.cos(rad + 2.5) * tam * 0.4, py + math.sin(rad + 2.5) * tam * 0.4),
                    (px - math.cos(rad) * tam * 0.3, py - math.sin(rad) * tam * 0.3),  # Base
                    (px + math.cos(rad - 2.5) * tam * 0.4, py + math.sin(rad - 2.5) * tam * 0.4),
                ]
                pygame.draw.polygon(self.tela, cor, pts)
                pygame.draw.polygon(self.tela, BRANCO, pts, 1)
                
            elif tipo_proj == "shuriken":
                # Desenha shuriken (estrela de 4 pontas girando)
                tam = max(pr * 2, 10)
                pts = []
                for i in range(8):
                    ang_pt = rad + i * (math.pi / 4)
                    dist = tam if i % 2 == 0 else tam * 0.3
                    pts.append((px + math.cos(ang_pt) * dist, py + math.sin(ang_pt) * dist))
                pygame.draw.polygon(self.tela, cor, pts)
                pygame.draw.polygon(self.tela, (50, 50, 50), pts, 1)
                
            elif tipo_proj == "chakram":
                # Desenha chakram (anel girando)
                tam = max(pr * 2, 12)
                pygame.draw.circle(self.tela, cor, (int(px), int(py)), int(tam), 3)
                pygame.draw.circle(self.tela, BRANCO, (int(px), int(py)), int(tam * 0.5), 2)
                # Lâminas
                for i in range(6):
                    ang_blade = rad + i * (math.pi / 3)
                    bx = px + math.cos(ang_blade) * tam
                    by = py + math.sin(ang_blade) * tam
                    pygame.draw.line(self.tela, cor, (px, py), (int(bx), int(by)), 2)
                
            elif tipo_proj == "flecha":
                # Desenha flecha
                tam = max(pr * 3, 15)
                # Corpo da flecha
                x1 = px - math.cos(rad) * tam * 0.7
                y1 = py - math.sin(rad) * tam * 0.7
                x2 = px + math.cos(rad) * tam * 0.3
                y2 = py + math.sin(rad) * tam * 0.3
                pygame.draw.line(self.tela, (139, 90, 43), (int(x1), int(y1)), (int(x2), int(y2)), 2)
                # Ponta da flecha (triângulo)
                pts = [
                    (px + math.cos(rad) * tam * 0.6, py + math.sin(rad) * tam * 0.6),
                    (px + math.cos(rad + 2.7) * tam * 0.2, py + math.sin(rad + 2.7) * tam * 0.2),
                    (px + math.cos(rad - 2.7) * tam * 0.2, py + math.sin(rad - 2.7) * tam * 0.2),
                ]
                pygame.draw.polygon(self.tela, cor, pts)
                # Penas (traseira)
                for offset in [-0.3, 0.3]:
                    fx = x1 + math.cos(rad + offset) * tam * 0.15
                    fy = y1 + math.sin(rad + offset) * tam * 0.15
                    pygame.draw.line(self.tela, (200, 200, 200), (int(x1), int(y1)), (int(fx), int(fy)), 1)
                
            else:
                # Projétil de skill (círculo padrão)
                pygame.draw.circle(self.tela, cor, (int(px), int(py)), int(pr))
                pygame.draw.circle(self.tela, BRANCO, (int(px), int(py)), max(1, int(pr)-2))

        # === DESENHA ORBES MÁGICOS ===
        for p in [self.p1, self.p2]:
            if hasattr(p, 'buffer_orbes'):
                for orbe in p.buffer_orbes:
                    if not orbe.ativo:
                        continue
                    
                    ox, oy = self.cam.converter(orbe.x * PPM, orbe.y * PPM)
                    or_visual = self.cam.converter_tam(orbe.raio_visual * PPM)
                    
                    # Trail quando disparando
                    if orbe.estado == "disparando" and len(orbe.trail) > 1:
                        for i in range(1, len(orbe.trail)):
                            alpha = int(255 * (i / len(orbe.trail)) * 0.6)
                            p1 = self.cam.converter(orbe.trail[i-1][0] * PPM, orbe.trail[i-1][1] * PPM)
                            p2 = self.cam.converter(orbe.trail[i][0] * PPM, orbe.trail[i][1] * PPM)
                            cor_trail = tuple(min(255, c + 50) for c in orbe.cor)
                            pygame.draw.line(self.tela, cor_trail, p1, p2, max(2, int(or_visual * 0.5)))
                    
                    # Partículas mágicas
                    for part in orbe.particulas:
                        ppx, ppy = self.cam.converter(part['x'] * PPM, part['y'] * PPM)
                        palpha = int(255 * (part['vida'] / 0.3))
                        s = pygame.Surface((6, 6), pygame.SRCALPHA)
                        pygame.draw.circle(s, (*part['cor'], palpha), (3, 3), 3)
                        self.tela.blit(s, (ppx - 3, ppy - 3))
                    
                    # Glow externo
                    glow_size = int(or_visual * 2.5)
                    if glow_size > 2:
                        s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
                        # Pulso de brilho
                        pulso = 0.7 + 0.3 * math.sin(orbe.pulso)
                        glow_alpha = int(100 * pulso)
                        pygame.draw.circle(s, (*orbe.cor, glow_alpha), (glow_size, glow_size), glow_size)
                        self.tela.blit(s, (ox - glow_size, oy - glow_size))
                    
                    # Orbe principal (núcleo brilhante)
                    if or_visual > 1:
                        # Borda colorida
                        pygame.draw.circle(self.tela, orbe.cor, (int(ox), int(oy)), int(or_visual))
                        # Core branco
                        pygame.draw.circle(self.tela, BRANCO, (int(ox), int(oy)), max(1, int(or_visual * 0.5)))
                    
                    # Estado visual extra
                    if orbe.estado == "carregando":
                        # Anéis de carga
                        carga_pct = orbe.tempo_carga / orbe.carga_max
                        ring_r = int(or_visual * (1.5 + carga_pct))
                        pygame.draw.circle(self.tela, orbe.cor, (int(ox), int(oy)), ring_r, 1)

        # === EFEITOS v7.0 IMPACT EDITION ===
        for ef in self.dash_trails: ef.draw(self.tela, self.cam)
        for ef in self.hit_sparks: ef.draw(self.tela, self.cam)
        for ef in self.magic_clashes: ef.draw(self.tela, self.cam)
        for ef in self.impact_flashes: ef.draw(self.tela, self.cam)
        for ef in self.block_effects: ef.draw(self.tela, self.cam)
        
        # === MAGIC VFX v11.0 DRAMATIC EDITION ===
        if hasattr(self, 'magic_vfx') and self.magic_vfx:
            self.magic_vfx.draw(self.tela, self.cam)

        # === ANIMAÇÕES DE MOVIMENTO v8.0 CINEMATIC EDITION ===
        if self.movement_anims:
            self.movement_anims.draw(self.tela, self.cam)

        # === ANIMAÇÕES DE ATAQUE v8.0 IMPACT EDITION ===
        if hasattr(self, 'attack_anims') and self.attack_anims:
            self.attack_anims.draw_effects(self.tela, self.cam)

        for s in self.shockwaves: s.draw(self.tela, self.cam)
        for t in self.textos: t.draw(self.tela, self.cam)

        # === SCREEN EFFECTS (FLASH) v8.0 IMPACT ===
        if hasattr(self, 'attack_anims') and self.attack_anims:
            self.attack_anims.draw_screen_effects(self.tela, self.screen_width, self.screen_height)

        # === DEBUG VISUAL DE HITBOX ===
        if self.show_hitbox_debug:
            self.desenhar_hitbox_debug()

        if self.show_hud and not self.vencedor:
            self.desenhar_barras(self.p1, 20, 20, COR_P1, self.vida_visual_p1)
            # Ajusta posição P2 baseado no modo (220 em portrait, 320 em normal)
            p2_offset = 220 if self.portrait_mode else 320
            self.desenhar_barras(self.p2, self.screen_width - p2_offset, 20, COR_P2, self.vida_visual_p2)
            self.desenhar_placar_serie()
            if not self.portrait_mode:  # Esconde controles em portrait para mais espaço
                self.desenhar_controles()

        # O resultado precisa permanecer visível mesmo com o HUD oculto.
        if self.vencedor:
            self.desenhar_vitoria()

        if self.show_hud:
            if self.paused: self.desenhar_pause()
        if self.show_analysis: self.desenhar_analise()

    def desenhar_grid(self):
        start_x = int((-self.cam.x * self.cam.zoom) % (50 * self.cam.zoom))
        start_y = int((-self.cam.y * self.cam.zoom) % (50 * self.cam.zoom))
        step = int(50 * self.cam.zoom)
        for x in range(start_x, self.screen_width, step): pygame.draw.line(self.tela, COR_GRID, (x, 0), (x, self.screen_height))
        for y in range(start_y, self.screen_height, step): pygame.draw.line(self.tela, COR_GRID, (0, y), (self.screen_width, y))

    def desenhar_lutador(self, l):
        if self._alvo_em_transicao_sombria(l):
            return
        px = l.pos[0] * PPM; py = l.pos[1] * PPM
        sx, sy = self.cam.converter(px, py); off_y = self.cam.converter_tam(l.z * PPM); raio = self.cam.converter_tam((l.dados.tamanho / 2) * PPM)
        if l in self.rastros and len(self.rastros[l]) > 2:
            pts_rastro = []
            for ponta, cabo in self.rastros[l]:
                p_conv = self.cam.converter(ponta[0], ponta[1]); c_conv = self.cam.converter(cabo[0], cabo[1])
                p_conv = (p_conv[0], p_conv[1] - off_y); c_conv = (c_conv[0], c_conv[1] - off_y)
                pts_rastro.append(p_conv); pts_rastro.insert(0, c_conv)
            s = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            cor_rastro = (l.dados.arma_obj.r, l.dados.arma_obj.g, l.dados.arma_obj.b, 80)
            if len(pts_rastro) > 2: pygame.draw.polygon(s, cor_rastro, pts_rastro); self.tela.blit(s, (0,0))
        if l.morto:
            pygame.draw.ellipse(self.tela, COR_CORPO, (sx-raio, sy-raio, raio*2, raio*2))
            if l.dados.arma_obj:
                ax = l.arma_droppada_pos[0]*PPM; ay = l.arma_droppada_pos[1]*PPM
                asx, asy = self.cam.converter(ax, ay)
                self.desenhar_arma(l.dados.arma_obj, (asx, asy), l.arma_droppada_ang, l.dados.tamanho, raio)
            return
        sombra = pygame.Surface((raio*2, raio*2), pygame.SRCALPHA); pygame.draw.ellipse(sombra, (0,0,0,80), (0,0,raio*2, raio*2))
        tam_s = int(raio * 2 * max(0.4, 1.0 - (l.z/4.0)))
        if tam_s > 0:
            sombra_scaled = pygame.transform.scale(sombra, (tam_s, tam_s)); self.tela.blit(sombra_scaled, (sx-tam_s//2, sy-tam_s//2))
        centro = (sx, sy - off_y)
        
        # === COR DO CORPO COM FLASH DE DANO MELHORADO ===
        if l.flash_timer > 0:
            # Usa cor de flash personalizada se disponível
            flash_cor = getattr(l, 'flash_cor', (255, 255, 255))
            # Intensidade do flash diminui com o tempo
            flash_intensity = l.flash_timer / 0.25
            # Mistura cor original com cor de flash
            cor_r = getattr(l.dados, 'cor_r', 200) or 200
            cor_g = getattr(l.dados, 'cor_g', 50) or 50
            cor_b = getattr(l.dados, 'cor_b', 50) or 50
            cor_original = (cor_r, cor_g, cor_b)
            cor = tuple(int(max(0, min(255, flash_cor[i] * flash_intensity + cor_original[i] * (1 - flash_intensity)))) for i in range(3))
        else:
            cor_r = getattr(l.dados, 'cor_r', 200) or 200
            cor_g = getattr(l.dados, 'cor_g', 50) or 50
            cor_b = getattr(l.dados, 'cor_b', 50) or 50
            cor = (int(cor_r), int(cor_g), int(cor_b))
        
        pygame.draw.circle(self.tela, cor, centro, raio)
        
        # === CONTORNO APRIMORADO ===
        if l.stun_timer > 0:
            contorno = AMARELO_FAISCA
            largura = max(2, self.cam.converter_tam(5))
        elif l.atacando:
            contorno = (255, 255, 255)
            largura = max(2, self.cam.converter_tam(4))
        elif l.flash_timer > 0:
            # Contorno vermelho durante dano
            contorno = (255, 100, 100)
            largura = max(2, self.cam.converter_tam(4))
        else:
            contorno = (50, 50, 50)
            largura = max(1, self.cam.converter_tam(2))
        
        pygame.draw.circle(self.tela, contorno, centro, raio, largura)
        
        # === EFEITO DE GLOW EM VIDA BAIXA (ADRENALINA) ===
        if l.modo_adrenalina and not l.morto:
            pulso = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 150)
            glow_size = int(raio * 1.3)
            s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
            glow_alpha = int(60 * pulso)
            pygame.draw.circle(s, (255, 50, 50, glow_alpha), (glow_size, glow_size), glow_size)
            self.tela.blit(s, (centro[0] - glow_size, centro[1] - glow_size))
        
        # === RENDERIZA ARMA COM ANIMAÇÕES APRIMORADAS ===
        if l.dados.arma_obj:
            # Aplica shake da animação
            shake = getattr(l, 'weapon_anim_shake', (0, 0))
            centro_ajustado = (centro[0] + shake[0], centro[1] + shake[1])
            
            # Escala da animação
            anim_scale = getattr(l, 'weapon_anim_scale', 1.0)
            
            # Desenha slash arc se estiver atacando (para armas melee)
            if l.atacando and l.dados.arma_obj.tipo in ["Reta", "Dupla", "Corrente", "Transformável"]:
                self._desenhar_slash_arc(l, centro, raio, anim_scale)
            
            # Desenha trail antes da arma
            self._desenhar_weapon_trail(l)
            
            # Desenha arma com escala
            self.desenhar_arma(l.dados.arma_obj, centro_ajustado, l.angulo_arma_visual, 
                             l.dados.tamanho, raio, anim_scale)
    
    def _desenhar_slash_arc(self, lutador, centro, raio, anim_scale):
        """Desenha arco de corte visível durante ataques melee"""
        arma = lutador.dados.arma_obj
        if not arma:
            return
        
        # Cor do arco baseada na arma
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (255, 255, 255)
        cor_brilho = tuple(min(255, c + 80) for c in cor)
        
        # Progresso da animação
        timer = lutador.timer_animacao
        
        # Perfil da arma para saber a duração total
        from neural_fights.effects.weapon_animations import WEAPON_PROFILES
        profile = WEAPON_PROFILES.get(arma.tipo, WEAPON_PROFILES["Reta"])
        total_time = profile.total_time
        
        # Progresso normalizado (0-1)
        prog = 1.0 - (timer / total_time) if total_time > 0 else 0
        
        # Só desenha durante a fase de ataque principal (não na anticipation ou recovery)
        antecipation_end = profile.anticipation_time / total_time
        attack_end = (profile.anticipation_time + profile.attack_time + profile.impact_time) / total_time
        
        if prog < antecipation_end or prog > attack_end + 0.2:
            return
        
        # Calcula fase dentro do ataque
        attack_prog = (prog - antecipation_end) / max(attack_end - antecipation_end, 0.01)
        attack_prog = max(0, min(1, attack_prog))
        
        # Parâmetros do arco
        angulo_base = lutador.angulo_olhar
        arc_start = angulo_base + profile.anticipation_angle
        arc_end = angulo_base + profile.attack_angle
        
        # Ângulo atual do arco (expande ao longo do ataque)
        current_arc = arc_start + (arc_end - arc_start) * attack_prog
        
        # Raio do arco
        arc_radius = raio * 2.5 * anim_scale
        
        # Alpha diminui conforme avança
        alpha = int(180 * (1 - attack_prog * 0.7))
        
        # Desenha o arco de corte
        s = pygame.Surface((int(arc_radius * 3), int(arc_radius * 3)), pygame.SRCALPHA)
        arc_center = (int(arc_radius * 1.5), int(arc_radius * 1.5))
        
        # Calcula pontos do arco
        num_points = 15
        points_outer = []
        points_inner = []
        
        for i in range(num_points + 1):
            t = i / num_points
            angle = math.radians(arc_start + (current_arc - arc_start) * t)
            
            # Ponto externo
            ox = arc_center[0] + math.cos(angle) * arc_radius
            oy = arc_center[1] + math.sin(angle) * arc_radius
            points_outer.append((ox, oy))
            
            # Ponto interno (para criar espessura)
            inner_radius = arc_radius * 0.7
            ix = arc_center[0] + math.cos(angle) * inner_radius
            iy = arc_center[1] + math.sin(angle) * inner_radius
            points_inner.append((ix, iy))
        
        # Cria polígono do arco
        if len(points_outer) > 2:
            arc_polygon = points_outer + points_inner[::-1]
            
            # Cor com alpha
            arc_color = (*cor_brilho, alpha)
            pygame.draw.polygon(s, arc_color, arc_polygon)
            
            # Contorno mais brilhante
            pygame.draw.lines(s, (*cor, min(255, alpha + 50)), False, points_outer, 2)
        
        # Blit na posição do lutador
        blit_pos = (centro[0] - arc_center[0], centro[1] - arc_center[1])
        self.tela.blit(s, blit_pos)
    
    def _desenhar_weapon_trail(self, lutador):
        """Desenha o trail da arma durante ataques"""
        trail = getattr(lutador, 'weapon_trail_positions', [])
        if len(trail) < 2:
            return
        
        arma = lutador.dados.arma_obj
        if not arma:
            return
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (200, 200, 200)
        tipo = arma.tipo
        
        # Diferentes estilos de trail por tipo
        for i in range(len(trail) - 1):
            x1, y1, a1 = trail[i]
            x2, y2, a2 = trail[i + 1]
            
            # Converte para tela (coordenadas mundo -> pixels)
            from neural_fights.utils.config import PPM
            p1 = self.cam.converter(x1 * PPM, y1 * PPM)
            p2 = self.cam.converter(x2 * PPM, y2 * PPM)
            
            alpha = min(a1, a2)
            if alpha < 0.1:
                continue
            
            # Largura e cor com fade
            width = max(1, int(5 * (i / len(trail)) * alpha))
            
            if tipo == "Mágica":
                # Trail brilhante para magia
                bright = tuple(min(255, int(c + 80 * alpha)) for c in cor)
                pygame.draw.line(self.tela, bright, p1, p2, width + 2)
                
                # Partícula no final
                if i == len(trail) - 2 and alpha > 0.5:
                    glow_size = int(8 * alpha)
                    s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
                    glow_alpha = int(100 * alpha)
                    pygame.draw.circle(s, (*cor, glow_alpha), (glow_size, glow_size), glow_size)
                    self.tela.blit(s, (p2[0] - glow_size, p2[1] - glow_size))
            else:
                # Trail padrão de corte
                blend = alpha * 0.8
                trail_color = tuple(min(255, int(c * 0.5 + 127 * blend)) for c in cor)
                pygame.draw.line(self.tela, trail_color, p1, p2, width)

    def desenhar_arma(self, arma, centro, angulo, tam_char, raio_char, anim_scale=1.0):
        """
        Renderiza a arma do lutador - VERSÃO APRIMORADA v3.0
        Visual muito mais bonito com gradientes, brilhos e detalhes.
        """
        cx, cy = centro
        rad = math.radians(angulo)
        
        # Cores da arma com validação
        cor_r = getattr(arma, 'r', 180) or 180
        cor_g = getattr(arma, 'g', 180) or 180
        cor_b = getattr(arma, 'b', 180) or 180
        cor = (int(cor_r), int(cor_g), int(cor_b))
        
        # Cor mais clara para highlights
        cor_clara = tuple(min(255, c + 60) for c in cor)
        # Cor mais escura para sombras
        cor_escura = tuple(max(0, c - 40) for c in cor)
        
        # Cor de raridade para efeitos especiais
        raridade = getattr(arma, 'raridade', 'Comum')
        cores_raridade = {
            'Comum': (180, 180, 180),
            'Incomum': (30, 255, 30),
            'Raro': (30, 144, 255),
            'Épico': (148, 0, 211),
            'Lendário': (255, 165, 0),
            'Mítico': (255, 20, 147)
        }
        cor_raridade = cores_raridade.get(raridade, (180, 180, 180))
        
        tipo = getattr(arma, 'tipo', 'Reta')
        
        # Escala base da arma
        base_scale = raio_char * 0.025  # Escala relativa ao personagem
        
        # Largura da arma proporcional
        larg_base = max(3, int(raio_char * 0.12 * anim_scale))
        
        # Flag de ataque ativo (para efeitos especiais)
        atacando = anim_scale > 1.05
        tempo = pygame.time.get_ticks()
        
        # === RETA (Espadas, Lanças, Machados) ===
        if tipo == "Reta":
            cabo_len = getattr(arma, 'comp_cabo', 20) * base_scale * 1.2
            lamina_len = getattr(arma, 'comp_lamina', 60) * base_scale * 1.5 * anim_scale
            larg = max(4, int(larg_base * 1.2))
            
            # Pontos
            cabo_end_x = cx + math.cos(rad) * cabo_len
            cabo_end_y = cy + math.sin(rad) * cabo_len
            lamina_end_x = cx + math.cos(rad) * (cabo_len + lamina_len)
            lamina_end_y = cy + math.sin(rad) * (cabo_len + lamina_len)
            
            # === CABO ===
            # Guarda (oval)
            guarda_x = cabo_end_x + math.cos(rad) * 2
            guarda_y = cabo_end_y + math.sin(rad) * 2
            pygame.draw.ellipse(self.tela, (80, 60, 40), 
                              (int(guarda_x - larg*1.5), int(guarda_y - larg*0.8), larg*3, larg*1.6))
            
            # Cabo com gradiente simulado
            for i in range(3):
                offset = i - 1
                cor_cabo = (90 - i*15, 50 - i*10, 20 - i*5)
                pygame.draw.line(self.tela, cor_cabo, 
                               (int(cx) + offset, int(cy) + offset), 
                               (int(cabo_end_x) + offset, int(cabo_end_y) + offset), 
                               max(2, larg - i))
            
            # === LÂMINA ===
            # Forma da lâmina (polígono para visual mais interessante)
            perp_x = math.cos(rad + math.pi/2) * larg * 0.6
            perp_y = math.sin(rad + math.pi/2) * larg * 0.6
            
            # Pontos da lâmina (forma de espada)
            lamina_pts = [
                (int(cabo_end_x - perp_x), int(cabo_end_y - perp_y)),  # Base esquerda
                (int(cabo_end_x + perp_x), int(cabo_end_y + perp_y)),  # Base direita
                (int(lamina_end_x - perp_x*0.3), int(lamina_end_y - perp_y*0.3)),  # Ponta esquerda
                (int(lamina_end_x), int(lamina_end_y)),  # Ponta
                (int(lamina_end_x + perp_x*0.3), int(lamina_end_y + perp_y*0.3)),  # Ponta direita
            ]
            
            # Lâmina principal
            if len(lamina_pts) >= 3:
                pygame.draw.polygon(self.tela, cor, lamina_pts)
                pygame.draw.polygon(self.tela, cor_escura, lamina_pts, 1)
            
            # Highlight central (fio da espada)
            mid_x = (cabo_end_x + lamina_end_x) / 2
            mid_y = (cabo_end_y + lamina_end_y) / 2
            pygame.draw.line(self.tela, cor_clara, 
                           (int(cabo_end_x), int(cabo_end_y)), 
                           (int(mid_x), int(mid_y)), max(1, larg//3))
            
            # Efeito de brilho durante ataque
            if atacando:
                glow_surface = pygame.Surface((int(lamina_len*2), int(lamina_len*2)), pygame.SRCALPHA)
                for r in range(3, 0, -1):
                    alpha = 50 // r
                    pygame.draw.line(glow_surface, (*cor_clara, alpha),
                                   (lamina_len, lamina_len),
                                   (lamina_len + math.cos(rad)*lamina_len*0.8, 
                                    lamina_len + math.sin(rad)*lamina_len*0.8), larg + r*2)
                self.tela.blit(glow_surface, (int(cabo_end_x - lamina_len), int(cabo_end_y - lamina_len)))
            
            # Efeito de raridade na ponta
            if raridade not in ['Comum', 'Incomum']:
                pulso = 0.5 + 0.5 * math.sin(tempo / 200)
                glow_r = max(3, int(larg * 0.8 * (1 + pulso * 0.3)))
                pygame.draw.circle(self.tela, cor_raridade, (int(lamina_end_x), int(lamina_end_y)), glow_r)
        
        # === DUPLA - ADAGAS GÊMEAS v3.0 (Karambit Reverse-Grip) ===
        elif tipo == "Dupla":
            estilo_arma = getattr(arma, 'estilo', '')
            sep = getattr(arma, 'separacao', 25) * base_scale * 1.6
            larg = max(4, int(larg_base * 1.1))

            if estilo_arma == "Adagas Gêmeas":
                # ── ADAGAS GÊMEAS v3.1: Laterais do corpo, empunhadura normal apontando à frente ──
                # Cada daga fica na mão do personagem (lateral), lâmina apontando na direção do ataque
                cabo_len  = getattr(arma, 'comp_cabo', 8) * base_scale * 1.3
                lamina_len = getattr(arma, 'comp_lamina', 50) * base_scale * 1.6 * anim_scale
                pulso = 0.5 + 0.5 * math.sin(tempo / 180)
                glow_alpha_base = int(100 + 70 * pulso) if atacando else int(35 + 20 * pulso)

                for i, lado_sinal in enumerate([-1, 1]):
                    # ── Posição da mão: lateral ao corpo, fora do centro ──
                    # sep já dá a separação lateral adequada
                    hand_x = cx + math.cos(rad + math.pi/2) * sep * lado_sinal * 0.85
                    hand_y = cy + math.sin(rad + math.pi/2) * sep * lado_sinal * 0.85

                    # Ângulo da daga: aponta para frente com leve abertura lateral
                    spread_deg = 18 * lado_sinal  # abertura: esquerda vai -18°, direita vai +18°
                    daga_ang = rad + math.radians(spread_deg)

                    # ── Cabo (handle) ──
                    cabo_ex = hand_x + math.cos(daga_ang) * cabo_len
                    cabo_ey = hand_y + math.sin(daga_ang) * cabo_len
                    # Sombra
                    pygame.draw.line(self.tela, (30, 18, 8),
                                     (int(hand_x)+1, int(hand_y)+1),
                                     (int(cabo_ex)+1, int(cabo_ey)+1), larg + 3)
                    # Madeira/grip
                    pygame.draw.line(self.tela, (60, 38, 18),
                                     (int(hand_x), int(hand_y)),
                                     (int(cabo_ex), int(cabo_ey)), larg + 2)
                    pygame.draw.line(self.tela, (100, 65, 30),
                                     (int(hand_x), int(hand_y)),
                                     (int(cabo_ex), int(cabo_ey)), max(1, larg))
                    # Faixas de grip
                    for gi in range(1, 4):
                        gt = gi / 4
                        gx = int(hand_x + (cabo_ex - hand_x) * gt)
                        gy = int(hand_y + (cabo_ey - hand_y) * gt)
                        gp_x = math.cos(daga_ang + math.pi/2) * (larg + 1)
                        gp_y = math.sin(daga_ang + math.pi/2) * (larg + 1)
                        pygame.draw.line(self.tela, (45, 28, 10),
                                         (int(gx-gp_x), int(gy-gp_y)),
                                         (int(gx+gp_x), int(gy+gp_y)), 1)

                    # ── Guarda cruzada (finger guard) ──
                    grd_x = math.cos(daga_ang + math.pi/2) * (larg + 3)
                    grd_y = math.sin(daga_ang + math.pi/2) * (larg + 3)
                    pygame.draw.line(self.tela, (150, 155, 165),
                                     (int(cabo_ex - grd_x), int(cabo_ey - grd_y)),
                                     (int(cabo_ex + grd_x), int(cabo_ey + grd_y)), max(2, larg))

                    # ── Lâmina: reta com ponta levemente curvada para dentro ──
                    # Divide em dois segmentos: corpo reto + curva terminal
                    corpo_pct = 0.72  # 72% da lâmina é reta
                    curva_pct = 0.28  # 28% final curva levemente

                    corpo_end_x = cabo_ex + math.cos(daga_ang) * lamina_len * corpo_pct
                    corpo_end_y = cabo_ey + math.sin(daga_ang) * lamina_len * corpo_pct

                    # Curva da ponta (gira ligeiramente para o centro)
                    curva_deg = -12 * lado_sinal  # curva para dentro
                    curva_ang = daga_ang + math.radians(curva_deg)
                    tip_x = corpo_end_x + math.cos(curva_ang) * lamina_len * curva_pct
                    tip_y = corpo_end_y + math.sin(curva_ang) * lamina_len * curva_pct

                    # Largura da lâmina (afunila até a ponta)
                    lam_w_base = max(3, larg - 1)
                    lam_w_tip  = max(1, larg // 3)

                    # Sombra da lâmina
                    pygame.draw.line(self.tela, (20, 20, 25),
                                     (int(cabo_ex)+1, int(cabo_ey)+1),
                                     (int(tip_x)+1,   int(tip_y)+1), lam_w_base + 2)

                    # Corpo da lâmina (parte reta)
                    perp_bx = math.cos(daga_ang + math.pi/2)
                    perp_by = math.sin(daga_ang + math.pi/2)
                    lam_poly = [
                        (int(cabo_ex - perp_bx * lam_w_base), int(cabo_ey - perp_by * lam_w_base)),
                        (int(cabo_ex + perp_bx * lam_w_base), int(cabo_ey + perp_by * lam_w_base)),
                        (int(corpo_end_x + perp_bx * lam_w_tip), int(corpo_end_y + perp_by * lam_w_tip)),
                        (int(tip_x), int(tip_y)),
                        (int(corpo_end_x - perp_bx * lam_w_tip), int(corpo_end_y - perp_by * lam_w_tip)),
                    ]
                    try:
                        pygame.draw.polygon(self.tela, cor_escura, lam_poly)
                        pygame.draw.polygon(self.tela, cor, lam_poly, 1)
                    except (pygame.error, TypeError, ValueError, OverflowError): pass
                    # Fio da lâmina (highlight central)
                    pygame.draw.line(self.tela, cor_clara,
                                     (int(cabo_ex), int(cabo_ey)),
                                     (int(corpo_end_x), int(corpo_end_y)), 1)

                    # ── Glow de energia durante ataque ──
                    if atacando or glow_alpha_base > 50:
                        try:
                            sz = max(8, int(lamina_len * 2))
                            gs = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                            mid_x = int((cabo_ex + tip_x) / 2) - sz
                            mid_y = int((cabo_ey + tip_y) / 2) - sz
                            local_s = (sz - int(cabo_ex - mid_x - sz), sz - int(cabo_ey - mid_y - sz))
                            local_e = (sz - int(cabo_ex - mid_x - sz) + int(tip_x - cabo_ex),
                                       sz - int(cabo_ey - mid_y - sz) + int(tip_y - cabo_ey))
                            pygame.draw.line(gs, (*cor, glow_alpha_base),
                                             (max(0,min(sz*2-1,local_s[0])), max(0,min(sz*2-1,local_s[1]))),
                                             (max(0,min(sz*2-1,local_e[0])), max(0,min(sz*2-1,local_e[1]))),
                                             max(4, lam_w_base + 3))
                            self.tela.blit(gs, (mid_x, mid_y))
                        except (pygame.error, TypeError, ValueError, OverflowError): pass

                    # ── Runa na lâmina (raridade) ──
                    if raridade not in ['Comum', 'Incomum']:
                        rune_x = int((cabo_ex + corpo_end_x) / 2)
                        rune_y = int((cabo_ey + corpo_end_y) / 2)
                        rune_a = int(160 + 80 * math.sin(tempo / 120 + i * math.pi))
                        try:
                            rs = pygame.Surface((8, 8), pygame.SRCALPHA)
                            pygame.draw.circle(rs, (*cor_raridade, rune_a), (4, 4), 3)
                            self.tela.blit(rs, (rune_x - 4, rune_y - 4))
                        except (pygame.error, TypeError, ValueError, OverflowError): pass

                    # ── Ponta brilhante ──
                    tip_r = max(2, larg - 1)
                    tip_a = int(160 + 80 * math.sin(tempo / 90 + i))
                    try:
                        ts = pygame.Surface((tip_r * 5, tip_r * 5), pygame.SRCALPHA)
                        pygame.draw.circle(ts, (*cor_clara, tip_a), (tip_r*2, tip_r*2), tip_r * 2)
                        self.tela.blit(ts, (int(tip_x) - tip_r*2, int(tip_y) - tip_r*2))
                    except (pygame.error, TypeError, ValueError, OverflowError): pass
                    tip_cor = cor_raridade if raridade not in ['Comum'] else cor_clara
                    pygame.draw.circle(self.tela, tip_cor, (int(tip_x), int(tip_y)), tip_r)

            else:
                # Outras armas Dupla (Sai, Garras, etc.)
                cabo_len = getattr(arma, 'comp_cabo', 20) * base_scale * 1.3
                lamina_len = getattr(arma, 'comp_lamina', 55) * base_scale * 1.8 * anim_scale
                for i, offset_deg in enumerate([-35, 35]):
                    r = rad + math.radians(offset_deg)
                    lado = math.cos(rad + math.pi/2) * sep * (1 if i == 0 else -1)
                    lado_y = math.sin(rad + math.pi/2) * sep * (1 if i == 0 else -1)
                    bx = cx + lado * 0.5; by = cy + lado_y * 0.5
                    cex = bx + math.cos(r) * cabo_len; cey = by + math.sin(r) * cabo_len
                    lex = bx + math.cos(r) * (cabo_len + lamina_len)
                    ley = by + math.sin(r) * (cabo_len + lamina_len)
                    pygame.draw.line(self.tela, (80, 50, 30), (int(bx), int(by)), (int(cex), int(cey)), larg)
                    px2 = math.cos(r + math.pi/2) * larg * 0.5; py2 = math.sin(r + math.pi/2) * larg * 0.5
                    pts2 = [(int(cex-px2),int(cey-py2)),(int(cex+px2),int(cey+py2)),(int(lex),int(ley))]
                    pygame.draw.polygon(self.tela, cor, pts2)
                    pygame.draw.polygon(self.tela, cor_clara, pts2, 1)
                    pygame.draw.circle(self.tela, cor_raridade, (int(lex), int(ley)), max(2, larg//2))
        
        # === CORRENTE - MANGUAL v3.0 (Heavy Flail com Física de Elos) ===
        elif tipo == "Corrente":
            estilo_arma = getattr(arma, 'estilo', '')

            if estilo_arma == "Mangual":
                # ── MANGUAL v3.0: Cabo pesado + Elos de ferro fundido + Bola espigada ──
                cabo_tam  = getattr(arma, 'comp_cabo', 18) * base_scale * 1.0
                corrente_comp = getattr(arma, 'comp_corrente', 60) * base_scale * 1.15 * anim_scale
                ponta_tam = max(6, int(raio_char * 0.20 * anim_scale))
                num_elos = 6
                pulso = 0.5 + 0.5 * math.sin(tempo / 200)

                # ── Cabo de madeira grossa ──
                cabo_ex = cx + math.cos(rad) * cabo_tam
                cabo_ey = cy + math.sin(rad) * cabo_tam
                # Sombra do cabo
                pygame.draw.line(self.tela, (30, 20, 10),
                                 (int(cx)+2, int(cy)+2), (int(cabo_ex)+2, int(cabo_ey)+2), max(6, larg_base + 4))
                # Madeira do cabo
                pygame.draw.line(self.tela, (90, 55, 25),
                                 (int(cx), int(cy)), (int(cabo_ex), int(cabo_ey)), max(6, larg_base + 4))
                pygame.draw.line(self.tela, (130, 85, 40),
                                 (int(cx), int(cy)), (int(cabo_ex), int(cabo_ey)), max(3, larg_base))
                # Faixas de couro no cabo
                for fi in range(1, 5):
                    ft = fi / 5
                    fx = int(cx + (cabo_ex - cx) * ft)
                    fy = int(cy + (cabo_ey - cy) * ft)
                    fperp_x = math.cos(rad + math.pi/2) * (larg_base + 2)
                    fperp_y = math.sin(rad + math.pi/2) * (larg_base + 2)
                    pygame.draw.line(self.tela, (55, 30, 10),
                                     (int(fx - fperp_x), int(fy - fperp_y)),
                                     (int(fx + fperp_x), int(fy + fperp_y)), 2)

                # ── Argola de conexão ──
                anel_r = max(4, larg_base + 1)
                pygame.draw.circle(self.tela, (80, 80, 90), (int(cabo_ex), int(cabo_ey)), anel_r + 2)
                pygame.draw.circle(self.tela, (160, 165, 175), (int(cabo_ex), int(cabo_ey)), anel_r, 3)
                pygame.draw.circle(self.tela, (200, 205, 215), (int(cabo_ex), int(cabo_ey)), max(2, anel_r - 2), 1)

                # ── Corrente com elos fundidos (pendular arc) ──
                chain_pts = []
                sag = corrente_comp * 0.08 * (1 + 0.08 * math.sin(tempo / 200))  # Sag gravitacional (reduzido v3.1)
                for ei in range(num_elos + 1):
                    t = ei / num_elos
                    # Catenary approximation: arco para baixo
                    base_px = cabo_ex + math.cos(rad) * corrente_comp * t
                    base_py = cabo_ey + math.sin(rad) * corrente_comp * t
                    # Curvatura gravitacional + ondulação de momentum
                    gravity_y = sag * math.sin(t * math.pi) * math.sin(rad + math.pi/2) * -1
                    wave = math.sin(t * math.pi * 2 + tempo / 200) * raio_char * 0.03 * (1 - t * 0.4)
                    wave_x = math.cos(rad + math.pi/2) * wave
                    wave_y = math.sin(rad + math.pi/2) * wave + gravity_y
                    chain_pts.append((base_px + wave_x, base_py + wave_y))

                # Sombra da corrente
                shadow_chain = [(int(p[0]+3), int(p[1]+3)) for p in chain_pts]
                if len(shadow_chain) > 1:
                    try: pygame.draw.lines(self.tela, (20, 20, 22), False, shadow_chain, max(4, larg_base + 2))
                    except (pygame.error, TypeError, ValueError, OverflowError): pass

                # Elos individuais (alternando horizontal/vertical)
                elo_w = max(5, larg_base + 2)
                elo_h = max(3, larg_base - 1)
                for ei in range(len(chain_pts)):
                    ex, ey = chain_pts[ei]
                    elo_ang = rad + math.pi/2 if ei % 2 == 0 else rad
                    # Elo como elipse/retângulo rotacionado
                    elo_perp_x = math.cos(elo_ang) * elo_w
                    elo_perp_y = math.sin(elo_ang) * elo_w
                    elo_fwd_x = math.cos(elo_ang + math.pi/2) * elo_h
                    elo_fwd_y = math.sin(elo_ang + math.pi/2) * elo_h
                    elo_pts = [
                        (int(ex - elo_perp_x - elo_fwd_x), int(ey - elo_perp_y - elo_fwd_y)),
                        (int(ex + elo_perp_x - elo_fwd_x), int(ey + elo_perp_y - elo_fwd_y)),
                        (int(ex + elo_perp_x + elo_fwd_x), int(ey + elo_perp_y + elo_fwd_y)),
                        (int(ex - elo_perp_x + elo_fwd_x), int(ey - elo_perp_y + elo_fwd_y)),
                    ]
                    try:
                        pygame.draw.polygon(self.tela, (90, 92, 100), elo_pts)
                        pygame.draw.polygon(self.tela, (145, 148, 160), elo_pts, 1)
                    except (pygame.error, TypeError, ValueError, OverflowError): pass

                # ── Bola espigada (iron flail head) ──
                if chain_pts:
                    end_x, end_y = chain_pts[-1]
                    ball_r = ponta_tam

                    # Glow de impacto (quando atacando)
                    if atacando:
                        glow_r = int(ball_r * 2.2)
                        try:
                            gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                            glow_a = int(120 * anim_scale)
                            pygame.draw.circle(gs, (*cor, min(255, glow_a)), (glow_r, glow_r), glow_r)
                            self.tela.blit(gs, (int(end_x) - glow_r, int(end_y) - glow_r))
                        except (pygame.error, TypeError, ValueError, OverflowError): pass

                    # Sombra da bola
                    pygame.draw.circle(self.tela, (15, 15, 18), (int(end_x) + 3, int(end_y) + 3), ball_r + 1)

                    # Bola principal (esfera fundida)
                    pygame.draw.circle(self.tela, cor_escura, (int(end_x), int(end_y)), ball_r)
                    pygame.draw.circle(self.tela, cor, (int(end_x), int(end_y)), ball_r - 1)
                    # Highlight da esfera
                    hl_x = int(end_x - ball_r * 0.3)
                    hl_y = int(end_y - ball_r * 0.3)
                    pygame.draw.circle(self.tela, cor_clara, (hl_x, hl_y), max(2, ball_r // 3))

                    # Spikes (6 espinhos fundidos)
                    num_spikes = 6
                    spike_len = ball_r * 0.7
                    spike_base_w = max(2, ball_r // 4)
                    spike_rot = tempo / 80  # Lenta rotação visual
                    for si in range(num_spikes):
                        s_ang = spike_rot + (si * math.pi * 2 / num_spikes)
                        # Base do spike na superfície da bola
                        s_base_x = end_x + math.cos(s_ang) * (ball_r - 1)
                        s_base_y = end_y + math.sin(s_ang) * (ball_r - 1)
                        # Ponta do spike
                        s_tip_x = end_x + math.cos(s_ang) * (ball_r + spike_len)
                        s_tip_y = end_y + math.sin(s_ang) * (ball_r + spike_len)
                        # Spike como triângulo
                        perp_sx = math.cos(s_ang + math.pi/2) * spike_base_w
                        perp_sy = math.sin(s_ang + math.pi/2) * spike_base_w
                        spike_pts = [
                            (int(s_base_x - perp_sx), int(s_base_y - perp_sy)),
                            (int(s_base_x + perp_sx), int(s_base_y + perp_sy)),
                            (int(s_tip_x), int(s_tip_y)),
                        ]
                        try:
                            pygame.draw.polygon(self.tela, cor, spike_pts)
                            pygame.draw.polygon(self.tela, cor_clara, spike_pts, 1)
                        except (pygame.error, TypeError, ValueError, OverflowError): pass

                    # Anel de reforço na bola
                    pygame.draw.circle(self.tela, (70, 72, 80), (int(end_x), int(end_y)), ball_r, 2)

                    # Glow de raridade
                    if raridade not in ['Comum']:
                        rar_alpha = int(100 + 80 * pulso)
                        try:
                            rs = pygame.Surface((ball_r * 4, ball_r * 4), pygame.SRCALPHA)
                            pygame.draw.circle(rs, (*cor_raridade, rar_alpha),
                                               (ball_r * 2, ball_r * 2), ball_r + 4)
                            self.tela.blit(rs, (int(end_x) - ball_r * 2, int(end_y) - ball_r * 2))
                        except (pygame.error, TypeError, ValueError, OverflowError): pass

            else:
                # Outras correntes (Chicote, Kusarigama, etc.)
                comp_total = getattr(arma, 'comp_corrente', 80) * base_scale * 2.5 * anim_scale
                ponta_tam = max(6, int(raio_char * 0.25))
                num_segs = 15
                pts = []
                for i in range(num_segs + 1):
                    t = i / num_segs
                    wave_amp = raio_char * 0.15 * (1 - t * 0.5)
                    wave = math.sin(t * math.pi * 4 + tempo / 150) * wave_amp
                    px2 = cx + math.cos(rad) * (comp_total * t)
                    py2 = cy + math.sin(rad) * (comp_total * t)
                    perp_x = math.cos(rad + math.pi/2) * wave
                    perp_y = math.sin(rad + math.pi/2) * wave
                    pts.append((int(px2 + perp_x), int(py2 + perp_y)))
                if len(pts) > 1:
                    shadow_pts = [(p[0]+2, p[1]+2) for p in pts]
                    try: pygame.draw.lines(self.tela, (30, 30, 30), False, shadow_pts, max(3, larg_base))
                    except (pygame.error, TypeError, ValueError, OverflowError): pass
                    try: pygame.draw.lines(self.tela, (120, 120, 130), False, pts, max(3, larg_base))
                    except (pygame.error, TypeError, ValueError, OverflowError): pass
                    for i, (px2, py2) in enumerate(pts):
                        if i % 2 == 0:
                            pygame.draw.circle(self.tela, (90, 90, 100), (px2, py2), max(2, larg_base//2))
                if pts:
                    end_x, end_y = pts[-1]
                    pygame.draw.circle(self.tela, cor, (end_x, end_y), ponta_tam)
                    pygame.draw.circle(self.tela, cor_escura, (end_x, end_y), ponta_tam, 2)
                    for spike_ang in range(0, 360, 45):
                        spike_r = math.radians(spike_ang + tempo/50)
                        sx = end_x + math.cos(spike_r) * ponta_tam * 1.4
                        sy = end_y + math.sin(spike_r) * ponta_tam * 1.4
                        pygame.draw.line(self.tela, cor_clara, (end_x, end_y), (int(sx), int(sy)), max(2, larg_base//2))
                    if raridade not in ['Comum']:
                        pygame.draw.circle(self.tela, cor_raridade, (end_x, end_y), ponta_tam + 3, 2)
        
        # === ARREMESSO (Facas, Chakram, Shuriken) ===
        elif tipo == "Arremesso":
            tam_proj = max(8, int(raio_char * 0.35))
            qtd = min(5, int(getattr(arma, 'quantidade', 3)))
            
            for i in range(qtd):
                offset_ang = (i - (qtd-1)/2) * 18
                r = rad + math.radians(offset_ang)
                
                dist = raio_char * 1.1 + tam_proj * 0.5
                px = cx + math.cos(r) * dist
                py = cy + math.sin(r) * dist
                
                # Rotação individual
                rot = tempo / 100 + i * 60
                
                # Desenha shuriken/chakram
                num_pontas = 4 if i % 2 == 0 else 6
                pontas = []
                
                for j in range(num_pontas * 2):
                    ang = rot + (j * math.pi / num_pontas)
                    raio = tam_proj if j % 2 == 0 else tam_proj * 0.4
                    pontas.append((
                        int(px + math.cos(ang) * raio),
                        int(py + math.sin(ang) * raio)
                    ))
                
                if len(pontas) >= 3:
                    pygame.draw.polygon(self.tela, cor, pontas)
                    pygame.draw.polygon(self.tela, cor_clara, pontas, 1)
                
                # Centro
                pygame.draw.circle(self.tela, cor_escura, (int(px), int(py)), max(2, tam_proj//3))
        
        # === ARCO ===
        elif tipo == "Arco":
            tam_arco = raio_char * 1.4 * anim_scale
            tam_flecha = raio_char * 2.0 * anim_scale
            
            # Desenha arco curvado
            arco_pts = []
            for i in range(13):
                ang = rad + math.radians(-50 + i * (100/12))
                # Curva do arco
                curva = math.sin((i / 12) * math.pi) * tam_arco * 0.15
                raio = tam_arco * 0.5 + curva
                arco_pts.append((
                    int(cx + math.cos(ang) * raio),
                    int(cy + math.sin(ang) * raio)
                ))
            
            if len(arco_pts) > 1:
                # Corpo do arco (madeira)
                pygame.draw.lines(self.tela, cor, False, arco_pts, max(4, larg_base))
                pygame.draw.lines(self.tela, cor_escura, False, arco_pts, 1)
                
                # Corda
                pygame.draw.line(self.tela, (200, 180, 140), arco_pts[0], arco_pts[-1], 2)
            
            # Flecha
            flecha_start_x = cx
            flecha_start_y = cy
            flecha_end_x = cx + math.cos(rad) * tam_flecha
            flecha_end_y = cy + math.sin(rad) * tam_flecha
            
            # Corpo da flecha
            pygame.draw.line(self.tela, (139, 90, 43), 
                           (int(flecha_start_x), int(flecha_start_y)), 
                           (int(flecha_end_x), int(flecha_end_y)), max(2, larg_base//2))
            
            # Ponta da flecha
            ponta_len = tam_flecha * 0.15
            perp = math.pi/2
            ponta_pts = [
                (int(flecha_end_x), int(flecha_end_y)),
                (int(flecha_end_x - math.cos(rad)*ponta_len + math.cos(rad+perp)*ponta_len*0.4),
                 int(flecha_end_y - math.sin(rad)*ponta_len + math.sin(rad+perp)*ponta_len*0.4)),
                (int(flecha_end_x - math.cos(rad)*ponta_len - math.cos(rad+perp)*ponta_len*0.4),
                 int(flecha_end_y - math.sin(rad)*ponta_len - math.sin(rad+perp)*ponta_len*0.4)),
            ]
            pygame.draw.polygon(self.tela, cor_raridade, ponta_pts)
            
            # Penas da flecha
            for pena_off in [-1, 1]:
                pena_x = flecha_start_x + math.cos(rad) * tam_flecha * 0.15
                pena_y = flecha_start_y + math.sin(rad) * tam_flecha * 0.15
                pena_end_x = pena_x + math.cos(rad + pena_off * 0.5) * tam_flecha * 0.1
                pena_end_y = pena_y + math.sin(rad + pena_off * 0.5) * tam_flecha * 0.1
                pygame.draw.line(self.tela, (200, 50, 50), 
                               (int(pena_x), int(pena_y)), (int(pena_end_x), int(pena_end_y)), 2)
        
        # === ORBITAL (Escudo, Drone, Orbes) ===
        elif tipo == "Orbital":
            dist_orbit = raio_char * 1.6
            qtd = max(1, min(5, int(getattr(arma, 'quantidade_orbitais', 2))))
            tam_orbe = max(6, int(raio_char * 0.3))
            
            rot_speed = tempo / 800
            
            for i in range(qtd):
                ang = rot_speed + (2 * math.pi / qtd) * i
                ox = cx + math.cos(ang) * dist_orbit
                oy = cy + math.sin(ang) * dist_orbit
                
                # Linha conectora sutil
                pygame.draw.line(self.tela, (60, 60, 80), (int(cx), int(cy)), (int(ox), int(oy)), 1)
                
                # Orbe com glow
                for glow_r in range(3, 0, -1):
                    alpha_cor = tuple(min(255, c + glow_r * 20) for c in cor)
                    pygame.draw.circle(self.tela, alpha_cor, (int(ox), int(oy)), tam_orbe + glow_r)
                
                pygame.draw.circle(self.tela, cor, (int(ox), int(oy)), tam_orbe)
                pygame.draw.circle(self.tela, cor_clara, (int(ox), int(oy)), tam_orbe//2)
                pygame.draw.circle(self.tela, cor_raridade, (int(ox), int(oy)), tam_orbe, 2)
        
        # === MÁGICA (Espadas espectrais, Runas) ===
        elif tipo == "Mágica":
            qtd = min(5, int(getattr(arma, 'quantidade', 3)))
            tam_espada = max(12, int(raio_char * 0.7))
            dist_base = raio_char * 1.4
            
            float_offset = math.sin(tempo / 250) * raio_char * 0.1
            rot_offset = tempo / 1500
            
            for i in range(qtd):
                offset_ang = (i - (qtd-1)/2) * 22 + math.degrees(rot_offset)
                r = rad + math.radians(offset_ang)
                
                dist = dist_base + float_offset * (1 + i * 0.2)
                px = cx + math.cos(r) * dist
                py = cy + math.sin(r) * dist
                
                # Espada espectral
                sword_end_x = px + math.cos(r) * tam_espada
                sword_end_y = py + math.sin(r) * tam_espada
                
                # Glow da espada
                for glow in range(4, 0, -1):
                    pygame.draw.line(self.tela, cor, 
                                   (int(px), int(py)), (int(sword_end_x), int(sword_end_y)), 
                                   max(2, larg_base//2) + glow)
                
                # Espada principal
                pygame.draw.line(self.tela, cor_clara, 
                               (int(px), int(py)), (int(sword_end_x), int(sword_end_y)), 
                               max(3, larg_base//2))
                
                # Ponta brilhante
                pygame.draw.circle(self.tela, cor_raridade, (int(sword_end_x), int(sword_end_y)), 3)
                
                # Runa flutuante no centro
                runa_pulso = 0.7 + 0.3 * math.sin(tempo / 200 + i)
                pygame.draw.circle(self.tela, cor_raridade, (int(px), int(py)), int(4 * runa_pulso), 1)
        
        # === TRANSFORMÁVEL ===
        elif tipo == "Transformável":
            forma = getattr(arma, 'forma_atual', 1)
            
            if forma == 1:
                cabo_len = getattr(arma, 'forma1_cabo', 20) * base_scale * 1.2
                lamina_len = getattr(arma, 'forma1_lamina', 50) * base_scale * 1.4 * anim_scale
            else:
                cabo_len = getattr(arma, 'forma2_cabo', 30) * base_scale * 1.2
                lamina_len = getattr(arma, 'forma2_lamina', 80) * base_scale * 1.4 * anim_scale
            
            cabo_end_x = cx + math.cos(rad) * cabo_len
            cabo_end_y = cy + math.sin(rad) * cabo_len
            lamina_end_x = cx + math.cos(rad) * (cabo_len + lamina_len)
            lamina_end_y = cy + math.sin(rad) * (cabo_len + lamina_len)
            
            larg = max(4, int(larg_base * 1.1))
            
            # Mecanismo de transformação
            pygame.draw.circle(self.tela, (100, 100, 110), (int(cabo_end_x), int(cabo_end_y)), larg)
            
            # Cabo
            pygame.draw.line(self.tela, (80, 50, 30), (int(cx), int(cy)), (int(cabo_end_x), int(cabo_end_y)), larg)
            
            # Lâmina
            pygame.draw.line(self.tela, cor, (int(cabo_end_x), int(cabo_end_y)), (int(lamina_end_x), int(lamina_end_y)), larg)
            pygame.draw.line(self.tela, cor_clara, (int(cabo_end_x), int(cabo_end_y)), (int(lamina_end_x), int(lamina_end_y)), larg//2)
            
            # Indicador de forma
            pygame.draw.circle(self.tela, cor_raridade, (int(lamina_end_x), int(lamina_end_y)), max(4, larg//2))
        
        # === FALLBACK ===
        else:
            cabo_len = getattr(arma, 'comp_cabo', 20) * base_scale
            lamina_len = getattr(arma, 'comp_lamina', 50) * base_scale * anim_scale
            
            cabo_end_x = cx + math.cos(rad) * cabo_len
            cabo_end_y = cy + math.sin(rad) * cabo_len
            lamina_end_x = cx + math.cos(rad) * (cabo_len + lamina_len)
            lamina_end_y = cy + math.sin(rad) * (cabo_len + lamina_len)
            
            pygame.draw.line(self.tela, (80, 50, 30), (int(cx), int(cy)), (int(cabo_end_x), int(cabo_end_y)), larg_base)
            pygame.draw.line(self.tela, cor, (int(cabo_end_x), int(cabo_end_y)), (int(lamina_end_x), int(lamina_end_y)), larg_base)

    def desenhar_hitbox_debug(self):
        """Desenha visualização de debug das hitboxes"""
        fonte = pygame.font.SysFont("Arial", 10)
        
        # Desenha hitboxes em tempo real para cada lutador
        for p in [self.p1, self.p2]:
            if p.morto or self._alvo_em_transicao_sombria(p):
                continue
            
            cor_debug = (0, 255, 0, 128) if p == self.p1 else (255, 255, 0, 128)
            
            # Calcula hitbox atual
            hitbox = sistema_hitbox.calcular_hitbox_arma(p)
            if not hitbox:
                continue
            
            # Posição na tela
            cx_screen, cy_screen = self.cam.converter(hitbox.centro[0], hitbox.centro[1])
            off_y = self.cam.converter_tam(p.z * PPM)
            cy_screen -= off_y
            
            # Surface transparente para desenho
            s = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            
            # Desenha raio de alcance
            alcance_screen = self.cam.converter_tam(hitbox.alcance)
            pygame.draw.circle(s, (*cor_debug[:3], 30), (cx_screen, cy_screen), alcance_screen, 2)
            
            # Se tem pontos (arma de lâmina ou corrente)
            if hitbox.pontos:
                # Corrente: desenha como arco
                if hitbox.tipo == "Corrente":
                    # Desenha os segmentos do arco
                    cor_arco = (255, 128, 0, 200) if hitbox.ativo else (100, 100, 100, 100)
                    pontos_screen = []
                    for ponto in hitbox.pontos:
                        ps = self.cam.converter(ponto[0], ponto[1])
                        pontos_screen.append((ps[0], ps[1] - off_y))
                    
                    # Desenha linhas conectando os pontos do arco
                    if len(pontos_screen) > 1:
                        for i in range(len(pontos_screen) - 1):
                            pygame.draw.line(s, cor_arco, pontos_screen[i], pontos_screen[i+1], 3)
                    
                    # Desenha círculo na posição real da bola (centro do arco, no ângulo da arma)
                    rad_bola = math.radians(hitbox.angulo)
                    bola_x = hitbox.centro[0] + math.cos(rad_bola) * hitbox.alcance
                    bola_y = hitbox.centro[1] + math.sin(rad_bola) * hitbox.alcance
                    bola_screen = self.cam.converter(bola_x, bola_y)
                    bola_screen = (bola_screen[0], bola_screen[1] - off_y)
                    pygame.draw.circle(s, (255, 50, 50, 255), bola_screen, 10, 3)  # Círculo vermelho na bola
                    
                    # Linha do centro até a bola
                    pygame.draw.line(s, (255, 128, 0, 100), (cx_screen, cy_screen), bola_screen, 1)
                    
                    # Desenha raio mínimo da corrente (onde ela NÃO acerta)
                    alcance_min = hitbox.alcance * 0.4
                    alcance_min_screen = self.cam.converter_tam(alcance_min)
                    pygame.draw.circle(s, (100, 100, 100, 50), (cx_screen, cy_screen), alcance_min_screen, 1)
                    
                    # Label
                    label = f"{p.dados.nome}: Corrente"
                    if hitbox.ativo:
                        label += f" [GIRANDO t={p.timer_animacao:.2f}]"
                    txt = fonte.render(label, True, BRANCO)
                    s.blit(txt, (cx_screen - 50, cy_screen - alcance_screen - 20))
                
                # Armas Ranged: desenha linhas de trajetória
                elif hitbox.tipo in ["Arremesso", "Arco"]:
                    cor_traj = (0, 200, 255, 150) if hitbox.ativo else (100, 100, 100, 80)
                    
                    # Múltiplos projéteis ou linha única
                    if len(hitbox.pontos) > 2:
                        # Múltiplos pontos = múltiplos projéteis
                        for ponto in hitbox.pontos:
                            ps = self.cam.converter(ponto[0], ponto[1])
                            ps = (ps[0], ps[1] - off_y)
                            # Linha tracejada do centro até destino
                            pygame.draw.line(s, cor_traj, (cx_screen, cy_screen), ps, 1)
                            pygame.draw.circle(s, cor_traj, ps, 5)
                    else:
                        # Linha única
                        if len(hitbox.pontos) == 2:
                            p1_screen = self.cam.converter(hitbox.pontos[0][0], hitbox.pontos[0][1])
                            p2_screen = self.cam.converter(hitbox.pontos[1][0], hitbox.pontos[1][1])
                            p1_screen = (p1_screen[0], p1_screen[1] - off_y)
                            p2_screen = (p2_screen[0], p2_screen[1] - off_y)
                            pygame.draw.line(s, cor_traj, p1_screen, p2_screen, 2)
                            pygame.draw.circle(s, (255, 100, 100), p2_screen, 6)
                    
                    # Label
                    label = f"{p.dados.nome}: {hitbox.tipo} [RANGED]"
                    if hitbox.ativo:
                        label += " DISPARANDO!"
                    txt = fonte.render(label, True, (0, 200, 255))
                    s.blit(txt, (cx_screen - 50, cy_screen - alcance_screen - 20))
                    
                else:
                    # Arma de lâmina normal
                    p1_screen = self.cam.converter(hitbox.pontos[0][0], hitbox.pontos[0][1])
                    p2_screen = self.cam.converter(hitbox.pontos[1][0], hitbox.pontos[1][1])
                    p1_screen = (p1_screen[0], p1_screen[1] - off_y)
                    p2_screen = (p2_screen[0], p2_screen[1] - off_y)
                    
                    # Linha da lâmina
                    cor_linha = (255, 0, 0, 200) if hitbox.ativo else (100, 100, 100, 100)
                    pygame.draw.line(s, cor_linha, p1_screen, p2_screen, 4)
                    
                    # Pontos nas extremidades
                    pygame.draw.circle(s, (255, 255, 0), p1_screen, 5)
                    pygame.draw.circle(s, (255, 0, 0), p2_screen, 5)
                    
                    # Label
                    label = f"{p.dados.nome}: {hitbox.tipo}"
                    if hitbox.ativo:
                        label += f" [ATACANDO t={p.timer_animacao:.2f}]"
                    txt = fonte.render(label, True, BRANCO)
                    s.blit(txt, (cx_screen - 50, cy_screen - alcance_screen - 20))
            
            # Arma de área
            else:
                # Desenha arco de ângulo
                rad = math.radians(hitbox.angulo)
                rad_min = rad - math.radians(hitbox.largura_angular / 2)
                rad_max = rad + math.radians(hitbox.largura_angular / 2)
                
                # Linha central
                fx = cx_screen + math.cos(rad) * alcance_screen
                fy = cy_screen + math.sin(rad) * alcance_screen
                pygame.draw.line(s, (*cor_debug[:3], 150), (cx_screen, cy_screen), (int(fx), int(fy)), 2)
                
                # Limites do arco
                fx_min = cx_screen + math.cos(rad_min) * alcance_screen
                fy_min = cy_screen + math.sin(rad_min) * alcance_screen
                fx_max = cx_screen + math.cos(rad_max) * alcance_screen
                fy_max = cy_screen + math.sin(rad_max) * alcance_screen
                pygame.draw.line(s, (*cor_debug[:3], 100), (cx_screen, cy_screen), (int(fx_min), int(fy_min)), 1)
                pygame.draw.line(s, (*cor_debug[:3], 100), (cx_screen, cy_screen), (int(fx_max), int(fy_max)), 1)
            
            self.tela.blit(s, (0, 0))
        
        # Desenha painel de debug no canto
        self.desenhar_painel_debug()
    
    def desenhar_painel_debug(self):
        """Desenha painel com info de debug"""
        x, y = self.screen_width - 300, 80
        w, h = 280, 250
        
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.tela.blit(s, (x, y))
        pygame.draw.rect(self.tela, (255, 100, 100), (x, y, w, h), 2)
        
        fonte = pygame.font.SysFont("Arial", 10)
        fonte_bold = pygame.font.SysFont("Arial", 11, bold=True)
        
        self.tela.blit(fonte_bold.render("DEBUG HITBOX [H para toggle]", True, (255, 100, 100)), (x + 10, y + 5))
        
        # Distância entre lutadores
        dist = math.hypot(self.p2.pos[0] - self.p1.pos[0], self.p2.pos[1] - self.p1.pos[1])
        self.tela.blit(fonte_bold.render(f"Distância: {dist:.2f}m", True, (200, 200, 255)), (x + 10, y + 22))
        
        off = 40
        for p in [self.p1, self.p2]:
            cor = (100, 255, 100) if p == self.p1 else (255, 255, 100)
            self.tela.blit(fonte_bold.render(f"=== {p.dados.nome} ===", True, cor), (x + 10, y + off))
            off += 14
            
            arma = p.dados.arma_obj
            if arma:
                self.tela.blit(fonte.render(f"Arma: {arma.nome} ({arma.tipo})", True, BRANCO), (x + 10, y + off))
                off += 11
            
            # Status de ataque
            atk_cor = (0, 255, 0) if p.atacando else (150, 150, 150)
            self.tela.blit(fonte.render(f"Atacando: {p.atacando} Timer: {p.timer_animacao:.3f}", True, atk_cor), (x + 10, y + off))
            off += 11
            self.tela.blit(fonte.render(f"Alcance IA: {p.alcance_ideal:.2f}m CD: {p.cooldown_ataque:.2f}", True, BRANCO), (x + 10, y + off))
            off += 11
            acao_atual = p.brain.acao_atual if p.brain is not None else "MANUAL"
            self.tela.blit(fonte.render(f"Ação: {acao_atual}", True, BRANCO), (x + 10, y + off))
            off += 16

    def desenhar_barras(self, l, x, y, cor, vida_vis):
        # Ajusta largura das barras baseado no modo (menor em portrait)
        w = 200 if self.portrait_mode else 300
        h = 25 if self.portrait_mode else 30
        pygame.draw.rect(self.tela, (20,20,20), (x, y, w, h))
        pct_vis = max(0, vida_vis / l.vida_max); pygame.draw.rect(self.tela, BRANCO, (x, y, int(w * pct_vis), h))
        pct_real = max(0, l.vida / l.vida_max); pygame.draw.rect(self.tela, cor, (x, y, int(w * pct_real), h))
        pygame.draw.rect(self.tela, BRANCO, (x, y, w, h), 2)
        pct_mana = max(0, l.mana / l.mana_max)
        pygame.draw.rect(self.tela, (20, 20, 20), (x, y + h + 5, w, 10))
        pygame.draw.rect(self.tela, AZUL_MANA, (x, y + h + 5, int(w * pct_mana), 10))
        ft_size = 14 if self.portrait_mode else 16
        ft = pygame.font.SysFont("Arial", ft_size, bold=True)
        self.tela.blit(ft.render(f"{l.dados.nome}", True, BRANCO), (x+10, y+5))

    def _renderizar_texto_ajustado(
        self, texto, fonte_nome, tamanho, cor, largura_max, bold=False, tamanho_min=14
    ):
        """Renderiza uma linha sem deixá-la escapar da largura da tela."""
        tamanho_atual = tamanho
        while True:
            fonte = pygame.font.SysFont(fonte_nome, tamanho_atual, bold=bold)
            surface = fonte.render(texto, True, cor)
            if surface.get_width() <= largura_max or tamanho_atual <= tamanho_min:
                break
            tamanho_atual = max(tamanho_min, tamanho_atual - 2)

        if surface.get_width() > largura_max:
            escala = largura_max / surface.get_width()
            surface = pygame.transform.smoothscale(
                surface,
                (largura_max, max(1, int(surface.get_height() * escala))),
            )
        return surface

    def desenhar_placar_serie(self):
        serie = self.best_of_series
        texto = (
            f"ROUND {serie.round_number}  |  "
            f"P1 {serie.wins['p1']} x {serie.wins['p2']} P2  |  "
            f"MD{serie.best_of}"
        )
        surface = self._renderizar_texto_ajustado(
            texto,
            "Arial",
            20,
            COR_TEXTO_TITULO,
            self.screen_width - 40,
            bold=True,
        )
        placar_y = 70 if self.portrait_mode else 20
        self.tela.blit(surface, ((self.screen_width - surface.get_width()) // 2, placar_y))

    def desenhar_controles(self):
        x, y = 20, 90 
        w, h = 220, 210
        s = pygame.Surface((w, h), pygame.SRCALPHA); s.fill(COR_UI_BG); self.tela.blit(s, (x, y))
        pygame.draw.rect(self.tela, (100, 100, 100), (x, y, w, h), 1)
        fonte_tit = pygame.font.SysFont("Arial", 14, bold=True); fonte_txt = pygame.font.SysFont("Arial", 12)
        self.tela.blit(fonte_tit.render("COMANDOS", True, COR_TEXTO_TITULO), (x + 10, y + 10))
        comandos = [("WASD / Setas", "Mover Câmera"), ("Scroll", "Zoom"), ("1/2/3", "Modos Cam"), ("SPACE", "Pause"), ("T/F", "Speed"), ("TAB", "Dados"), ("G", "HUD"), ("H", "Debug Hitbox"), ("R", "Reset"), ("ESC", "Sair")]
        off_y = 35
        for t, a in comandos:
            self.tela.blit(fonte_txt.render(t, True, BRANCO), (x + 10, y + off_y))
            self.tela.blit(fonte_txt.render(a, True, COR_TEXTO_INFO), (x + 110, y + off_y))
            off_y += 16

    def desenhar_analise(self):
        s = pygame.Surface((300, self.screen_height)); s.fill(COR_UI_BG); self.tela.blit(s, (0,0))
        ft = pygame.font.SysFont("Consolas", 14)
        lines = [
            "--- ANÁLISE ---", f"FPS: {int(self.clock.get_fps())}", f"Cam: {self.cam.modo}", "",
            f"--- {self.p1.dados.nome} ---", f"HP: {int(self.p1.vida)}", f"Mana: {int(self.p1.mana)}", f"Estamina: {int(self.p1.estamina)}",
            f"Action: {self.p1.brain.acao_atual}", f"Skill: {self.p1.skill_arma_nome}", "",
            f"--- {self.p2.dados.nome} ---", f"HP: {int(self.p2.vida)}", f"Mana: {int(self.p2.mana)}", f"Estamina: {int(self.p2.estamina)}",
            f"Action: {self.p2.brain.acao_atual}", f"Skill: {self.p2.skill_arma_nome}"
        ]
        for i, l in enumerate(lines):
            c = COR_TEXTO_TITULO if "---" in l else COR_TEXTO_INFO
            self.tela.blit(ft.render(l, True, c), (20, 20 + i*20))

    def desenhar_pause(self):
        ft = pygame.font.SysFont("Impact", 60); txt = ft.render("PAUSE", True, BRANCO)
        self.tela.blit(txt, (self.screen_width//2 - txt.get_width()//2, self.screen_height//2 - 50))

    def desenhar_vitoria(self):
        s = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA); s.fill(COR_UI_BG); self.tela.blit(s, (0,0))
        serie = self.best_of_series
        if serie.finished:
            nome_campeao = self._nome_do_slot(serie.winner)
            titulo = f"{nome_campeao} CAMPEÃO DA SÉRIE!"
            instrucao = "Pressione 'R' para Nova Série ou 'ESC' para Sair"
        elif self.empate_round:
            titulo = f"EMPATE NO ROUND {serie.round_number}!"
            instrucao = "Pressione 'R' para Repetir o Round ou 'ESC' para Sair"
        else:
            titulo = f"{self.vencedor} VENCEU O ROUND {serie.round_number}!"
            instrucao = "Pressione 'R' para Próximo Round ou 'ESC' para Sair"

        txt = self._renderizar_texto_ajustado(
            titulo,
            "Impact",
            64,
            COR_TEXTO_TITULO,
            self.screen_width - 40,
            tamanho_min=20,
        )
        self.tela.blit(txt, (self.screen_width//2 - txt.get_width()//2, self.screen_height//2 - 100))
        placar = f"PLACAR: P1 {serie.wins['p1']} x {serie.wins['p2']} P2"
        score = self._renderizar_texto_ajustado(
            placar,
            "Arial",
            28,
            BRANCO,
            self.screen_width - 40,
            bold=True,
        )
        self.tela.blit(score, (self.screen_width//2 - score.get_width()//2, self.screen_height//2))
        msg = self._renderizar_texto_ajustado(
            instrucao,
            "Arial",
            22,
            COR_TEXTO_INFO,
            self.screen_width - 40,
        )
        self.tela.blit(msg, (self.screen_width//2 - msg.get_width()//2, self.screen_height//2 + 45))

    def run(self):
        if self.headless:
            raise RuntimeError(
                "Use neural_fights.simulation.headless.HeadlessMatchRunner para execução headless"
            )
        self._slow_mo_ended = False  # Flag para tocar som de vitória uma vez
        try:
            while self.rodando:
                raw_dt = self.clock.tick(FPS) / 1000.0
                if self.slow_mo_timer > 0:
                    self.slow_mo_timer -= raw_dt
                    if self.slow_mo_timer <= 0:
                        self.time_scale = 1.0
                        # Som de fim do slow-mo e vitória
                        if not self._slow_mo_ended and self.vencedor:
                            if self.audio:
                                self.audio.play_special("slowmo_end", 0.5)
                                self.audio.play_special("arena_victory", 1.0)
                            self._slow_mo_ended = True
                dt = raw_dt * self.time_scale
                self.processar_inputs(); self.update(dt); self.desenhar(); pygame.display.flip()
        except BaseException as exc:
            try:
                self.close()
            except BaseException as cleanup_error:
                exc.add_note(f"Falha adicional ao limpar Simulador: {cleanup_error}")
            raise
        else:
            self.close()

    def close(self):
        """Libera recursos do processo; é seguro chamar mais de uma vez."""
        cleanup_errors = []
        with Simulador._lifecycle_lock:
            token = getattr(self, "_lifecycle_token", None)
            if (
                getattr(self, "_closed", True)
                or token is None
                or Simulador._active_owner_token is not token
            ):
                self._closed = True
                self._lifecycle_token = None
                return

            self._closed = True
            try:
                # Enquanto este token é o dono exclusivo, qualquer singleton
                # existente pertence a esta execução, inclusive os criados
                # parcialmente antes de uma exceção de bootstrap.
                for manager_class in (
                    AudioManager,
                    MagicVFXManager,
                    AttackAnimationManager,
                    MovementAnimationManager,
                    GameFeelManager,
                    HitStopManager,
                    CombatChoreographer,
                ):
                    try:
                        manager_class.reset()
                    except Exception as exc:
                        cleanup_errors.append((manager_class.__name__, exc))
                        # Mesmo que a rotina específica de teardown falhe,
                        # não deixe um singleton parcial acessível à próxima
                        # execução do simulador.
                        if hasattr(manager_class, "_instance"):
                            manager_class._instance = None

                try:
                    pygame.quit()
                except Exception as exc:
                    cleanup_errors.append(("pygame", exc))

                random_state = getattr(self, "_random_state_before_seed", None)
                if random_state is not None:
                    try:
                        random.setstate(random_state)
                    except Exception as exc:
                        cleanup_errors.append(("random", exc))
                    finally:
                        self._random_state_before_seed = None

                for attr in (
                    "audio",
                    "magic_vfx",
                    "attack_anims",
                    "movement_anims",
                    "game_feel",
                    "choreographer",
                ):
                    if hasattr(self, attr):
                        setattr(self, attr, None)
            finally:
                if Simulador._active_owner_token is token:
                    Simulador._active_owner_token = None
                self._lifecycle_token = None

        if cleanup_errors:
            detalhes = ", ".join(nome for nome, _exc in cleanup_errors)
            raise RuntimeError(
                f"Falha ao limpar recurso(s) do Simulador: {detalhes}"
            ) from cleanup_errors[0][1]

if __name__ == "__main__":
    Simulador().run()
