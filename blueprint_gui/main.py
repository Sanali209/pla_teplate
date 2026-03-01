"""
main.py — Blueprint GUI desktop application (PySide2).
Provides 6 panels:
  1. Entity Tables   — per-type artifact tables (Goals, Features, Research, Use Cases, Tasks)
  2. Artifact Viewer — tree + markdown reader + trace path breadcrumbs
  3. Critique        — approve / reject / request change + history
  4. PlantUML Viewer — diagram render via plantuml CLI subprocess
  5. Inbound Editor  — raw data entry, file creation/editing in _blueprint/inbound/
  6. Roadmap         — phase progress table
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import markdown as md_lib
import yaml

from PySide6.QtCore import Qt, QFileSystemWatcher, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QTextBrowser, QLabel, QPlainTextEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem, QScrollArea,
    QMessageBox, QComboBox, QLineEdit, QGroupBox, QFileDialog, QFrame,
)

from fs_reader import BLUEPRINT_ROOT, read_frontmatter, read_body, patch_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_COLORS: dict[str, str] = {
    "APPROVED":    "#40a02b",   # Catppuccin Green
    "REVIEW":      "#df8e1d",   # Catppuccin Yellow
    "NEEDS_FIX":   "#d20f39",   # Catppuccin Red
    "REJECTED":    "#e64553",   # Catppuccin Maroon variant
    "BLOCKED":     "#45475a",   # Surface1 (dark grey)
    "DRAFT":       "#1e3a5f",   # Dark blue tint
    "DONE":        "#1e3a2f",   # Dark green tint
    "ARCHIVED":    "#585b70",   # Overlay0
}

ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "Goals": {
        "prefix": "GL-",
        "dir": BLUEPRINT_ROOT / "dev_docs" / "brain",
        "columns": ["id", "title", "status", "kpi", "owner"],
    },
    "Features": {
        "prefix": "FT-",
        "dir": BLUEPRINT_ROOT / "dev_docs" / "logic",
        "columns": ["id", "title", "status", "priority", "parent_goal"],
    },
    "Research": {
        "prefix": "RS-",
        "dir": BLUEPRINT_ROOT / "dev_docs" / "brain" / "R_D_Archive",
        "columns": ["id", "hypothesis", "verdict", "parent_goal"],
    },
    "Use Cases": {
        "prefix": "UC-",
        "dir": BLUEPRINT_ROOT / "dev_docs" / "logic",
        "columns": ["id", "title", "status", "parent_feat", "actors"],
    },
    "Tasks": {
        "prefix": "TSK-",
        "dir": BLUEPRINT_ROOT / "execution" / "backlog",
        "columns": ["id", "title", "status", "assignee", "parent_uc"],
    },
    "Screens": {
        "prefix": "SCR-",
        "dir": BLUEPRINT_ROOT / "dev_docs" / "architecture" / "UI_UX",
        "columns": ["id", "title", "status", "parent_feat"],
    },
}

INBOUND_DIRS: dict[str, Path] = {
    "Briefings":       BLUEPRINT_ROOT / "inbound" / "Briefings",
    "MindMaps":        BLUEPRINT_ROOT / "inbound" / "MindMaps",
    "Wireframes":      BLUEPRINT_ROOT / "inbound" / "Wireframes",
    "Issues_and_Bugs": BLUEPRINT_ROOT / "inbound" / "Issues_and_Bugs",
    "Knowledge_Raw":   BLUEPRINT_ROOT / "inbound" / "Knowledge_Raw",
    "User_Feedback":   BLUEPRINT_ROOT / "inbound" / "User_Feedback",
    "Session_Logs":    BLUEPRINT_ROOT / "execution" / "session_logs",
    # Reverse Engineering inbound
    "Codebase_Scans":  BLUEPRINT_ROOT / "inbound" / "Codebase_Scans",
    "API_Contracts":   BLUEPRINT_ROOT / "inbound" / "API_Contracts",
    "Test_Suites":     BLUEPRINT_ROOT / "inbound" / "Test_Suites",
    "Legacy_Docs":     BLUEPRINT_ROOT / "inbound" / "Legacy_Docs",
    # Brainstorming
    "Brainstorms":     BLUEPRINT_ROOT / "inbound" / "Brainstorms",
}

INBOUND_PROTOCOL_HINT: dict[str, str] = {
    "Briefings":      "Protocol: P0_Ingestion — converts briefs into Goals/Features",
    "MindMaps":       "Protocol: P0_Ingestion — parses mind-map structure",
    "Wireframes":     "Protocol: P2.5_UI_Architecture — extracts Screens (SCR-xxx)",
    "Issues_and_Bugs":"Protocol: P0.5_Bug_Triage — resolves bugs to Tasks or Use Cases",
    "Knowledge_Raw":  "Protocol: P0_Ingestion or H2_Wiki_Update — feeds Knowledge Base",
    "User_Feedback":  "Protocol: R2_User_Critique → R3_Fix — triggers agent fix cycle",
    "Session_Logs":   "Protocol: E1_Sprint_Execution — Agent daily work logs",
    # Reverse Engineering hints
    "Codebase_Scans": "Protocol: RE0_Codebase_Scanner — paste file tree, cloc output, dependency manifests",
    "API_Contracts":  "Protocol: RE2_Feature_Inferencer — OpenAPI YAML/JSON, Postman, gRPC .proto",
    "Test_Suites":    "Protocol: RE3_UseCase_Reconstructor — existing test files reveal intended behavior",
    "Legacy_Docs":    "Protocol: RE2_Feature_Inferencer — README, old PRDs, wiki exports, changelogs",
    # Brainstorming
    "Brainstorms":    "Protocol: P0_Ingestion — BS0 output ready for Goal/Feature extraction",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _scan_artifacts(entity_name: str) -> list[dict[str, Any]]:
    cfg = ENTITY_CONFIG[entity_name]
    prefix = cfg["prefix"]
    folder: Path = cfg["dir"]
    results = []
    if folder.exists():
        for f in sorted(folder.glob("*.md")):
            meta = read_frontmatter(f)
            if str(meta.get("id", "")).startswith(prefix):
                results.append({"path": f, "meta": meta})
    return results


def _color_for_status(status: str) -> QColor:
    hex_color = STATUS_COLORS.get(status, "#2a2a2a")
    return QColor(hex_color)


# ---------------------------------------------------------------------------
# Panel 1: Artifact Workbench (tree + viewer + critique in one pane)
# ---------------------------------------------------------------------------

class ArtifactWorkbenchPanel(QWidget):
    """Combined viewer + critique panel. Tree on left, viewer+critique on right."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(Qt.Horizontal)

        # ── LEFT: artifact tree ───────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 0, 4)
        left_layout.setSpacing(4)

        # Search + pending filter row
        filter_row = QHBoxLayout()
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("🔍 Filter artifacts…")
        search_bar.setStyleSheet(
            "background:#11111b; color:#cdd6f4; border:1px solid #313244;"
            " border-radius:4px; padding:3px 6px;"
        )
        search_bar.textChanged.connect(self._filter_tree)
        self._search_bar = search_bar
        filter_row.addWidget(search_bar, stretch=1)

        self._pending_btn = QPushButton("⚠️")
        self._pending_btn.setToolTip("Show only NEEDS_FIX and REJECTED artifacts")
        self._pending_btn.setCheckable(True)
        self._pending_btn.setFixedWidth(30)
        self._pending_btn.setStyleSheet(
            "QPushButton { background:#3a1a0a; color:#f90; border:1px solid #7a4a00;"
            " border-radius:4px; padding:3px; font-size:11px; }"
            "QPushButton:checked { background:#7a3000; color:#ffa; border-color:#f90; }"
            "QPushButton:hover { background:#5a2a00; }"
        )
        self._pending_btn.toggled.connect(self._on_pending_toggled)
        filter_row.addWidget(self._pending_btn)
        left_layout.addLayout(filter_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Artifacts")
        self._tree.setIndentation(14)
        self._tree.itemClicked.connect(self._on_tree_click)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self._tree)

        # Status summary bar
        self._status_bar_lbl = QLabel("")
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setStyleSheet(
            "color:#6a8a9a; font-size:9px; padding:2px 4px;"
            " background:#11111b; border-top:1px solid #313244;"
        )
        left_layout.addWidget(self._status_bar_lbl)
        main_splitter.addWidget(left)

        # ── RIGHT: viewer (top) + critique (bottom) ───────────────────────────
        right_splitter = QSplitter(Qt.Vertical)

        # ── Viewer section ─────────────────────────────────────────────────
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        viewer_layout.setContentsMargins(4, 4, 4, 0)

        self._trace_label = QLabel("Trace: —")
        self._trace_label.setWordWrap(True)
        self._trace_label.setStyleSheet("color:#a6adc8; font-style:italic; padding:2px 4px;")
        viewer_layout.addWidget(self._trace_label)

        self._content_browser = QTextBrowser()
        self._content_browser.setOpenLinks(False)
        viewer_layout.addWidget(self._content_browser)
        right_splitter.addWidget(viewer_widget)

        # ── Critique section ───────────────────────────────────────────────
        critique_widget = QWidget()
        critique_layout = QVBoxLayout(critique_widget)
        critique_layout.setContentsMargins(4, 0, 4, 4)

        # Info bar
        self._artifact_label = QLabel("Select an artifact from the tree")
        self._artifact_label.setStyleSheet(
            "font-weight:bold; color:#a6adc8; padding:4px;"
            " background:#181825; border-radius:4px;"
        )
        critique_layout.addWidget(self._artifact_label)

        # Feedback + history side by side
        feedback_splitter = QSplitter(Qt.Horizontal)

        # Feedback input
        fb_widget = QWidget()
        fb_layout = QVBoxLayout(fb_widget)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.addWidget(QLabel("Feedback:"))
        self._feedback_input = QPlainTextEdit()
        self._feedback_input.setPlaceholderText("Write your critique or approval notes here…")
        self._feedback_input.setMaximumHeight(90)
        fb_layout.addWidget(self._feedback_input)

        btn_row = QHBoxLayout()
        self._approve_btn = QPushButton("✅ APPROVE")
        self._change_btn  = QPushButton("🔁 REQUEST CHANGE")
        self._reject_btn  = QPushButton("❌ REJECT")
        self._approve_btn.clicked.connect(lambda: self._submit("APPROVED"))
        self._change_btn .clicked.connect(lambda: self._submit("NEEDS_FIX"))
        self._reject_btn .clicked.connect(lambda: self._submit("REJECTED"))
        for btn in (self._approve_btn, self._change_btn, self._reject_btn):
            btn.setStyleSheet(
                "QPushButton { background:#181825; border:1px solid #313244;"
                " color:#a6adc8; border-radius:4px; padding:4px 10px; }"
                "QPushButton:hover { background:#24273a; color:#cdd6f4; }"
            )
            btn_row.addWidget(btn)
        fb_layout.addLayout(btn_row)
        feedback_splitter.addWidget(fb_widget)

        # History
        hist_widget = QWidget()
        hist_layout = QVBoxLayout(hist_widget)
        hist_layout.setContentsMargins(0, 0, 0, 0)
        hist_layout.addWidget(QLabel("Feedback History:"))
        self._history_browser = QTextBrowser()
        hist_layout.addWidget(self._history_browser)
        feedback_splitter.addWidget(hist_widget)
        feedback_splitter.setSizes([500, 400])

        critique_layout.addWidget(feedback_splitter)
        right_splitter.addWidget(critique_widget)
        right_splitter.setSizes([480, 220])

        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([260, 900])
        root_layout.addWidget(main_splitter)

        self._index: dict[str, dict] = {}
        self._current_path: Path | None = None
        self._current_meta: dict = {}
        self._pending_only: bool = False

    # ── Helpers ──────────────────────────────────────────────────────────────

    _STATUS_EMOJI: dict[str, str] = {
        "APPROVED": "✅",
        "DONE":     "✓ ",
        "REVIEW":   "🔍",
        "DRAFT":    "📝",
        "NEEDS_FIX": "🔧",
        "REJECTED": "❌",
        "BLOCKED":  "🚫",
        "ARCHIVED": "📦",
    }

    _ATTENTION_STATUSES = {"NEEDS_FIX", "REJECTED", "BLOCKED"}

    # The preferred display order for status sub-groups
    _STATUS_ORDER = [
        "NEEDS_FIX", "REJECTED", "BLOCKED",  # attention first
        "REVIEW", "DRAFT",                    # in-progress
        "APPROVED", "DONE",                   # completed
        "ARCHIVED",                           # cold storage
    ]

    # ── Refresh / build tree ─────────────────────────────────────────────────

    def refresh(self) -> None:
        self._index = {}
        self._tree.clear()
        total = 0
        status_counts: dict[str, int] = {}

        for entity_name in ENTITY_CONFIG:
            all_entries = _scan_artifacts(entity_name)
            if not all_entries:
                continue

            # Count attention items for header badge
            attention_count = sum(
                1 for e in all_entries
                if str(e["meta"].get("status", "")) in self._ATTENTION_STATUSES
            )
            badge = f"  ⚠️ {attention_count}" if attention_count else ""
            type_item = QTreeWidgetItem([f"{entity_name}{badge}"])
            type_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            type_item.setForeground(0, QColor("#f90" if attention_count else "#a6adc8"))
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsSelectable)

            # Group entries by status
            by_status: dict[str, list] = {}
            for entry in all_entries:
                status = str(entry["meta"].get("status", "DRAFT"))
                by_status.setdefault(status, []).append(entry)
                status_counts[status] = status_counts.get(status, 0) + 1
                total += 1
                self._index[str(entry["meta"].get("id", ""))] = entry

            # Add status sub-groups in defined order
            ordered = sorted(
                by_status.items(),
                key=lambda kv: self._STATUS_ORDER.index(kv[0])
                    if kv[0] in self._STATUS_ORDER else 99
            )
            for status, entries in ordered:
                emoji = self._STATUS_EMOJI.get(status, "")
                status_item = QTreeWidgetItem([f"  {emoji} {status}  ({len(entries)})"])
                status_item.setForeground(0, _color_for_status(status))
                status_item.setFont(0, QFont("Segoe UI", 8, QFont.Bold))
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsSelectable)

                for entry in sorted(entries, key=lambda e: str(e["meta"].get("id", ""))):
                    meta  = entry["meta"]
                    aid   = str(meta.get("id", "?"))
                    title = str(meta.get("title", meta.get("hypothesis", "")))
                    label = f"{aid}  —  {title[:38]}" if title else aid
                    child = QTreeWidgetItem([label])
                    child.setForeground(0, _color_for_status(status))
                    child.setData(0, Qt.UserRole, entry)
                    # Bold attention items
                    if status in self._ATTENTION_STATUSES:
                        f = QFont("Segoe UI", 9)
                        f.setBold(True)
                        child.setFont(0, f)
                    status_item.addChild(child)

                type_item.addChild(status_item)

            self._tree.addTopLevelItem(type_item)

        self._tree.expandAll()
        # Collapse ARCHIVED and DONE by default to reduce noise
        for i in range(self._tree.topLevelItemCount()):
            root = self._tree.topLevelItem(i)
            for j in range(root.childCount()):
                child = root.child(j)
                txt = child.text(0)
                if "ARCHIVED" in txt or "DONE" in txt:
                    child.setExpanded(False)

        # Update status bar
        if total == 0:
            self._status_bar_lbl.setText("No artifacts found.")
        else:
            parts = [f"{cnt} {s}" for s, cnt in sorted(status_counts.items())]
            self._status_bar_lbl.setText(f"{total} artifacts  ·  " + "  ·  ".join(parts))

        # Re-apply pending filter if active
        if self._pending_only:
            self._apply_pending_filter()

    # ── Tree interaction ─────────────────────────────────────────────────────

    def _on_tree_click(self, item: QTreeWidgetItem, _col: int) -> None:
        entry = item.data(0, Qt.UserRole)
        if entry:
            self._load(entry["path"], entry["meta"])

    def _on_pending_toggled(self, checked: bool) -> None:
        self._pending_only = checked
        if checked:
            self._apply_pending_filter()
        else:
            self._filter_tree(self._search_bar.text())

    def _apply_pending_filter(self) -> None:
        """Show only NEEDS_FIX and REJECTED artifact leaves."""
        for i in range(self._tree.topLevelItemCount()):
            type_node = self._tree.topLevelItem(i)
            type_visible = False
            for j in range(type_node.childCount()):
                status_node = type_node.child(j)
                txt = status_node.text(0)
                is_attention = any(s in txt for s in ("NEEDS_FIX", "REJECTED", "BLOCKED"))
                status_node.setHidden(not is_attention)
                if is_attention:
                    status_node.setExpanded(True)
                    type_visible = True
            type_node.setHidden(not type_visible)
            if type_visible:
                type_node.setExpanded(True)

    def _filter_tree(self, text: str) -> None:
        if self._pending_only:
            return
        search = text.lower().strip()
        for i in range(self._tree.topLevelItemCount()):
            type_node = self._tree.topLevelItem(i)
            type_visible = False
            for j in range(type_node.childCount()):
                status_node = type_node.child(j)
                status_visible = False
                status_node.setHidden(False)
                for k in range(status_node.childCount()):
                    leaf = status_node.child(k)
                    match = not search or search in leaf.text(0).lower()
                    leaf.setHidden(not match)
                    if match:
                        status_visible = True
                status_node.setHidden(not status_visible and bool(search))
                if status_visible or not search:
                    type_visible = True
            type_node.setHidden(not type_visible and bool(search))

    def _show_context_menu(self, pos) -> None:
        """Right-click context menu with quick actions."""
        item = self._tree.itemAt(pos)
        if not item:
            return
        entry = item.data(0, Qt.UserRole)
        if not entry:
            return
        meta = entry["meta"]
        aid = str(meta.get("id", ""))
        if not aid:
            return

        from PySide6.QtWidgets import QMenu
        import subprocess, platform
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#181825; color:#cdd6f4; border:1px solid #313244; }"
            "QMenu::item:selected { background:#1e3a5f; }"
        )
        menu.addAction(f"ID: {aid}").setEnabled(False)
        menu.addSeparator()

        def do_quick_action(action_str: str, comment: str = "") -> None:
            self._load(entry["path"], meta)
            self._feedback_input.setPlainText(comment)
            self._submit(action_str)
            self.refresh()

        a_approve = menu.addAction("✅  Approve")
        a_approve.triggered.connect(lambda: do_quick_action("APPROVED", "Quick-approved"))
        a_fix = menu.addAction("🔧  Request Fix")
        a_fix.triggered.connect(lambda: do_quick_action("NEEDS_FIX"))
        a_reject = menu.addAction("❌  Reject (archive signal)")
        a_reject.triggered.connect(lambda: do_quick_action("REJECTED", ""))
        a_archive = menu.addAction("📦  Archive")
        a_archive.triggered.connect(lambda: do_quick_action("ARCHIVED", "Archived via context menu"))
        menu.addSeparator()

        a_copy = menu.addAction("📋  Copy ID")
        def copy_id():
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(aid)
        a_copy.triggered.connect(copy_id)

        a_open = menu.addAction("📂  Open File")
        def open_file():
            path = str(entry["path"])
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path])
            else:
                subprocess.Popen(["xdg-open", path])
        a_open.triggered.connect(open_file)

        menu.exec_(self._tree.viewport().mapToGlobal(pos))

    # ── Load artifact ─────────────────────────────────────────────────────────

    def _load(self, path: Path, meta: dict) -> None:
        self._current_path = path
        self._current_meta = meta

        # Viewer
        body = read_body(path)
        html = md_lib.markdown(body, extensions=["fenced_code", "tables"])
        meta_html = "  ".join(
            f"<span style='color:#a6adc8'>{k}:</span> <b>{v}</b>"
            for k, v in meta.items()
        )
        self._content_browser.setHtml(
            f"<div style='background:#181825;padding:6px 10px;border-radius:4px;"
            f"font-size:11px;margin-bottom:6px'>{meta_html}</div>"
            f"{html}"
        )

        # Trace path
        chain: list[str] = []
        cur = meta
        visited: set[str] = set()
        while True:
            aid = str(cur.get("id", ""))
            if aid in visited:
                break
            visited.add(aid)
            chain.append(aid)
            parent = None
            for key in ("parent_uc", "parent_feat", "parent_goal", "origin"):
                val = cur.get(key)
                if val:
                    parent = str(val)
                    break
            if not parent or parent not in self._index:
                break
            cur = self._index[parent]["meta"]
        self._trace_label.setText("Trace: " + " → ".join(reversed(chain)))

        # Critique
        aid = str(meta.get("id", path.stem))
        status = str(meta.get("status", "?"))
        self._artifact_label.setText(f"  {aid}  │  Status: {status}")
        self._feedback_input.clear()
        self._load_history(aid)

    # ── Critique actions ─────────────────────────────────────────────────────

    def _submit(self, action: str) -> None:
        if not self._current_path:
            QMessageBox.warning(self, "No artifact", "Select an artifact from the tree first.")
            return
        comment = self._feedback_input.toPlainText().strip()
        aid     = str(self._current_meta.get("id", self._current_path.stem))
        fb_path = BLUEPRINT_ROOT / "inbound" / "User_Feedback" / f"FB-{aid}.md"
        ts      = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        fb_path.parent.mkdir(parents=True, exist_ok=True)
        with fb_path.open("a", encoding="utf-8") as f:
            f.write(f"\n---\ntimestamp: {ts}Z\naction: {action}\n---\n\n{comment}\n")
        patch_frontmatter(self._current_path, {"status": action})
        self._artifact_label.setText(f"  {aid}  │  Status: {action}")
        self._feedback_input.clear()
        self._load_history(aid)

    def _load_history(self, artifact_id: str) -> None:
        fb_path = BLUEPRINT_ROOT / "inbound" / "User_Feedback" / f"FB-{artifact_id}.md"
        if fb_path.exists():
            self._history_browser.setPlainText(fb_path.read_text(encoding="utf-8"))
        else:
            self._history_browser.setPlainText("No feedback history yet.")

    def load_artifact(self, path: Path, meta: dict) -> None:
        """External call to load a specific artifact."""
        self._load(path, meta)



