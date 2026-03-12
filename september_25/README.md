# Jane Street Monthly Puzzle — Hooks 11 (September 2025)

This folder contains my solution artifacts for Jane Street’s [Hooks 11 puzzle](https://www.janestreet.com/puzzles/hooks-11-index/) from September 2025.

## Contents

- `hooks11_editor_gui.py` — Python GUI used for grid editing, cell marking, and state management
- `hooks11_solution_state.json` — final solved state saved from the GUI
- `README.md` — short notes on the solution process
- `final_grid.PNG` — screenshot of the final solved grid

## Approach

The solution process had four main steps:

1. Build a small Python GUI to work with the puzzle grid more efficiently than by hand.

2. Use the GUI to test partial configurations, mark progress, and save intermediate states during the solve.

3. Solve straightforward parts directly and use interactive exploration to resolve the remaining placements.

4. Verify that the final configuration is internally consistent and record the resulting answer.

## Result

Final answer: **1620**

![Final Grid](final_grid.PNG)


