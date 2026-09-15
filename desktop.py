"""Entry point for the downloadable Mac app; no developer secrets are bundled."""
import multiprocessing
import os
import sys

from runtime_paths import data_dir, load_settings, settings_path

SERVICE = 'Swift Voice Assistant'
KEY_NAMES = ('GEMINI_API_KEY', 'ELEVENLABS_API_KEY', 'WEATHER_API')

def configure(parent=None, required=False):
    import json
    import keyring
    from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox
    dialog = QDialog(parent)
    dialog.setWindowTitle('Swift · Settings')
    dialog.setMinimumWidth(440)
    layout = QFormLayout(dialog)
    note = QLabel('Your Mac handles microphone input and native app actions. Gemini receives your requests and relevant context; ElevenLabs can provide the voice. Keys are saved in your macOS Keychain.')
    note.setWordWrap(True)
    layout.addRow(note)
    settings = load_settings()
    name = QLineEdit(settings.get('user_first_name', ''))
    layout.addRow('Your first name', name)
    fields = {}
    for key, label in zip(KEY_NAMES, ('Gemini API key', 'ElevenLabs key (optional)', 'WeatherAPI key (optional)')):
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setPlaceholderText('Saved · leave blank to keep' if os.getenv(key) else 'Paste your key')
        fields[key] = field
        layout.addRow(label, field)
    extra = QLabel('Start voice chat to allow the microphone. macOS may ask for Automation or Accessibility access when you request native actions. Local speech models download on first use.')
    extra.setWordWrap(True)
    layout.addRow(extra)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    layout.addRow(buttons)
    def save():
        if not (fields['GEMINI_API_KEY'].text().strip() or os.getenv('GEMINI_API_KEY')):
            QMessageBox.information(dialog, 'Gemini key needed', 'Add a Gemini API key to enable Swift.')
            return
        try:
            for key, field in fields.items():
                value = field.text().strip()
                if value:
                    keyring.set_password(SERVICE, key, value)
                    os.environ[key] = value
            settings['user_first_name'] = name.text().strip()
            settings_path().write_text(json.dumps(settings, indent=2))
        except Exception:
            QMessageBox.warning(dialog, 'Could not save', 'Settings could not be saved. Check that your login Keychain is unlocked and try again.')
            return
        dialog.accept()
    buttons.accepted.connect(save)
    buttons.rejected.connect(dialog.reject)
    return dialog.exec_() == QDialog.Accepted

def main():
    if sys.platform != 'darwin':
        raise SystemExit('Swift desktop runs on macOS. Use web_app.py for the Replit browser demo.')
    data_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('HF_HOME', str(data_dir() / 'models' / 'huggingface'))
    os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(data_dir() / 'models' / 'tiktoken'))
    from dotenv import load_dotenv
    load_dotenv(data_dir() / '.env')
    import keyring
    for key in KEY_NAMES:
        if not os.getenv(key):
            try:
                value = keyring.get_password(SERVICE, key)
                if value:
                    os.environ[key] = value
            except Exception:
                pass
    from PyQt5.QtWidgets import QApplication, QPushButton
    app = QApplication(sys.argv)
    app.setApplicationName('Swift')
    if not os.getenv('GEMINI_API_KEY') and not configure(required=True):
        return 0
    from ui import SwiftWindow
    window = SwiftWindow()
    settings_button = QPushButton('Settings')
    settings_button.clicked.connect(lambda: configure(window))
    window.layout().itemAt(0).widget().layout().addWidget(settings_button)
    window.show()
    return app.exec_()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
