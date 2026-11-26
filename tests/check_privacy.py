#!/usr/bin/env python3
"""Check the privacy-sensitive runtime source against known regressions."""
import os
import sys
import traceback
import re
from pathlib import Path

def CheckPrivacy():

    root = Path(__file__).resolve().parents[1]
    runtimeAssets = [*root.glob('templates/*.ecr'), *root.glob('assets/**/*.js'), *root.glob('assets/**/*.css')]
    for path in runtimeAssets:
        content = path.read_text()
        if path.suffix == '.ecr':
            assert not re.search(r'<(?:link|script|img|audio|video)\b[^>]*(?:src|href)\s*=\s*["\x27](?:https?:)?//', content, re.I), str(path)
        assert not re.search(r'url\(\s*["\x27]?(?:https?:)?//', content, re.I), str(path)
        assert not re.search(r'["\x27]https?://(?:fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|unpkg)\.', content), str(path)
    for path in root.glob('src/**/*.cr'):
        content = path.read_text()
        assert 'Access-Control-Allow-Origin' not in content, str(path)
        assert not re.search(r'Log\.\w+\s*\{[^\n]*(?:Received WebSocket message|Writing (?:absolute )?mouse report|Writing key (?:press|release)|Sending text:|Text char|unsupported character:)', content), str(path)
    for name in ('pico.min.css', 'fonts.css', 'Oxanium.ttf', 'MaterialIcons-Regular.ttf'):
        assert (root / 'assets' / 'vendor' / name).is_file(), name
    assert not (root / 'kvm_server').exists()
    print('Static privacy regression checks passed.')

if __name__ == '__main__':
    try:
        CheckPrivacy()
    except Exception as e:
        trbk = f'Exception! {e.__class__.__name__}: {e}\n{traceback.format_exc()}'
        print(trbk)
        sys.exit(1)
