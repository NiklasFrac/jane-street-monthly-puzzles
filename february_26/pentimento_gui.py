#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "Pillow ist erforderlich. Installiere es via: pip install pillow\n"
        f"Fehler: {e}"
    )

Coord = Tuple[int, int]  # (row, col)

# -----------------------------
# 1) Konfiguration / Givens
# -----------------------------

GRID_SIZE = 13

# Koordinaten sind 0-indexiert: (row, col)
# Aus dem Bild extrahiert.
DEFAULT_GIVENS: Dict[Coord, int] = {
    (0, 4): 15,
    (1, 7): 11,
    (2, 1): 15,
    (2, 3): 5,
    (2, 6): 15,
    (2, 8): 11,
    (2, 10): 11,
    (3, 4): 15,
    (3, 7): 8,
    (3, 9): 12,
    (3, 11): 12,
    (4, 1): 16,
    (4, 5): 8,
    (4, 10): 6,
    (5, 3): 16,
    (5, 12): 6,
    (6, 2): 16,
    (6, 4): 3,
    (6, 6): 16,
    (6, 8): 1,
    (6, 10): 12,
    (7, 0): 13,
    (7, 9): 4,
    (8, 2): 7,
    (8, 7): 12,
    (8, 11): 10,
    (9, 1): 2,
    (9, 3): 13,
    (9, 5): 16,
    (9, 8): 14,
    (10, 2): 13,
    (10, 4): 14,
    (10, 6): 14,
    (10, 9): 14,
    (10, 11): 10,
    (11, 5): 9,
    (12, 8): 9,
}

# -----------------------------
# 2) Model
# -----------------------------


@dataclass
class Cell:
    value: Optional[int] = None
    fixed: bool = False
    color: Optional[str] = None  # hex, e.g. "#ff00aa"


class PuzzleModel:
    """Logik/State ohne GUI."""

    def __init__(self, size: int, givens: Dict[Coord, int]):
        self.size = size
        self._grid: List[List[Cell]] = [[Cell() for _ in range(size)] for _ in range(size)]
        for (r, c), v in givens.items():
            self._grid[r][c].value = int(v)
            self._grid[r][c].fixed = True

    def cell(self, r: int, c: int) -> Cell:
        return self._grid[r][c]

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def set_value(self, r: int, c: int, value: Optional[int]) -> None:
        cell = self.cell(r, c)
        if cell.fixed:
            raise ValueError("Fixe Zellen können nicht verändert werden.")
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValueError("value muss None oder eine nichtnegative ganze Zahl sein.")
        cell.value = value

    def set_color(self, r: int, c: int, color: Optional[str]) -> None:
        # Farbe ist auch auf fixed Zellen erlaubt.
        if color is not None:
            if not (isinstance(color, str) and color.startswith("#") and len(color) in (7, 9)):
                raise ValueError("color muss Hex sein, z.B. '#RRGGBB'.")
        self.cell(r, c).color = color

    def to_dict(self) -> dict:
        givens = {
            (r, c): self.cell(r, c).value
            for r in range(self.size)
            for c in range(self.size)
            if self.cell(r, c).fixed
        }
        entries = {
            (r, c): self.cell(r, c).value
            for r in range(self.size)
            for c in range(self.size)
            if (not self.cell(r, c).fixed and self.cell(r, c).value is not None)
        }
        colors = {
            (r, c): self.cell(r, c).color
            for r in range(self.size)
            for c in range(self.size)
            if self.cell(r, c).color is not None
        }

        def pack(d: Dict[Coord, object]) -> Dict[str, object]:
            return {f"{r},{c}": v for (r, c), v in d.items()}

        return {"size": self.size, "givens": pack(givens), "entries": pack(entries), "colors": pack(colors)}

    @staticmethod
    def from_dict(payload: dict) -> "PuzzleModel":
        size = int(payload["size"])

        def unpack(d: Dict[str, object]) -> Dict[Coord, object]:
            out: Dict[Coord, object] = {}
            for k, v in d.items():
                rs, cs = k.split(",")
                out[(int(rs), int(cs))] = v
            return out

        givens = {k: int(v) for k, v in unpack(payload.get("givens", {})).items()}
        model = PuzzleModel(size=size, givens=givens)

        entries = unpack(payload.get("entries", {}))
        for (r, c), v in entries.items():
            if model.cell(r, c).fixed:
                continue
            model.cell(r, c).value = int(v)

        colors = unpack(payload.get("colors", {}))
        for (r, c), col in colors.items():
            model.cell(r, c).color = str(col)

        return model


