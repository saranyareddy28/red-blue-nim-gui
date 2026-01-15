#!/usr/bin/env python3
"""
Red-Blue Nim — Tkinter GUI + Markdown/PDF Reports (with charts)
---------------------------------------------------------------
- Two piles (Red, Blue). On each turn remove 1 or 2 from ONE pile.
- Variant 'standard': move that empties ANY pile => mover WINS
- Variant 'misere'  : move that empties ANY pile => mover LOSES
- Modes: Human vs Human, Human vs AI, AI vs AI
- Optimal AI via memoized win/lose DP
- GUI: start parameters, play controls, transcript
- Reports: Markdown + PDF saved next to the script
  - PDF generated via matplotlib.backends.backend_pdf.PdfPages
  - Charts (matplotlib):
      * Red marbles over moves
      * Blue marbles over moves
      * Move count per player (bar chart)

Run:
  python3 red_blue_nim_gui.py
"""

from __future__ import annotations
import os
import sys
import datetime
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# Tkinter
import tkinter as tk
from tkinter import ttk, messagebox

# Charts / PDF
import matplotlib
matplotlib.use("Agg")  # headless for file export
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# -----------------------------
# Core game logic
# -----------------------------

@dataclass(frozen=True)
class State:
    red: int
    blue: int

@dataclass
class Move:
    pile: str   # "R" or "B"
    take: int   # 1 or 2

class Rules:
    def __init__(self, variant: str):
        v = variant.strip().lower()
        if v not in ("standard", "misere"):
            raise ValueError("variant must be 'standard' or 'misere'")
        self.variant = v

    def legal_moves(self, s: State) -> List[Move]:
        moves: List[Move] = []
        if s.red > 0:
            if s.red >= 1: moves.append(Move("R", 1))
            if s.red >= 2: moves.append(Move("R", 2))
        if s.blue > 0:
            if s.blue >= 1: moves.append(Move("B", 1))
            if s.blue >= 2: moves.append(Move("B", 2))
        return moves

    def apply(self, s: State, m: Move) -> State:
        if m.pile == "R":
            if m.take not in (1,2) or s.red < m.take:
                raise ValueError("Illegal move on red pile")
            return State(s.red - m.take, s.blue)
        else:
            if m.take not in (1,2) or s.blue < m.take:
                raise ValueError("Illegal move on blue pile")
            return State(s.red, s.blue - m.take)

    def ends_immediately(self, s_after: State) -> bool:
        return s_after.red == 0 or s_after.blue == 0

    def terminal_value_from_mover(self) -> bool:
        # STANDARD -> mover wins.  MISERE -> mover loses.
        return True if self.variant == "standard" else False

    def terminal_value_from_next(self) -> bool:
        # Start-of-turn interpretation if a pile is 0 at start:
        # STANDARD: current loses; MISERE: current wins
        return False if self.variant == "standard" else True

class Solver:
    def __init__(self, rules: Rules):
        self.rules = rules
        self.memo: Dict[Tuple[int,int], bool] = {}

    def is_winning(self, s: State) -> bool:
        if s.red == 0 or s.blue == 0:
            return self.rules.terminal_value_from_next()

        key = (s.red, s.blue)
        if key in self.memo:
            return self.memo[key]

        for mv in self.rules.legal_moves(s):
            s2 = self.rules.apply(s, mv)
            if self.rules.ends_immediately(s2):
                result = self.rules.terminal_value_from_mover()
            else:
                result = not self.is_winning(s2)
            if result:
                self.memo[key] = True
                return True

        self.memo[key] = False
        return False

    def best_move(self, s: State) -> Move:
        legal = self.rules.legal_moves(s)
        # Prefer winning moves; tie-breaker: take 2 over 1, prefer Red over Blue
        for take in (2,1):
            for pile in ("R","B"):
                cand = Move(pile, take)
                if cand not in legal: continue
                s2 = self.rules.apply(s, cand)
                if self.rules.ends_immediately(s2):
                    if self.rules.terminal_value_from_mover():
                        return cand
                    else:
                        continue
                if not self.is_winning(s2):
                    return cand
        # No winning move; pick a legal move with same tie-breaker
        for take in (2,1):
            for pile in ("R","B"):
                cand = Move(pile, take)
                if cand in legal:
                    return cand
        raise RuntimeError("No legal moves (game should be over)")


# -----------------------------
# Transcript
# -----------------------------

@dataclass
class TranscriptEntry:
    player: str
    move: Move
    before: State
    after: State
    ended: bool
    mover_wins_if_end: Optional[bool]

# -----------------------------
# GUI Application
# -----------------------------

class NimApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Red-Blue Nim — GUI")
        self.root.geometry("880x620")

        # Session state
        self.rules: Optional[Rules] = None
        self.solver: Optional[Solver] = None
        self.current_state: Optional[State] = None
        self.transcript: List[TranscriptEntry] = []
        self.turn = 0  # 0 or 1
        self.player_types = ["human", "ai"]  # p1, p2

        # Layout
        self.build_ui()

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        # Header with Name + Date
        header = ttk.Frame(frm)
        header.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,10))
        ttk.Label(header, text="Name:", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Saranya Reddy Pulicherla").grid(row=0, column=1, sticky="w", padx=(6,24))
        ttk.Label(header, text="Date:", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, sticky="w")
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(header, textvariable=self.date_var, width=14).grid(row=0, column=3, sticky="w", padx=(6,0))

        # Variant
        ttk.Label(frm, text="Variant:").grid(row=1, column=0, sticky="w")
        self.variant_var = tk.StringVar(value="standard")
        ttk.Combobox(frm, textvariable=self.variant_var, values=["standard","misere"], width=12, state="readonly").grid(row=1, column=1, sticky="w")

        # Mode
        ttk.Label(frm, text="Mode:").grid(row=1, column=2, sticky="w")
        self.mode_var = tk.StringVar(value="ha")
        ttk.Combobox(frm, textvariable=self.mode_var, values=["hh","ha","aa"], width=8, state="readonly").grid(row=1, column=3, sticky="w")

        # Who first (for HA)
        ttk.Label(frm, text="First (HA only):").grid(row=2, column=0, sticky="w")
        self.first_var = tk.StringVar(value="human")
        ttk.Combobox(frm, textvariable=self.first_var, values=["human","ai"], width=12, state="readonly").grid(row=2, column=1, sticky="w")

        # Piles
        ttk.Label(frm, text="Red marbles:").grid(row=3, column=0, sticky="w")
        self.red_var = tk.StringVar(value="7")
        ttk.Entry(frm, textvariable=self.red_var, width=10).grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="Blue marbles:").grid(row=3, column=2, sticky="w")
        self.blue_var = tk.StringVar(value="7")
        ttk.Entry(frm, textvariable=self.blue_var, width=10).grid(row=3, column=3, sticky="w")

        # Human move controls
        sep = ttk.Separator(frm, orient="horizontal")
        sep.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8,8))

        ttk.Label(frm, text="Human Move:").grid(row=5, column=0, sticky="w")
        self.pile_var = tk.StringVar(value="R")
        ttk.Combobox(frm, textvariable=self.pile_var, values=["R","B"], state="readonly", width=6).grid(row=5, column=1, sticky="w")
        ttk.Label(frm, text="Take:").grid(row=5, column=2, sticky="w")
        self.take_var = tk.StringVar(value="1")
        ttk.Combobox(frm, textvariable=self.take_var, values=["1","2"], state="readonly", width=6).grid(row=5, column=3, sticky="w")

        # Buttons
        self.btn_start = ttk.Button(frm, text="Start Game", command=self.on_start)
        self.btn_start.grid(row=6, column=0, pady=6, sticky="w")

        self.btn_human_move = ttk.Button(frm, text="Play Human Move", command=self.on_human_move, state="disabled")
        self.btn_human_move.grid(row=6, column=1, pady=6, sticky="w")

        self.btn_ai_move = ttk.Button(frm, text="Play AI Move", command=self.on_ai_move, state="disabled")
        self.btn_ai_move.grid(row=6, column=2, pady=6, sticky="w")

        self.btn_auto = ttk.Button(frm, text="Auto-Play to End", command=self.on_autoplay, state="disabled")
        self.btn_auto.grid(row=6, column=3, pady=6, sticky="w")

        # Compare (instructional checkbox area placeholder)
        ttk.Label(frm, text="Select algorithms to compare:").grid(row=7, column=0, sticky="w", pady=(10,0))
        checks = ttk.Frame(frm)
        checks.grid(row=8, column=0, columnspan=4, sticky="ew")
        ttk.Label(checks, text="(N/A for Nim — placeholder to match assignment style)").pack(anchor="w")

        # Output
        ttk.Label(frm, text="Output:").grid(row=10, column=0, sticky="w", pady=(10,0))
        self.txt = tk.Text(frm, height=12, wrap="word")
        self.txt.grid(row=11, column=0, columnspan=4, sticky="nsew")
        frm.rowconfigure(11, weight=1)
        for c in range(4):
            frm.columnconfigure(c, weight=1)

        # Report
        self.btn_report = ttk.Button(frm, text="Generate Report (MD + PDF)", command=self.on_report, state="disabled")
        self.btn_report.grid(row=12, column=0, pady=8, sticky="w")

    # -----------------------------
    # Game lifecycle
    # -----------------------------

    def on_start(self):
        # Parse inputs
        variant = self.variant_var.get().strip().lower()
        mode = self.mode_var.get().strip().lower()
        first = self.first_var.get().strip().lower()

        try:
            r = int(self.red_var.get().strip())
            b = int(self.blue_var.get().strip())
            assert r >= 1 and b >= 1
        except Exception:
            messagebox.showerror("Error", "Red/Blue marbles must be integers >= 1")
            return

        self.rules = Rules(variant)
        self.solver = Solver(self.rules)
        self.current_state = State(r, b)
        self.transcript = []
        self.turn = 0

        # Player types
        if mode == "hh":
            self.player_types = ["human", "human"]
        elif mode == "ha":
            self.player_types = ["human","ai"] if first == "human" else ["ai","human"]
        else:
            self.player_types = ["ai","ai"]

        self.txt.delete("1.0", "end")
        self.log(f"Started game: variant={variant}, start=(R{r},B{b}), mode={mode}, first={self.player_types[0]}")
        self.update_buttons_after_start()

        # If AI to move first, do it
        if self.player_types[self.turn] == "ai":
            self.on_ai_move()

    def update_buttons_after_start(self):
        self.btn_start.config(state="disabled")
        self.btn_report.config(state="disabled")
        self.btn_human_move.config(state="normal" if self.player_types[self.turn]=="human" else "disabled")
        self.btn_ai_move.config(state="normal" if self.player_types[self.turn]=="ai" else "disabled")
        self.btn_auto.config(state="normal")

    def on_human_move(self):
        if not self.current_state or not self.rules: return
        if self.player_types[self.turn] != "human":
            messagebox.showinfo("Info", "It's not the human's turn.")
            return
        pile = self.pile_var.get().strip().upper()
        take = int(self.take_var.get().strip())
        mv = Move(pile, take)
        legal = self.rules.legal_moves(self.current_state)
        if mv not in legal:
            messagebox.showwarning("Illegal", "That move is not legal.")
            return
        self.apply_move(mv, mover="Human")

    def on_ai_move(self):
        if not self.current_state or not self.rules or not self.solver: return
        if self.player_types[self.turn] != "ai":
            messagebox.showinfo("Info", "It's not the AI's turn.")
            return
        mv = self.solver.best_move(self.current_state)
        self.apply_move(mv, mover="AI")

    def on_autoplay(self):
        # Play to end using the appropriate mover each turn
        safety = 10000
        while safety > 0 and self.current_state and self.rules:
            safety -= 1
            if self.player_types[self.turn] == "human":
                # For auto mode, simulate a simple human by choosing best legal (same as AI)
                mv = self.solver.best_move(self.current_state)
                self.apply_move(mv, mover="Human (auto)")
            else:
                mv = self.solver.best_move(self.current_state)
                self.apply_move(mv, mover="AI (auto)")
            # Stop if game ended (buttons will be disabled)
            if self.btn_start['state'] == "normal":
                break

    def apply_move(self, mv: Move, mover: str):
        assert self.current_state and self.rules
        before = self.current_state
        after = self.rules.apply(before, mv)
        ended = self.rules.ends_immediately(after)
        winner_idx = None

        if ended:
            mover_wins = self.rules.terminal_value_from_mover()
            winner_idx = self.turn if mover_wins else (1 - self.turn)

        # record transcript
        self.transcript.append(TranscriptEntry(
            player=mover,
            move=mv,
            before=before,
            after=after,
            ended=ended,
            mover_wins_if_end=(self.rules.terminal_value_from_mover() if ended else None),
        ))

        self.current_state = after

        # log
        self.log(f"{mover}: take {mv.take} from {'Red' if mv.pile=='R' else 'Blue'} | "
                 f"before=(R{before.red},B{before.blue}) -> after=(R{after.red},B{after.blue})")

        if winner_idx is not None:
            self.log("*** GAME ENDED on this move ***")
            winner_name = "P1" if winner_idx == 0 else "P2"
            self.log(f"Winner: {winner_name}")
            self.finish_game()
            return

        # Next turn
        self.turn = 1 - self.turn

        # Start-of-turn terminal check
        if self.current_state.red == 0 or self.current_state.blue == 0:
            if self.rules.terminal_value_from_next():
                winner_idx = self.turn
            else:
                winner_idx = 1 - self.turn
            self.log("*** GAME ENDED at start of turn ***")
            winner_name = "P1" if winner_idx == 0 else "P2"
            self.log(f"Winner: {winner_name}")
            self.finish_game()
            return

        # Enable correct button for next mover
        self.btn_human_move.config(state="normal" if self.player_types[self.turn]=="human" else "disabled")
        self.btn_ai_move.config(state="normal" if self.player_types[self.turn]=="ai" else "disabled")

    def finish_game(self):
        # Disable move buttons, enable Start + Report
        self.btn_human_move.config(state="disabled")
        self.btn_ai_move.config(state="disabled")
        self.btn_auto.config(state="disabled")
        self.btn_start.config(state="normal")
        self.btn_report.config(state="normal")

    def log(self, msg: str):
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")

    # -----------------------------
    # Reports (Markdown + PDF with charts)
    # -----------------------------

    def on_report(self):
        if not self.transcript:
            messagebox.showinfo("Report", "No moves recorded yet.")
            return

        base_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.join(base_dir, f"nim_report_{ts}")

        md_path = base + ".md"
        pdf_path = base + ".pdf"
        png_red = base + "_red.png"
        png_blue = base + "_blue.png"
        png_moves = base + "_moves.png"

        # Prepare series
        moves_idx = list(range(1, len(self.transcript)+1))
        reds = [t.after.red for t in self.transcript]
        blues = [t.after.blue for t in self.transcript]
        p1_moves = sum(1 for i,_ in enumerate(self.transcript) if i % 2 == 0)
        p2_moves = len(self.transcript) - p1_moves

        # Chart 1: Red marbles over time
        plt.figure()
        plt.plot(moves_idx, reds, marker="o")
        plt.title("Red marbles over moves")
        plt.xlabel("Move #")
        plt.ylabel("Red marbles remaining")
        plt.tight_layout()
        plt.savefig(png_red)
        plt.close()

        # Chart 2: Blue marbles over time
        plt.figure()
        plt.plot(moves_idx, blues, marker="o")
        plt.title("Blue marbles over moves")
        plt.xlabel("Move #")
        plt.ylabel("Blue marbles remaining")
        plt.tight_layout()
        plt.savefig(png_blue)
        plt.close()

        # Chart 3: Move count per player (bar)
        plt.figure()
        plt.bar(["P1","P2"], [p1_moves, p2_moves])
        plt.title("Moves per player")
        plt.xlabel("Player")
        plt.ylabel("Move count")
        plt.tight_layout()
        plt.savefig(png_moves)
        plt.close()

        # Markdown report
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Red-Blue Nim Report\n\n")
            f.write(f"- **Name:** Saranya Reddy Pulicherla\n")
            f.write(f"- **Date:** {self.date_var.get()}\n")
            f.write(f"- **Variant:** {self.rules.variant if self.rules else '?'}\n")
            start_r = self.transcript[0].before.red if self.transcript else 0
            start_b = self.transcript[0].before.blue if self.transcript else 0
            f.write(f"- **Start:** Red={start_r}, Blue={start_b}\n")
            f.write(f"- **Moves played:** {len(self.transcript)}\n\n")

            f.write("## Moves\n\n")
            f.write("No. | Player | Move | Before -> After | Ended\n")
            f.write("---:|:------:|:----:|:---------------:|:----:\n")
            for i, t in enumerate(self.transcript, 1):
                mv = f"take {t.move.take} from {'Red' if t.move.pile=='R' else 'Blue'}"
                bef = f"(R{t.before.red},B{t.before.blue})"
                aft = f"(R{t.after.red},B{t.after.blue})"
                ended = ""
                if t.ended:
                    ended = "mover WINS" if t.mover_wins_if_end else "mover LOSES"
                f.write(f"{i} | {t.player} | {mv} | {bef} → {aft} | {ended}\n")

            f.write("\n## Charts\n\n")
            f.write(f"![Red]({os.path.basename(png_red)})\n\n")
            f.write(f"![Blue]({os.path.basename(png_blue)})\n\n")
            f.write(f"![Moves]({os.path.basename(png_moves)})\n\n")

        # PDF report via PdfPages (each chart on its own page, plus a title page)
        with PdfPages(pdf_path) as pdf:
            # Title page
            plt.figure()
            plt.axis("off")
            lines = [
                "Red-Blue Nim Report",
                "",
                f"Name: Saranya Reddy Pulicherla",
                f"Date: {self.date_var.get()}",
                f"Variant: {self.rules.variant if self.rules else '?'}",
                f"Moves played: {len(self.transcript)}",
            ]
            plt.text(0.1, 0.8, "\n".join(lines), fontsize=14, va="top")
            pdf.savefig()
            plt.close()

            # Red
            img = plt.imread(png_red)
            plt.figure()
            plt.imshow(img)
            plt.axis("off")
            pdf.savefig()
            plt.close()

            # Blue
            img = plt.imread(png_blue)
            plt.figure()
            plt.imshow(img)
            plt.axis("off")
            pdf.savefig()
            plt.close()

            # Moves per player
            img = plt.imread(png_moves)
            plt.figure()
            plt.imshow(img)
            plt.axis("off")
            pdf.savefig()
            plt.close()

        messagebox.showinfo("Report created",
                            f"Markdown: {md_path}\nPDF: {pdf_path}\n\nCharts:\n{png_red}\n{png_blue}\n{png_moves}")

def main():
    root = tk.Tk()
    app = NimApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
