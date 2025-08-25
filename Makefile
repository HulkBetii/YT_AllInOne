PYTHON ?= python
PIP ?= pip

.PHONY: dev test build-win build-mac

dev:
	$(PIP) install -r yt_allinone/requirements.txt

test:
	$(PYTHON) -m pytest -q

build-win:
	pyinstaller --noconfirm --onefile --name yt-allinone-cli yt_allinone/src/app_cli.py
	pyinstaller --noconfirm --windowed --name yt-allinone-gui yt_allinone/src/app_gui.py

build-mac:
	pyinstaller --noconfirm --onefile --name yt-allinone-cli yt_allinone/src/app_cli.py
	pyinstaller --noconfirm --windowed --name yt-allinone-gui yt_allinone/src/app_gui.py