# -----------------------------
# 3) Undo/Redo
# -----------------------------


@dataclass(frozen=True)
class CellPatch:
    coord: Coord
    before_value: Optional[int]
    after_value: Optional[int]
    before_color: Optional[str]
    after_color: Optional[str]


class History:
    def __init__(self) -> None:
        self._undo: List[List[CellPatch]] = []
        self._redo: List[List[CellPatch]] = []

    def push(self, patches: List[CellPatch]) -> None:
        if not patches:
            return
        self._undo.append(patches)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self, model: PuzzleModel) -> None:
        if not self._undo:
            return
        patches = self._undo.pop()
        for p in patches:
            r, c = p.coord
            if not model.cell(r, c).fixed:
                model.cell(r, c).value = p.before_value
            model.cell(r, c).color = p.before_color
        self._redo.append(patches)

    def redo(self, model: PuzzleModel) -> None:
        if not self._redo:
            return
        patches = self._redo.pop()
        for p in patches:
            r, c = p.coord
            if not model.cell(r, c).fixed:
                model.cell(r, c).value = p.after_value
            model.cell(r, c).color = p.after_color
        self._undo.append(patches)


# -----------------------------
# 4) Rendering / Export
# -----------------------------


class BoardRenderer:
    """Render to a Pillow image (for PNG export)."""

    def __init__(self, cell_px: int = 52, pad_px: int = 18) -> None:
        self.cell_px = cell_px
        self.pad_px = pad_px

    def render(self, model: PuzzleModel) -> Image.Image:
        s = model.size
        W = self.pad_px * 2 + s * self.cell_px
        H = self.pad_px * 2 + s * self.cell_px
        img = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(img)

        x0 = self.pad_px
        y0 = self.pad_px
        x1 = x0 + s * self.cell_px
        y1 = y0 + s * self.cell_px

        # colors
        for r in range(s):
            for c in range(s):
                cell = model.cell(r, c)
                if cell.color:
                    draw.rectangle(
                        [
                            x0 + c * self.cell_px,
                            y0 + r * self.cell_px,
                            x0 + (c + 1) * self.cell_px,
                            y0 + (r + 1) * self.cell_px,
                        ],
                        fill=cell.color,
                        outline=None,
                    )

        # grid lines (light)
        for i in range(s + 1):
            x = x0 + i * self.cell_px
            y = y0 + i * self.cell_px
            draw.line([(x, y0), (x, y1)], fill=(180, 180, 180), width=1)
            draw.line([(x0, y), (x1, y)], fill=(180, 180, 180), width=1)

        # outer border
        draw.rectangle([x0, y0, x1, y1], outline="black", width=3)

        # font
        try:
            font = ImageFont.truetype("DejaVuSerif-Italic.ttf", int(self.cell_px * 0.55))
        except Exception:
            font = ImageFont.load_default()

        # numbers
        for r in range(s):
            for c in range(s):
                v = model.cell(r, c).value
                if v is None:
                    continue
                text = str(v)
                cx = x0 + c * self.cell_px + self.cell_px / 2
                cy = y0 + r * self.cell_px + self.cell_px / 2
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((cx - tw / 2, cy - th / 2), text, fill="black", font=font)

        return img


# -----------------------------
# 5) GUI
# -----------------------------


