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
    "APPROVED":    "#2d6a2d",
    "REVIEW":      "#7a6b00",
    "NEEDS_FIX":   "#7a2020",
    "BLOCKED":     "#3a3a3a",
    "DRAFT":       "#1a3a5a",
    "DONE":        "#004d40",
    "ARCHIVED":    "#555555",
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
    "Briefings":      BLUEPRINT_ROOT / "inbound" / "Briefings",
    "MindMaps":       BLUEPRINT_ROOT / "inbound" / "MindMaps",
    "Wireframes":     BLUEPRINT_ROOT / "inbound" / "Wireframes",
    "Issues_and_Bugs":BLUEPRINT_ROOT / "inbound" / "Issues_and_Bugs",
    "Knowledge_Raw":  BLUEPRINT_ROOT / "inbound" / "Knowledge_Raw",
    "User_Feedback":  BLUEPRINT_ROOT / "inbound" / "User_Feedback",
}

INBOUND_PROTOCOL_HINT: dict[str, str] = {
    "Briefings":      "Protocol: P0_Ingestion — converts briefs into Goals/Features",
    "MindMaps":       "Protocol: P0_Ingestion — parses mind-map structure",
    "Wireframes":     "Protocol: P2.5_UI_Architecture — extracts Screens (SCR-xxx)",
    "Issues_and_Bugs":"Protocol: P0.5_Bug_Triage — resolves bugs to Tasks or Use Cases",
    "Knowledge_Raw":  "Protocol: P0_Ingestion or H2_Wiki_Update — feeds Knowledge Base",
    "User_Feedback":  "Protocol: R2_User_Critique → R3_Fix — triggers agent fix cycle",
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

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("🔍 Filter artifacts…")
        search_bar.setStyleSheet(
            "background:#111827; color:#d0d8e8; border:1px solid #2a3a5a;"
            " border-radius:4px; padding:3px 6px;"
        )
        search_bar.textChanged.connect(self._filter_tree)
        left_layout.addWidget(search_bar)
        self._search_bar = search_bar

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Artifacts")
        self._tree.itemClicked.connect(self._on_tree_click)
        left_layout.addWidget(self._tree)
        main_splitter.addWidget(left)

        # ── RIGHT: viewer (top) + critique (bottom) ───────────────────────────
        right_splitter = QSplitter(Qt.Vertical)

        # ── Viewer section ─────────────────────────────────────────────────
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        viewer_layout.setContentsMargins(4, 4, 4, 0)

        self._trace_label = QLabel("Trace: —")
        self._trace_label.setWordWrap(True)
        self._trace_label.setStyleSheet("color:#8ab; font-style:italic; padding:2px 4px;")
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
            "font-weight:bold; color:#8ab; padding:4px;"
            " background:#16213e; border-radius:4px;"
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
        self._reject_btn .clicked.connect(lambda: self._submit("NEEDS_FIX"))
        for btn in (self._approve_btn, self._change_btn, self._reject_btn):
            btn.setStyleSheet(
                "QPushButton { background:#16213e; border:1px solid #2a3a5a;"
                " color:#8ab; border-radius:4px; padding:4px 10px; }"
                "QPushButton:hover { background:#1a2a4a; color:#d0e8ff; }"
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

    # ── Refresh / build tree ─────────────────────────────────────────────────

    def refresh(self) -> None:
        self._index = {}
        self._tree.clear()
        for entity_name, cfg in ENTITY_CONFIG.items():
            root_item = QTreeWidgetItem([entity_name])
            root_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            root_item.setForeground(0, QColor("#8ab"))
            root_item.setFlags(root_item.flags() & ~Qt.ItemIsSelectable)
            for entry in _scan_artifacts(entity_name):
                meta   = entry["meta"]
                aid    = str(meta.get("id", "?"))
                title  = str(meta.get("title", meta.get("hypothesis", aid)))
                status = str(meta.get("status", ""))
                child  = QTreeWidgetItem([f"{aid}  [{status}]  {title[:45]}"])
                child.setForeground(0, _color_for_status(status))
                child.setData(0, Qt.UserRole, entry)
                root_item.addChild(child)
                self._index[aid] = entry
            self._tree.addTopLevelItem(root_item)
        self._tree.expandAll()

    # ── Tree interaction ─────────────────────────────────────────────────────

    def _on_tree_click(self, item: QTreeWidgetItem, _col: int) -> None:
        entry = item.data(0, Qt.UserRole)
        if entry:
            self._load(entry["path"], entry["meta"])

    def _filter_tree(self, text: str) -> None:
        search = text.lower().strip()
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            any_visible = False
            for j in range(group.childCount()):
                child = group.child(j)
                match = not search or search in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    any_visible = True
            group.setHidden(not any_visible and bool(search))

    # ── Load artifact ─────────────────────────────────────────────────────────

    def _load(self, path: Path, meta: dict) -> None:
        self._current_path = path
        self._current_meta = meta

        # Viewer
        body = read_body(path)
        html = md_lib.markdown(body, extensions=["fenced_code", "tables"])
        meta_html = "  ".join(
            f"<span style='color:#8ab'>{k}:</span> <b>{v}</b>"
            for k, v in meta.items()
        )
        self._content_browser.setHtml(
            f"<div style='background:#16213e;padding:6px 10px;border-radius:4px;"
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
        jar_lbl.setStyleSheet("color:#8ab; font-size:9px;")
        ll.addWidget(jar_lbl)
        main_split.addWidget(left)

        # ── RIGHT: image (top) + critique (bottom) ────────────────────────────
        right_split = QSplitter(Qt.Vertical)

        img_w = QWidget()
        il = QVBoxLayout(img_w)
        il.setContentsMargins(4, 4, 4, 0)
        top_bar = QHBoxLayout()
        self._status_label = QLabel("Select a diagram")
        self._status_label.setStyleSheet("color:#8ab;")
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
            "font-weight:bold; color:#8ab; background:#16213e;"
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
                "QPushButton{background:#16213e;border:1px solid #2a3a5a;"
                "color:#8ab;border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#1a2a4a;color:#d0e8ff;}"
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
        self._protocol_hint.setStyleSheet("color: #8ab; font-style: italic; padding: 4px;")
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
# Panel 7: Prompts Launcher
# ---------------------------------------------------------------------------

# Each entry: (emoji, phase_key, label, short_desc, prompt_file_rel)
PROMPT_PHASES: list[tuple[str, str, str, str, str]] = [
    ("📥", "P0",  "P0 · Ingestion",
     "Parse raw inbound material into structured Goals/Features extract",
     "protocols/generation/P0_Ingestion.md"),
    ("🐛", "P0.5","P0.5 · Bug Triage",
     "Triage an issue or bug report into a structured artifact or use case update",
     "protocols/generation/P0_5_Bug_Triage.md"),
    ("🎯", "P1",  "P1 · Inception",
     "Transform project idea → Goals + Feature Map + Roadmap",
     "protocols/generation/P1_Inception.md"),
    ("🎯", "P1.5","P1.5 · Goal Decomposition",
     "Break down high-level Goals into actionable Sub-Goals and initial Features",
     "protocols/generation/P1_5_Goal_Decomposition.md"),
    ("🔬", "P2",  "P2 · Research",
     "Run R&D spikes to eliminate uncertainty in features",
     "protocols/generation/P2_Research.md"),
    ("🎨", "P2.5","P2.5 · UI Architecture",
     "Extract and design UI Screen artifacts from visual wireframes",
     "protocols/generation/P2_5_UI_Architecture.md"),
    ("📐", "P3",  "P3 · Analysis",
     "Decompose approved features → Use Cases + User Flows",
     "protocols/generation/P3_Analysis.md"),
    ("🗺", "P3.5","P3.5 · UML Generator",
     "Generate PlantUML diagrams from approved Use Cases",
     "protocols/generation/P3_5_UML_Generator.md"),
    ("⚙️", "P4",  "P4 · Dev Sync",
     "Decompose Use Cases → atomic Tasks + Fuzzing vectors",
     "protocols/generation/P4_Dev_Sync.md"),
    ("📅", "P5",  "P5 · Sprint Planning",
     "Organize selected Tasks into an actionable Sprint board",
     "protocols/generation/P5_Sprint_Planning.md"),
    ("⚡", "E1",  "E1 · Sprint Execution",
     "Execute a Task, run tests, and harvest session logs + knowledge",
     "protocols/execution/E1_Sprint_Execution.md"),
    ("🪞", "R1",  "R1 · Self-Critique",
     "Auto-review an artifact for logic gaps before human review",
     "protocols/review/R1_Agent_Self_Critic.md"),
    ("🧐", "R1.5","R1.5 · Code Review",
     "Auto-review source code for syntax, security, and context loss before commit",
     "protocols/review/R1_5_Code_Review.md"),
    ("📬", "R2",  "R2 · User Critique",
     "Process human feedback file → structured change requests",
     "protocols/review/R2_User_Critique_Process.md"),
    ("🔧", "R3",  "R3 · Fix & Refactor",
     "Apply change requests → revised artifact → resubmit",
     "protocols/review/R3_Fix_and_Refactor.md"),
    ("✅", "R4",  "R4 · UML Validator",
     "Cross-check UML draft against parent UseCase requirements",
     "protocols/review/R4_UML_Validator.md"),
    ("⏸", "S1",  "S1 · Wait For Approval",
     "Pause agent and request human review before continuing",
     "protocols/interactive/S1_Wait_For_Approval.md"),
    ("⚖️", "S2",  "S2 · Conflict Resolution",
     "Surface contradictions between artifacts for human decision",
     "protocols/interactive/S2_Conflict_Resolution.md"),
    ("🔄", "S3",  "S3 · Incremental Update",
     "Apply a minor scoped fix without triggering full re-analysis",
     "protocols/interactive/S3_Incremental_Update.md"),
    ("🧠", "H1",  "H1 · Pattern Recognition",
     "Harvest reusable patterns from completed sprint artifacts",
     "protocols/knowledge/H1_Pattern_Recognition.md"),
    ("📖", "H2",  "H2 · Wiki Update",
     "Sync Terminology.md with new domain terms from recent artifacts",
     "protocols/knowledge/H2_Wiki_Update.md"),
]


class PromptsPanel(QWidget):
    """Panel 7: copy-paste ready prompt cards for each protocol phase."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Top bar ──────────────────────────────────────────────────────────
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 6, 8, 6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter phases…")
        self._search.textChanged.connect(self._filter)
        self._search.setStyleSheet(
            "background:#111827; color:#d0d8e8; border:1px solid #2a3a5a;"
            " border-radius:4px; padding:4px 8px;"
        )
        top_layout.addWidget(self._search)

        context_btn = QPushButton("↻ Refresh Context")
        context_btn.clicked.connect(self._build_context)
        top_layout.addWidget(context_btn)
        outer.addWidget(top_bar)

        # ── Cards scroll area ─────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(6)
        self._cards_layout.setContentsMargins(8, 4, 8, 8)
        self._scroll.setWidget(self._cards_container)
        outer.addWidget(self._scroll)

        # Context snapshot shown in each copied prompt
        self._context_snapshot: str = ""
        self._cards: list[dict] = []  # {widget, label_text}

        self._build_cards()
        self._build_context()

    # ── Build cards ──────────────────────────────────────────────────────────

    def _build_cards(self) -> None:
        self._cards = []
        for emoji, phase_key, label, desc, rel_path in PROMPT_PHASES:
            card = self._make_card(emoji, phase_key, label, desc, rel_path)
            self._cards.append({"widget": card["frame"], "label": label.lower()})
            self._cards_layout.addWidget(card["frame"])
        self._cards_layout.addStretch()

    def _make_card(self, emoji: str, phase_key: str, label: str, desc: str, rel_path: str) -> dict:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #16213e; border: 1px solid #2a3a5a; border-radius: 6px; padding: 4px; }"
            "QFrame:hover { border-color: #4a8acc; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)

        # Left: emoji + title + desc
        left = QVBoxLayout()
        title_lbl = QLabel(f"{emoji}  <b>{label}</b>")
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setStyleSheet("color:#d0e8ff; font-size:12px;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color:#8ab; font-size:10px;")
        desc_lbl.setWordWrap(True)
        left.addWidget(title_lbl)
        left.addWidget(desc_lbl)
        row.addLayout(left, stretch=1)

        # Right: buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        copy_btn = QPushButton("📋 Copy Prompt")
        copy_btn.setFixedWidth(130)
        copy_btn.setStyleSheet(
            "QPushButton { background:#1a3a5a; color:#7dd; border:1px solid #2a5a8a;"
            " border-radius:4px; padding:4px 8px; font-size:10px; }"
            "QPushButton:hover { background:#1e4a6a; color:#aef; }"
        )
        copy_btn.clicked.connect(lambda checked=False, r=rel_path, l=label: self._copy_prompt(r, l))

        view_btn = QPushButton("👁 View Full")
        view_btn.setFixedWidth(130)
        view_btn.setStyleSheet(
            "QPushButton { background:#16213e; color:#8ab; border:1px solid #2a3a5a;"
            " border-radius:4px; padding:4px 8px; font-size:10px; }"
            "QPushButton:hover { background:#1a2a4a; color:#d0e8ff; }"
        )
        view_btn.clicked.connect(lambda checked=False, r=rel_path, l=label: self._view_full(r, l))

        btn_col.addWidget(copy_btn)
        btn_col.addWidget(view_btn)
        row.addLayout(btn_col)

        return {"frame": frame}

    # ── Context snapshot ──────────────────────────────────────────────────────

    def _build_context(self) -> None:
        """Scan artifacts and build a compact context block to inject into prompts."""
        lines = ["\n---\n## Current Project Context (auto-injected by Blueprint GUI)\n"]
        total = 0
        pending = 0
        for entity_name in ENTITY_CONFIG:
            arts = _scan_artifacts(entity_name)
            approved = sum(1 for a in arts if a["meta"].get("status") == "APPROVED")
            review   = sum(1 for a in arts if a["meta"].get("status") == "REVIEW")
            needs_fix = sum(1 for a in arts if a["meta"].get("status") == "NEEDS_FIX")
            if arts:
                lines.append(
                    f"- **{entity_name}**: {len(arts)} total "
                    f"({approved} approved, {review} in review, {needs_fix} needs_fix)"
                )
            total   += len(arts)
            pending += review + needs_fix

        lines.append(f"\n**Total artifacts:** {total}  |  **Pending review:** {pending}")

        # List IDs awaiting review
        waiting = []
        for entity_name in ENTITY_CONFIG:
            for a in _scan_artifacts(entity_name):
                s = a["meta"].get("status", "")
                if s in ("REVIEW", "NEEDS_FIX"):
                    waiting.append(f"{a['meta'].get('id','?')} ({s})")
        if waiting:
            lines.append("\n**Awaiting action:** " + ", ".join(waiting))

        self._context_snapshot = "\n".join(lines)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _copy_prompt(self, rel_path: str, label: str) -> None:
        proto_path = BLUEPRINT_ROOT / rel_path
        if proto_path.exists():
            protocol_text = proto_path.read_text(encoding="utf-8")
        else:
            protocol_text = f"# {label}\n\n[Protocol file not found: {rel_path}]"

        full_text = protocol_text + self._context_snapshot
        QApplication.clipboard().setText(full_text)

        # Flash feedback — find the button that was clicked
        self._show_copied_toast(label)

    def _view_full(self, rel_path: str, label: str) -> None:
        proto_path = BLUEPRINT_ROOT / rel_path
        dialog_widget = QWidget(self, Qt.Window)
        dialog_widget.setWindowTitle(f"{label} — Full Protocol")
        dialog_widget.resize(800, 600)
        layout = QVBoxLayout(dialog_widget)
        browser = QTextBrowser()
        if proto_path.exists():
            html = md_lib.markdown(proto_path.read_text(encoding="utf-8"),
                                   extensions=["fenced_code", "tables"])
            browser.setHtml(html)
        else:
            browser.setPlainText(f"File not found: {proto_path}")
        browser.setStyleSheet("background:#111827; color:#d0d8e8;")
        layout.addWidget(browser)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog_widget.close)
        layout.addWidget(close_btn)
        dialog_widget.show()

    def _show_copied_toast(self, label: str) -> None:
        toast = QLabel(f"  ✅  Copied: {label}  ", self)
        toast.setStyleSheet(
            "background:#1a3a1a; color:#4caf50; border:1px solid #2d6a2d;"
            " border-radius:6px; padding:6px 12px; font-size:11px;"
        )
        toast.adjustSize()
        # Center at bottom
        x = (self.width() - toast.width()) // 2
        y = self.height() - toast.height() - 20
        toast.move(x, y)
        toast.show()
        QTimer.singleShot(1500, toast.deleteLater)

    def _filter(self, text: str) -> None:
        search = text.lower().strip()
        for card in self._cards:
            card["widget"].setVisible(not search or search in card["label"])

    def refresh(self) -> None:
        self._build_context()


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
                    item.setForeground(QColor("#4caf50"))
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
            QMainWindow, QWidget { background: #1a1a2e; color: #d0d8e8; }
            QTabWidget::pane { border: 1px solid #2a3a5a; }
            QTabBar::tab { background: #16213e; padding: 6px 16px; color: #8ab; }
            QTabBar::tab:selected { background: #1a2a4a; color: #d0e8ff; }
            QTableWidget { gridline-color: #2a3a5a; }
            QHeaderView::section { background: #16213e; color: #8ab; padding: 4px; }
            QTreeWidget { border: 1px solid #2a3a5a; }
            QPushButton { background: #16213e; color: #8ab; border: 1px solid #2a3a5a; padding: 5px 12px; border-radius: 4px; }
            QPushButton:hover { background: #1a2a4a; color: #d0e8ff; }
            QPlainTextEdit, QTextBrowser { background: #111827; color: #d0d8e8; border: 1px solid #2a3a5a; }
            QListWidget { background: #111827; color: #c0c8d8; border: 1px solid #2a3a5a; }
            QComboBox { background: #16213e; color: #8ab; border: 1px solid #2a3a5a; padding: 3px; }
            QGroupBox { border: 1px solid #2a3a5a; margin-top: 6px; color: #8ab; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; }
            QScrollArea { border: none; }
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
