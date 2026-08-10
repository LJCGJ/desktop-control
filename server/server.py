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

# ---------------------------------------------------------------------------
# Log de auditoria
# ---------------------------------------------------------------------------

_AUDIT_LOG = os.environ.get(
    "T2M_AUDIT_LOG",
    str(Path(__file__).resolve().parent.parent / "t2m_audit.log"),
)


def _audit(event: str, **data) -> None:
    """Registra um evento no log de auditoria (uma linha JSON por evento)."""
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": event,
        **data,
    }
    try:
        with open(_AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Nunca deixar o log quebrar a execucao da ferramenta.
        pass


# ---------------------------------------------------------------------------
# Gerenciamento de aprovacao
# ---------------------------------------------------------------------------

_APPROVAL_SCRIPT = str(Path(__file__).with_name("approval.py"))

# Modo global: "ask" pede confirmacao; "auto" aprova tudo sem popup.
_approval_mode: str = os.environ.get("T2M_APPROVAL_MODE", "ask").lower()
if _approval_mode not in ("ask", "auto"):
    _approval_mode = "ask"

# Ferramentas que o usuario marcou como "Sempre permitir esta ferramenta".
_always_allowed: set[str] = set()


class ActionDenied(Exception):
    """Levantada quando o usuario nega uma acao."""


def _require_pyautogui() -> None:
    if pyautogui is None:
        raise RuntimeError(
            "A biblioteca pyautogui nao esta disponivel neste ambiente. "
            f"Detalhe: {_PYAUTOGUI_IMPORT_ERROR}. "
            "Instale com: pip install -r requirements.txt"
        )


def _prompt_user(tool_name: str, details: str) -> str:
    """Abre o popup de aprovacao num processo separado e retorna a escolha."""
    try:
        proc = subprocess.run(
            [sys.executable, _APPROVAL_SCRIPT, tool_name, details],
            capture_output=True,
            text=True,
            timeout=300,
        )
        choice = (proc.stdout or "").strip().splitlines()
        return choice[-1].strip() if choice else "deny"
    except Exception:
        # Se nao conseguimos nem mostrar o popup, negamos por seguranca.
        return "deny"


def _check_approval(tool_name: str, details: str) -> None:
    """Aplica a politica de aprovacao. Levanta ActionDenied se negado."""
    if _approval_mode == "auto":
        _audit("action_auto_approved", tool=tool_name, details=details)
        return
    if tool_name in _always_allowed:
        _audit("action_pre_approved", tool=tool_name, details=details)
        return
    choice = _prompt_user(tool_name, details)
    if choice == "always":
        _always_allowed.add(tool_name)
        _audit("action_approved", tool=tool_name, details=details, scope="always")
        return
    if choice == "once":
        _audit("action_approved", tool=tool_name, details=details, scope="once")
        return
    _audit("action_denied", tool=tool_name, details=details)
    raise ActionDenied(
        f"Acao '{tool_name}' negada pelo usuario. "
        "Nada foi executado no computador."
    )


# ---------------------------------------------------------------------------
# Ferramentas de configuracao / aprovacao
# ---------------------------------------------------------------------------


@mcp.tool()
def set_approval_mode(mode: Literal["ask", "auto"]) -> str:
    """Define como as acoes sao aprovadas (o "dropdown" manual vs automatico).

    IMPORTANTE (seguranca): mudar para "auto" desliga os popups, entao essa
    troca EXIGE uma confirmacao sua no popup nativo. O proprio Claude nao
    consegue afrouxar a seguranca sozinho. Voltar para "ask" e sempre
    permitido (deixa mais seguro).

    Args:
        mode: "ask" = pedir confirmacao a cada acao (padrao, mais seguro);
              "auto" = aprovar todas as acoes automaticamente, sem popup.

    Returns:
        Confirmacao do modo ativo.
    """
    global _approval_mode
    if mode == "auto" and _approval_mode != "auto":
        # Exige confirmacao humana explicita para afrouxar a seguranca.
        choice = _prompt_user(
            "ATIVAR MODO AUTOMATICO",
            "O Claude quer DESLIGAR os pedidos de permissao e passar a executar "
            "TODAS as acoes automaticamente. Confirme apenas se voce tem certeza.",
        )
        if choice not in ("once", "always"):
            _audit("auto_mode_change_denied")
            return (
                "Mudanca para o modo 'auto' NEGADA. O modo continua 'ask' "
                "(cada acao ainda pede confirmacao)."
            )
    _approval_mode = mode
    _audit("approval_mode_changed", mode=mode)
    return f"Modo de aprovacao definido para '{mode}'."


@mcp.tool()
def get_approval_status() -> dict:
    """Retorna o modo de aprovacao atual, as ferramentas ja aprovadas
    permanentemente e o caminho do log de auditoria.
    """
    return {
        "mode": _approval_mode,
        "always_allowed_tools": sorted(_always_allowed),
        "audit_log": _AUDIT_LOG,
    }


@mcp.tool()
def reset_approvals() -> str:
    """Revoga todas as aprovacoes de 'Sempre permitir' e volta o modo para
    'ask'. Use para "esquecer" tudo que foi autorizado antes.
    """
    global _approval_mode
    _always_allowed.clear()
    _approval_mode = "ask"
    _audit("approvals_reset")
    return "Aprovacoes revogadas. Modo voltou para 'ask'."


# ---------------------------------------------------------------------------
# Ferramentas de LEITURA (nao pedem aprovacao - nao alteram nada)
# ---------------------------------------------------------------------------


@mcp.tool()
def screenshot(path: str = "") -> dict:
    """Captura a tela inteira e salva como PNG.

    Acao apenas de leitura - nao pede aprovacao. Use para "ver" a tela antes
    de decidir onde clicar.

    Args:
        path: Caminho do arquivo PNG de saida. Se vazio, salva em
              t2m_screenshot.png na pasta atual.

    Returns:
        Caminho salvo e o tamanho (largura, altura) da tela em pixels.
    """
    _require_pyautogui()
    out = path or "t2m_screenshot.png"
    img = pyautogui.screenshot()
    img.save(out)
    _audit("screenshot", path=os.path.abspath(out))
    return {"saved_to": os.path.abspath(out), "size": {"width": img.width, "height": img.height}}


@mcp.tool()
def get_screen_size() -> dict:
    """Retorna a resolucao da tela em pixels. Acao apenas de leitura."""
    _require_pyautogui()
    w, h = pyautogui.size()
    return {"width": w, "height": h}


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
    _check_approval("move_mouse", f"Mover o mouse para ({x}, {y}).")
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse movido para ({x}, {y})."


@mcp.tool()
def click(
    x: int = -1,
    y: int = -1,
    button: Literal["left", "right", "middle"] = "left",
    clicks: int = 1,
) -> str:
    """Clica com o mouse. Se x/y forem informados, move ate la antes de clicar.

    Requer aprovacao do usuario.

    Args:
        x: Coordenada X (deixe -1 para clicar na posicao atual).
        y: Coordenada Y (deixe -1 para clicar na posicao atual).
        button: Botao do mouse: "left", "right" ou "middle".
        clicks: Numero de cliques (2 = duplo clique).
    """
    _require_pyautogui()
    where = "na posicao atual" if x < 0 or y < 0 else f"em ({x}, {y})"
    _check_approval("click", f"Clicar ({button} x{clicks}) {where}.")
    if x >= 0 and y >= 0:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
    else:
        pyautogui.click(clicks=clicks, button=button)
    return f"Clique {button} x{clicks} executado {where}."


@mcp.tool()
def type_text(text: str, interval: float = 0.02, sensitive: bool = False) -> str:
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
    """
    _require_pyautogui()
    if sensitive:
        preview = f"<conteudo sensivel oculto, {len(text)} caracteres>"
    else:
        preview = text if len(text) <= 60 else text[:57] + "..."
    _check_approval("type_text", f"Digitar o texto: {preview!r}")

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
def press_keys(keys: list[str]) -> str:
    """Aperta uma tecla ou combinacao de teclas (hotkey).

    Requer aprovacao do usuario.

    Args:
        keys: Lista de teclas. Uma tecla sozinha e apertada (ex: ["enter"]).
              Varias teclas viram um atalho simultaneo (ex: ["ctrl", "c"]).
              Nomes validos: enter, tab, esc, ctrl, alt, shift, win, f1..f12,
              up, down, left, right, delete, backspace, etc.
    """
    _require_pyautogui()
    if not keys:
        raise ValueError("A lista 'keys' nao pode ser vazia.")
    _check_approval("press_keys", f"Apertar teclas: {' + '.join(keys)}")
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
    _check_approval("scroll", f"Rolar a tela em {amount}.")
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
    _check_approval("drag", f"Arrastar de ({from_x}, {from_y}) para ({to_x}, {to_y}).")
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
    _check_approval("focus_window", f"Focar a janela: {matches[0].title!r}")
    win = matches[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
    except Exception as exc:
        return f"Janela encontrada ({win.title!r}) mas nao foi possivel focar: {exc}"
    return f"Janela focada: {win.title!r}."


if __name__ == "__main__":
    _audit("server_start", mode=_approval_mode, pyautogui=bool(pyautogui))
    mcp.run()
