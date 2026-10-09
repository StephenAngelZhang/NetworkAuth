"""历史日志弹窗：展示登录记录与诊断信息。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigStore


class LogDialog(QDialog):
    """历史与诊断信息弹窗。"""

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("登录日志与诊断")
        self.setMinimumSize(560, 440)
        self.setStyleSheet("background:#FFFFFF;")

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("登录日志与诊断")
        title.setObjectName("statusTitle")
        layout.addWidget(title)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(QLabel("筛选："))
        self._filter = QComboBox()
        self._filter.addItem("全部", "all")
        self._filter.addItem("成功", "success")
        self._filter.addItem("失败", "fail")
        self._filter.currentIndexChanged.connect(self._load)
        top.addWidget(self._filter)
        top.addStretch()

        self._clear_btn = QPushButton("清空记录")
        self._clear_btn.setObjectName("ghostButton")
        self._clear_btn.clicked.connect(self._clear)
        top.addWidget(self._clear_btn)

        layout.addLayout(top)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["时间", "网络", "学号", "结果"])
        self._table.setColumnWidth(0, 90)
        self._table.setColumnWidth(1, 110)
        self._table.setColumnWidth(2, 90)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        layout.addWidget(QLabel("诊断详情（已脱敏）："))
        self._detail = QTextBrowser()
        self._detail.setMaximumHeight(140)
        layout.addWidget(self._detail)

        close = QPushButton("关闭")
        close.setObjectName("primaryButton")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignCenter)

    def _load(self) -> None:
        self._records = self.store.history()
        self._records.reverse()
        filt = self._filter.currentData()

        self._table.setRowCount(0)
        for record in self._records:
            ok = bool(record.get("ok"))
            if filt == "success" and not ok:
                continue
            if filt == "fail" and ok:
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            ts = record.get("ts", 0)
            time_text = self._fmt_time(ts)
            self._table.setItem(row, 0, QTableWidgetItem(time_text))
            self._table.setItem(row, 1, QTableWidgetItem(str(record.get("network", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(str(record.get("username", ""))))
            result = "成功" if ok else (record.get("message", "失败"))
            self._table.setItem(row, 3, QTableWidgetItem(result))

    def _on_select(self) -> None:
        rows = self._table.selectedIndexes()
        if not rows:
            self._detail.clear()
            return
        index = rows[0].row()
        record = self._records[index]
        lines = [
            f"时间：{self._fmt_time(record.get('ts', 0))}",
            f"网络：{record.get('network', '')}  ({record.get('network_id', '')})",
            f"学号：{record.get('username', '')}",
            f"服务：{record.get('carrier', '')}",
            f"结果：{'成功' if record.get('ok') else '失败'}",
            f" verdict：{record.get('verdict', '')}",
            f"消息：{record.get('message', '')}",
            "",
            "请求：",
            record.get("request", "") or "无",
            "",
            "响应片段：",
            record.get("detail", "") or "无",
        ]
        self._detail.setPlainText("\n".join(lines))

    def _clear(self) -> None:
        self.store.clear_history()
        self._load()
        self._detail.clear()

    @staticmethod
    def _fmt_time(ts: float) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
