"""历史日志弹窗：展示登录记录与脱敏后的诊断信息。"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme
from app.widgets import ComboBox, DialogHeader
from core.config import ConfigStore


class LogDialog(QDialog):
    """历史与诊断信息弹窗。"""

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._visible: list[dict] = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowIcon(icons.app_icon())
        self.setWindowTitle("登录日志与诊断")
        self.setFixedSize(600, 520)

        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ 界面

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._root = QFrame(self)
        self._root.setObjectName("root")
        theme.make_opaque(self)
        theme.make_opaque(self._root)
        outer.addWidget(self._root)

        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = DialogHeader("登录日志与诊断", self._root)
        header.closeRequested.connect(self.accept)
        root_layout.addWidget(header)

        body = QWidget(self._root)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        root_layout.addWidget(body)

        # 工具行
        toolbar = QHBoxLayout()
        toolbar.setSpacing(theme.GAP_SM)
        toolbar.addWidget(QLabel("筛选", body))
        self._filter = ComboBox(body)
        self._filter.setFixedWidth(110)
        self._filter.addItem("全部", "all")
        self._filter.addItem("成功", "success")
        self._filter.addItem("失败", "fail")
        self._filter.currentIndexChanged.connect(self._load)
        toolbar.addWidget(self._filter)

        self._summary = QLabel("", body)
        self._summary.setObjectName("hintLabel")
        toolbar.addWidget(self._summary)
        toolbar.addStretch()

        self._copy_btn = QPushButton("复制诊断", body)
        self._copy_btn.setObjectName("outlineButton")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setToolTip("复制选中记录的诊断信息到剪贴板")
        self._copy_btn.clicked.connect(self._copy_detail)
        toolbar.addWidget(self._copy_btn)

        self._clear_btn = QPushButton("清空记录", body)
        self._clear_btn.setObjectName("outlineButton")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(self._clear_btn)
        layout.addLayout(toolbar)

        # 记录表
        self._table = QTableWidget(body)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["时间", "网络", "学号", "结果"])
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 120)
        self._table.setColumnWidth(2, 100)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table, 1)

        # 诊断详情
        detail_label = QLabel("诊断详情（密码已脱敏）", body)
        detail_label.setObjectName("sectionTitle")
        layout.addWidget(detail_label)

        self._detail = QTextBrowser(body)
        mono = QFont()
        mono.setFamilies(["Consolas", "JetBrains Mono", "Courier New", "monospace"])
        mono.setPixelSize(12)
        self._detail.setFont(mono)
        self._detail.setMinimumHeight(150)
        layout.addWidget(self._detail, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("关闭", self._root)
        close.setObjectName("primaryButton")
        close.setFixedWidth(120)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        footer.addStretch()
        layout.addLayout(footer)

    # ------------------------------------------------------------------ 数据

    def _load(self) -> None:
        records = self.store.history()
        records.reverse()
        mode = self._filter.currentData()

        # 表格行与 _visible 严格一一对应，避免筛选后详情错位
        self._visible = [
            record
            for record in records
            if not (
                (mode == "success" and not record.get("ok"))
                or (mode == "fail" and record.get("ok"))
            )
        ]

        self._table.setRowCount(0)
        for record in self._visible:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(
                row, 0, QTableWidgetItem(self._fmt_time(record.get("ts", 0)))
            )
            self._table.setItem(row, 1, QTableWidgetItem(str(record.get("network", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(str(record.get("username", ""))))
            ok = bool(record.get("ok"))
            result = "成功" if ok else str(record.get("message", "失败"))
            item = QTableWidgetItem(result)
            item.setForeground(QBrush(theme.state_color("online" if ok else "failed")))
            self._table.setItem(row, 3, item)

        total = len(records)
        succeeded = sum(1 for record in records if record.get("ok"))
        self._summary.setText(
            f"共 {total} 条 · 成功 {succeeded} · 失败 {total - succeeded} · 当前显示 {len(self._visible)}"
        )
        self._detail.clear()

    def _on_select(self) -> None:
        rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not rows:
            self._detail.clear()
            return
        row = rows[0].row()
        if not (0 <= row < len(self._visible)):
            self._detail.clear()
            return
        self._detail.setPlainText(self._detail_text(self._visible[row]))

    @staticmethod
    def _detail_text(record: dict) -> str:
        return "\n".join(
            [
                f"时间：{LogDialog._fmt_time(record.get('ts', 0), with_date=True)}",
                f"网络：{record.get('network', '')}  ({record.get('network_id', '')})",
                f"学号：{record.get('username', '')}",
                f"服务：{record.get('carrier', '')}",
                f"结果：{'成功' if record.get('ok') else '失败'}",
                f"判定：{record.get('verdict', '')}",
                f"消息：{record.get('message', '')}",
                "",
                "请求：",
                record.get("request", "") or "无",
                "",
                "响应片段：",
                record.get("detail", "") or "无",
            ]
        )

    def _copy_detail(self) -> None:
        rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not rows or not (0 <= rows[0].row() < len(self._visible)):
            QApplication.clipboard().setText(self._summary.text())
            self._summary.setText(f"{self._summary.text()}（未选中记录，已复制统计）")
            return
        QApplication.clipboard().setText(self._detail_text(self._visible[rows[0].row()]))
        self._summary.setText("诊断信息已复制到剪贴板")

    def _clear(self) -> None:
        self.store.clear_history()
        self._load()

    @staticmethod
    def _fmt_time(ts: float, with_date: bool = False) -> str:
        if not ts:
            return ""
        pattern = "%m-%d %H:%M:%S" if with_date else "%m-%d %H:%M"
        return datetime.fromtimestamp(ts).strftime(pattern)
