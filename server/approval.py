"""
Pedido de permissao para o usuario.

Executado como PROCESSO SEPARADO pelo servidor MCP a cada acao que precisa de
confirmacao. Imprime no stdout a escolha do usuario:

    once   -> "Permitir uma vez"
    always -> "Sempre permitir (nesta janela)"
    deny   -> "Negar" (ou fechar, ou nao responder a tempo)

Sao dois mecanismos, tentados nesta ordem:

  1. Caixa de dialogo NATIVA do Windows (MessageBox via ctypes). E uma chamada
     direta ao user32.dll, sem inicializar toolkit grafico nenhum. E o caminho
     preferido porque o servidor MCP as vezes roda num contexto restrito, onde
     inicializar um toolkit completo (tkinter) simplesmente TRAVA - a janela
     nunca nasce e o pedido expira sem o usuario ver nada.

  2. tkinter, como alternativa. Da uma janela mais bonita, com contador
     regressivo, quando o ambiente permite.

Se nenhum funcionar, o retorno e "deny": sem conseguir perguntar, nada deve ser
executado. Falhar fechado e a unica opcao aceitavel aqui.

Uso:
    python approval.py "<ferramenta>" "<detalhes>" [timeout_s]
"""

import sys

# Retornos da MessageBox do Windows
IDCANCEL = 2
IDYES = 6
IDNO = 7
TIMEOUT_RETORNO = 32000


def monta_texto(tool_name: str, details: str) -> str:
    """Texto do pedido, deixando claro o que cada botao faz."""
    return (
        "Claude quer executar uma acao no seu computador.\n\n"
        f"Ferramenta:  {tool_name}\n"
        f"{details or '(sem detalhes adicionais)'}\n\n"
        "-------------------------------------------\n"
        "SIM      = Sempre permitir (nesta janela)\n"
        "NAO      = Permitir uma vez\n"
        "CANCELAR = Negar (nada sera executado)"
    )


def ask_nativo(tool_name: str, details: str, timeout_s: int) -> str:
    """Caixa de dialogo nativa do Windows. Levanta excecao se nao der."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    MB_YESNOCANCEL = 0x00000003
    MB_ICONWARNING = 0x00000030
    MB_SYSTEMMODAL = 0x00001000   # fica por cima de tudo
    MB_SETFOREGROUND = 0x00010000  # traz para frente
    MB_TOPMOST = 0x00040000
    flags = (MB_YESNOCANCEL | MB_ICONWARNING | MB_SYSTEMMODAL
             | MB_SETFOREGROUND | MB_TOPMOST)

    titulo = "Claude - Pedido de permissao"
    texto = monta_texto(tool_name, details)

    resultado = None
    # MessageBoxTimeoutW fecha sozinha; nem toda versao do Windows exporta.
    try:
        fn = user32.MessageBoxTimeoutW
        fn.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       wintypes.UINT, wintypes.WORD, wintypes.DWORD]
        fn.restype = ctypes.c_int
        resultado = fn(None, texto, titulo, flags, 0, int(timeout_s * 1000))
        sys.stderr.write("metodo=MessageBoxTimeoutW\n")
    except AttributeError:
        fn = user32.MessageBoxW
        fn.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       wintypes.UINT]
        fn.restype = ctypes.c_int
        resultado = fn(None, texto, titulo, flags)
        sys.stderr.write("metodo=MessageBoxW\n")

    if resultado == IDYES:
        return "always"
    if resultado == IDNO:
        return "once"
    # IDCANCEL, fechar no X, ou estouro de tempo
    return "deny"


def primary_screen_size(fallback_w: int, fallback_h: int) -> tuple:
    """Tamanho do monitor PRIMARIO, em pixels.

    O winfo_screenwidth() do tkinter costuma devolver a area virtual somada de
    todos os monitores. Centralizar por esse numero joga a janela para o meio da
    area virtual - possivelmente em outro monitor, onde o usuario nao esta
    olhando. Um pedido de permissao invisivel e pior que inutil.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:
        pass
    return fallback_w, fallback_h


