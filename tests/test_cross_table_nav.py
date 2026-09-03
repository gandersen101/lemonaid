"""Moving the cursor between the main table and the non-switchable table.

The two tables read as one list: pressing down past the last switchable session
drops into the non-switchable ones, and pressing up from their top returns. A
focused DataTable binds the arrow keys itself, so this navigation lives in
on_key, which runs first. The arrows always work; up_down adds vim or emacs keys.
"""

import asyncio
import itertools

from textual.widgets import DataTable

from lemonaid.config import Config, KeybindingsConfig, TuiConfig
from lemonaid.inbox import db
from lemonaid.inbox.tui.app import LemonaidApp, _parse_up_down

_ids = itertools.count(900)


def _active(name: str) -> int:
    """A live session in the main table, switchable from this (tmux) environment."""
    return _seed(name, "tmux")


def _other(name: str) -> int:
    """A live session from another terminal - non-switchable from here."""
    return _seed(name, "wezterm")


def _seed(name: str, source: str) -> int:
    with db.connect() as conn:
        n = db.add(
            conn,
            f"claude:{name}",
            "a message",
            name,
            {"tty": f"/dev/ttys{next(_ids)}", "cwd": "/tmp", "session_id": f"s{next(_ids)}"},
        )
        conn.execute("UPDATE notifications SET switch_source = ? WHERE id = ?", (source, n.id))
        conn.commit()
        return n.id


def _run(steps, *, up_down="", size=(120, 40), monkeypatch):
    monkeypatch.setattr(LemonaidApp, "_archive_channel", lambda self, channel: None)
    # A long refresh interval keeps the periodic rebuild from moving the cursor
    # while a step is mid-way through a key sequence.
    config = Config(
        tui=TuiConfig(
            refresh_interval=1000.0,
            keybindings=KeybindingsConfig(up_down=up_down),
        )
    )
    monkeypatch.setattr("lemonaid.inbox.tui.app.load_config", lambda: config)

    async def run():
        app = LemonaidApp()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(run())


# ---- _parse_up_down --------------------------------------------------------


def test_parse_up_down_empty_is_none():
    assert _parse_up_down("") is None


def test_parse_up_down_two_chars_split_per_key():
    assert _parse_up_down("kj") == ("k", "j")
    assert _parse_up_down("ri") == ("r", "i")


def test_parse_up_down_comma_form_keeps_modifier_names():
    assert _parse_up_down("ctrl+p,ctrl+n") == ("ctrl+p", "ctrl+n")


def test_parse_up_down_comma_form_strips_spaces():
    assert _parse_up_down(" ctrl+p , ctrl+n ") == ("ctrl+p", "ctrl+n")


def test_parse_up_down_rejects_malformed():
    assert _parse_up_down("k") is None  # one bare character
    assert _parse_up_down("abc") is None  # three characters, no comma
    assert _parse_up_down("a,b,c") is None  # three parts
    assert _parse_up_down("ctrl+p,") is None  # an empty part


# ---- arrow-key crossover ---------------------------------------------------


def test_down_crosses_from_main_into_non_switchable(monkeypatch):
    for i in range(2):
        _active(f"main-{i}")
    for i in range(2):
        _other(f"other-{i}")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        main.move_cursor(row=main.row_count - 1)
        await pilot.press("down")
        await pilot.pause()
        return app.focused.id, app.focused.cursor_coordinate.row

    focused_id, row = _run(steps, monkeypatch=monkeypatch)
    assert focused_id == "other_sources_table"
    assert row == 0


def test_up_crosses_back_from_non_switchable_to_main(monkeypatch):
    for i in range(2):
        _active(f"main-{i}")
    _other("other-0")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        main.move_cursor(row=main.row_count - 1)
        await pilot.press("down")  # into the non-switchable table
        await pilot.pause()
        await pilot.press("up")  # back to main
        await pilot.pause()
        return app.focused.id, app.focused.cursor_coordinate.row, main.row_count

    focused_id, row, main_rows = _run(steps, monkeypatch=monkeypatch)
    assert focused_id == "main_table"
    assert row == main_rows - 1


def test_down_within_main_moves_without_crossing(monkeypatch):
    for i in range(3):
        _active(f"main-{i}")
    _other("other-0")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        main.move_cursor(row=0)
        await pilot.press("down")
        await pilot.pause()
        return app.focused.id, app.focused.cursor_coordinate.row

    focused_id, row = _run(steps, monkeypatch=monkeypatch)
    assert focused_id == "main_table"
    assert row == 1


def test_down_at_the_bottom_stays_when_nothing_is_non_switchable(monkeypatch):
    for i in range(2):
        _active(f"main-{i}")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        main.move_cursor(row=main.row_count - 1)
        await pilot.press("down")
        await pilot.pause()
        return app.focused.id, app.focused.cursor_coordinate.row, main.row_count

    focused_id, row, rows = _run(steps, monkeypatch=monkeypatch)
    assert focused_id == "main_table"
    assert row == rows - 1


# ---- configured vim / emacs keys -------------------------------------------


def test_vim_j_and_k_cross_between_tables(monkeypatch):
    _active("main-0")
    _other("other-0")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        await pilot.press("j")  # down, into non-switchable
        await pilot.pause()
        crossed = app.focused.id
        await pilot.press("k")  # up, back to main
        await pilot.pause()
        return crossed, app.focused.id

    crossed, back = _run(steps, up_down="kj", monkeypatch=monkeypatch)
    assert crossed == "other_sources_table"
    assert back == "main_table"


def test_emacs_ctrl_n_and_ctrl_p_cross_between_tables(monkeypatch):
    _active("main-0")
    _other("other-0")

    async def steps(app, pilot):
        main = app.query_one("#main_table", DataTable)
        main.focus()
        await pilot.press("ctrl+n")  # down, into non-switchable
        await pilot.pause()
        crossed = app.focused.id
        await pilot.press("ctrl+p")  # up, back to main
        await pilot.pause()
        return crossed, app.focused.id

    crossed, back = _run(steps, up_down="ctrl+p,ctrl+n", monkeypatch=monkeypatch)
    assert crossed == "other_sources_table"
    assert back == "main_table"


# ---- command palette moved off Ctrl+p --------------------------------------


def test_ctrl_p_no_longer_opens_the_command_palette(monkeypatch):
    _active("main-0")

    async def steps(app, pilot):
        await pilot.press("ctrl+p")
        await pilot.pause()
        return type(app.screen).__name__

    assert _run(steps, monkeypatch=monkeypatch) != "CommandPalette"


def test_command_palette_opens_on_ctrl_backslash(monkeypatch):
    _active("main-0")

    async def steps(app, pilot):
        await pilot.press("ctrl+backslash")
        await pilot.pause()
        return type(app.screen).__name__

    assert _run(steps, monkeypatch=monkeypatch) == "CommandPalette"
