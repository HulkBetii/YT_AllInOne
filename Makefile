PYTHON ?= python
PIP ?= pip

.PHONY: dev test build-win build-mac icon

dev:
	$(PIP) install -r yt_allinone/requirements.txt

test:
	$(PYTHON) -m pytest -q

build-win:
	$(MAKE) icon
	cd yt_allinone && pyinstaller --noconfirm yt_allinone.spec

build-mac:
	$(MAKE) icon
	cd yt_allinone && pyinstaller --noconfirm yt_allinone.spec

icon:
	$(PYTHON) - <<'PY'
import os, sys
from PIL import Image
png_path = os.path.join('yt_allinone', 'icon.png')
ico_dir = os.path.join('yt_allinone', 'assets')
ico_path = os.path.join(ico_dir, 'icon.ico')
os.makedirs(ico_dir, exist_ok=True)
img = Image.open(png_path).convert('RGBA')
sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128), (256,256)]
img.save(ico_path, sizes=sizes)
print('Wrote', ico_path)
PY