def centered_geometry(win_w: int, win_h: int, screen_w: int, screen_h: int) -> tuple:
    """Posicao (x, y) para centralizar a janela, sempre dentro da tela."""
    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 3  # um pouco acima do centro: mais natural de ler
    x = max(0, min(x, max(0, screen_w - win_w)))
    y = max(0, min(y, max(0, screen_h - win_h)))
    return x, y


def ask_tkinter(tool_name: str, details: str, timeout_s: int) -> str:
    """Janela em tkinter, com contador regressivo. Alternativa ao dialogo nativo."""
    import tkinter as tk

    result = {"choice": "deny"}

    root = tk.Tk()
    root.title("Claude - Pedido de permissao")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    win_w, win_h = 520, 260
    screen_w, screen_h = primary_screen_size(
        root.winfo_screenwidth(), root.winfo_screenheight()
    )
    x, y = centered_geometry(win_w, win_h, screen_w, screen_h)
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    pad = 20
    container = tk.Frame(root, padx=pad, pady=pad)
    container.pack(fill="both", expand=True)

    tk.Label(container, text="Claude quer executar uma acao no seu computador",
             font=("Segoe UI", 12, "bold"), anchor="w", justify="left").pack(fill="x")
    tk.Label(container, text=f"Ferramenta:  {tool_name}", font=("Segoe UI", 10),
             anchor="w", justify="left", fg="#333333").pack(fill="x", pady=(12, 2))
    tk.Message(container, text=details or "(sem detalhes adicionais)",
               font=("Consolas", 9), width=win_w - 2 * pad, anchor="w",
               justify="left", fg="#555555").pack(fill="x", pady=(0, 4))

    def choose(value: str) -> None:
        result["choice"] = value
        root.destroy()

    btn_row = tk.Frame(container)
    btn_row.pack(side="bottom", fill="x", pady=(16, 0))
    tk.Button(btn_row, text="Negar", width=12,
              command=lambda: choose("deny")).pack(side="right", padx=(8, 0))
    tk.Button(btn_row, text="Permitir uma vez", width=16,
              command=lambda: choose("once")).pack(side="right", padx=(8, 0))
    tk.Button(btn_row, text="Sempre permitir (nesta janela)", width=28,
              command=lambda: choose("always")).pack(side="right")

    countdown = tk.Label(container, text="", font=("Segoe UI", 8),
                         anchor="w", fg="#888888")
    countdown.pack(side="bottom", fill="x")

    remaining = {"s": max(5, int(timeout_s))}

    def tick() -> None:
        if remaining["s"] <= 0:
            choose("deny")
            return
        countdown.config(
            text=f"Sem resposta em {remaining['s']}s, o pedido e negado "
                 "automaticamente (nada sera executado)."
        )
        remaining["s"] -= 1
        root.after(1000, tick)

    root.protocol("WM_DELETE_WINDOW", lambda: choose("deny"))
    root.bind("<Return>", lambda _e: choose("once"))
    root.bind("<Escape>", lambda _e: choose("deny"))

    def chamar_atencao() -> None:
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            root.bell()
        except Exception:
            pass

    root.after(100, chamar_atencao)
    tick()
    root.mainloop()
    sys.stderr.write("metodo=tkinter\n")
    return result["choice"]


def ask(tool_name: str, details: str, timeout_s: int = 46) -> str:
    """Pergunta ao usuario, tentando o dialogo nativo antes do tkinter."""
    if sys.platform == "win32":
        try:
            return ask_nativo(tool_name, details, timeout_s)
        except Exception as exc:
            sys.stderr.write(f"dialogo nativo falhou: {exc}\n")
    try:
        return ask_tkinter(tool_name, details, timeout_s)
    except Exception as exc:
        sys.stderr.write(f"tkinter falhou: {exc}\n")
        return "deny"


def main() -> None:
    tool_name = sys.argv[1] if len(sys.argv) > 1 else "acao desconhecida"
    details = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        timeout_s = int(sys.argv[3]) if len(sys.argv) > 3 else 46
    except ValueError:
        timeout_s = 46
    try:
        choice = ask(tool_name, details, timeout_s)
    except Exception as exc:
        sys.stderr.write(f"Falha ao pedir permissao: {exc}\n")
        choice = "deny"
    # A unica coisa no stdout e a escolha, para o servidor ler com seguranca.
    print(choice)


if __name__ == "__main__":
    main()