# ---------------------------------------------------------------------------
# Panel 2: PlantUML Viewer + Critique
# ---------------------------------------------------------------------------

# Bundled JAR lives in blueprint_gui/ next to main.py
_GUI_DIR  = Path(__file__).parent
_PUML_JAR = _GUI_DIR / "plantuml-1.2026.1.jar"


def _find_java() -> str:
    """Return path to java executable, searching common locations."""
    import shutil as _shutil, os as _os
    j = _shutil.which("java")
    if j:
        return j
    jh = _os.environ.get("JAVA_HOME")
    if jh:
        c = Path(jh) / "bin" / "java.exe"
        if c.exists():
            return str(c)
    for base in (
        Path("C:/Program Files/Eclipse Adoptium"),
        Path("C:/Program Files/Java"),
        Path("C:/Program Files/Microsoft"),
        Path("C:/Program Files/Zulu"),
    ):
        if base.exists():
            for p in sorted(base.iterdir(), reverse=True):
                c = p / "bin" / "java.exe"
                if c.exists():
                    return str(c)
    return "java"


class PlantUMLPanel(QWidget):
    """Panel 2: PlantUML diagram viewer (bundled JAR) + diagram critique."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        main_split = QSplitter(Qt.Horizontal)

        # ── LEFT: file list ───────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 0, 4)
        ll.addWidget(QLabel("UML Diagrams:"))
        self._file_list = QListWidget()
        self._file_list.itemClicked.connect(self._render_diagram)
        ll.addWidget(self._file_list)
        jar_ok  = _PUML_JAR.exists()
        jar_lbl = QLabel(("✅ " if jar_ok else "❌ ") + _PUML_JAR.name)
        jar_lbl.setStyleSheet("color:#a6adc8; font-size:9px;")
        ll.addWidget(jar_lbl)
        main_split.addWidget(left)

        # ── RIGHT: image (top) + critique (bottom) ────────────────────────────
        right_split = QSplitter(Qt.Vertical)

        img_w = QWidget()
        il = QVBoxLayout(img_w)
        il.setContentsMargins(4, 4, 4, 0)
        top_bar = QHBoxLayout()
        self._status_label = QLabel("Select a diagram")
        self._status_label.setStyleSheet("color:#a6adc8;")
        top_bar.addWidget(self._status_label, stretch=1)
        exp_btn = QPushButton("💾 Export PNG…")
        exp_btn.clicked.connect(self._export_png)
        top_bar.addWidget(exp_btn)
        il.addLayout(top_bar)
        self._scroll = QScrollArea()
        self._img_label = QLabel("No diagram rendered.")
        self._img_label.setAlignment(Qt.AlignCenter)
        self._scroll.setWidget(self._img_label)
        self._scroll.setWidgetResizable(True)
        il.addWidget(self._scroll)
        right_split.addWidget(img_w)

        # critique
        crit_w = QWidget()
        cl = QVBoxLayout(crit_w)
        cl.setContentsMargins(4, 2, 4, 4)
        self._diag_label = QLabel("No diagram selected")
        self._diag_label.setStyleSheet(
            "font-weight:bold; color:#a6adc8; background:#181825;"
            " border-radius:4px; padding:4px;"
        )
        cl.addWidget(self._diag_label)
        crit_split = QSplitter(Qt.Horizontal)

        fb_w = QWidget()
        fl = QVBoxLayout(fb_w)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(QLabel("Feedback:"))
        self._feedback_input = QPlainTextEdit()
        self._feedback_input.setPlaceholderText("Describe diagram issues…")
        self._feedback_input.setMaximumHeight(80)
        fl.addWidget(self._feedback_input)
        btn_bar = QHBoxLayout()
        for lbl, act in (("✅ APPROVE", "APPROVED"), ("🔁 REQUEST CHANGE", "NEEDS_FIX")):
            b = QPushButton(lbl)
            b.setStyleSheet(
                "QPushButton{background:#181825;border:1px solid #313244;"
                "color:#a6adc8;border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#24273a;color:#cdd6f4;}"
            )
            b.clicked.connect(lambda checked=False, a=act: self._submit(a))
            btn_bar.addWidget(b)
        fl.addLayout(btn_bar)
        crit_split.addWidget(fb_w)

        hist_w = QWidget()
        hl = QVBoxLayout(hist_w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(QLabel("Feedback History:"))
        self._history_browser = QTextBrowser()
        hl.addWidget(self._history_browser)
        crit_split.addWidget(hist_w)
        crit_split.setSizes([500, 400])
        cl.addWidget(crit_split)
        right_split.addWidget(crit_w)
        right_split.setSizes([560, 190])

        main_split.addWidget(right_split)
        main_split.setSizes([200, 900])
        root.addWidget(main_split)

        self._current_png:    Path | None = None
        self._current_source: Path | None = None
        self._tmp_dir = tempfile.mkdtemp()
        self._java    = _find_java()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._file_list.clear()
        uml_root = BLUEPRINT_ROOT / "dev_docs" / "architecture" / "UML_Models"
        if not uml_root.exists():
            return
        for pf in sorted(uml_root.rglob("*.puml")):
            tag  = "✅" if "Approved" in str(pf) else "📝"
            item = QListWidgetItem(f"{tag} {pf.stem}")
            item.setData(Qt.UserRole, pf)
            self._file_list.addItem(item)
        for mf in sorted(uml_root.rglob("*.md")):
            if mf.exists() and "@startuml" in mf.read_text(encoding="utf-8"):
                tag  = "✅" if "Approved" in str(mf) else "📝"
                item = QListWidgetItem(f"{tag} {mf.stem} (embedded .md)")
                item.setData(Qt.UserRole, mf)
                self._file_list.addItem(item)

    # ── Render ────────────────────────────────────────────────────────────────

    def _render_diagram(self, list_item: QListWidgetItem) -> None:
        orig: Path = list_item.data(Qt.UserRole)
        self._current_source = orig
        self._status_label.setText(f"Rendering {orig.name}…")
        QApplication.processEvents()

        source = self._extract_puml_from_md(orig) if orig.suffix == ".md" else orig
        if source is None:
            self._status_label.setText("No @startuml block found.")
            return

        if not _PUML_JAR.exists():
            self._status_label.setText(f"❌ JAR not found: {_PUML_JAR}")
            return

        out_dir = Path(self._tmp_dir)
        out_png = out_dir / f"{source.stem}.png"

        try:
            res = subprocess.run(
                [self._java, "-jar", str(_PUML_JAR), "-tpng", "-o", str(out_dir), str(source)],
                capture_output=True, timeout=30, text=True,
            )
            if res.returncode != 0:
                err = (res.stderr or res.stdout or "unknown")[:200]
                self._status_label.setText(f"❌ PlantUML: {err}")
                return
        except FileNotFoundError:
            self._status_label.setText(f"❌ Java not found at: {self._java}")
            return
        except subprocess.TimeoutExpired:
            self._status_label.setText("❌ Render timed out.")
            return

        if out_png.exists():
            pix = QPixmap(str(out_png))
            self._img_label.setPixmap(pix)
            self._img_label.resize(pix.size())
            self._current_png = out_png
            tag = "✅ Approved" if "Approved" in str(orig) else "📝 Draft"
            self._status_label.setText(f"{tag}  ·  {orig.stem}")
            self._diag_label.setText(f"  {orig.stem}  │  {tag}")
            self._load_history(orig)
        else:
            self._status_label.setText("❌ Render failed — no PNG produced.")

    def _extract_puml_from_md(self, md: Path) -> Path | None:
        text  = md.read_text(encoding="utf-8")
        start = text.find("@startuml")
        end   = text.find("@enduml")
        if start == -1 or end == -1:
            return None
        tmp = Path(self._tmp_dir) / f"{md.stem}.puml"
        tmp.write_text(text[start: end + len("@enduml")], encoding="utf-8")
        return tmp

    # ── Critique ──────────────────────────────────────────────────────────────

    def _submit(self, action: str) -> None:
        if not self._current_source:
            QMessageBox.warning(self, "No diagram", "Render a diagram first.")
            return
        art_id  = self._current_source.stem
        comment = self._feedback_input.toPlainText().strip()
        fb_path = BLUEPRINT_ROOT / "inbound" / "User_Feedback" / f"FB-{art_id}.md"
        ts      = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        fb_path.parent.mkdir(parents=True, exist_ok=True)
        with fb_path.open("a", encoding="utf-8") as f:
            f.write(f"\n---\ntimestamp: {ts}Z\naction: {action}\n---\n\n{comment}\n")
        if self._current_source.suffix == ".md":
            patch_frontmatter(self._current_source, {"status": action})
        self._diag_label.setText(f"  {art_id}  │  Status: {action}")
        self._feedback_input.clear()
        self._load_history(self._current_source)

    def _load_history(self, source: Path) -> None:
        fb_path = BLUEPRINT_ROOT / "inbound" / "User_Feedback" / f"FB-{source.stem}.md"
        self._history_browser.setPlainText(
            fb_path.read_text(encoding="utf-8") if fb_path.exists() else "No feedback history yet."
        )

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_png(self) -> None:
        if not self._current_png or not self._current_png.exists():
            QMessageBox.warning(self, "No image", "Render a diagram first.")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save PNG", self._current_png.name, "PNG (*.png)")
        if dest:
            import shutil
            shutil.copy(self._current_png, dest)



# ---------------------------------------------------------------------------
# Panel 5: Inbound Editor
# ---------------------------------------------------------------------------

class InboundEditorPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._folder_combo = QComboBox()
        for folder_name in INBOUND_DIRS:
            self._folder_combo.addItem(folder_name)
        self._folder_combo.currentTextChanged.connect(self._load_file_list)
        left_layout.addWidget(self._folder_combo)
        self._file_list = QListWidget()
        self._file_list.itemClicked.connect(self._load_file)
        left_layout.addWidget(self._file_list)
        self._new_btn = QPushButton("+ New File")
        self._new_btn.clicked.connect(self._new_file)
        left_layout.addWidget(self._new_btn)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self._protocol_hint = QLabel("")
        self._protocol_hint.setStyleSheet("color: #a6adc8; font-style: italic; padding: 4px;")
        right_layout.addWidget(self._protocol_hint)
        
        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.hide()
        right_layout.addWidget(self._img_label)
        
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self._editor)
        self._save_btn = QPushButton("💾 Save")
        self._save_btn.clicked.connect(self._save_file)
        right_layout.addWidget(self._save_btn)
        splitter.addWidget(right)
        splitter.setSizes([220, 660])
        layout.addWidget(splitter)

        self._current_file: Path | None = None

    def refresh(self) -> None:
        self._load_file_list(self._folder_combo.currentText())

    def _load_file_list(self, folder_name: str) -> None:
        self._file_list.clear()
        folder = INBOUND_DIRS.get(folder_name)
        if folder and folder.exists():
            for f in sorted(folder.iterdir()):
                if f.is_file():
                    item = QListWidgetItem(f.name)
                    item.setData(Qt.UserRole, f)
                    self._file_list.addItem(item)
        hint = INBOUND_PROTOCOL_HINT.get(folder_name, "")
        self._protocol_hint.setText(hint)

    def _load_file(self, list_item: QListWidgetItem) -> None:
        path: Path = list_item.data(Qt.UserRole)
        self._current_file = path
        
        ext = path.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            pix = QPixmap(str(path))
            pix = pix.scaled(800, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_label.setPixmap(pix)
            self._img_label.show()
            self._editor.hide()
            self._save_btn.hide()
        else:
            self._img_label.hide()
            self._editor.show()
            self._save_btn.show()
            try:
                self._editor.setPlainText(path.read_text(encoding="utf-8"))
            except OSError as e:
                self._editor.setPlainText(f"Error reading file: {e}")

    def _save_file(self) -> None:
        if not self._current_file:
            QMessageBox.warning(self, "No file", "Select or create a file first.")
            return
        self._current_file.write_text(self._editor.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, "Saved", f"Saved: {self._current_file.name}")

    def _new_file(self) -> None:
        folder_name = self._folder_combo.currentText()
        folder = INBOUND_DIRS.get(folder_name)
        if not folder:
            return
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        new_file = folder / f"input_{ts}.md"
        new_file.write_text("", encoding="utf-8")
        self._load_file_list(folder_name)
        # Select the new file
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item.data(Qt.UserRole) == new_file:
                self._file_list.setCurrentItem(item)
                self._load_file(item)
                break


# ---------------------------------------------------------------------------
# Panel 7: Prompts Launcher — improved
# ---------------------------------------------------------------------------

# Group keys match the filter buttons shown in the top bar.
# Each entry: (group, emoji, phase_key, label, short_desc, prompt_file_rel)
PROMPT_PHASES: list[tuple[str, str, str, str, str, str]] = [
    ("generation", "📥", "P0",   "P0 · Ingestion",
     "Parse inbound material into an extract and vector-index knowledge (RAG)",
     "protocols/generation/P0_Ingestion.md"),
    ("generation", "🐛", "P0.5", "P0.5 · Bug Triage",
     "Triage issues, trace root causes, and find anti-patterns via Agentic RAG",
     "protocols/generation/P0_5_Bug_Triage.md"),
    ("generation", "🎯", "P1",   "P1 · Inception",
     "Transform project idea → Goals + Feature Map + Roadmap",
     "protocols/generation/P1_Inception.md"),
    ("generation", "🎯", "P1.5", "P1.5 · Goal Decomposition",
     "Break down high-level Goals into actionable Sub-Goals and initial Features",
     "protocols/generation/P1_5_Goal_Decomposition.md"),
    ("generation", "🔬", "P2",   "P2 · Research",
     "Check RAG for past solutions, then run structural R&D spikes",
     "protocols/generation/P2_Research.md"),
    ("generation", "🎨", "P2.5", "P2.5 · UI Architecture",
     "Extract and design UI Screen artifacts from visual wireframes",
     "protocols/generation/P2_5_UI_Architecture.md"),
    ("generation", "📐", "P3",   "P3 · Analysis",
     "Load AI domain context via RAG, then decompose features → Use Cases",
     "protocols/generation/P3_Analysis.md"),
    ("generation", "🗺", "P3.5", "P3.5 · UML Generator",
     "Generate PlantUML diagrams from approved Use Cases",
     "protocols/generation/P3_5_UML_Generator.md"),
    ("generation", "⚙️", "P4",   "P4 · Dev Sync",
     "Decompose into Tasks + Fuzzing + inject relevant tech skills via RAG",
     "protocols/generation/P4_Dev_Sync.md"),
    ("generation", "📅", "P5",   "P5 · Sprint Planning",
     "Organize selected Tasks into an actionable Sprint board",
     "protocols/generation/P5_Sprint_Planning.md"),
    ("execution",  "⚡", "E1",   "E1 · Sprint Execution",
     "Execute task using RAG-skills, enforce TDD, and index new knowledge",
     "protocols/execution/E1_Sprint_Execution.md"),
    ("review",     "🪞", "R1",   "R1 · Self-Critique",
     "Auto-review an artifact for logic gaps before human review",
     "protocols/review/R1_Agent_Self_Critic.md"),
    ("review",     "🧐", "R1.5", "R1.5 · Code Review",
     "Review code against a dynamically RAG-loaded code-review checklist",
     "protocols/review/R1_5_Code_Review.md"),
    ("review",     "📬", "R2",   "R2 · User Critique",
     "Read rejection reason → fix artifact + resubmit, or archive via S4",
     "protocols/review/R2_User_Critique_Process.md"),
    ("review",     "🔧", "R3",   "R3 · Fix & Refactor",
     "Apply change requests → revised artifact → resubmit",
     "protocols/review/R3_Fix_and_Refactor.md"),
    ("review",     "✅", "R4",   "R4 · UML Validator",
     "Cross-check UML draft against parent UseCase requirements",
     "protocols/review/R4_UML_Validator.md"),
    ("interactive","💡", "BS0",  "BS0 · Brainstorm Session",
     "Facilitate an interactive brainstorm yielding structured problem/value/features",
     "protocols/interactive/BS0_Brainstorm_Session.md"),
    ("interactive","⏸", "S1",   "S1 · Wait For Approval",
     "Pause agent and request human review before continuing",
     "protocols/interactive/S1_Wait_For_Approval.md"),
    ("interactive","⚖️", "S2",   "S2 · Conflict Resolution",
     "Surface contradictions between artifacts for human decision",
     "protocols/interactive/S2_Conflict_Resolution.md"),
    ("interactive","🔄", "S3",   "S3 · Incremental Update",
     "Apply a minor scoped fix without triggering full re-analysis",
     "protocols/interactive/S3_Incremental_Update.md"),
    ("interactive","🗑️", "S4",   "S4 · Rejection Handler",
     "Decide: fix+resubmit (NEEDS_FIX with reason) or archive (REJECTED empty)",
     "protocols/interactive/S4_Rejection_Handler.md"),
    ("knowledge",  "🧠", "H1",   "H1 · Pattern Recognition",
     "Harvest reusable patterns from completed sprint artifacts",
     "protocols/knowledge/H1_Pattern_Recognition.md"),
    ("knowledge",  "📖", "H2",   "H2 · Wiki Update",
     "Sync Terminology.md with new domain terms from recent artifacts",
     "protocols/knowledge/H2_Wiki_Update.md"),
    # ── Reverse Engineering ──
    ("re", "🔍", "RE0",  "RE0 · Codebase Scanner",
     "Scan tech stack, modules, dependencies → tech_profile.md",
     "protocols/reverse/RE0_Codebase_Scanner.md"),
    ("re", "🏗", "RE1",  "RE1 · Architecture Extractor",
     "Extract architecture pattern + PlantUML component diagram + GL-000/FT-000",
     "protocols/reverse/RE1_Architecture_Extractor.md"),
    ("re", "🔬", "RE2",  "RE2 · Feature Inferencer",
     "Infer Goals + Features from API contracts, UI routes, README, legacy docs",
     "protocols/reverse/RE2_Feature_Inferencer.md"),
    ("re", "🗂", "RE3",  "RE3 · Use Case Reconstructor",
     "Rebuild Use Cases from handlers, service methods, validation logic, tests",
     "protocols/reverse/RE3_UseCase_Reconstructor.md"),
    ("re", "🩺", "RE4",  "RE4 · Debt Scanner",
     "Scan TODO/FIXME/skipped tests, detect gaps, create TSK for critical debt",
     "protocols/reverse/RE4_Debt_Scanner.md"),
    ("re", "🔗", "RE5",  "RE5 · RE Hand-off",
     "Validate traceability, generate coverage report, resume standard pipeline",
     "protocols/reverse/RE5_Handoff.md"),
]

# Ordered group definitions for the filter button bar
_PROMPT_GROUPS: list[tuple[str, str]] = [
    ("all",         "🔷 All"),
    ("generation",  "📥 Generation"),
    ("review",      "🔬 Review"),
    ("execution",   "⚡ Execution"),
    ("interactive", "💬 Interactive"),
    ("knowledge",   "🧠 Knowledge"),
    ("re",          "🔍 Reverse"),
]

_RECENT_PATH: Path = BLUEPRINT_ROOT / ".recent_prompts.json"
_MAX_RECENT  = 5


class PromptsPanel(QWidget):
    """
    Panel 7: improved protocol launcher.
    Features: phase-group filter buttons, collapsible context preview,
    Copy+Ctx / Copy Raw dual buttons, file-status badges,
    inline side viewer, compact mode, recently-used ribbon.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 1. Recently-used ribbon ───────────────────────────────────────────
        recent_bar = QWidget()
        recent_bar.setFixedHeight(30)
        recent_bar.setStyleSheet("background:#11111b; border-bottom:1px solid #313244;")
        rl = QHBoxLayout(recent_bar)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(6)
        rl.addWidget(QLabel("<span style='color:#a6adc8;font-size:10px;'>Recent:</span>"))
        self._recent_btns: list[QPushButton] = []
        for _ in range(_MAX_RECENT):
            b = QPushButton()
            b.setFixedHeight(22)
            b.setStyleSheet(
                "QPushButton{background:#24273a;color:#89dceb;border:1px solid #45475a;"
                "border-radius:10px;padding:2px 10px;font-size:10px;}"
                "QPushButton:hover{background:#1e4a6a;color:#cba6f7;}"
            )
            b.hide()
            self._recent_btns.append(b)
            rl.addWidget(b)
        rl.addStretch()
        clear_r = QPushButton("🗑 Clear")
        clear_r.setFixedHeight(22)
        clear_r.setStyleSheet(
            "QPushButton{background:transparent;color:#585b70;border:none;font-size:10px;}"
            "QPushButton:hover{color:#cdd6f4;}"
        )
        clear_r.clicked.connect(self._clear_recent)
        rl.addWidget(clear_r)
        outer.addWidget(recent_bar)

        # ── 2. Top bar: search + group buttons + compact toggle ───────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background:#11111b; border-bottom:1px solid #313244;")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter phases…")
        self._search.setFixedHeight(26)
        self._search.textChanged.connect(self._filter)
        self._search.setStyleSheet(
            "background:#11111b;color:#cdd6f4;border:1px solid #313244;"
            "border-radius:4px;padding:3px 8px;"
        )
        tl.addWidget(self._search, stretch=1)

        self._group_btns: dict[str, QPushButton] = {}
        for key, name in _PROMPT_GROUPS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton{background:#181825;color:#a6adc8;border:1px solid #313244;"
                "border-radius:4px;padding:2px 8px;font-size:10px;}"
                "QPushButton:checked{background:#1e3a5f;color:#89dceb;border-color:#89b4fa;}"
                "QPushButton:hover{color:#cdd6f4;}"
            )
            btn.clicked.connect(lambda checked=False, k=key: self._on_group_changed(k))
            tl.addWidget(btn)
            self._group_btns[key] = btn
        self._group_btns["all"].setChecked(True)
        self._active_group = "all"

        ctx_btn = QPushButton("↻")
        ctx_btn.setToolTip("Refresh context snapshot")
        ctx_btn.setFixedSize(26, 26)
        ctx_btn.clicked.connect(self._build_context)
        tl.addWidget(ctx_btn)

        self._compact_btn = QPushButton("≡ Compact")
        self._compact_btn.setCheckable(True)
        self._compact_btn.setFixedHeight(26)
        self._compact_btn.setStyleSheet(
            "QPushButton{background:#181825;color:#a6adc8;border:1px solid #313244;"
            "border-radius:4px;padding:2px 8px;font-size:10px;}"
            "QPushButton:checked{background:#1e3a5f;color:#89dceb;border-color:#89b4fa;}"
            "QPushButton:hover{color:#cdd6f4;}"
        )
        self._compact_btn.clicked.connect(self._toggle_compact)
        tl.addWidget(self._compact_btn)
        outer.addWidget(top_bar)

        # ── 3. Context snapshot (collapsible) ─────────────────────────────────
        ctx_toggle_bar = QWidget()
        ctx_toggle_bar.setFixedHeight(26)
        ctx_toggle_bar.setStyleSheet("background:#11111b; border-bottom:1px solid #313244;")
        ctl = QHBoxLayout(ctx_toggle_bar)
        ctl.setContentsMargins(8, 2, 8, 2)
        self._ctx_toggle_btn = QPushButton("▼ Context Snapshot")
        self._ctx_toggle_btn.setCheckable(True)
        self._ctx_toggle_btn.setChecked(True)
        self._ctx_toggle_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#a6adc8;border:none;"
            "font-size:10px;text-align:left;padding:4px 0;}"
            "QPushButton:hover{color:#cdd6f4;}"
        )
        self._ctx_toggle_btn.clicked.connect(self._toggle_context)
        ctl.addWidget(self._ctx_toggle_btn)
        ctl.addStretch()
        outer.addWidget(ctx_toggle_bar)

        self._ctx_browser = QTextBrowser()
        self._ctx_browser.setFixedHeight(60)
        self._ctx_browser.setStyleSheet(
            "QTextBrowser{background:#11111b;color:#a6adc8;border:none;"
            "border-bottom:1px solid #313244;padding:4px 12px;font-size:10px;}"
        )
        outer.addWidget(self._ctx_browser)

        # ── 4. Main splitter: card list | inline viewer ───────────────────────
        self._main_splitter = QSplitter(Qt.Horizontal)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea{border:none;}")
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(4)
        self._cards_layout.setContentsMargins(8, 6, 8, 8)
        self._scroll.setWidget(self._cards_container)
        self._main_splitter.addWidget(self._scroll)

        # Inline viewer (hidden until user clicks "👁 View")
        self._viewer_widget = QWidget()
        self._viewer_widget.setMinimumWidth(280)
        vl = QVBoxLayout(self._viewer_widget)
        vl.setContentsMargins(4, 4, 4, 4)
        vtop = QHBoxLayout()
        self._viewer_title = QLabel()
        self._viewer_title.setStyleSheet(
            "color:#89dceb;font-weight:bold;font-size:11px;padding:2px;"
        )
        vtop.addWidget(self._viewer_title, stretch=1)
        close_v = QPushButton("✕ Close")
        close_v.setFixedHeight(22)
        close_v.setStyleSheet(
            "QPushButton{background:#1e1e2e;color:#a6adc8;border:1px solid #313244;"
            "border-radius:4px;padding:1px 8px;font-size:10px;}"
            "QPushButton:hover{color:#cdd6f4;}"
        )
        close_v.clicked.connect(self._close_inline_viewer)
        vtop.addWidget(close_v)
        vl.addLayout(vtop)
        self._viewer_browser = QTextBrowser()
        self._viewer_browser.setStyleSheet(
            "QTextBrowser{background:#11111b;color:#cdd6f4;border:none;}"
        )
        vl.addWidget(self._viewer_browser)
        self._viewer_widget.hide()
        self._main_splitter.addWidget(self._viewer_widget)

        outer.addWidget(self._main_splitter)

        # State
        self._context_snapshot: str = ""
        self._cards: list[dict] = []
        self._compact_mode = False

        self._build_cards()
        self._build_context()
        self._update_recent_ribbon()

    # ── Build cards ───────────────────────────────────────────────────────────

    def _build_cards(self) -> None:
        self._cards = []
        for group, emoji, phase_key, label, desc, rel_path in PROMPT_PHASES:
            card = self._make_card(group, emoji, label, desc, rel_path)
            self._cards.append({
                "widget":   card["frame"],
                "label":    label.lower(),
                "group":    group,
                "desc_lbl": card["desc_lbl"],
            })
            self._cards_layout.addWidget(card["frame"])
        self._cards_layout.addStretch()

    def _make_card(
        self, group: str, emoji: str, label: str, desc: str, rel_path: str
    ) -> dict:
        file_ok = (BLUEPRINT_ROOT / rel_path).exists()

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(
            "QFrame{background:#181825;border:1px solid #313244;"
            "border-radius:6px;padding:2px;}"
            "QFrame:hover{border-color:#89b4fa;}"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(6)

        # Status badge
        dot = QLabel("🟢" if file_ok else "🔴")
        dot.setStyleSheet("font-size:9px;")
        dot.setToolTip(
            "Protocol file found" if file_ok
            else f"File missing: {rel_path}"
        )
        row.addWidget(dot)

        # Left: title + desc
        left = QVBoxLayout()
        left.setSpacing(1)
        title_lbl = QLabel(f"{emoji}  <b>{label}</b>")
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setStyleSheet("color:#cdd6f4;font-size:11px;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color:#a6adc8;font-size:10px;")
        desc_lbl.setWordWrap(True)
        left.addWidget(title_lbl)
        left.addWidget(desc_lbl)
        row.addLayout(left, stretch=1)

        # Right: three buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(3)

        _card_btn_style = (
            "QPushButton{{background:{bg};color:{fg};border:1px solid {bd};"
            "border-radius:4px;padding:2px 6px;font-size:10px;}}"
            "QPushButton:hover{{background:{hbg};color:{hfg};}}"
            "QPushButton:disabled{{color:#4a6a7a;border-color:#1e2a3a;}}"
        )

        copy_ctx_btn = QPushButton("📋 Copy+Ctx")
        copy_ctx_btn.setFixedWidth(112)
        copy_ctx_btn.setFixedHeight(22)
        copy_ctx_btn.setEnabled(file_ok)
        copy_ctx_btn.setToolTip("Copy prompt + project context")
        copy_ctx_btn.setStyleSheet(
            _card_btn_style.format(
                bg="#1e3a5f", fg="#89dceb", bd="#45475a",
                hbg="#1e4a6a", hfg="#cba6f7",
            )
        )
        copy_ctx_btn.clicked.connect(
            lambda checked=False, r=rel_path, lbl=label: self._copy_prompt(r, lbl)
        )

        copy_raw_btn = QPushButton("📄 Copy Raw")
        copy_raw_btn.setFixedWidth(112)
        copy_raw_btn.setFixedHeight(22)
        copy_raw_btn.setEnabled(file_ok)
        copy_raw_btn.setToolTip("Copy prompt only — no context block")
        copy_raw_btn.setStyleSheet(
            _card_btn_style.format(
                bg="#181825", fg="#a6adc8", bd="#313244",
                hbg="#24273a", hfg="#cdd6f4",
            )
        )
        copy_raw_btn.clicked.connect(
            lambda checked=False, r=rel_path, lbl=label: self._copy_raw(r, lbl)
        )

        view_btn = QPushButton("👁 View")
        view_btn.setFixedWidth(112)
        view_btn.setFixedHeight(22)
        view_btn.setEnabled(file_ok)
        view_btn.setToolTip("Preview protocol in side panel")
        view_btn.setStyleSheet(
            _card_btn_style.format(
                bg="#181825", fg="#94e2d5", bd="#313244",
                hbg="#24273a", hfg="#cdd6f4",
            )
        )
        view_btn.clicked.connect(
            lambda checked=False, r=rel_path, lbl=label: self._view_inline(r, lbl)
        )

        btn_col.addWidget(copy_ctx_btn)
        btn_col.addWidget(copy_raw_btn)
        btn_col.addWidget(view_btn)
        row.addLayout(btn_col)

        return {"frame": frame, "desc_lbl": desc_lbl}

    # ── Context snapshot ──────────────────────────────────────────────────────

    def _build_context(self) -> None:
        """Scan artifacts, build context block for injection + update preview widget."""
        lines = ["\n---\n## Current Project Context (auto-injected by Blueprint GUI)\n"]
        display: list[str] = []
        total, pending = 0, 0
        for entity_name in ENTITY_CONFIG:
            arts      = _scan_artifacts(entity_name)
            approved  = sum(1 for a in arts if a["meta"].get("status") == "APPROVED")
            review    = sum(1 for a in arts if a["meta"].get("status") == "REVIEW")
            needs_fix = sum(1 for a in arts if a["meta"].get("status") == "NEEDS_FIX")
            if arts:
                lines.append(
                    f"- **{entity_name}**: {len(arts)} total "
                    f"({approved} approved, {review} in review, {needs_fix} needs_fix)"
                )
                display.append(
                    f"{entity_name}: {len(arts)} total  "
                    f"✅{approved}  🔄{review}  🔧{needs_fix}"
                )
            total   += len(arts)
            pending += review + needs_fix

        lines.append(f"\n**Total artifacts:** {total}  |  **Pending review:** {pending}")
        display.append(f"\nTotal: {total}  |  Pending: {pending}")

        waiting = []
        for entity_name in ENTITY_CONFIG:
            for a in _scan_artifacts(entity_name):
                s = a["meta"].get("status", "")
                if s in ("REVIEW", "NEEDS_FIX"):
                    waiting.append(f"{a['meta'].get('id', '?')} ({s})")
        if waiting:
            lines.append("\n**Awaiting action:** " + ", ".join(waiting))
            display.append("Awaiting: " + ", ".join(waiting))

        self._context_snapshot = "\n".join(lines)
        self._ctx_browser.setPlainText("\n".join(display))

    # ── Copy actions ──────────────────────────────────────────────────────────

    def _copy_prompt(self, rel_path: str, label: str) -> None:
        """Copy protocol text WITH context block appended."""
        proto_path = BLUEPRINT_ROOT / rel_path
        text = (
            proto_path.read_text(encoding="utf-8")
            if proto_path.exists()
            else f"# {label}\n\n[Protocol file not found: {rel_path}]"
        )
        QApplication.clipboard().setText(text + self._context_snapshot)
        self._save_recent(label, rel_path)
        self._show_copied_toast(f"{label}  +ctx")

    def _copy_raw(self, rel_path: str, label: str) -> None:
        """Copy protocol text only — no context block."""
        proto_path = BLUEPRINT_ROOT / rel_path
        text = (
            proto_path.read_text(encoding="utf-8")
            if proto_path.exists()
            else f"# {label}\n\n[Protocol file not found: {rel_path}]"
        )
        QApplication.clipboard().setText(text)
        self._save_recent(label, rel_path)
        self._show_copied_toast(f"{label}  raw")

    # ── Inline viewer ─────────────────────────────────────────────────────────

    def _view_inline(self, rel_path: str, label: str) -> None:
        proto_path = BLUEPRINT_ROOT / rel_path
        self._viewer_title.setText(f"  {label}")
        if proto_path.exists():
            html = md_lib.markdown(
                proto_path.read_text(encoding="utf-8"),
                extensions=["fenced_code", "tables"],
            )
            self._viewer_browser.setHtml(
                "<style>"
                "body{background:#11111b;color:#cdd6f4;font-family:sans-serif;font-size:13px;}"
                "code{background:#1a2a3a;padding:2px 4px;border-radius:3px;font-size:11px;}"
                "pre{background:#1a2a3a;padding:8px;border-radius:4px;}"
                "h1,h2,h3{color:#89dceb;}a{color:#6aacdd;}"
                "</style>" + html
            )
        else:
            self._viewer_browser.setPlainText(f"File not found:\n{proto_path}")
        self._viewer_widget.show()
        # Give viewer ~40% of the splitter width
        total = self._main_splitter.width() or 1200
        self._main_splitter.setSizes([int(total * 0.58), int(total * 0.42)])

    def _close_inline_viewer(self) -> None:
        self._viewer_widget.hide()

    # ── Filtering & grouping ──────────────────────────────────────────────────

    def _on_group_changed(self, key: str) -> None:
        self._active_group = key
        for k, btn in self._group_btns.items():
            btn.setChecked(k == key)
        self._apply_visibility()

    def _filter(self, _text: str = "") -> None:
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        search = self._search.text().lower().strip()
        for card in self._cards:
            group_ok = (self._active_group == "all" or card["group"] == self._active_group)
            text_ok  = (not search or search in card["label"])
            card["widget"].setVisible(group_ok and text_ok)

    # ── Compact mode ──────────────────────────────────────────────────────────

    def _toggle_compact(self, checked: bool) -> None:
        self._compact_mode = checked
        for card in self._cards:
            card["desc_lbl"].setVisible(not checked)

    # ── Context panel toggle ──────────────────────────────────────────────────

    def _toggle_context(self, checked: bool) -> None:
        self._ctx_browser.setVisible(checked)
        self._ctx_toggle_btn.setText(
            "▼ Context Snapshot" if checked else "▶ Context Snapshot"
        )

    # ── Recently used ─────────────────────────────────────────────────────────

    def _load_recent(self) -> list[dict]:
        try:
            if _RECENT_PATH.exists():
                return json.loads(_RECENT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_recent(self, label: str, rel_path: str) -> None:
        recent = self._load_recent()
        recent = [e for e in recent if e.get("rel_path") != rel_path]
        recent.insert(0, {"label": label, "rel_path": rel_path})
        try:
            _RECENT_PATH.write_text(
                json.dumps(recent[:_MAX_RECENT], indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        self._update_recent_ribbon()

    def _clear_recent(self) -> None:
        try:
            if _RECENT_PATH.exists():
                _RECENT_PATH.unlink()
        except Exception:
            pass
        self._update_recent_ribbon()

    def _update_recent_ribbon(self) -> None:
        recent = self._load_recent()
        for i, btn in enumerate(self._recent_btns):
            if i < len(recent):
                entry = recent[i]
                lbl   = entry.get("label", "")
                short = lbl.split("·")[0].strip() if "·" in lbl else lbl[:12]
                btn.setText(short)
                btn.setToolTip(f"Copy: {lbl}")
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                btn.clicked.connect(
                    lambda checked=False, r=entry["rel_path"], l=lbl:
                    self._copy_prompt(r, l)
                )
                btn.show()
            else:
                btn.hide()

    # ── Toast & refresh ───────────────────────────────────────────────────────

    def _show_copied_toast(self, label: str) -> None:
        toast = QLabel(f"  ✅  Copied: {label}  ", self)
        toast.setStyleSheet(
            "background:#1e2d1e;color:#a6e3a1;border:1px solid #40a02b;"
            "border-radius:6px;padding:6px 12px;font-size:11px;"
        )
        toast.adjustSize()
        x = (self.width() - toast.width()) // 2
        y = self.height() - toast.height() - 20
        toast.move(x, y)
        toast.show()
        QTimer.singleShot(1500, toast.deleteLater)

    def refresh(self) -> None:
        self._build_context()
        self._update_recent_ribbon()


# ---------------------------------------------------------------------------
# Panel 6: Roadmap
# ---------------------------------------------------------------------------

class RoadmapPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Entity Type", "Total", "Approved", "Pending", "Progress"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)
        text_group = QGroupBox("roadmap.md")
        text_layout = QVBoxLayout(text_group)
        self._roadmap_text = QTextBrowser()
        text_layout.addWidget(self._roadmap_text)
        layout.addWidget(text_group)

    def refresh(self) -> None:
        rows = []
        for entity_name in ENTITY_CONFIG:
            artifacts = _scan_artifacts(entity_name)
            total = len(artifacts)
            approved = sum(1 for a in artifacts if a["meta"].get("status") == "APPROVED")
            pending = total - approved
            pct = f"{int(approved / total * 100)}%" if total else "—"
            rows.append((entity_name, total, approved, pending, pct))

        self._table.setRowCount(len(rows))
        for row_idx, (name, total, approved, pending, pct) in enumerate(rows):
            for col_idx, val in enumerate([name, str(total), str(approved), str(pending), pct]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col_idx == 2:
                    item.setForeground(QColor("#a6e3a1"))
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()

        roadmap_path = BLUEPRINT_ROOT / "execution" / "roadmap.md"
        if roadmap_path.exists():
            html = md_lib.markdown(roadmap_path.read_text(encoding="utf-8"), extensions=["tables"])
            self._roadmap_text.setHtml(html)
        else:
            self._roadmap_text.setPlainText("roadmap.md not found in _blueprint/execution/")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Blueprint Studio")
        self.resize(1400, 900)
        self.setStyleSheet("""
            /* ── Catppuccin Mocha — Blueprint Studio ── */

            QMainWindow, QWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }

            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #313244;
                background: #1e1e2e;
            }
            QTabBar::tab {
                background: #181825;
                color: #a6adc8;
                padding: 6px 18px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid transparent;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e;
                color: #cba6f7;
                border: 1px solid #313244;
                border-bottom: 2px solid #cba6f7;
            }
            QTabBar::tab:hover:!selected { background: #24273a; color: #cdd6f4; }

            /* Tables */
            QTableWidget {
                gridline-color: #313244;
                background: #1e1e2e;
                alternate-background-color: #181825;
            }
            QHeaderView::section {
                background: #181825;
                color: #89b4fa;
                padding: 5px;
                border: none;
                border-right: 1px solid #313244;
                border-bottom: 1px solid #313244;
                font-weight: bold;
            }

            /* Tree */
            QTreeWidget {
                border: 1px solid #313244;
                background: #11111b;
                show-decoration-selected: 1;
                outline: none;
            }
            QTreeWidget::item:selected {
                background: #313244;
                color: #cba6f7;
            }
            QTreeWidget::item:hover { background: #24273a; }

            /* Lists */
            QListWidget {
                background: #11111b;
                color: #bac2de;
                border: 1px solid #313244;
                outline: none;
            }
            QListWidget::item:selected {
                background: #313244;
                color: #cba6f7;
            }
            QListWidget::item:hover { background: #1e1e2e; }

            /* Text areas */
            QPlainTextEdit, QTextBrowser {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                selection-background-color: #45475a;
                selection-color: #cdd6f4;
            }

            /* Inputs */
            QLineEdit {
                background: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 8px;
                selection-background-color: #45475a;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }

            /* Buttons */
            QPushButton {
                background: #181825;
                color: #a6adc8;
                border: 1px solid #313244;
                padding: 5px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #24273a;
                color: #cdd6f4;
                border-color: #585b70;
            }
            QPushButton:pressed { background: #313244; }
            QPushButton:checked {
                background: #1e3a5f;
                color: #89b4fa;
                border-color: #89b4fa;
            }
            QPushButton:disabled { color: #45475a; border-color: #24273a; }

            /* ComboBox */
            QComboBox {
                background: #181825;
                color: #a6adc8;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QComboBox:focus { border-color: #89b4fa; }
            QComboBox QAbstractItemView {
                background: #181825;
                color: #cdd6f4;
                selection-background-color: #313244;
                selection-color: #cba6f7;
                border: 1px solid #313244;
            }

            /* GroupBox */
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 4px;
                margin-top: 8px;
                color: #a6adc8;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                color: #89b4fa;
            }

            /* Splitter */
            QSplitter::handle {
                background: #313244;
                width: 1px;
                height: 1px;
            }
            QSplitter::handle:hover { background: #585b70; }

            /* Scrollbars */
            QScrollBar:vertical {
                background: #181825;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #585b70; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: #181825;
                height: 10px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background: #45475a;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background: #585b70; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            /* Frames / Cards */
            QFrame { border: none; }
            QScrollArea { border: none; }

            /* Tooltips */
            QToolTip {
                background: #24273a;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)

        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Instantiate panels
        self._workbench = ArtifactWorkbenchPanel()
        self._plantuml = PlantUMLPanel()
        self._inbound_editor = InboundEditorPanel()
        self._roadmap = RoadmapPanel()
        self._prompts = PromptsPanel()

        self._tabs.addTab(self._workbench,       "� Workbench")
        self._tabs.addTab(self._plantuml,        "🗺 UML")
        self._tabs.addTab(self._inbound_editor,  "📥 Inbound")
        self._tabs.addTab(self._roadmap,         "🛣 Roadmap")
        self._tabs.addTab(self._prompts,         "🚀 Prompts")

        # No cross-panel wiring needed — workbench is self-contained

        # File system watcher — auto-refresh on any change in _blueprint/
        self._watcher = QFileSystemWatcher()
        self._watcher.addPath(str(BLUEPRINT_ROOT))
        for d in BLUEPRINT_ROOT.rglob("*"):
            if d.is_dir():
                self._watcher.addPath(str(d))
        self._watcher.directoryChanged.connect(self._scheduled_refresh)
        self._watcher.fileChanged.connect(self._scheduled_refresh)

        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_all)
        self._refresh_all()

    def _scheduled_refresh(self) -> None:
        """Debounce rapid file-system events into a single refresh."""
        self._refresh_timer.start(300)

    def _refresh_all(self) -> None:
        self._workbench.refresh()
        self._roadmap.refresh()
        self._inbound_editor.refresh()
        self._plantuml.refresh()
        self._prompts.refresh()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Blueprint Studio")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
