# Facebook DM Prospect Tracker — Windows 11 Desktop Application

A modern Windows 11 desktop application (`.exe`) designed to automate the reconciliation of daily Facebook prospect lead lists against Messenger outreach and sync confirmed leads into a Master Tracking Sheet.

Built with **Python**, **PyQt6 (Windows 11 Fluent Dark Theme)**, and **Chrome DevTools Protocol (CDP)**.

---

## ✨ Features

- **Windows 11 Fluent Dark Design**: Custom dark acrylic UI with real-time colored CDP console logs, animated progress indicators, and statistics summary cards.
- **Dedicated CDP Chrome Launcher**:
  - One-click **"🚀 Launch CDP Chrome"** button starts a clean Chrome instance with `--remote-debugging-port=9222` and isolated profile so it reliably enables CDP even if regular Chrome windows are already open.
- **Dynamic Tab Selection (No Hardcoding)**:
  - **Multiple Prospect Sheet Tabs**: Select 1 or more daily prospect sheets (e.g. "OCT 27 FB PROSPECTS") with multi-select checkboxes or "Select All".
  - **Messenger Tab Selector**: Dropdown with automatic smart detection for your active Facebook Messenger chat tab.
  - **Master Sheet Selector**: Dropdown to choose the destination Master Tracking Sheet ("FB Prospect Tracking Sheet").
  - **Refresh Tabs Button**: Detects tabs on the fly whenever new sheets or windows are opened.
- **Automated Technical Playbook**:
  - **Messenger Audit**: Inspects message history, notes replies verbatim, identifies affirmative replies (`"Yes"`, `"DFW"`, etc.).
  - **Classification**:
    - Confirmed reply $\rightarrow$ `Hot - Follow Up`
    - DM'd without reply $\rightarrow$ `Pending`
    - Follower priority $\ge 100 \rightarrow$ `High`, $10\text{–}99 \rightarrow$ `Medium`, $<10 \rightarrow$ `Low`
  - **Daily Sheet Cleanup**: Automatically removes rows of prospects who were not DM'd.
  - **Master Sheet Append**: Writes DM'd records into the master sheet following columns `A` through `L` (`Initial Contact Date`, `Status`, `Priority`, `Owner`, `Company`, `Social Link`, `Website`, `Email`, `Phone`, `Notes`).
  - **Formula-Bar Verified Editing**: Uses verified formula-bar focusing and commit keys to avoid Google Sheets corruption.
  - **Clipboard Integration**: Copies `done` to clipboard upon completion.

---

## 🚀 Getting Started

### Option 1: Run the Precompiled Windows Executable
Download or launch directly:
- **`dist/FBProspectTracker_Standalone.exe`** (Single-file portable executable)
- Or **`dist/FBProspectTracker/FBProspectTracker.exe`**

### Option 2: Run from Source
```powershell
pip install PyQt6 requests websockets
python main.py
```

### Option 3: Compile to .exe yourself
```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "FBProspectTracker_Standalone" main.py
```

---

## 📋 Technical Playbook Rules Followed
- **Messenger is the source of truth.**
- Follower count rules applied for lead prioritization.
- Safety checks before cell writing and row deletion.
- Automated clipboard write: `Set-Clipboard -Value "done"`.
