# Red-Blue Nim — GUI (Tkinter) + Reports

## Run
```bash
python3 red_blue_nim_gui.py
```

## Features
- Standard / Misère variants
- Human vs Human, Human vs AI, AI vs AI
- Optimal AI (memoized DP)
- Transcript display
- **Generate Report** → Markdown + PDF + three charts (saved next to the script)

## How to use
1. Pick **Variant**, **Mode**, first player (if HA), and initial marbles.
2. Click **Start Game**.
3. If it's the human’s turn, select pile (R/B) and take (1/2) then **Play Human Move**.
4. If it's the AI’s turn, press **Play AI Move** (or use **Auto-Play to End**).
5. When the game ends, click **Generate Report (MD + PDF)** to save files next to `red_blue_nim_gui.py`.
