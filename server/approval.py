"""
Janela de aprovacao estilo Claude Code.

Este script e executado como um PROCESSO SEPARADO pelo servidor MCP toda vez
que uma acao de controle precisa de confirmacao. Ele mostra um popup nativo do
Windows com tres opcoes e imprime a escolha do usuario no stdout:

    once   -> "Permitir uma vez"
    always -> "Sempre permitir esta ferramenta"
    deny   -> "Negar" (ou fechar a janela)

Rodar a UI em um processo separado evita conflitos entre o tkinter e a thread
principal do servidor MCP (que fica ocupada com o transporte stdio).

Uso:
    python approval.py "<nome_da_ferramenta>" "<detalhes_da_acao>"
"""

import sys


def ask(tool_name: str, details: str) -> str:
    import tkinter as tk

    result = {"choice": "deny"}

    root = tk.Tk()
    root.title("Claude - Pedido de permissao")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # Centraliza a janela na tela
    win_w, win_h = 520, 260
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 3
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    pad = 20
    container = tk.Frame(root, padx=pad, pady=pad)
    container.pack(fill="both", expand=True)

    tk.Label(
        container,
        text="Claude quer executar uma acao no seu computador",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
        justify="left",
    ).pack(fill="x")

    tk.Label(
        container,
        text=f"Ferramenta:  {tool_name}",
        font=("Segoe UI", 10),
        anchor="w",
        justify="left",
        fg="#333333",
    ).pack(fill="x", pady=(12, 2))

    detail_box = tk.Message(
        container,
        text=details or "(sem detalhes adicionais)",
        font=("Consolas", 9),
        width=win_w - 2 * pad,
        anchor="w",
        justify="left",
        fg="#555555",
    )
    detail_box.pack(fill="x", pady=(0, 4))

    def choose(value: str) -> None:
        result["choice"] = value
        root.destroy()

    btn_row = tk.Frame(container)
    btn_row.pack(side="bottom", fill="x", pady=(16, 0))

    tk.Button(
        btn_row,
        text="Negar",
        width=12,
        command=lambda: choose("deny"),
    ).pack(side="right", padx=(8, 0))

    tk.Button(
        btn_row,
        text="Permitir uma vez",
        width=16,
        command=lambda: choose("once"),
    ).pack(side="right", padx=(8, 0))

    tk.Button(
        btn_row,
        text="Sempre permitir (nesta janela)",
        width=28,
        command=lambda: choose("always"),
    ).pack(side="right")

    # Fechar no X = negar. Enter = permitir uma vez. Esc = negar.
    root.protocol("WM_DELETE_WINDOW", lambda: choose("deny"))
    root.bind("<Return>", lambda _e: choose("once"))
    root.bind("<Escape>", lambda _e: choose("deny"))

    root.after(100, lambda: root.focus_force())
    root.mainloop()
    return result["choice"]


def main() -> None:
    tool_name = sys.argv[1] if len(sys.argv) > 1 else "acao desconhecida"
    details = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        choice = ask(tool_name, details)
    except Exception as exc:  # se a UI falhar, nega por seguranca
        sys.stderr.write(f"Falha ao mostrar o popup de aprovacao: {exc}\n")
        choice = "deny"
    # A unica coisa no stdout e a escolha, para o servidor ler com seguranca.
    print(choice)


if __name__ == "__main__":
    main()
