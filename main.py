"""
Modern Windows 11 Fluent Dark UI Application for Facebook Prospect Tracker
Features:
- Windows 11 Acrylic / Mica inspired dark style
- Launch Chrome with CDP Remote Debugging (--remote-debugging-port=9222)
- Auto-discovery and Refresh of active Chrome tabs
- Interactive Selection:
    * Multiple Prospect Sheets Tabs (Checkboxes / Multi-select list)
    * Messenger Tab (Radio / Dropdown with smart auto-detection)
    * Master Tracking Sheet Tab (Radio / Dropdown with smart auto-detection)
- Real-time Console Log with color badges
- Progress Bar with Percentage and Stage notifications
- Statistics Summary Cards
- One-click Start / Stop / Reset controls
"""

import sys
import os
import subprocess
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QProgressBar, QTextEdit, QFrame, QSplitter, QCheckBox,
    QGroupBox, QMessageBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCursor

from cdp_engine import get_tabs
from tracker_worker import TrackerWorker

STYLE_SHEET = """
QMainWindow {
    background-color: #0d1117;
}

QWidget {
    color: #e6edf3;
    font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 13px;
}

/* Header & Card Containers */
.CardFrame {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px;
}

.CardHeader {
    font-size: 14px;
    font-weight: 600;
    color: #58a6ff;
    padding-bottom: 6px;
    border-bottom: 1px solid #21262d;
}

/* Modern PushButtons */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #363b42;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
    color: #f0f6fc;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton#PrimaryBtn {
    background-color: #238636;
    border-color: #2ea043;
    color: #ffffff;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 24px;
}

QPushButton#PrimaryBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QPushButton#PrimaryBtn:disabled {
    background-color: #21262d;
    border-color: #30363d;
    color: #484f58;
}

QPushButton#LaunchChromeBtn {
    background-color: #1f6feb;
    border-color: #388bfd;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#LaunchChromeBtn:hover {
    background-color: #388bfd;
}

/* ComboBox */
QComboBox {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e6edf3;
}

QComboBox:hover {
    border-color: #58a6ff;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid #30363d;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    padding: 4px;
}

/* ListWidget for Multiple Tabs Selection */
QListWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px;
    color: #e6edf3;
}

QListWidget::item {
    padding: 6px;
    border-radius: 4px;
    margin-bottom: 2px;
}

QListWidget::item:hover {
    background-color: #21262d;
}

QListWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

/* Progress Bar */
QProgressBar {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1f6feb, stop:1 #2ea043);
    border-radius: 5px;
}

/* Log Console */
QTextEdit {
    background-color: #090d12;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px;
    color: #7ee787;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 12px;
}

/* Stat Box */
.StatBox {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 8px;
    text-align: center;
}

.StatNumber {
    font-size: 20px;
    font-weight: 700;
    color: #58a6ff;
}

.StatLabel {
    font-size: 11px;
    color: #8b949e;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Facebook DM Prospect Tracker — Windows 11 Professional")
        self.resize(1120, 820)
        self.setMinimumSize(950, 700)
        self.setStyleSheet(STYLE_SHEET)

        self.available_tabs = []
        self.worker = None

        self.init_ui()

        # Initial probe for open Chrome CDP tabs
        QTimer.singleShot(500, self.refresh_tabs)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. Top Bar: Title & Launch Chrome Button
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_label = QLabel("Facebook DM Prospect Tracker")
        title_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #f0f6fc;")
        subtitle_label = QLabel("Automated Daily Messenger Verification & Master Tracking Synchronization via Chrome CDP")
        subtitle_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        title_box.addWidget(title_label)
        title_box.addWidget(subtitle_label)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.launch_chrome_btn = QPushButton("🚀 Launch CDP Chrome (Port 9222)")
        self.launch_chrome_btn.setObjectName("LaunchChromeBtn")
        self.launch_chrome_btn.clicked.connect(self.launch_cdp_chrome)
        top_bar.addWidget(self.launch_chrome_btn)

        self.refresh_btn = QPushButton("🔄 Refresh Tabs")
        self.refresh_btn.clicked.connect(self.refresh_tabs)
        top_bar.addWidget(self.refresh_btn)

        main_layout.addLayout(top_bar)

        # 2. Main Content Splitter (Left: Controls & Tab Selectors, Right: Execution & Logs)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL: TAB SELECTIONS
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(12)

        # Group 1: Prospect Lists / Sheets (Multiple Selection Allowed!)
        prospect_card = QFrame()
        prospect_card.setProperty("class", "CardFrame")
        p_card_layout = QVBoxLayout(prospect_card)
        p_card_layout.setSpacing(8)

        p_header_layout = QHBoxLayout()
        p_title = QLabel("1. Select Prospect Leads Sheet(s)")
        p_title.setStyleSheet("font-weight: 600; color: #58a6ff; font-size: 14px;")
        p_header_layout.addWidget(p_title)
        p_header_layout.addStretch()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.select_all_btn.clicked.connect(self.select_all_prospects)
        p_header_layout.addWidget(self.select_all_btn)

        self.clear_sel_btn = QPushButton("Clear")
        self.clear_sel_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.clear_sel_btn.clicked.connect(self.clear_prospect_selection)
        p_header_layout.addWidget(self.clear_sel_btn)

        p_card_layout.addLayout(p_header_layout)

        p_hint = QLabel("Select one or more Google Sheets tabs containing today's prospects:")
        p_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        p_card_layout.addWidget(p_hint)

        self.prospect_list_widget = QListWidget()
        self.prospect_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        p_card_layout.addWidget(self.prospect_list_widget)

        left_layout.addWidget(prospect_card, stretch=4)

        # Group 2: Facebook Messenger Tab Selection
        messenger_card = QFrame()
        messenger_card.setProperty("class", "CardFrame")
        m_card_layout = QVBoxLayout(messenger_card)
        m_card_layout.setSpacing(6)

        m_title = QLabel("2. Select Facebook Messenger Tab")
        m_title.setStyleSheet("font-weight: 600; color: #58a6ff; font-size: 14px;")
        m_card_layout.addWidget(m_title)

        m_hint = QLabel("The open Messenger tab where prospect chats are loaded:")
        m_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        m_card_layout.addWidget(m_hint)

        self.messenger_combo = QComboBox()
        m_card_layout.addWidget(self.messenger_combo)
        left_layout.addWidget(messenger_card, stretch=2)

        # Group 3: Master Tracking Sheet Selection
        master_card = QFrame()
        master_card.setProperty("class", "CardFrame")
        master_card_layout = QVBoxLayout(master_card)
        master_card_layout.setSpacing(6)

        master_title = QLabel("3. Select Master Sheet Tab")
        master_title.setStyleSheet("font-weight: 600; color: #58a6ff; font-size: 14px;")
        master_card_layout.addWidget(master_title)

        master_hint = QLabel("Destination Master Sheet (e.g. 'FB Prospect Tracking Sheet'):")
        master_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        master_card_layout.addWidget(master_hint)

        self.master_combo = QComboBox()
        master_card_layout.addWidget(self.master_combo)
        left_layout.addWidget(master_card, stretch=2)

        # Action Buttons Area
        action_layout = QHBoxLayout()
        self.continue_btn = QPushButton("▶ Continue & Start Task")
        self.continue_btn.setObjectName("PrimaryBtn")
        self.continue_btn.clicked.connect(self.start_tracker_task)
        action_layout.addWidget(self.continue_btn)

        self.stop_btn = QPushButton("⏹ Stop Task")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_tracker_task)
        action_layout.addWidget(self.stop_btn)

        left_layout.addLayout(action_layout)

        splitter.addWidget(left_widget)

        # RIGHT PANEL: STATS, PROGRESS & LIVE LOGS
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(12)

        # Stats Cards Row
        stats_frame = QFrame()
        stats_frame.setProperty("class", "CardFrame")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(8)

        self.stat_scanned = self.create_stat_box(stats_layout, "0", "Prospects Checked")
        self.stat_dmd = self.create_stat_box(stats_layout, "0", "DM'd Confirmed")
        self.stat_replied = self.create_stat_box(stats_layout, "0", "Replies (Hot)")
        self.stat_removed = self.create_stat_box(stats_layout, "0", "Removed (No DM)")
        self.stat_appended = self.create_stat_box(stats_layout, "0", "Appended to Master")

        right_layout.addWidget(stats_frame)

        # Progress Section
        progress_card = QFrame()
        progress_card.setProperty("class", "CardFrame")
        p_layout = QVBoxLayout(progress_card)
        p_layout.setSpacing(6)

        p_status_layout = QHBoxLayout()
        self.progress_status_label = QLabel("Status: Ready to configure and start")
        self.progress_status_label.setStyleSheet("font-weight: 500; color: #8b949e;")
        p_status_layout.addWidget(self.progress_status_label)
        p_status_layout.addStretch()

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setStyleSheet("font-weight: 600; color: #58a6ff;")
        p_status_layout.addWidget(self.progress_percent_label)
        p_layout.addLayout(p_status_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        p_layout.addWidget(self.progress_bar)

        right_layout.addWidget(progress_card)

        # Live Console Output
        log_card = QFrame()
        log_card.setProperty("class", "CardFrame")
        l_layout = QVBoxLayout(log_card)
        l_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("Real-time Activity & CDP Console")
        log_title.setStyleSheet("font-weight: 600; color: #c9d1d9;")
        log_header.addWidget(log_title)
        log_header.addStretch()

        clear_log_btn = QPushButton("Clear Console")
        clear_log_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        clear_log_btn.clicked.connect(self.clear_logs)
        log_header.addWidget(clear_log_btn)
        l_layout.addLayout(log_header)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        l_layout.addWidget(self.log_console)

        right_layout.addWidget(log_card, stretch=5)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        main_layout.addWidget(splitter)

    def create_stat_box(self, layout, default_val, label_text):
        box = QFrame()
        box.setStyleSheet("background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 6px;")
        b_layout = QVBoxLayout(box)
        b_layout.setContentsMargins(4, 4, 4, 4)
        b_layout.setSpacing(2)

        num_label = QLabel(default_val)
        num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #58a6ff;")
        b_layout.addWidget(num_label)

        txt_label = QLabel(label_text)
        txt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_label.setStyleSheet("font-size: 10px; color: #8b949e;")
        b_layout.addWidget(txt_label)

        layout.addWidget(box)
        return num_label

    def log(self, message, level="info"):
        timestamp = QTimer().remainingTime() # fallback
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")

        colors = {
            "info": "#7ee787",
            "warning": "#d29922",
            "error": "#f85149",
            "success": "#3fb950"
        }
        color = colors.get(level, "#e6edf3")
        formatted = f'<span style="color: #8b949e;">[{time_str}]</span> <span style="color: {color};">{message}</span>'
        self.log_console.append(formatted)
        self.log_console.moveCursor(QTextCursor.MoveOperation.End)

    def clear_logs(self):
        self.log_console.clear()

    def launch_cdp_chrome(self):
        """
        Launches Google Chrome with Remote Debugging Port 9222 enabled.
        Important: If Chrome is already running without --remote-debugging-port, launching Chrome
        normally just tells the existing Chrome process to open a tab WITHOUT enabling CDP.
        To guarantee CDP starts properly, we use a dedicated user-data-dir or isolate the debugging instance.
        """
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        chosen_path = None
        for p in chrome_paths:
            if os.path.exists(p):
                chosen_path = p
                break

        if not chosen_path:
            QMessageBox.critical(self, "Chrome Not Found", "Could not find chrome.exe in standard installation paths.")
            return

        # Dedicated profile directory so CDP debug port is guaranteed to open even if default Chrome is running
        profile_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ChromeCDPProfile")
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            chosen_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://www.messenger.com",
            "https://docs.google.com/spreadsheets"
        ]

        try:
            self.log(f"Starting Chrome with CDP on port 9222 (profile: {profile_dir})...", "info")
            subprocess.Popen(cmd)
            self.log("Chrome CDP process launched successfully!", "success")
            self.log("Opening Messenger and Google Sheets...", "info")
            # Probe multiple times as Chrome starts up
            QTimer.singleShot(1500, self.refresh_tabs)
            QTimer.singleShot(3500, self.refresh_tabs)
        except Exception as e:
            self.log(f"Failed to launch Chrome: {e}", "error")
            QMessageBox.critical(self, "Launch Error", f"Failed to start Chrome: {e}")

    def refresh_tabs(self):
        self.log("Scanning Chrome CDP endpoint (http://127.0.0.1:9222)...", "info")
        tabs = get_tabs(9222)
        self.available_tabs = [t for t in tabs if t.get("type") == "page"]

        self.prospect_list_widget.clear()
        self.messenger_combo.clear()
        self.master_combo.clear()

        if not self.available_tabs:
            self.log("No active Chrome tabs detected. Ensure Chrome is running with port 9222.", "warning")
            self.progress_status_label.setText("Status: CDP Chrome not connected (click 'Launch CDP Chrome')")
            return

        self.log(f"Found {len(self.available_tabs)} active Chrome tab(s).", "success")
        self.progress_status_label.setText(f"Connected: {len(self.available_tabs)} tabs available")

        # Populate Prospect Lists (Multi-select)
        default_messenger_idx = 0
        default_master_idx = 0

        for idx, tab in enumerate(self.available_tabs):
            title = tab.get("title", "Untitled")
            url = tab.get("url", "")
            display_text = f"{title[:50]} ({url[:35]}...)" if len(url) > 35 else f"{title[:50]}"

            # Add to prospect list
            item = QListWidgetItem(f"📄 {display_text}")
            item.setData(Qt.ItemDataRole.UserRole, tab)
            self.prospect_list_widget.addItem(item)

            # Auto-check if matches daily prospect patterns
            if "prospect" in title.lower() or "oct" in title.lower() or "nov" in title.lower() or "sheet" in title.lower():
                item.setSelected(True)

            # Add to dropdowns
            self.messenger_combo.addItem(f"💬 {display_text}", tab)
            self.master_combo.addItem(f"📊 {display_text}", tab)

            # Auto-select messenger
            if "messenger" in url.lower() or "facebook.com/messages" in url.lower() or "messenger" in title.lower():
                default_messenger_idx = idx

            # Auto-select master sheet
            if "master" in title.lower() or "tracking" in title.lower():
                default_master_idx = idx

        if self.messenger_combo.count() > default_messenger_idx:
            self.messenger_combo.setCurrentIndex(default_messenger_idx)

        if self.master_combo.count() > default_master_idx:
            self.master_combo.setCurrentIndex(default_master_idx)

    def select_all_prospects(self):
        for i in range(self.prospect_list_widget.count()):
            self.prospect_list_widget.item(i).setSelected(True)

    def clear_prospect_selection(self):
        self.prospect_list_widget.clearSelection()

    def start_tracker_task(self):
        # 1. Validate Selections
        selected_prospect_items = self.prospect_list_widget.selectedItems()
        if not selected_prospect_items:
            QMessageBox.warning(self, "Selection Required", "Please select at least one Prospect Google Sheets tab.")
            return

        selected_prospect_tabs = [item.data(Qt.ItemDataRole.UserRole) for item in selected_prospect_items]

        messenger_tab = self.messenger_combo.currentData()
        if not messenger_tab:
            QMessageBox.warning(self, "Selection Required", "Please select the Facebook Messenger tab.")
            return

        master_tab = self.master_combo.currentData()
        if not master_tab:
            QMessageBox.warning(self, "Selection Required", "Please select the Master Tracking Sheet tab.")
            return

        # Disable controls during run
        self.continue_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.launch_chrome_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        # Reset stats
        self.stat_scanned.setText("0")
        self.stat_dmd.setText("0")
        self.stat_replied.setText("0")
        self.stat_removed.setText("0")
        self.stat_appended.setText("0")
        self.progress_bar.setValue(0)
        self.progress_percent_label.setText("0%")

        # Start background worker
        self.worker = TrackerWorker(
            messenger_tab=messenger_tab,
            prospect_tabs=selected_prospect_tabs,
            master_tab=master_tab,
            options={}
        )
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def stop_tracker_task(self):
        if self.worker and self.worker.isRunning():
            self.log("Cancelling task, waiting for safe boundary...", "warning")
            self.worker.cancel()
            self.stop_btn.setEnabled(False)

    def update_progress(self, percent, status_text):
        self.progress_bar.setValue(percent)
        self.progress_percent_label.setText(f"{percent}%")
        self.progress_status_label.setText(f"Status: {status_text}")

    def on_worker_finished(self, success, message, stats):
        self.continue_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.launch_chrome_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

        if stats:
            self.stat_scanned.setText(str(stats.get("prospects_scanned", 0)))
            self.stat_dmd.setText(str(stats.get("dmd_count", 0)))
            self.stat_replied.setText(str(stats.get("replied_count", 0)))
            self.stat_removed.setText(str(stats.get("not_dmd_removed", 0)))
            self.stat_appended.setText(str(stats.get("master_appended", 0)))

        if success:
            QMessageBox.information(
                self, "Task Completed",
                f"FB Prospect Tracker completed successfully!\n\n"
                f"• Prospects Audited: {stats.get('prospects_scanned', 0)}\n"
                f"• DM'd Confirmed: {stats.get('dmd_count', 0)}\n"
                f"• Hot Follow-Ups: {stats.get('replied_count', 0)}\n"
                f"• Removed from daily sheet: {stats.get('not_dmd_removed', 0)}\n"
                f"• Appended to Master Sheet: {stats.get('master_appended', 0)}\n\n"
                f"'done' has been copied to your clipboard."
            )
        else:
            QMessageBox.critical(self, "Task Stopped or Failed", f"Execution finished with message:\n{message}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
