"""设置弹窗：行为开关、检测策略、门户地址与网络绑定管理。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme
from app.widgets import ComboBox, DialogHeader, InputFrame, Switch, field_label, h_switch_row
from core import autostart
from core.config import ConfigStore

# 已保存网络列表按行数自适应高度
_LIST_ROW_HEIGHT = 34
_LIST_MIN_ROWS = 2
_LIST_MAX_ROWS = 5


class SettingsDialog(QDialog):
    """模态设置对话框。"""

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowIcon(icons.app_icon())
        self.setFixedWidth(theme.DIALOG_WIDTH)
        self.setWindowTitle("设置")

        self._build_ui()
        self._load()
        self._fit_height()

    def _fit_height(self) -> None:
        """按内容自适应高度；内容超出可用屏幕高度时交给滚动区，底部按钮始终可见。"""
        self._body.adjustSize()
        content = (
            self._header.height()
            + self._body.sizeHint().height()
            + self._footer.sizeHint().height()
            + 2
        )
        screen = QGuiApplication.primaryScreen()
        limit = int(screen.availableGeometry().height() * 0.94) if screen else content
        self.setFixedHeight(max(400, min(content, limit)))

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

        self._header = DialogHeader("设置", self._root)
        self._header.closeRequested.connect(self.reject)
        root_layout.addWidget(self._header)

        # 内容放进滚动区：小屏上也能保证底部按钮始终可达
        self._scroll = QScrollArea(self._root)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(self._scroll, 1)

        self._body = QWidget()
        layout = QVBoxLayout(self._body)
        layout.setContentsMargins(16, 12, 16, 4)
        layout.setSpacing(10)
        self._scroll.setWidget(self._body)

        layout.addWidget(
            self._section(
                "行为",
                [
                    self._switch_row("开机自启", "auto_start"),
                    self._switch_row("关闭窗口时最小化到托盘", "close_to_tray"),
                    self._switch_row("检测到未认证时自动登录", "auto_login"),
                    self._switch_row("掉线或被踢下线时自动重连", "reconnect"),
                    self._switch_row("登录/失败时弹出 Windows 通知", "notify"),
                ],
            )
        )

        strategy = QHBoxLayout()
        strategy.setSpacing(theme.GAP_LG)
        strategy.addLayout(
            self._combo_row(
                "检测间隔",
                "interval",
                [("10 秒", 10), ("15 秒", 15), ("30 秒", 30), ("60 秒", 60)],
            ),
            1,
        )
        strategy.addLayout(
            self._combo_row(
                "已在线时的间隔",
                "interval_online",
                [("30 秒", 30), ("60 秒", 60), ("120 秒", 120), ("300 秒", 300)],
            ),
            1,
        )
        layout.addWidget(self._wrap("检测策略", strategy))

        # 门户地址（复用主界面同款输入框，保证边框与聚焦态一致）
        portal_box = QVBoxLayout()
        portal_box.setSpacing(theme.GAP_SM)
        self._portal_edit = InputFrame(placeholder="http://10.2.255.26")
        self._portal_edit.setToolTip("普通用户无需修改")
        portal_box.addWidget(field_label("认证门户地址", self._body))
        portal_box.addWidget(self._portal_edit)
        layout.addWidget(self._wrap("门户", portal_box))

        # 已保存网络
        saved_box = QVBoxLayout()
        saved_box.setSpacing(theme.GAP_SM)
        self._network_list = QListWidget(self._body)
        self._network_list.setMinimumHeight(_LIST_MIN_ROWS * _LIST_ROW_HEIGHT)
        delete_btn = QPushButton("删除选中的绑定", self._body)
        delete_btn.setObjectName("outlineButton")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._delete_selected)
        saved_box.addWidget(field_label("已保存的网络账号", self._body))
        saved_box.addWidget(self._network_list)
        saved_box.addWidget(delete_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._wrap("网络绑定", saved_box))

        # 内容不足时把剩余空间留在底部，卡片整体靠上
        layout.addStretch()

        # 底部按钮固定在滚动区之外，内容再长也不会被挤出屏幕
        self._footer = QWidget(self._root)
        btn_row = QHBoxLayout(self._footer)
        btn_row.setContentsMargins(16, 10, 16, 16)
        btn_row.setSpacing(theme.GAP_SM)
        btn_row.addStretch()
        cancel = QPushButton("取消", self._footer)
        cancel.setObjectName("outlineButton")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存", self._footer)
        save.setObjectName("primaryButton")
        save.setFixedWidth(88)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root_layout.addWidget(self._footer)

    def _section(self, title: str, rows: list[QHBoxLayout]) -> QWidget:
        box = QVBoxLayout()
        box.setSpacing(theme.GAP_MD)
        for row in rows:
            box.addLayout(row)
        return self._wrap(title, box)

    def _wrap(self, title: str, content) -> QWidget:
        """把一组设置包进统一的白色分区卡片。"""
        card = QWidget(self._body)
        card.setObjectName("sectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(theme.GAP_SM + 2)

        label = QLabel(title, card)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        layout.addLayout(content)
        return card

    def _switch_row(self, label: str, option_key: str) -> QHBoxLayout:
        switch = Switch(self._body)
        switch.setObjectName(option_key)
        return h_switch_row(label, switch)

    def _combo_row(
        self, label: str, option_key: str, items: list[tuple[str, object]]
    ) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(theme.GAP_SM)
        layout.addWidget(field_label(label, self._body))
        combo = ComboBox(self._body)
        combo.setObjectName(option_key)
        for text, value in items:
            combo.addItem(text, value)
        layout.addWidget(combo)
        return layout

    # ------------------------------------------------------------------ 数据

    def _find_switch(self, key: str) -> Switch:
        return self._root.findChild(Switch, key)

    def _find_combo(self, key: str) -> ComboBox:
        return self._root.findChild(ComboBox, key)

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

        online_combo = self._find_combo("interval_online")
        for i in range(online_combo.count()):
            if online_combo.itemData(i) == options.get("interval_online", 60):
                online_combo.setCurrentIndex(i)
                break

        self._portal_edit.setText(self.store.portal_base)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._network_list.clear()
        for nid, username, carrier in self.store.saved_networks():
            name = nid[5:] if nid.startswith("ssid:") else "有线网络"
            self._network_list.addItem(f"{name} · {username}({carrier})")

        rows = max(_LIST_MIN_ROWS, min(_LIST_MAX_ROWS, self._network_list.count() or _LIST_MIN_ROWS))
        self._network_list.setFixedHeight(rows * _LIST_ROW_HEIGHT + 8)

    def _delete_selected(self) -> None:
        row = self._network_list.currentRow()
        networks = self.store.saved_networks()
        if row < 0 or row >= len(networks):
            return
        self.store.remove_profile(networks[row][0])
        self._refresh_list()

    def _save(self) -> None:
        base = self._portal_edit.text().strip()
        if not base.startswith(("http://", "https://")):
            QMessageBox.warning(self, "格式错误", "门户地址需要以 http:// 或 https:// 开头")
            return

        self.store.set_options(
            {
                "close_to_tray": self._find_switch("close_to_tray").isChecked(),
                "auto_login": self._find_switch("auto_login").isChecked(),
                "reconnect": self._find_switch("reconnect").isChecked(),
                "notify": self._find_switch("notify").isChecked(),
                "interval": int(self._find_combo("interval").currentData()),
                "interval_online": int(self._find_combo("interval_online").currentData()),
            }
        )

        # 开机自启以注册表实际写入结果为准，失败时提示并回显真实状态
        wanted = self._find_switch("auto_start").isChecked()
        saved, reason = autostart.set_enabled(wanted)
        actual = autostart.is_enabled()
        self.store.set_option("auto_start", actual)
        if not saved:
            switch = self._find_switch("auto_start")
            switch.blockSignals(True)
            switch.setChecked(actual)
            switch.blockSignals(False)
            QMessageBox.warning(self, "开机自启设置失败", f"未能修改注册表自启项：{reason}")

        self.store.portal_base = base
        self.accept()
