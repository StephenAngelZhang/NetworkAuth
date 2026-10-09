"""设置弹窗：开机自启、检测策略、网络绑定管理。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme
from app.widgets import Switch
from core import autostart
from core.config import ConfigStore


def _force_opaque(widget: QWidget) -> None:
    """强制不透明：分层窗口整窗 alpha=0 会导致透明且鼠标点击穿透。"""
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    widget.setPalette(palette)


class SettingsDialog(QDialog):
    """模态设置对话框。"""

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowIcon(icons.app_icon())
        self.setFixedWidth(500)
        self.setWindowTitle("设置")

        self._build_ui()
        self._load()
        self.adjustSize()
        self.setFixedHeight(self.height())

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._root = QFrame(self)
        self._root.setObjectName("root")
        _force_opaque(self._root)
        outer.addWidget(self._root)

        layout = QVBoxLayout(self._root)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("statusTitle")
        layout.addWidget(title)

        # 行为开关
        layout.addWidget(self._group(
            self._switch_row("开机自启", "auto_start"),
            self._switch_row("关闭窗口时最小化到托盘", "close_to_tray"),
            self._switch_row("检测到未认证时自动登录", "auto_login"),
            self._switch_row("掉线或被踢下线时自动重连", "reconnect"),
            self._switch_row("登录/失败时弹出 Windows 通知", "notify"),
        ))

        # 策略参数
        strategy = QHBoxLayout()
        strategy.setSpacing(16)
        strategy.addLayout(self._combo_row("检测间隔", "interval", [("10 秒", 10), ("15 秒", 15), ("30 秒", 30), ("60 秒", 60)]))
        strategy.addLayout(self._combo_row("请求方式", "login_method", [("GET", "GET"), ("POST", "POST")]))
        layout.addLayout(strategy)

        # 门户地址
        portal_label = QLabel("认证门户地址", self._root)
        portal_label.setObjectName("fieldLabel")
        layout.addWidget(portal_label)
        self._portal_edit = QLineEdit(self._root)
        self._portal_edit.setPlaceholderText("http://10.2.255.26")
        self._portal_edit.setToolTip("普通用户无需修改")
        layout.addWidget(self._portal_edit)

        # 已保存网络
        saved_label = QLabel("已保存的网络账号", self._root)
        saved_label.setObjectName("fieldLabel")
        layout.addWidget(saved_label)
        self._network_list = QListWidget(self._root)
        self._network_list.setMaximumHeight(120)
        layout.addWidget(self._network_list)

        delete_btn = QPushButton("删除选中的绑定", self._root)
        delete_btn.setObjectName("ghostButton")
        delete_btn.clicked.connect(self._delete_selected)
        layout.addWidget(delete_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("取消", self._root)
        cancel.setObjectName("ghostButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存", self._root)
        save.setObjectName("primaryButton")
        save.setFixedWidth(80)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _group(self, *rows: QHBoxLayout) -> QWidget:
        widget = QWidget(self._root)
        widget.setObjectName("formCard")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        for row in rows:
            layout.addLayout(row)
        return widget

    def _switch_row(self, label: str, option_key: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)
        switch = Switch(self._root)
        switch.setObjectName(option_key)
        lbl = QLabel(label)
        lbl.setObjectName("statusSub")
        layout.addWidget(switch)
        layout.addWidget(lbl)
        layout.addStretch()
        return layout

    def _combo_row(self, label: str, option_key: str, items: list[tuple[str, object]]) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        layout.addWidget(lbl)
        combo = QComboBox(self._root)
        combo.setObjectName(option_key)
        for text, value in items:
            combo.addItem(text, value)
        layout.addWidget(combo)
        return layout

    def _find_switch(self, key: str) -> Switch:
        return self._root.findChild(Switch, key)

    def _find_combo(self, key: str) -> QComboBox:
        return self._root.findChild(QComboBox, key)

    def _load(self) -> None:
        options = self.store.options
        self._find_switch("auto_start").setChecked(bool(autostart.is_enabled()))
        self._find_switch("close_to_tray").setChecked(bool(options.get("close_to_tray", True)))
        self._find_switch("auto_login").setChecked(bool(options.get("auto_login", True)))
        self._find_switch("reconnect").setChecked(bool(options.get("reconnect", True)))
        self._find_switch("notify").setChecked(bool(options.get("notify", True)))

        interval_combo = self._find_combo("interval")
        for i in range(interval_combo.count()):
            if interval_combo.itemData(i) == options.get("interval", 15):
                interval_combo.setCurrentIndex(i)
                break

        method_combo = self._find_combo("login_method")
        for i in range(method_combo.count()):
            if method_combo.itemData(i) == options.get("login_method", "GET"):
                method_combo.setCurrentIndex(i)
                break

        self._portal_edit.setText(self.store.portal_base)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._network_list.clear()
        for nid, username, carrier in self.store.saved_networks():
            name = nid[5:] if nid.startswith("ssid:") else "有线网络"
            self._network_list.addItem(f"{name} · {username}({carrier})")

    def _delete_selected(self) -> None:
        row = self._network_list.currentRow()
        networks = self.store.saved_networks()
        if row < 0 or row >= len(networks):
            return
        nid = networks[row][0]
        self.store.remove_profile(nid)
        self._refresh_list()

    def _save(self) -> None:
        base = self._portal_edit.text().strip()
        if not base.startswith(("http://", "https://")):
            QMessageBox.warning(self, "格式错误", "门户地址需要以 http:// 或 https:// 开头")
            return

        new_options = {
            "close_to_tray": self._find_switch("close_to_tray").isChecked(),
            "auto_login": self._find_switch("auto_login").isChecked(),
            "reconnect": self._find_switch("reconnect").isChecked(),
            "notify": self._find_switch("notify").isChecked(),
            "interval": int(self._find_combo("interval").currentData()),
            "login_method": str(self._find_combo("login_method").currentData()).upper(),
        }
        self.store.set_options(new_options)
        self.store.set_option("auto_start", self._find_switch("auto_start").isChecked())
        autostart.set_enabled(self._find_switch("auto_start").isChecked())
        self.store.portal_base = base
        self.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if hasattr(self, "_drag_pos"):
            self.move(self.pos() + event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)
