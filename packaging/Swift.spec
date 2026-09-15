# Run on macOS with: python -m PyInstaller packaging/Swift.spec
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
modules = ['whisper', 'silero_vad', 'keyring.backends.macOS', 'tiktoken_ext.openai_public']
data = []
for name in ('whisper', 'silero_vad'):
    data += collect_data_files(name)
for name in ('openai-whisper', 'torch', 'tqdm', 'regex', 'requests', 'packaging', 'filelock', 'numpy'):
    data += copy_metadata(name)
hidden = modules + collect_submodules('keyring.backends')
a = Analysis([str(root / 'desktop.py')], pathex=[str(root)], binaries=[], datas=data, hiddenimports=hidden,
             excludes=['matplotlib', 'IPython', 'pytest', 'tkinter', 'chromadb', 'sentence_transformers', 'transformers', 'memory_legacy'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Swift', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, target_arch=None,
          codesign_identity=os.getenv('SWIFT_CODESIGN_IDENTITY'), entitlements_file=str(root / 'packaging' / 'entitlements.plist'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Swift')
app = BUNDLE(coll, name='Swift.app', bundle_identifier='io.github.pearl-natalia.swift-assistant',
             info_plist={
                 'CFBundleShortVersionString': '0.1.0', 'CFBundleVersion': '1',
                 'NSMicrophoneUsageDescription': 'Swift listens to your voice while a voice chat is active.',
                 'NSAppleEventsUsageDescription': 'Swift controls Mac apps when you ask it to perform an action.',
                 'NSHighResolutionCapable': True,
             })
