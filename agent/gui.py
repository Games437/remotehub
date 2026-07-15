import sys
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QCheckBox,
    QInputDialog,
)

from agent import config
from agent.client import login, pair_with_code, start_agent_loop, stop_agent_loop


class AgentStatusBridge(QObject):
    changed = Signal(str)


class LoginWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, email: str, password: str):
        super().__init__()
        self.email = email
        self.password = password

    def run(self):
        ok, message = login(self.email, self.password)
        self.finished.emit(ok, message)


class PairWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, code: str):
        super().__init__()
        self.code = code

    def run(self):
        ok, message = pair_with_code(self.code)
        self.finished.emit(ok, message)


class AgentWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("RemoteHub Agent")
        self.resize(350, 280)

        layout = QVBoxLayout()

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setText(config.load_last_email())

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)

        self.remember_checkbox = QCheckBox("จดจำการเข้าสู่ระบบ (ครั้งหน้าไม่ต้องกรอกรหัสผ่าน)")
        self.remember_checkbox.setChecked(config.load_remember())

        self.button = QPushButton("Login")
        self.button.clicked.connect(self.login)

        self.pair_link = QPushButton("ใช้ Pair Code แทน")
        self.pair_link.setFlat(True)
        self.pair_link.clicked.connect(self.login_with_pair_code)

        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.hide()

        # Manual escape hatch for anyone stuck at "Connecting..." with no
        # terminal access — clears local credentials and forces a fresh
        # login, same recovery this app already does automatically when
        # the server explicitly rejects a removed/invalid machine. This
        # covers the cases where it doesn't respond at all instead of
        # rejecting cleanly.
        self.reset_button = QPushButton("Reset connection")
        self.reset_button.setFlat(True)
        self.reset_button.clicked.connect(self.reset_connection)
        self.reset_button.hide()

        self.status = QLabel("Status: Offline")

        layout.addWidget(self.email)
        layout.addWidget(self.password)
        layout.addWidget(self.remember_checkbox)
        layout.addWidget(self.button)
        layout.addWidget(self.pair_link)
        layout.addWidget(self.logout_button)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.status)

        self.setLayout(layout)

        self._thread = None
        self._worker = None

        self._status_bridge = AgentStatusBridge()
        self._status_bridge.changed.connect(self._on_agent_status)

        self._try_auto_start()

    # -- view state helpers --------------------------------------------------
    def _show_login_form(self):
        self.email.setEnabled(True)
        self.password.setEnabled(True)
        self.password.clear()
        self.remember_checkbox.setEnabled(True)
        self.button.show()
        self.button.setEnabled(True)
        self.pair_link.show()
        self.pair_link.setEnabled(True)
        self.logout_button.hide()
        self.reset_button.hide()

    def _show_connected_view(self):
        self.email.setEnabled(False)
        self.password.setEnabled(False)
        self.remember_checkbox.setEnabled(False)
        self.button.hide()
        self.pair_link.hide()
        self.logout_button.show()
        self.logout_button.setEnabled(True)
        self.reset_button.show()

    def _set_busy(self, busy: bool):
        self.button.setEnabled(not busy)
        self.pair_link.setEnabled(not busy)

    # -- startup ---------------------------------------------------------------
    def _try_auto_start(self):
        """Auto-connect only if this device is both paired AND marked as
        remembered — otherwise always require the password first."""
        if not config.load_remember():
            self._show_login_form()
            return

        started = start_agent_loop(on_status=self._status_bridge.changed.emit)
        if started:
            self.status.setText("Status: Connecting...")
            self._show_connected_view()
        else:
            self._show_login_form()

    # -- login -------------------------------------------------------------
    def login(self):
        email = self.email.text().strip()
        password = self.password.text()
        if not email or not password:
            self.status.setText("Status: กรุณากรอก email และ password")
            return

        self.status.setText("Status: Logging in...")
        self._set_busy(True)

        self._thread = QThread()
        self._worker = LoginWorker(email, password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_login_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_login_finished(self, ok: bool, message: str):
        self._set_busy(False)
        if not ok:
            self.status.setText(f"Status: Login ไม่สำเร็จ — {message}")
            return

        config.save_remember(self.remember_checkbox.isChecked(), self.email.text().strip())

        started = start_agent_loop(on_status=self._status_bridge.changed.emit)
        if started:
            self.status.setText("Status: Connecting...")
            self._show_connected_view()
        else:
            self.status.setText("Status: Login สำเร็จ แต่เริ่มเชื่อมต่อไม่ได้")

    # -- pair code -----------------------------------------------------------
    def login_with_pair_code(self):
        code, ok_pressed = QInputDialog.getText(self, "Pair Code", "กรอกรหัส Pair Code:")
        if not ok_pressed or not code.strip():
            return

        self.status.setText("Status: Pairing...")
        self._set_busy(True)

        self._thread = QThread()
        self._worker = PairWorker(code.strip())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_pair_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_pair_finished(self, ok: bool, message: str):
        self._set_busy(False)
        if not ok:
            self.status.setText(f"Status: Pair ไม่สำเร็จ — {message}")
            return

        # Pair-code machines never use a password, so there's nothing to
        # "remember" — treat them as always-trusted for auto-start.
        config.save_remember(True)

        started = start_agent_loop(on_status=self._status_bridge.changed.emit)
        if started:
            self.status.setText("Status: Connecting...")
            self._show_connected_view()
        else:
            self.status.setText("Status: Pair สำเร็จ แต่เริ่มเชื่อมต่อไม่ได้")

    # -- logout ----------------------------------------------------------------
    def logout(self):
        stop_agent_loop()
        config.save_remember(False)
        self.status.setText("Status: Offline")
        self._show_login_form()

    # -- manual recovery for a stuck connection --------------------------------
    def reset_connection(self):
        """Same recovery the app does automatically when the server
        explicitly rejects a removed/invalid machine — offered here as a
        button too, for the case where the connection just hangs instead
        of rejecting cleanly, and the person has no other way to unstick
        it (no terminal, doesn't know what pair.json is)."""
        stop_agent_loop()
        config.clear_credentials()
        config.save_remember(False)
        self.status.setText("Status: รีเซ็ตการเชื่อมต่อแล้ว — กรุณา Login ใหม่")
        self._show_login_form()

    # -- status updates from the background websocket thread ------------------
    def _on_agent_status(self, state: str):
        mapping = {
            "connecting": "Status: Connecting...",
            "connected": "Status: Connected ✓",
            "disconnected": "Status: Disconnected, retrying...",
            "handshake_timeout": "Status: การเชื่อมต่อไม่ตอบสนอง กำลังลองใหม่... "
                                  "(ถ้าค้างนานผิดปกติ ลองกด Reset connection)",
        }
        if state in mapping:
            self.status.setText(mapping[state])
        elif state.startswith("error:"):
            self.status.setText(f"Status: Error — {state[6:]}")
        elif state.startswith("removed:"):
            # The agent already cleared local credentials on its side —
            # reflect that here by resetting to the login form so the
            # person can log in again (which will register a fresh machine).
            config.save_remember(False)
            self.status.setText(f"Status: เครื่องนี้ถูกลบออกจากบัญชี — กรุณา Login ใหม่ ({state[8:]})")
            self._show_login_form()


app = QApplication(sys.argv)

window = AgentWindow()
window.show()

sys.exit(app.exec())