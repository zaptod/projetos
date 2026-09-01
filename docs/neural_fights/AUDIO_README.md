# Áudio no Neural Fights

O áudio de combate é gerenciado por `neural_fights.effects.audio.AudioManager`. O projeto distribui assets padrão em `neural_fights/sounds/` e permite substituí-los por arquivos locais sem modificar a instalação.

## Resolução de arquivos

Para cada evento, o sistema procura o arquivo nesta ordem:

1. override no diretório de execução do usuário;
2. asset padrão empacotado em `neural_fights/sounds/`;
3. fallback para outro asset compatível, quando o evento possui um fallback definido.

Se nenhuma dessas opções existir, o evento fica silencioso. Não há geração ou síntese automática de sons. Os formatos aceitos para overrides são `.wav`, `.ogg` e `.mp3`, sujeitos aos codecs disponíveis no SDL_mixer da plataforma.

Os assets empacotados são somente leitura. Por padrão, os overrides e o `sound_config.json` local ficam em:

- Windows: `%LOCALAPPDATA%\neural-fights\sounds`;
- Linux: `$XDG_STATE_HOME/neural-fights/sounds` ou `~/.local/state/neural-fights/sounds`.

`NEURAL_FIGHTS_RUNTIME_DIR` muda a raiz de todos os dados locais. Para isolar apenas o áudio, use `NEURAL_FIGHTS_SOUND_RUNTIME_DIR`.

## Configuração pela interface

A tela de configuração de sons é o fluxo recomendado. Ao selecionar um arquivo, ela:

- copia o arquivo para o diretório local com o identificador do evento;
- atualiza o `sound_config.json` local;
- preserva os assets originais do pacote;
- recarrega o cache do gerenciador ao salvar.

O botão de limpar remove somente os overrides locais daquele evento. Na próxima carga, o asset empacotado ou seu fallback volta a ser usado.

## API pública

```python
from neural_fights.effects.audio import AudioManager

audio = AudioManager.get_instance()

audio.play("slash_light", volume=0.8)
audio.play_positional("fireball_impact", pos_x=10.0, listener_x=4.0)
audio.play_attack("Reta", damage=28, is_critical=False)
audio.play_impact(35, is_critical=True)
audio.play_skill("PROJETIL", "Bola de Fogo", phase="cast")
audio.play_movement("jump")
audio.play_special("ko", volume=1.0)
```

O singleton inicializa o mixer sob demanda. Se o dispositivo de áudio não estiver disponível, o gerenciador é desabilitado e o jogo continua sem som.

### Volume e recarga

```python
audio.set_master_volume(0.7)
audio.set_sfx_volume(0.8)
audio.set_category_volume("movimento", 0.5)
audio.save_volume_config()

# Releia a configuração e os arquivos depois de uma alteração externa.
audio.reload_sounds()

audio.stop_all()
audio.toggle_enable()
```

Categorias válidas: `golpes`, `impactos`, `projeteis`, `skills`, `movimento`, `ambiente` e `ui`. O volume efetivo combina volume mestre, SFX, categoria e chamada.

## Override por código

O exemplo [examples/exemplo_sons_customizados.py](examples/exemplo_sons_customizados.py) usa somente as APIs atuais para instalar, remover e testar um override no diretório gravável:

```powershell
python examples/exemplo_sons_customizados.py caminho
python examples/exemplo_sons_customizados.py instalar slash_light C:\audio\meu_corte.ogg
python examples/exemplo_sons_customizados.py tocar slash_light
python examples/exemplo_sons_customizados.py remover slash_light
```

Não copie arquivos diretamente para `neural_fights/sounds/`: essa pasta pertence ao pacote, pode não ser gravável e será substituída em uma atualização.

## Diagnóstico

Para uma verificação manual do mixer e dos assets:

```powershell
python test_sound.py
python test_jump_sound.py
```

Se não houver som:

1. confirme que o volume mestre, SFX e da categoria são maiores que zero;
2. verifique o caminho efetivo com o comando `caminho` do exemplo;
3. confira se o arquivo existe e possui extensão suportada;
4. execute `pygame.mixer.get_init()` para verificar se o dispositivo abriu;
5. teste WAV ou OGG se o backend da plataforma não decodificar o MP3 escolhido.
