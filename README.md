
# RocketReviewer (hand reviews using RocketSolver)

This is fully vibe-coded, so if you do not like AI-SLOB, this is not for you ..

An automated poker hand history review suite and interactive replayer with live **RocketSolver** GTO verification.

Supports importing hand histories from **888poker**, **CoinPoker**, and **GGPoker**,  stepping action-by-action through solver trees, and highlighting tactical mistakes in a modern web dashboard.

I have only tested 6max tables cashgames..

##how to use
1. Install Rocketreviewer
2. Start rocketsolver and load the solution you want to use.
3. Start Rocketreviewer
4. Open browser to http://localhost:8085
5. Import hands
6. Filter hands that you want to check ..fex. pot over $2
7. Press "run rocketsolver check" and let it run until finished
8. Select review tab and go through the reviewed hands


---



## Requirements

- **Operating System**: Windows 10 or Windows 11 (required for Win32 API window automation and RocketSolver).
- **Python**: Python 3.10+ (tested on Python 3.13).
- **Dependencies**: Listed in `requirements.txt` (`Pillow` for screen grid analysis, `uiautomation` for Windows UI automation).
- **RocketSolver**: (Optional for live solver stepping) `RocketSolver.exe` running with solutions loaded.

---

## Installation

### 1. Clone or Open the Repository
Ensure you are in the project folder:
```powershell
cd C:\misc\code\appautomation
```

### 2. Install Python Dependencies
Install all required dependencies (`Pillow`, `uiautomation`) using `requirements.txt`:
```powershell
py -m pip install -r requirements.txt
```

*(Optional: If you use a virtual environment, activate it before installing).*



## Usage Guide

### 1. Start the Web Server

Launch the web application from PowerShell or Command Prompt:

```powershell
py web/server.py 8085
```

You can specify any custom port as the first argument (defaults to `8085`).

### 2. Open the Web Dashboard

Open your web browser and navigate to:
```
http://localhost:8085
```

### 3. Importing Hand Histories

There are three ways to load hands:

1. **Paste Hand History**:
   - Click the **"Import Hands"** button in the top navigation.
   - Paste raw text from 888poker, CoinPoker, or GGPoker.
   - Click **"Import & Convert"**. The hands are parsed, saved to `converted_hands/`, and added to your session.
2. **Auto-Load Converted Hands**:
   - Hands saved in `converted_hands/` are automatically loaded on server startup.
   - Click **"Reload from Disk"** anytime to sync newly placed files.
3. **Load Sample Hands**:
   - Click **"Load Samples"** to populate the replayer with test hands from the test suite.

---

### 4. Reviewing Hands Against RocketSolver

#### Live Solver Review (Recommended)
1. Launch **RocketSolver.exe** and open your solution tree.
2. Ensure the solver window is in the **Strategy** tab.
3. In the web dashboard:
   - Select any hand from the left sidebar.
   - Click **"Step Hand in RocketSolver"** to watch RocketSolver step through the actions in real time and sample strategy percentages directly from the screen.
   - Or click **"Run Solver Check"** to batch-analyze filtered hands in the background.
4. When the check finishes:
   - The strategy window in RocketSolver automatically resets back to the start stage (Root).
   - Any deviations from GTO appear in the **"RocketSolver GTO Analysis"** panel on the right.

#### Offline / Rule-Based Check
If RocketSolver is not running, the application automatically uses built-in 6-max GTO opening charts and made-hand defense rules to flag preflop blunders and exploitative folds.

---

### 5. Understanding GTO Review Cards

When a hand deviates from GTO, an issue card is generated:

- **Preflop Fold Mistakes**:
  - If Hero raised or called with a hand that has $100\%$ Fold frequency in the solver (e.g. K7o from BU), it is marked as a **Hand-Ending Mistake**.
  - The check terminates on Preflop so that subsequent streets do not generate confusing duplicate errors.
- **Postflop Fold Mistakes**:
  - If Hero calls or raises when the solver mandates a Fold, the check ends on that street.
- **Sizing & Action Deviations**:
  - If Hero makes a non-fatal mistake (e.g. wrong raise size, or checking when betting is favored) while the hand remains in range, solving continues across later streets.
- **Out of Range Hands**:
  - If a hand reaches a node where it has $0\%$ presence in the active range window, the check concludes without false warnings.

---


## License & Credits

Built for poker study and strategy review, integrating with **RocketSolver** and featuring self-contained hand parsers (`hand_replayer.py`, `generic_hand_format.py`, `poker_888_importer.py`, `extract_gg_river_hands.py`) directly within the project.

### Third-Party Dependencies & Libraries

| Dependency | License | Purpose |
| :--- | :--- | :--- |
| **[Pillow (PIL)](https://python-pillow.org/)** | HPND / Historical Permission Notice | Screen capture processing, color classification, and 13×13 solver grid pixel analysis. |
| **[uiautomation](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows)** | Apache License 2.0 | Windows UI Automation driver for interacting with desktop application controls. |
| **[comtypes](https://github.com/enthought/comtypes)** | MIT License | Pure-Python COM client library underlying Windows UI Automation. |
| **[Tailwind CSS](https://tailwindcss.com/)** | MIT License | Utility-first styling framework used by the modern web replayer dashboard. |
| **[Font Awesome](https://fontawesome.com/)** | CC BY 4.0 / SIL OFL 1.1 / MIT | Iconography across table cards, chips, badges, and action buttons. |

### Integrations

- **[RocketSolver](https://rocketsolver.com/)**: GTO poker solving engine used for live strategy tree stepping and solution validation.
- **rangegame**: Base hand models and serialization format structure adapted from the local range study suite.