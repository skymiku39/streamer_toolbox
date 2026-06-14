"""使用 rich 在終端機美化呈現聊天室訊息。"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from .reader import ChatMessage

_console = Console()


def _badge(message: ChatMessage) -> Text:
    badges: list[str] = []
    if message.is_owner:
        badges.append("[bold magenta]主[/bold magenta]")
    if message.is_moderator:
        badges.append("[bold blue]MOD[/bold blue]")
    if message.is_member:
        badges.append("[bold green]訂[/bold green]")
    if message.is_verified:
        badges.append("[bold cyan]V[/bold cyan]")
    if not badges:
        return Text("")
    return Text.from_markup(" ".join(badges) + " ")


def _author_color(message: ChatMessage) -> str:
    if message.color:
        return message.color
    if message.is_owner:
        return "bold magenta"
    if message.is_moderator:
        return "bold blue"
    if message.is_member:
        return "bold green"
    return "bold yellow"


def print_message(message: ChatMessage) -> None:
    """以易讀格式列印一則聊天室訊息。"""

    timestamp = message.timestamp.astimezone().strftime("%H:%M:%S")
    line = Text()
    line.append(f"[{timestamp}] ", style="dim")

    if message.message_type in ("system", "joined", "notice", "reconnect", "error", "disconnected"):
        line.append("[system] ", style="cyan")
        line.append(message.message or "", style="dim")
        _console.print(line)
        return

    line.append_text(_badge(message))

    try:
        line.append(message.author_name, style=_author_color(message))
    except Exception:
        line.append(message.author_name, style="bold yellow")

    if message.amount:
        line.append(f" 🪙 {message.amount}", style="bold red")

    line.append(": ", style="white")
    line.append(message.message or "", style="white")

    _console.print(line)
