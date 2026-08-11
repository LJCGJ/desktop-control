"""
T2M Desktop Control - Servidor MCP de controle de desktop para Windows.

Expoe ferramentas que permitem ao Claude operar o mouse, o teclado e as janelas
do Windows, com um sistema de aprovacao estilo Claude Code: toda acao que altera
o estado da maquina (mover/clicar mouse, digitar, arrastar, scroll) pede
confirmacao ao usuario atraves de um popup nativo, com as opcoes:

    - Permitir uma vez
    - Sempre permitir esta ferramenta
    - Negar

As acoes apenas de leitura (screenshot, listar janelas, localizar imagem) NAO
pedem aprovacao, pois nao alteram nada - mesma logica do Claude Code, onde ler
nao pede permissao mas escrever/executar pede.

Seguranca (endurecido na v0.2.0):
  * O MODELO NAO consegue desligar a propria trava. Chamar set_approval_mode
    para "auto" exige uma confirmacao no popup nativo do usuario.
  * Todas as acoes e decisoes de aprovacao vao para um LOG DE AUDITORIA.
  * Texto marcado como sensivel (ex: senhas) e mascarado no popup e no log.

O modo pode ser pre-definido pela variavel de ambiente T2M_APPROVAL_MODE.
O caminho do log de auditoria pode ser definido por T2M_AUDIT_LOG.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

try:
    import pyautogui
    # Failsafe: mover o mouse pro canto superior esquerdo aborta tudo.
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except Exception as _exc:  # pragma: no cover - so acontece em ambiente sem GUI
    pyautogui = None
    _PYAUTOGUI_IMPORT_ERROR = str(_exc)
else:
    _PYAUTOGUI_IMPORT_ERROR = ""

mcp = FastMCP("t2m-desktop-control")

# Versao do servidor. Fica exposta em get_approval_status() e diagnostico()
# porque descobrir "qual versao esta realmente rodando" foi uma fonte recorrente
# de confusao: o app mantem o processo antigo vivo ate reiniciar, e um zip
# antigo na pasta de downloads e facil de subir por engano.
VERSAO = "0.8.5"

# ---------------------------------------------------------------------------
# Log de auditoria
# ---------------------------------------------------------------------------

_AUDIT_LOG = os.environ.get(
    "T2M_AUDIT_LOG",
    str(Path(__file__).resolve().parent.parent / "t2m_audit.log"),
)


def _audit(event: str, **data) -> None:
    """Registra um evento no log de auditoria (uma linha JSON por evento).

    Se o caminho padrao nao for gravavel (ex.: plugin instalado numa pasta
    protegida), muda de vez para um arquivo no diretorio temporario - auditoria
    capenga e melhor que auditoria nenhuma, e sumir em silencio seria pior.
    O caminho efetivo aparece em get_approval_status().
    """
    global _AUDIT_LOG
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": event,
        **data,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    try:
        with open(_AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        fallback = os.path.join(tempfile.gettempdir(), "t2m_audit.log")
        try:
            with open(fallback, "a", encoding="utf-8") as fh:
                fh.write(line)
            _AUDIT_LOG = fallback
        except Exception:
            # Nunca deixar o log quebrar a execucao da ferramenta.
            pass


# ---------------------------------------------------------------------------
# Gerenciamento de aprovacao
# ---------------------------------------------------------------------------

_APPROVAL_SCRIPT = str(Path(__file__).with_name("approval.py"))

# Segundos de espera pela resposta no popup. Precisa ficar abaixo do timeout de
# quem chama (a ponte do app desktop corta em ~60s). Ajustavel por env var.
try:
    _APPROVAL_TIMEOUT = int(os.environ.get("T2M_APPROVAL_TIMEOUT", "50"))
except ValueError:
    _APPROVAL_TIMEOUT = 50

# Modo de consentimento.
#
#   host (padrao) - QUEM PERGUNTA E O APLICATIVO ANFITRIAO. No MCP, mediar o
#                   consentimento e papel do cliente (Claude), nao do servidor.
#                   O app ja tem sua propria configuracao de aprovacao, e o
#                   usuario ja decidiu ali como quer ser consultado. Abrir um
#                   segundo pedido aqui duplicaria a pergunta e ignoraria essa
#                   decisao. Neste modo o servidor executa e apenas REGISTRA.
#   ask           - o servidor abre seu proprio pedido de permissao. Util em
#                   clientes que nao mediam chamadas de ferramenta, ou para quem
#                   quer uma segunda barreira deliberada.
#   auto          - nao pergunta nada (equivalente a host na pratica; mantido
#                   por compatibilidade e para deixar a intencao explicita).
_approval_mode: str = os.environ.get("T2M_APPROVAL_MODE", "host").lower()
if _approval_mode not in ("host", "ask", "auto"):
    _approval_mode = "host"

# Aprovacoes permanentes: pares (ferramenta, titulo_da_janela_ativa).
# Vincular a janela evita que um "Sempre permitir" dado para testar um app
# vaze para o resto do sistema. Ex: liberar 'click' com o T2M Security em foco
# NAO libera cliques quando outra janela esta ativa.
_always_allowed: set[tuple[str, str]] = set()


class ActionDenied(Exception):
    """Levantada quando o usuario nega uma acao."""


def _active_window_key() -> str | None:
    """Retorna o titulo da janela ativa (foreground), ou None se nao der pra
    determinar.

    ATENCAO: a janela ativa e um proxy FRAGIL para "a janela que a acao vai
    atingir". Enquanto o usuario le/decide, ele pode trocar de janela - e a
    permissao acabaria vinculada a janela errada. Por isso, para acoes com
    coordenadas, prefira _window_at_point(). Esta funcao serve para acoes de
    teclado, onde o alvo realmente e quem tem o foco.
    """
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        if w is None:
            return None
        title = (w.title or "").strip()
        return title or None
    except Exception:
        return None


def _window_at_point(x: int, y: int) -> str | None:
    """Retorna o titulo da janela visivel que esta sob o ponto (x, y).

    Usado como escopo das aprovacoes de acoes com coordenadas (clique, arraste,
    scroll). E mais honesto que a janela ativa: descreve exatamente ONDE a acao
    vai acontecer, independente do que o usuario esteja olhando no momento em
    que decide. Percorre as janelas na ordem em que o sistema as devolve e pega
    a primeira que contem o ponto, ignorando janelas minimizadas (que o Windows
    posiciona em coordenadas negativas fora da tela).
    """
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            title = (w.title or "").strip()
            if not title:
                continue
            # Janelas minimizadas ficam em -32000; nao sao alvo de clique.
            if w.left <= -30000 or w.top <= -30000:
                continue
            if w.left <= x < w.left + w.width and w.top <= y < w.top + w.height:
                return title
    except Exception:
        return None
    return None


def _resolve_window(title_contains: str):
    """Acha a primeira janela NAO minimizada cujo titulo contem o texto dado.

    Levanta erro se nao encontrar - melhor falhar do que agir na janela errada.
    """
    try:
        import pygetwindow as gw
    except Exception as exc:
        raise RuntimeError(f"pygetwindow nao instalado. Detalhe: {exc}")
    needle = title_contains.lower()
    for w in gw.getAllWindows():
        title = (w.title or "").strip()
        if not title or needle not in title.lower():
            continue
        return w
    raise RuntimeError(
        f"Nenhuma janela encontrada contendo {title_contains!r}. "
        "Nada foi executado."
    )


def _forcar_frente(win) -> bool:
    """Traz a janela para frente, contornando o bloqueio de foco do Windows.

    O Windows impede que um processo em segundo plano roube o foco (protecao
    contra apps que se impoem na frente do usuario). Como o servidor MCP roda em
    segundo plano, `SetForegroundWindow` sozinho falha - foi o erro 183 que
    apareceu no uso real.

    Tenta tres estrategias, da mais educada para a mais insistente:

      1. Restaurar se estiver minimizada e pedir o foco normalmente.
      2. Anexar a fila de entrada da thread em primeiro plano (AttachThreadInput)
         - com isso o Windows passa a considerar que somos "do mesmo contexto"
         e libera a troca de foco.
      3. Apenas ELEVAR a janela na pilha, sem ativar. Nao da foco de teclado,
         mas coloca a janela por cima - que e o que importa para um clique por
         coordenadas.

    Retorna True se a janela ficou em primeiro plano.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except Exception:
        return False

    hwnd = getattr(win, "_hWnd", None)
    if not hwnd:
        return False

    SW_RESTORE = 9
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.2)
    except Exception:
        pass

    # 1) tentativa direta
    try:
        if user32.SetForegroundWindow(hwnd):
            return True
    except Exception:
        pass

    # 2) anexar a thread em primeiro plano
    anexado = False
    thread_fg = thread_eu = None
    try:
        janela_fg = user32.GetForegroundWindow()
        thread_fg = user32.GetWindowThreadProcessId(janela_fg, None)
        thread_eu = kernel32.GetCurrentThreadId()
        if thread_fg and thread_fg != thread_eu:
            anexado = bool(user32.AttachThreadInput(thread_eu, thread_fg, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    finally:
        if anexado:
            try:
                user32.AttachThreadInput(thread_eu, thread_fg, False)
            except Exception:
                pass

    try:
        if user32.GetForegroundWindow() == hwnd:
            return True
    except Exception:
        pass

    # 3) elevar sem ativar - suficiente para clique por coordenadas
    try:
        HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
        SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0040
        flags = SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
    except Exception:
        pass

    try:
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _focus_and_verify(win, x: int | None = None, y: int | None = None) -> None:
    """Traz a janela para frente e confirma que ela realmente esta sob o ponto.

    Esta verificacao e o que impede o acidente mais perigoso desta ferramenta:
    clicar em coordenadas de tela sem saber QUAL aplicativo esta ali. Se outra
    janela estiver por cima do ponto (o proprio chat, um popup, outro app), o
    clique iria para o lugar errado. Preferimos abortar com uma mensagem clara.
    """
    try:
        if getattr(win, "isMinimized", False):
            win.restore()
    except Exception:
        pass
    # Nao dependemos do activate() do pygetwindow: ele usa SetForegroundWindow
    # direto, que o Windows bloqueia para processos em segundo plano.
    _forcar_frente(win)
    time.sleep(0.35)  # o gerenciador de janelas precisa de um instante

    if x is None or y is None or x < 0 or y < 0:
        return
    top = _window_at_point(x, y)
    expected = (win.title or "").strip()
    if top != expected:
        raise RuntimeError(
            f"Abortado por seguranca: o ponto ({x}, {y}) esta sobre "
            f"{top!r}, e nao sobre a janela alvo {expected!r}. "
            "Nada foi clicado. Traga a janela alvo para frente e tente de novo."
        )


def _scope_for(tool_name: str, x: int | None = None, y: int | None = None) -> str | None:
    """Decide o escopo (janela) de uma aprovacao.

    Com coordenadas, o alvo e a janela sob o ponto. Sem coordenadas (teclado,
    ou clique na posicao atual), cai para a janela ativa.
    """
    if x is not None and y is not None and x >= 0 and y >= 0:
        return _window_at_point(x, y) or _active_window_key()
    return _active_window_key()


def _require_pyautogui() -> None:
    if pyautogui is None:
        raise RuntimeError(
            "A biblioteca pyautogui nao esta disponivel neste ambiente. "
            f"Detalhe: {_PYAUTOGUI_IMPORT_ERROR}. "
            "Instale com: pip install -r requirements.txt"
        )


def _prompt_user(tool_name: str, details: str) -> str:
    """Abre o popup de aprovacao num processo separado e retorna a escolha.

    O tempo de espera precisa ser MENOR que o timeout de quem chama o servidor.
    Quando o plugin e acessado por uma sessao na nuvem, a ponte do app desktop
    desiste em ~60s: se o popup esperasse mais que isso, o chamador receberia um
    erro de timeout enquanto a acao ainda poderia ser executada depois - e um
    retry acabaria executando a acao DUAS vezes. Esperando menos, o pior caso
    vira uma negacao limpa: nada e executado e tentar de novo e seguro.
    """
    try:
        proc = subprocess.run(
            # A janela se fecha sozinha 3s antes do nosso limite, para devolver
            # "deny" de forma limpa em vez de ser morta pelo timeout.
            [sys.executable, _APPROVAL_SCRIPT, tool_name, details,
             str(max(5, _APPROVAL_TIMEOUT - 3))],
            capture_output=True,
            text=True,
            timeout=_APPROVAL_TIMEOUT,
        )
        choice = (proc.stdout or "").strip().splitlines()
        return choice[-1].strip() if choice else "deny"
    except subprocess.TimeoutExpired:
        _audit("approval_timeout", tool=tool_name, seconds=_APPROVAL_TIMEOUT)
        return "timeout"
    except Exception:
        # Se nao conseguimos nem mostrar o popup, negamos por seguranca.
        return "deny"


def _check_approval(tool_name: str, details: str,
                    x: int | None = None, y: int | None = None,
                    scope: str | None = None) -> None:
    """Aplica a politica de aprovacao. Levanta ActionDenied se negado.

    O "Sempre permitir" e vinculado a JANELA ALVO da acao - a janela sob as
    coordenadas, quando houver, ou a janela em foco para acoes de teclado.
    Vincular ao alvo (e nao a janela que por acaso esta em foco na hora de
    decidir) evita que a permissao seja registrada na janela errada quando o
    usuario troca de janela enquanto le o pedido.
    """
    if _approval_mode in ("host", "auto"):
        # Sem pedido proprio: o consentimento ficou a cargo do aplicativo
        # anfitriao. Ainda assim registramos tudo - auditoria e independente de
        # quem perguntou, e e o que permite reconstruir o que foi feito.
        _audit("action_executed", tool=tool_name, details=details,
               consentimento=_approval_mode,
               janela=scope or _scope_for(tool_name, x, y))
        return

    win = scope or _scope_for(tool_name, x, y)

    # Ja liberado permanentemente para esta ferramenta NESTA janela?
    if win is not None and (tool_name, win) in _always_allowed:
        _audit("action_pre_approved", tool=tool_name, window=win, details=details)
        return

    # Mostra ao usuario a qual janela o "Sempre permitir" ficaria restrito.
    if win:
        scope_note = f"\n\nJanela alvo: {win}\n(\"Sempre permitir\" vale so para esta janela.)"
    else:
        scope_note = ("\n\n(Janela ativa nao detectada - \"Sempre permitir\" "
                      "vai valer apenas UMA vez, por seguranca.)")

    choice = _prompt_user(tool_name, details + scope_note)

    if choice == "always":
        if win is not None:
            _always_allowed.add((tool_name, win))
            _audit("action_approved", tool=tool_name, details=details,
                   scope="always", window=win)
        else:
            # Sem janela identificada, nao da pra restringir o escopo com
            # seguranca: trata como "uma vez".
            _audit("action_approved", tool=tool_name, details=details,
                   scope="once_no_window")
        return
    if choice == "once":
        _audit("action_approved", tool=tool_name, details=details,
               scope="once", window=win)
        return
    if choice == "timeout":
        raise ActionDenied(
            f"Acao '{tool_name}' NAO executada: o usuario nao respondeu ao "
            f"pedido de permissao em {_APPROVAL_TIMEOUT}s. Nada foi executado "
            "no computador - e seguro tentar de novo se ele estiver por perto."
        )
    _audit("action_denied", tool=tool_name, details=details, window=win)
    raise ActionDenied(
        f"Acao '{tool_name}' negada pelo usuario. "
        "Nada foi executado no computador."
    )


# ---------------------------------------------------------------------------
# Ferramentas de configuracao / aprovacao
# ---------------------------------------------------------------------------


@mcp.tool()
def set_approval_mode(mode: Literal["host", "ask", "auto"]) -> str:
    """Define quem pede o consentimento para as acoes.

    O padrao e "host": quem pergunta e o aplicativo (Claude), conforme a
    configuracao de aprovacao que o usuario escolheu la. Este servidor nao
    duplica a pergunta.

    IMPORTANTE (seguranca): se o usuario tiver ligado o modo "ask" (barreira
    propria do servidor), sair dele EXIGE confirmacao no proprio pedido - o
    Claude nao consegue desligar sozinho uma barreira que o usuario ligou.
    Entrar em "ask" e sempre permitido, porque so aumenta o rigor.

    Args:
        mode: "host" = o aplicativo anfitriao pergunta (padrao);
              "ask"  = este servidor abre seu proprio pedido de permissao;
              "auto" = ninguem pergunta.

    Returns:
        Confirmacao do modo ativo.
    """
    global _approval_mode
    if mode != "ask" and _approval_mode == "ask":
        # Exige confirmacao humana explicita para afrouxar a seguranca.
        choice = _prompt_user(
            "DESLIGAR A BARREIRA DO SERVIDOR",
            f"O Claude quer sair do modo 'ask' e passar para '{mode}', ou seja, "
            "este servidor deixaria de pedir permissao por conta propria. "
            "Confirme apenas se voce tem certeza.",
        )
        if choice not in ("once", "always"):
            _audit("mode_change_denied", tentativa=mode)
            return (
                f"Mudanca para o modo '{mode}' NEGADA. O modo continua 'ask' "
                "(cada acao ainda pede confirmacao neste servidor)."
            )
    _approval_mode = mode
    _audit("approval_mode_changed", mode=mode)
    return f"Modo de aprovacao definido para '{mode}'."


@mcp.tool()
def diagnostico() -> dict:
    """Coleta informacoes sobre o ambiente em que ESTE servidor esta rodando.

    Serve para investigar por que um popup de aprovacao pode nao aparecer:
    compara o contexto do processo do servidor com o de um terminal comum e
    testa, de fato, se uma janela grafica consegue ser criada aqui.

    Acao apenas de leitura, nao pede aprovacao.
    """
    info: dict = {
        "versao_do_servidor": VERSAO,
        "processo": {
            "pid": os.getpid(),
            "executavel_python": sys.executable,
            "versao_python": sys.version.split()[0],
            "pasta_de_trabalho": os.getcwd(),
            "arquivo_do_servidor": str(Path(__file__).resolve()),
        },
        "ambiente": {
            "usuario": os.environ.get("USERNAME", "?"),
            "sessao": os.environ.get("SESSIONNAME", "?"),
            "perfil": os.environ.get("USERPROFILE", "?"),
            "modo_aprovacao": _approval_mode,
            "timeout_aprovacao_s": _APPROVAL_TIMEOUT,
        },
        "pyautogui_disponivel": pyautogui is not None,
    }

    # Teste 1: dá para criar uma janela grafica a partir daqui?
    prova = (
        "import tkinter; r = tkinter.Tk(); r.withdraw(); "
        "print('TK_OK'); r.destroy()"
    )
    try:
        p = subprocess.run([sys.executable, "-c", prova],
                           capture_output=True, text=True, timeout=8)
        info["teste_janela_grafica"] = {
            "resultado": "ok" if "TK_OK" in (p.stdout or "") else "falhou",
            "saida": (p.stdout or "").strip()[:200],
            "erro": (p.stderr or "").strip()[:300],
            "codigo_retorno": p.returncode,
        }
    except subprocess.TimeoutExpired:
        info["teste_janela_grafica"] = {
            "resultado": "travou",
            "detalhe": ("A criacao da janela nao retornou em 8s. Indica que este "
                        "processo nao tem acesso a area de trabalho interativa."),
        }
    except Exception as exc:
        info["teste_janela_grafica"] = {"resultado": "erro", "detalhe": str(exc)}

    # Teste 1b: a caixa de dialogo NATIVA do Windows aparece daqui?
    prova_nativa = (
        "import ctypes; from ctypes import wintypes; u=ctypes.windll.user32; "
        "f=u.MessageBoxTimeoutW; "
        "f.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,"
        "wintypes.UINT,wintypes.WORD,wintypes.DWORD]; "
        "r=f(None,'Teste do plugin. Fecha sozinha em 5s.',"
        "'Claude - teste',0x00041030,0,5000); print('MB_RESULT=%d'%r)"
    )
    try:
        p = subprocess.run([sys.executable, "-c", prova_nativa],
                           capture_output=True, text=True, timeout=12)
        saida = (p.stdout or "").strip()
        info["teste_dialogo_nativo"] = {
            "resultado": "ok" if "MB_RESULT=" in saida else "falhou",
            "saida": saida[:120],
            "erro": (p.stderr or "").strip()[:300],
            "observacao": ("MB_RESULT=32000 significa que fechou por tempo "
                           "(ninguem clicou) - o que ja prova que ela apareceu."),
        }
    except subprocess.TimeoutExpired:
        info["teste_dialogo_nativo"] = {"resultado": "travou"}
    except Exception as exc:
        info["teste_dialogo_nativo"] = {"resultado": "erro", "detalhe": str(exc)}

    # Teste 2: o proprio popup de aprovacao, com prazo curto
    try:
        p = subprocess.run(
            [sys.executable, _APPROVAL_SCRIPT, "DIAGNOSTICO",
             "Janela de teste - pode ignorar, fecha sozinha.", "6"],
            capture_output=True, text=True, timeout=12)
        info["teste_popup_aprovacao"] = {
            "resultado": (p.stdout or "").strip()[:100] or "(sem saida)",
            "erro": (p.stderr or "").strip()[:300],
            "codigo_retorno": p.returncode,
        }
    except subprocess.TimeoutExpired:
        info["teste_popup_aprovacao"] = {
            "resultado": "travou",
            "detalhe": ("O popup nao respondeu nem se fechou sozinho. Confirma "
                        "que a janela nao chega a ser criada neste contexto."),
        }
    except Exception as exc:
        info["teste_popup_aprovacao"] = {"resultado": "erro", "detalhe": str(exc)}

    _audit("diagnostico", **{"tk": info.get("teste_janela_grafica", {}).get("resultado")})
    return info


@mcp.tool()
def get_approval_status() -> dict:
    """Retorna o modo de aprovacao atual, as ferramentas ja aprovadas
    permanentemente e o caminho do log de auditoria.
    """
    return {
        "versao_do_servidor": VERSAO,
        "mode": _approval_mode,
        "always_allowed": [
            {"tool": tool, "window": win} for (tool, win) in sorted(_always_allowed)
        ],
        "audit_log": _AUDIT_LOG,
    }


@mcp.tool()
def reset_approvals() -> str:
    """Revoga as liberacoes de 'Sempre permitir' e liga a barreira propria
    do servidor (modo 'ask'). Use para "esquecer" tudo que foi autorizado.
    """
    global _approval_mode
    _always_allowed.clear()
    _approval_mode = "ask"
    _audit("approvals_reset")
    return ("Liberacoes revogadas. O servidor passou a pedir permissao por "
            "conta propria (modo 'ask'), alem do que o aplicativo ja pergunta.")


# ---------------------------------------------------------------------------
# Ferramentas de LEITURA (nao pedem aprovacao - nao alteram nada)
# ---------------------------------------------------------------------------


# Pasta padrao das capturas de tela. Fica na raiz do projeto/plugin para ser
# facil de achar e de APAGAR: a pasta inteira e descartavel - o usuario (ou o
# Claude) pode exclui-la para limpar as capturas, e o servidor a recria na
# captura seguinte. Configuravel via T2M_SCREENSHOT_DIR.
_SCREENSHOT_DIR = os.environ.get(
    "T2M_SCREENSHOT_DIR",
    str(Path(__file__).resolve().parent.parent / "capturas"),
)


def _ensure_screenshot_dir() -> str:
    """Garante que a pasta de capturas exista e devolve o caminho dela.

    A pasta e pensada para ser DESCARTAVEL: apagar a pasta inteira e a forma
    oficial de limpeza, e aqui ela e recriada quando a proxima captura chegar.
    Dentro dela o servidor mantem um .gitignore que ignora tudo - assim nada
    do que cair ali vai parar no repositorio, mesmo depois de a pasta ser
    apagada e recriada (o .gitignore renasce junto).

    Se a pasta padrao nao for gravavel (ex.: plugin instalado numa pasta
    protegida), cai para uma pasta 't2m-capturas' no diretorio temporario.
    """
    candidatos = (
        _SCREENSHOT_DIR,
        os.path.join(tempfile.gettempdir(), "t2m-capturas"),
    )
    for base in candidatos:
        try:
            os.makedirs(base, exist_ok=True)
            gi = os.path.join(base, ".gitignore")
            if not os.path.exists(gi):
                with open(gi, "w", encoding="utf-8") as fh:
                    fh.write(
                        "# Pasta de capturas do t2m-desktop-control.\n"
                        "# Conteudo descartavel e potencialmente sensivel - "
                        "nunca versionar.\n"
                        "# Pode apagar a pasta inteira: o servidor a recria "
                        "quando precisar.\n"
                        "*\n"
                        "!.gitignore\n"
                    )
            return base
        except Exception:
            continue
    return tempfile.gettempdir()


def _virtual_screen_rect() -> tuple[int, int, int, int] | None:
    """Retorna (left, top, width, height) da TELA VIRTUAL do Windows - o
    retangulo que engloba todos os monitores.

    O canto (left, top) pode ser NEGATIVO: o Windows ancora a origem (0, 0) no
    canto do monitor principal, e monitores a esquerda/acima dele ficam em
    coordenadas negativas. Esse offset e essencial para converter um pixel da
    captura em coordenada de tela para clique.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
        return (
            user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
    except Exception:
        return None


@mcp.tool()
def screenshot(path: str = "", monitor: Literal["all", "primary"] = "all") -> dict:
    """Captura a tela e salva como PNG.

    Acao apenas de leitura - nao pede aprovacao. Use para "ver" a tela antes
    de decidir onde clicar.

    Por padrao captura TODOS os monitores (a tela virtual inteira). A resposta
    inclui `origin`: o canto superior esquerdo da captura em coordenadas de
    tela. Para converter um pixel da imagem em coordenada de clique:

        x_tela = x_pixel + origin.left
        y_tela = y_pixel + origin.top

    (Com um unico monitor, origin e (0, 0) e nada muda. `origin` pode ser
    negativo quando ha monitor a esquerda/acima do principal.)

    Args:
        path: Caminho do arquivo PNG de saida. Se VAZIO, salva na pasta de
              capturas (por padrao 'capturas/' na raiz do projeto/plugin) com
              nome timestampado. Caminho RELATIVO e resolvido dentro dessa
              mesma pasta. A pasta e descartavel: pode ser apagada inteira
              para limpeza, o servidor a recria (com um .gitignore proprio)
              na captura seguinte. NUNCA sobrescreve arquivo existente: em
              caso de colisao, salva com sufixo numerico e avisa.
        monitor: "all" (padrao) captura todos os monitores; "primary" captura
                 so o monitor principal (comportamento das versoes <= 0.8.2).

    Returns:
        Caminho salvo, tamanho da imagem em pixels, `origin` para conversao
        pixel -> coordenada de tela e quais monitores foram capturados.
    """
    _require_pyautogui()
    if not path:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(_ensure_screenshot_dir(), f"t2m_{stamp}.png")
    elif os.path.isabs(path):
        out = path
    else:
        out = os.path.join(_ensure_screenshot_dir(), path)
    out = os.path.abspath(out)

    # NUNCA sobrescrever um arquivo existente. screenshot e uma ferramenta de
    # leitura (nao pede aprovacao), entao escrever por cima de um arquivo do
    # usuario seria uma acao destrutiva sem consentimento. Havendo colisao,
    # renomeia com um sufixo numerico e informa no resultado.
    renomeado_de = None
    if os.path.exists(out):
        raiz, ext = os.path.splitext(out)
        for i in range(2, 1000):
            candidato = f"{raiz}_{i}{ext or '.png'}"
            if not os.path.exists(candidato):
                renomeado_de = out
                out = candidato
                break
        else:
            raise RuntimeError(
                f"Ja existe um arquivo em {out!r} (e em todas as variantes "
                "numeradas). Nada foi sobrescrito - escolha outro nome."
            )

    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as exc:
            raise RuntimeError(f"Nao foi possivel criar a pasta {parent!r}: {exc}")

    origin = {"left": 0, "top": 0}
    captured = "primary"
    img = None
    if monitor == "all":
        # ImageGrab.grab(all_screens=True) captura a tela virtual inteira no
        # Windows. Se falhar por qualquer motivo, cai para o monitor principal
        # em vez de falhar a ferramenta.
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            captured = "all"
            rect = _virtual_screen_rect()
            if rect is not None:
                origin = {"left": rect[0], "top": rect[1]}
        except Exception as exc:
            _audit("screenshot_all_screens_fallback", erro=str(exc)[:200])
            img = None
    if img is None:
        img = pyautogui.screenshot()
        captured = "primary"
        origin = {"left": 0, "top": 0}

    result = {
        "size": {"width": img.width, "height": img.height},
        "origin": origin,
        "monitors": captured,
        "nota": ("coordenada de tela = pixel da imagem + origin "
                 "(origin pode ser negativo com multiplos monitores)"),
    }
    if renomeado_de:
        result["aviso_nome"] = (
            f"Ja existia um arquivo em {renomeado_de!r}; para nao sobrescrever, "
            f"a captura foi salva com sufixo numerico."
        )
    try:
        img.save(out)
    except PermissionError:
        # Fallback: se o caminho pedido nao for gravavel, salva no temp.
        fallback = os.path.join(tempfile.gettempdir(), "t2m_screenshot.png")
        img.save(fallback)
        _audit("screenshot_fallback", requested=out, saved=fallback)
        result["saved_to"] = fallback
        result["aviso"] = (f"Sem permissao de escrita em {out!r}; "
                           f"a imagem foi salva em {fallback!r}.")
        return result
    _audit("screenshot", path=out, monitors=captured)
    result["saved_to"] = out
    return result


@mcp.tool()
def get_screen_size() -> dict:
    """Retorna a resolucao do monitor principal e, se houver mais de um
    monitor, o retangulo da tela virtual completa. Acao apenas de leitura.
    """
    _require_pyautogui()
    w, h = pyautogui.size()
    result: dict = {"width": w, "height": h}
    rect = _virtual_screen_rect()
    if rect is not None and (rect[2], rect[3]) != (w, h):
        result["virtual_screen"] = {
            "left": rect[0], "top": rect[1],
            "width": rect[2], "height": rect[3],
        }
        result["nota"] = ("Ha mais de um monitor. screenshot(monitor='all') "
                          "captura a tela virtual inteira.")
    return result


@mcp.tool()
def get_mouse_position() -> dict:
    """Retorna a posicao atual do cursor do mouse. Acao apenas de leitura."""
    _require_pyautogui()
    x, y = pyautogui.position()
    return {"x": x, "y": y}


@mcp.tool()
def locate_on_screen(image_path: str, confidence: float = 0.8) -> dict:
    """Procura uma imagem de referencia na tela e retorna o centro dela.

    Acao apenas de leitura. Util para achar um botao/icone a partir de um
    recorte de imagem antes de clicar com precisao.

    Args:
        image_path: Caminho da imagem de referencia (PNG/JPG).
        confidence: Nivel de confianca de 0 a 1 (requer opencv instalado).

    Returns:
        Coordenadas do centro se encontrado, ou found=False.
    """
    _require_pyautogui()
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Imagem de referencia nao encontrada: {image_path}")
    try:
        box = pyautogui.locateOnScreen(image_path, confidence=confidence)
    except Exception as exc:
        raise RuntimeError(
            "Falha ao localizar a imagem. Verifique se o opencv-python esta "
            f"instalado (para usar 'confidence'). Detalhe: {exc}"
        )
    if box is None:
        return {"found": False}
    center = pyautogui.center(box)
    return {"found": True, "x": center.x, "y": center.y,
            "box": {"left": box.left, "top": box.top, "width": box.width, "height": box.height}}


@mcp.tool()
def list_windows() -> list[dict]:
    """Lista as janelas abertas do Windows (titulo, posicao e tamanho).

    Acao apenas de leitura. Requer o pacote pygetwindow.
    """
    try:
        import pygetwindow as gw
    except Exception as exc:
        raise RuntimeError(
            "pygetwindow nao instalado. Instale com: pip install -r requirements.txt. "
            f"Detalhe: {exc}"
        )
    result = []
    for w in gw.getAllWindows():
        if not w.title:
            continue
        result.append({
            "title": w.title,
            "left": w.left, "top": w.top,
            "width": w.width, "height": w.height,
            "active": bool(getattr(w, "isActive", False)),
        })
    return result


# ---------------------------------------------------------------------------
# Ferramentas de ESCRITA (pedem aprovacao)
# ---------------------------------------------------------------------------


@mcp.tool()
def move_mouse(x: int, y: int, duration: float = 0.25) -> str:
    """Move o cursor do mouse para uma coordenada (x, y) na tela.

    Requer aprovacao do usuario.

    Args:
        x: Coordenada horizontal em pixels.
        y: Coordenada vertical em pixels.
        duration: Tempo (segundos) do movimento, para parecer mais natural.
    """
    _require_pyautogui()
    _check_approval("move_mouse", f"Mover o mouse para ({x}, {y}).", x, y)
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse movido para ({x}, {y})."


@mcp.tool()
def click(
    x: int = -1,
    y: int = -1,
    button: Literal["left", "right", "middle"] = "left",
    clicks: int = 1,
    window: str = "",
) -> str:
    """Clica com o mouse. Se x/y forem informados, move ate la antes de clicar.

    Requer aprovacao do usuario.

    SEMPRE informe `window` ao operar um aplicativo. Coordenadas de tela nao
    dizem nada sobre QUAL programa esta naquele ponto: se outra janela estiver
    por cima (o chat, um popup, outro app), o clique vai para o lugar errado.
    Com `window`, a janela e trazida para frente e verificada antes do clique,
    e a permissao fica restrita a ela.

    Args:
        x: Coordenada X (deixe -1 para clicar na posicao atual).
        y: Coordenada Y (deixe -1 para clicar na posicao atual).
        button: Botao do mouse: "left", "right" ou "middle".
        clicks: Numero de cliques (2 = duplo clique).
        window: Trecho do titulo da janela alvo (ex: "T2M Security"). Se
                informado, a janela e focada e verificada antes de clicar; se
                outra janela estiver sobre o ponto, a acao e abortada.
    """
    _require_pyautogui()
    where = "na posicao atual" if x < 0 or y < 0 else f"em ({x}, {y})"

    target = None
    scope = None
    if window:
        target = _resolve_window(window)
        scope = (target.title or "").strip() or None
        where += f" na janela {scope!r}"

    _check_approval("click", f"Clicar ({button} x{clicks}) {where}.", x, y, scope=scope)

    if target is not None:
        _focus_and_verify(target, x, y)

    if x >= 0 and y >= 0:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
    else:
        pyautogui.click(clicks=clicks, button=button)
    _audit("click", x=x, y=y, button=button, clicks=clicks, window=scope)
    return f"Clique {button} x{clicks} executado {where}."


@mcp.tool()
def type_text(text: str, interval: float = 0.02, sensitive: bool = False,
              window: str = "") -> str:
    """Digita um texto usando o teclado.

    Suporta acentuacao e caracteres especiais (c, a, e, o...). Quando o texto
    tem caracteres nao-ASCII, usa colagem via area de transferencia (e restaura
    o conteudo anterior do clipboard depois), o que evita o problema classico
    do typewrite com layouts de teclado.

    Requer aprovacao do usuario.

    Args:
        text: Texto a digitar.
        interval: Intervalo (segundos) entre teclas (usado no modo digitacao).
        sensitive: Se True, o conteudo NAO aparece no popup nem no log de
                   auditoria (use para senhas).
        window: Trecho do titulo da janela alvo. Informe sempre que estiver
                operando um aplicativo: garante que o texto va para a janela
                certa, e nao para o que estiver em foco por acaso.
    """
    _require_pyautogui()
    if sensitive:
        preview = f"<conteudo sensivel oculto, {len(text)} caracteres>"
    else:
        preview = text if len(text) <= 60 else text[:57] + "..."

    target = None
    scope = None
    if window:
        target = _resolve_window(window)
        scope = (target.title or "").strip() or None

    _check_approval("type_text", f"Digitar o texto: {preview!r}"
                    + (f" na janela {scope!r}" if scope else ""), scope=scope)

    if target is not None:
        _focus_and_verify(target)

    is_ascii = all(ord(c) < 128 for c in text)
    if is_ascii:
        pyautogui.typewrite(text, interval=interval)
        method = "typewrite"
    else:
        # Colagem via clipboard preserva acentos. Salva e restaura o clipboard.
        method = "clipboard-paste"
        saved = None
        try:
            import pyperclip
            try:
                saved = pyperclip.paste()
            except Exception:
                saved = None
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except Exception as exc:
            # Fallback: tenta digitar mesmo assim.
            pyautogui.typewrite(text, interval=interval)
            method = f"typewrite-fallback ({exc})"
        finally:
            if saved is not None:
                try:
                    import pyperclip
                    pyperclip.copy(saved)
                except Exception:
                    pass
    _audit("type_text", chars=len(text), method=method,
           text=("<oculto>" if sensitive else text))
    return f"Texto digitado ({len(text)} caracteres, via {method})."


@mcp.tool()
def press_keys(keys: list[str], window: str = "") -> str:
    """Aperta uma tecla ou combinacao de teclas (hotkey).

    Requer aprovacao do usuario.

    Args:
        keys: Lista de teclas. Uma tecla sozinha e apertada (ex: ["enter"]).
              Varias teclas viram um atalho simultaneo (ex: ["ctrl", "c"]).
              Nomes validos: enter, tab, esc, ctrl, alt, shift, win, f1..f12,
              up, down, left, right, delete, backspace, etc.
        window: Trecho do titulo da janela alvo. Informe sempre que estiver
                operando um aplicativo, para o atalho nao cair na janela errada
                (um Ctrl+S no app errado pode ter consequencias).
    """
    _require_pyautogui()
    if not keys:
        raise ValueError("A lista 'keys' nao pode ser vazia.")

    target = None
    scope = None
    if window:
        target = _resolve_window(window)
        scope = (target.title or "").strip() or None

    _check_approval("press_keys", f"Apertar teclas: {' + '.join(keys)}"
                    + (f" na janela {scope!r}" if scope else ""), scope=scope)

    if target is not None:
        _focus_and_verify(target)
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return f"Teclas acionadas: {' + '.join(keys)}."


@mcp.tool()
def scroll(amount: int, x: int = -1, y: int = -1) -> str:
    """Rola a tela verticalmente.

    Requer aprovacao do usuario.

    Args:
        amount: Quantidade de scroll. Positivo rola para cima, negativo para baixo.
        x: Coordenada X onde posicionar o mouse antes de rolar (-1 = atual).
        y: Coordenada Y onde posicionar o mouse antes de rolar (-1 = atual).
    """
    _require_pyautogui()
    _check_approval("scroll", f"Rolar a tela em {amount}.", x, y)
    if x >= 0 and y >= 0:
        pyautogui.scroll(amount, x=x, y=y)
    else:
        pyautogui.scroll(amount)
    return f"Scroll de {amount} executado."


@mcp.tool()
def drag(
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    duration: float = 0.5,
    button: Literal["left", "right", "middle"] = "left",
) -> str:
    """Arrasta (drag and drop) de um ponto para outro segurando o botao.

    Requer aprovacao do usuario.

    Args:
        from_x: X inicial.
        from_y: Y inicial.
        to_x: X final.
        to_y: Y final.
        duration: Tempo (segundos) do arrasto.
        button: Botao do mouse usado no arrasto.
    """
    _require_pyautogui()
    _check_approval("drag", f"Arrastar de ({from_x}, {from_y}) para ({to_x}, {to_y}).",
                    from_x, from_y)
    pyautogui.moveTo(from_x, from_y, duration=0.2)
    pyautogui.dragTo(to_x, to_y, duration=duration, button=button)
    return f"Arraste de ({from_x}, {from_y}) para ({to_x}, {to_y}) executado."


@mcp.tool()
def focus_window(title_contains: str) -> str:
    """Traz para frente (foca) a primeira janela cujo titulo contem o texto dado.

    Requer aprovacao do usuario.

    Args:
        title_contains: Trecho do titulo da janela (ex: "T2M Security").
    """
    try:
        import pygetwindow as gw
    except Exception as exc:
        raise RuntimeError(f"pygetwindow nao instalado. Detalhe: {exc}")
    matches = [w for w in gw.getAllWindows() if title_contains.lower() in (w.title or "").lower()]
    if not matches:
        return f"Nenhuma janela encontrada contendo '{title_contains}'."
    # O alvo aqui e conhecido explicitamente: a janela que sera focada.
    _check_approval("focus_window", f"Focar a janela: {matches[0].title!r}",
                    scope=(matches[0].title or "").strip() or None)
    win = matches[0]
    try:
        if win.isMinimized:
            win.restore()
    except Exception:
        pass
    veio = _forcar_frente(win)
    _audit("focus_window", janela=win.title, primeiro_plano=veio)
    if veio:
        return f"Janela focada: {win.title!r}."
    # Mesmo sem o foco de teclado, a janela pode ter sido elevada - o que basta
    # para cliques por coordenadas. Quem decide e a verificacao antes de agir.
    return (f"Janela {win.title!r} elevada, mas o Windows nao concedeu o foco de "
            "teclado (protecao contra roubo de foco por processo em segundo "
            "plano). Cliques por coordenada ainda funcionam se ela estiver por "
            "cima; para digitar, clique nela uma vez.")


if __name__ == "__main__":
    _audit("server_start", versao=VERSAO, mode=_approval_mode,
           pyautogui=bool(pyautogui))
    mcp.run()