class PuzzleGUI(tk.Tk):
    def __init__(self, model: PuzzleModel):
        super().__init__()
        self.title("JS Puzzle Grid — Editor")
        self.model = model
        self.history = History()

        self.cell_px = 56
        self.margin = 18

        self.selected: Coord = (0, 0)
        self._cell_items: Dict[Coord, Tuple[int, int]] = {}

        self._editor: Optional[tk.Entry] = None
        self._editing_coord: Optional[Coord] = None
        self._editing_before: Optional[int] = None

        # QoL: "Zahlenmodus" (sticky editor)
        self.number_mode = tk.BooleanVar(value=False)

        self._build_ui()
        self._bind_keys()
        self._draw_board()
        self._update_status()

    # ---- Crash sichtbar machen: statt "Fenster weg"
    def report_callback_exception(self, exc, val, tb):
        msg = "".join(traceback.format_exception(exc, val, tb))
        try:
            messagebox.showerror("Fehler (Tkinter Callback)", msg)
        finally:
            print(msg, file=sys.stderr)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = tk.Frame(self, padx=8, pady=6)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(99, weight=1)

        def btn(txt: str, cmd, col: int) -> None:
            b = tk.Button(toolbar, text=txt, command=cmd)
            b.grid(row=0, column=col, padx=4)

        btn("Farbe… (C)", self.pick_color, 0)
        btn("Farbe löschen (X)", self.clear_color, 1)
        btn("Zahl löschen (Del)", self.clear_value, 2)
        btn("Reset Zahlen", self.reset_numbers, 3)
        btn("Reset Farben", self.reset_colors, 4)
        btn("Undo (Ctrl+Z)", self.undo, 5)
        btn("Redo (Ctrl+Y)", self.redo, 6)
        btn("Speichern…", self.save_json, 7)
        btn("Laden…", self.load_json, 8)
        btn("Export PNG…", self.export_png, 9)

        # QoL: Zahlenmodus Toggle
        chk = tk.Checkbutton(
            toolbar,
            text="Zahlenmodus (M)",
            variable=self.number_mode,
            command=self._on_toggle_number_mode,
        )
        chk.grid(row=0, column=10, padx=10)

        self.status = tk.Label(toolbar, text="", anchor="w")
        self.status.grid(row=0, column=99, sticky="ew", padx=8)

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Zahl bearbeiten…", command=self.edit_value)
        self.menu.add_command(label="Zahl löschen", command=self.clear_value)
        self.menu.add_separator()
        self.menu.add_command(label="Farbe…", command=self.pick_color)
        self.menu.add_command(label="Farbe löschen", command=self.clear_color)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", lambda e: self.edit_value())

        # Right click: Windows/Linux + Mac variants
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_right_click)  # some mac setups
        self.canvas.bind("<Control-Button-1>", self._on_right_click)

    def _bind_keys(self) -> None:
        for key, dr, dc in [("<Up>", -1, 0), ("<Down>", 1, 0), ("<Left>", 0, -1), ("<Right>", 0, 1)]:
            self.bind(key, lambda e, dr=dr, dc=dc: self.move_selection(dr, dc))

        self.bind("<Return>", lambda e: self._enter_key())
        self.bind("<Delete>", lambda e: self.clear_value())
        self.bind("<BackSpace>", lambda e: self._backspace_key())

        self.bind("<Tab>", lambda e: self._tab_key(shift=False))
        self.bind("<ISO_Left_Tab>", lambda e: self._tab_key(shift=True))   # Linux
        self.bind("<Shift-Tab>", lambda e: self._tab_key(shift=True))      # Windows/mac

        self.bind("c", lambda e: self.pick_color())
        self.bind("C", lambda e: self.pick_color())
        self.bind("x", lambda e: self.clear_color())
        self.bind("X", lambda e: self.clear_color())

        self.bind("m", lambda e: self._toggle_number_mode())
        self.bind("M", lambda e: self._toggle_number_mode())

        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())

        # Digit shortcuts: if no editor open -> open and prefill (wie vorher)
        for d in "0123456789":
            self.bind(d, self._start_edit_from_digit)

        self.bind("<Escape>", lambda e: self._close_editor(cancel=True))

    def _toggle_number_mode(self) -> None:
        self.number_mode.set(not self.number_mode.get())
        self._on_toggle_number_mode()

    def _on_toggle_number_mode(self) -> None:
        # Wenn man Zahlenmodus aktiviert: falls editierbar -> Editor sofort öffnen.
        if self.number_mode.get():
            self._ensure_editor_for_selection()
        else:
            # Deaktivieren: commit + schließen
            self._close_editor(cancel=False)
            self._destroy_editor()

        self._update_status()

    def _board_bbox(self) -> Tuple[int, int, int, int]:
        s = self.model.size
        x0 = self.margin
        y0 = self.margin
        x1 = x0 + s * self.cell_px
        y1 = y0 + s * self.cell_px
        return x0, y0, x1, y1

    def _cell_bbox(self, r: int, c: int) -> Tuple[int, int, int, int]:
        x0, y0, _, _ = self._board_bbox()
        L = x0 + c * self.cell_px
        T = y0 + r * self.cell_px
        return L, T, L + self.cell_px, T + self.cell_px

    def _xy_to_cell(self, x: int, y: int) -> Optional[Coord]:
        x0, y0, x1, y1 = self._board_bbox()
        if not (x0 <= x < x1 and y0 <= y < y1):
            return None
        c = int((x - x0) // self.cell_px)
        r = int((y - y0) // self.cell_px)
        return (r, c) if self.model.in_bounds(r, c) else None

    def _draw_board(self) -> None:
        self.canvas.delete("all")
        self._cell_items.clear()

        x0, y0, x1, y1 = self._board_bbox()
        s = self.model.size

        # Canvas Größe (Grid passt; dennoch resize-freundlich)
        self.canvas.config(width=x1 + self.margin, height=y1 + self.margin)

        for r in range(s):
            for c in range(s):
                L, T, R, B = self._cell_bbox(r, c)
                cell = self.model.cell(r, c)
                fill = cell.color if cell.color else "white"
                rect = self.canvas.create_rectangle(L, T, R, B, fill=fill, outline="")

                text = "" if cell.value is None else str(cell.value)
                font = ("Times New Roman", int(self.cell_px * 0.45), "italic")
                t = self.canvas.create_text((L + R) / 2, (T + B) / 2, text=text, font=font, fill="black")
                self._cell_items[(r, c)] = (rect, t)

        dash = (1, 3)
        for i in range(s + 1):
            x = x0 + i * self.cell_px
            y = y0 + i * self.cell_px
            self.canvas.create_line(x, y0, x, y1, fill="#b5b5b5", dash=dash)
            self.canvas.create_line(x0, y, x1, y, fill="#b5b5b5", dash=dash)

        self.canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=3)

        self._draw_selection()

    def _redraw_cell(self, r: int, c: int) -> None:
        rect, text_id = self._cell_items[(r, c)]
        cell = self.model.cell(r, c)
        self.canvas.itemconfig(rect, fill=cell.color if cell.color else "white")
        self.canvas.itemconfig(text_id, text="" if cell.value is None else str(cell.value))

    def _draw_selection(self) -> None:
        self.canvas.delete("selection")
        r, c = self.selected
        L, T, R, B = self._cell_bbox(r, c)
        self.canvas.create_rectangle(
            L + 2, T + 2, R - 2, B - 2,
            outline="#0078D7", width=3, tags="selection"
        )

    def _update_status(self) -> None:
        r, c = self.selected
        cell = self.model.cell(r, c)
        flags = "FIX" if cell.fixed else "EDIT"
        v = "" if cell.value is None else str(cell.value)
        col = cell.color if cell.color else "—"
        mode = "ON" if self.number_mode.get() else "OFF"
        self.status.config(
            text=f"Zelle (r={r+1}, c={c+1}) [{flags}] | Wert: {v or '—'} | Farbe: {col} | Zahlenmodus: {mode}"
        )

    def _on_click(self, event) -> None:
        # Robust: erst committen, dann selection ändern
        self._close_editor(cancel=False)

        cell = self._xy_to_cell(event.x, event.y)
        if cell is None:
            return
        self.selected = cell
        self._draw_selection()
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def _on_right_click(self, event) -> None:
        self._close_editor(cancel=False)

        cell = self._xy_to_cell(event.x, event.y)
        if cell is not None:
            self.selected = cell
            self._draw_selection()
            self._update_status()

        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            # verhindert “stuck grab” auf manchen Systemen
            try:
                self.menu.grab_release()
            except Exception:
                pass

    def move_selection(self, dr: int, dc: int) -> None:
        self._close_editor(cancel=False)

        r, c = self.selected
        nr = max(0, min(self.model.size - 1, r + dr))
        nc = max(0, min(self.model.size - 1, c + dc))
        self.selected = (nr, nc)
        self._draw_selection()
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def _tab_key(self, shift: bool) -> str:
        # Tab navigiert; verhindert Fokus-Wechsel aus der App
        self._close_editor(cancel=False)
        self.move_selection(0, -1 if shift else 1)
        return "break"

    def _enter_key(self) -> None:
        # Enter: wenn Editor offen -> commit; in Zahlenmodus zusätzlich down bewegen
        if self._editor is not None:
            self._close_editor(cancel=False)
            if self.number_mode.get():
                self.move_selection(1, 0)
                return
        # wie vorher: wenn kein Editor -> Editor öffnen
        self.edit_value()

    def _backspace_key(self) -> None:
        # Wenn Editor offen: normales Backspace im Entry (tk macht das).
        # Wenn kein Editor: wie "Zahl löschen" (QoL)
        if self._editor is None:
            self.clear_value()

    def _start_edit_from_digit(self, event) -> None:
        # Wenn Editor offen: Entry bekommt die Taste ohnehin; nichts erzwingen.
        if self._editor is not None:
            return
        # Wenn Zahlenmodus an: Editor soll sowieso offen sein, also öffnen und prefill
        self.edit_value(prefill=str(event.char))

    def _ensure_editor_for_selection(self) -> None:
        r, c = self.selected
        cell = self.model.cell(r, c)
        if cell.fixed:
            self._destroy_editor()
            return
        if self._editor is None:
            self.edit_value(prefill=None)
        else:
            # Editor existiert: wenn er zu anderer Zelle gehört, commit + neu öffnen
            if self._editing_coord != (r, c):
                self._close_editor(cancel=False)
                self.edit_value(prefill=None)

    def edit_value(self, prefill: Optional[str] = None) -> None:
        r, c = self.selected
        cell = self.model.cell(r, c)
        if cell.fixed:
            self.bell()
            return

        # Falls ein Editor offen ist: committen und sauber neu öffnen
        self._close_editor(cancel=False)
        self._destroy_editor()

        L, T, R, B = self._cell_bbox(r, c)
        self._editor = tk.Entry(self.canvas, justify="center")
        self._editor.place(x=L + 4, y=T + 10, width=self.cell_px - 8, height=self.cell_px - 20)

        self._editing_coord = (r, c)
        self._editing_before = cell.value

        current = "" if cell.value is None else str(cell.value)
        self._editor.insert(0, prefill if prefill is not None else current)
        self._editor.select_range(0, tk.END)
        self._editor.focus_set()

        # Enter handled globally; hier nur committen
        self._editor.bind("<Return>", lambda e: self._close_editor(cancel=False))
        self._editor.bind("<FocusOut>", lambda e: self._close_editor(cancel=False))

    def _destroy_editor(self) -> None:
        if self._editor is not None:
            try:
                self._editor.destroy()
            finally:
                self._editor = None
                self._editing_coord = None
                self._editing_before = None

    def _close_editor(self, cancel: bool) -> None:
        """cancel=True: Editor schließen ohne commit (revert). cancel=False: commit wenn sinnvoll."""
        if self._editor is None:
            return

        if cancel:
            # revert: setze Entry zurück, ohne History-Eintrag
            if self._editing_coord is not None:
                r, c = self._editing_coord
                cell = self.model.cell(r, c)
                if not cell.fixed:
                    cell.value = self._editing_before
                    self._redraw_cell(r, c)
            self._destroy_editor()
            self._update_status()
            return

        # commit:
        raw = self._editor.get().strip()
        coord = self._editing_coord
        self._destroy_editor()

        if coord is None:
            return

        r, c = coord
        cell = self.model.cell(r, c)
        if cell.fixed:
            return

        if raw == "" or raw == "0":
            new_val: Optional[int] = None
        else:
            if not raw.isdigit():
                self.bell()
                messagebox.showwarning("Ungültig", "Bitte nur Ziffern eingeben (oder leer lassen / 0 zum Löschen).")
                return
            new_val = int(raw)

        if cell.value == new_val:
            return

        patch = CellPatch((r, c), cell.value, new_val, cell.color, cell.color)
        self.model.set_value(r, c, new_val)
        self.history.push([patch])
        self._redraw_cell(r, c)
        self._update_status()

    def clear_value(self) -> None:
        self._close_editor(cancel=False)

        r, c = self.selected
        cell = self.model.cell(r, c)
        if cell.fixed:
            self.bell()
            return
        if cell.value is None:
            return
        patch = CellPatch((r, c), cell.value, None, cell.color, cell.color)
        self.model.set_value(r, c, None)
        self.history.push([patch])
        self._redraw_cell(r, c)
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def pick_color(self) -> None:
        self._close_editor(cancel=False)

        r, c = self.selected
        cell = self.model.cell(r, c)
        initial = cell.color if cell.color else "#ffffff"
        col = colorchooser.askcolor(color=initial, title="Zellenfarbe wählen")
        if not col or not col[1]:
            return
        new_color = col[1]
        if cell.color == new_color:
            return

        # FIX: value muss korrekt gepatcht werden, sonst zerstört Undo Zahlen
        patch = CellPatch((r, c), cell.value, cell.value, cell.color, new_color)
        self.model.set_color(r, c, new_color)
        self.history.push([patch])
        self._redraw_cell(r, c)
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def clear_color(self) -> None:
        self._close_editor(cancel=False)

        r, c = self.selected
        cell = self.model.cell(r, c)
        if cell.color is None:
            return

        patch = CellPatch((r, c), cell.value, cell.value, cell.color, None)
        self.model.set_color(r, c, None)
        self.history.push([patch])
        self._redraw_cell(r, c)
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def reset_numbers(self) -> None:
        self._close_editor(cancel=True)

        patches: List[CellPatch] = []
        for r in range(self.model.size):
            for c in range(self.model.size):
                cell = self.model.cell(r, c)
                if cell.fixed or cell.value is None:
                    continue
                patches.append(CellPatch((r, c), cell.value, None, cell.color, cell.color))
                cell.value = None
        if patches:
            self.history.push(patches)
            self._draw_board()
            self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def reset_colors(self) -> None:
        self._close_editor(cancel=False)

        patches: List[CellPatch] = []
        for r in range(self.model.size):
            for c in range(self.model.size):
                cell = self.model.cell(r, c)
                if cell.color is None:
                    continue
                patches.append(CellPatch((r, c), cell.value, cell.value, cell.color, None))
                cell.color = None
        if patches:
            self.history.push(patches)
            self._draw_board()
            self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def undo(self) -> None:
        self._close_editor(cancel=True)

        if not self.history.can_undo():
            self.bell()
            return
        self.history.undo(self.model)
        self._draw_board()
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def redo(self) -> None:
        self._close_editor(cancel=True)

        if not self.history.can_redo():
            self.bell()
            return
        self.history.redo(self.model)
        self._draw_board()
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def save_json(self) -> None:
        self._close_editor(cancel=False)

        path = filedialog.asksaveasfilename(
            title="State speichern",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        payload = self.model.to_dict()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte nicht speichern:\n{e}")
            return
        messagebox.showinfo("OK", "Gespeichert.")

    def load_json(self) -> None:
        self._close_editor(cancel=True)

        path = filedialog.askopenfilename(
            title="State laden",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            model = PuzzleModel.from_dict(payload)
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte nicht laden:\n{e}")
            return
        self.model = model
        self.history = History()
        self.selected = (0, 0)
        self._draw_board()
        self._update_status()

        if self.number_mode.get():
            self._ensure_editor_for_selection()

    def export_png(self) -> None:
        self._close_editor(cancel=False)

        path = filedialog.asksaveasfilename(
            title="Als PNG exportieren",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            return
        try:
            renderer = BoardRenderer(cell_px=self.cell_px, pad_px=self.margin)
            image = renderer.render(self.model)
            image.save(path)
        except Exception as e:
            messagebox.showerror("Fehler", f"Export fehlgeschlagen:\n{e}")
            return
        messagebox.showinfo("OK", "PNG exportiert.")


# -----------------------------
# 6) Tests (unittest)
# -----------------------------


def _run_tests() -> int:
    import unittest

    class PuzzleTests(unittest.TestCase):
        def setUp(self) -> None:
            self.m = PuzzleModel(GRID_SIZE, DEFAULT_GIVENS)

        def test_fixed_cells_cannot_change(self):
            r, c = next(iter(DEFAULT_GIVENS.keys()))
            with self.assertRaises(ValueError):
                self.m.set_value(r, c, 7)

        def test_color_allowed_on_fixed(self):
            r, c = next(iter(DEFAULT_GIVENS.keys()))
            self.m.set_color(r, c, "#ff0000")
            self.assertEqual(self.m.cell(r, c).color, "#ff0000")

        def test_undo_redo_value(self):
            h = History()
            r, c = 0, 0
            self.assertFalse(self.m.cell(r, c).fixed)
            before = self.m.cell(r, c).value
            self.m.set_value(r, c, 12)
            h.push([CellPatch((r, c), before, 12, None, None)])
            h.undo(self.m)
            self.assertIsNone(self.m.cell(r, c).value)
            h.redo(self.m)
            self.assertEqual(self.m.cell(r, c).value, 12)

        def test_save_load_roundtrip(self):
            self.m.set_color(0, 0, "#00ff00")
            self.m.set_value(0, 0, 7)
            payload = self.m.to_dict()
            m2 = PuzzleModel.from_dict(payload)
            self.assertEqual(m2.size, self.m.size)
            self.assertEqual(m2.cell(0, 0).value, 7)
            self.assertEqual(m2.cell(0, 0).color, "#00ff00")
            for (r, c), v in DEFAULT_GIVENS.items():
                self.assertTrue(m2.cell(r, c).fixed)
                self.assertEqual(m2.cell(r, c).value, v)

        def test_color_patch_does_not_affect_value(self):
            # Regression: Color changes must not erase values via undo
            h = History()
            self.m.set_value(0, 0, 9)
            before_v = self.m.cell(0, 0).value
            before_c = self.m.cell(0, 0).color
            self.m.set_color(0, 0, "#123456")
            h.push([CellPatch((0, 0), before_v, before_v, before_c, "#123456")])
            h.undo(self.m)
            self.assertEqual(self.m.cell(0, 0).value, 9)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PuzzleTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


# -----------------------------
# 7) main
# -----------------------------


def main(argv: List[str]) -> int:
    if "--test" in argv:
        return _run_tests()

    model = PuzzleModel(GRID_SIZE, DEFAULT_GIVENS)
    app = PuzzleGUI(model)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))