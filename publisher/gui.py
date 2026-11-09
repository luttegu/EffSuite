"""Publisher-only graphical key generation and offline licence issuance for EffSuite."""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from typing import Callable

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .license_tool import generate_keys, load_private, issue, write_new, read_request
from effsuite.licensing.dates import expiry_after_day, readable_day, readable_utc, utc_datetime
from effsuite.licensing.verification import utc_text


class PublisherWindow(QWidget):
    """Simple publisher UI; passphrase entry is masked and never saved in preferences."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        super().__init__()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.setWindowTitle("EffSuite — Publisher Licence Manager — CONFIDENTIAL")
        self.resize(780, 560)
        layout = QVBoxLayout(self)

        header = QLabel(
            "<b>EffSuite Publisher Licence Tool</b><br>"
            "1. Generate an Ed25519 publisher keypair once and keep the private key secure.<br>"
            "2. Distribute the public key with customer builds.<br>"
            "3. Issue signed offline licence files (.efflic) for laboratories and workstations below."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        create_btn = QPushButton("🔑 1. Create a new publisher signing keypair…")
        create_btn.clicked.connect(lambda: self.guard(self.create_key))
        layout.addWidget(create_btn)

        form = QFormLayout()

        self.private_path = QLineEdit()
        choose = QPushButton("Choose private key…")
        choose.clicked.connect(self.choose_private)
        row1 = QHBoxLayout()
        row1.addWidget(self.private_path, 1)
        row1.addWidget(choose)
        form.addRow("Publisher private key (.pem)", row1)

        self.licensee = QLineEdit()
        self.licensee.setPlaceholderText("Name of the customer, facility, or laboratory")
        form.addRow("Licensed to (Organization)", self.licensee)

        self.edition = QComboBox()
        self.edition.addItems(["laboratory", "standard", "enterprise"])
        form.addRow("Licence edition", self.edition)

        self.max_version = QLineEdit()
        self.max_version.setPlaceholderText("Optional: e.g. 1.99.999 (blank allows all versions)")
        form.addRow("Version limit", self.max_version)

        self.duration = QComboBox()
        self.duration.addItems(
            ["30 calendar days", "90 calendar days", "1 calendar year", "2 calendar years", "Custom last valid day"]
        )
        self.duration.setCurrentIndex(2)
        form.addRow("Licence duration", self.duration)

        self.expiry = QDateEdit(self.utc_today().addYears(1).addDays(-1))
        self.expiry.setCalendarPopup(True)
        self.expiry.setDisplayFormat("yyyy-MM-dd")
        self.duration.currentIndexChanged.connect(self.duration_changed)
        self.expiry.dateChanged.connect(self.expiry_changed)
        form.addRow("Valid through (inclusive)", self.expiry)

        self.expiry_preview = QLabel()
        self.expiry_preview.setWordWrap(True)
        form.addRow("Exact expiry", self.expiry_preview)

        self.installation = QLineEdit()
        self.installation.setPlaceholderText("Optional: leave blank for an unbound laboratory licence")
        req_btn = QPushButton("Load customer request…")
        req_btn.clicked.connect(lambda: self.guard(self.load_request))
        row2 = QHBoxLayout()
        row2.addWidget(self.installation, 1)
        row2.addWidget(req_btn)
        form.addRow("Workstation ID (binding)", row2)

        layout.addLayout(form)

        issue_btn = QPushButton("📝 2. Issue and sign customer licence file (.efflic)…")
        issue_btn.setStyleSheet("font-weight: bold; padding: 6px; font-size: 13px;")
        issue_btn.clicked.connect(lambda: self.guard(self.issue_file))
        layout.addWidget(issue_btn)

        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.update_expiry_preview()

    def utc_today(self) -> QDate:
        d = self.clock().astimezone(timezone.utc).date()
        return QDate(d.year, d.month, d.day)

    def duration_changed(self, index: int) -> None:
        today = self.utc_today()
        if index == 0:
            self.expiry.setDate(today.addDays(29))
        elif index == 1:
            self.expiry.setDate(today.addDays(89))
        elif index == 2:
            self.expiry.setDate(today.addYears(1).addDays(-1))
        elif index == 3:
            self.expiry.setDate(today.addYears(2).addDays(-1))
        self.update_expiry_preview()

    def expiry_changed(self, _date: QDate) -> None:
        self.update_expiry_preview()

    def update_expiry_preview(self) -> None:
        qdate = self.expiry.date()
        pydate = datetime(qdate.year(), qdate.month(), qdate.day()).date()
        cutoff = expiry_after_day(pydate)
        self.expiry_preview.setText(
            f"Active through <b>{readable_day(pydate)}</b> (expires at <b>{readable_utc(cutoff)}</b>)"
        )

    def guard(self, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as exc:
            QMessageBox.critical(self, "Licensing Error", str(exc))

    def choose_private(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self, "Choose Publisher Private Key", "", "PEM Private Key (*.pem);;All Files (*.*)"
        )
        if file:
            self.private_path.setText(file)

    def create_key(self) -> None:
        priv, _ = QFileDialog.getSaveFileName(
            self, "Save New Encrypted Private Key", "effsuite_publisher_private.pem", "PEM Private Key (*.pem)"
        )
        if not priv:
            return
        pub, _ = QFileDialog.getSaveFileName(
            self, "Save Public Verification Key", "effsuite_publisher_public.json", "JSON Public Key (*.json)"
        )
        if not pub:
            return
        pw, ok = QInputDialog.getText(
            self, "Private Key Passphrase", "Enter a passphrase (min 8 chars) to encrypt the private key:", QLineEdit.EchoMode.Password
        )
        if not ok or not pw:
            return
        pw_confirm, ok = QInputDialog.getText(
            self, "Confirm Passphrase", "Re-enter passphrase to confirm:", QLineEdit.EchoMode.Password
        )
        if not ok or pw != pw_confirm:
            QMessageBox.warning(self, "Passphrase Mismatch", "The passphrases did not match.")
            return

        generate_keys(Path(priv), Path(pub), pw)
        self.private_path.setText(priv)
        QMessageBox.information(
            self,
            "Keypair Generated",
            f"Publisher keypair generated successfully!\n\nPrivate key: {priv}\nPublic key: {pub}\n\nKeep the private key safe and confidential.",
        )

    def load_request(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Customer Activation Request", "", "Activation Request (*.req *.json);;All Files (*.*)"
        )
        if file:
            data = read_request(Path(file))
            inst = data.get("installation_id")
            if inst:
                self.installation.setText(inst)
                self.status.setText(f"Loaded workstation ID: {inst}")

    def issue_file(self) -> None:
        priv_str = self.private_path.text().strip()
        if not priv_str or not Path(priv_str).is_file():
            QMessageBox.warning(self, "Missing Key", "Please select an existing publisher private key (.pem).")
            return
        name = self.licensee.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Licensee", "Please enter the laboratory or customer name.")
            return

        out, _ = QFileDialog.getSaveFileName(
            self, "Save Customer Licence", f"{name.replace(' ', '_')}.efflic", "EffSuite Licence (*.efflic)"
        )
        if not out:
            return

        pw, ok = QInputDialog.getText(
            self, "Unlock Private Key", "Enter passphrase for publisher private key:", QLineEdit.EchoMode.Password
        )
        if not ok or not pw:
            return

        key = load_private(Path(priv_str), pw)
        qdate = self.expiry.date()
        pydate = datetime(qdate.year(), qdate.month(), qdate.day()).date()
        cutoff = expiry_after_day(pydate)

        inst_id = self.installation.text().strip() or None
        max_ver = self.max_version.text().strip() or None

        lic_data = issue(
            key,
            licensee=name,
            expires_at=utc_text(cutoff),
            edition=self.edition.currentText(),
            max_version=max_ver,
            installation_id=inst_id,
        )
        write_new(Path(out), lic_data, 0o644)
        QMessageBox.information(
            self, "Licence Issued", f"Licence issued successfully for {name}!\n\nSaved to: {out}"
        )
        self.status.setText(f"Issued licence for {name} -> {out}")


def main() -> int:
    app = QApplication(sys.argv)
    window = PublisherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
