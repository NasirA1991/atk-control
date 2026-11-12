PREFIX ?= /usr
DESTDIR ?=
VERSION := $(shell python3 -c 'from atk_control.config import VERSION; print(VERSION)')

.PHONY: all run demo test verify compile install uninstall appimage flatpak clean

all: run

run:
	./atk-control

demo:
	./atk-control --demo

test:
	python3 -m unittest discover -s tests -v

verify:
	./scripts/verify-device.sh

compile:
	python3 -m compileall -q atk_control

install:
	./install.sh --prefix "$(PREFIX)"

uninstall:
	./uninstall.sh

appimage:
	./packaging/appimage/build.sh $(VERSION) dist

flatpak:
	./packaging/flatpak/build.sh $(VERSION) dist

clean:
	rm -rf dist build AppDir .flatpak-builder screenshots
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
