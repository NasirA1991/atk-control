PREFIX ?= /usr
DESTDIR ?=

.PHONY: all run demo test compile install uninstall appimage flatpak clean

all: run

run:
	./atk-control

demo:
	./atk-control --demo

test:
	python3 -m unittest discover -s tests -v

compile:
	python3 -m compileall -q atk_control

install:
	./install.sh --prefix "$(PREFIX)"

uninstall:
	./uninstall.sh

appimage:
	./packaging/appimage/build.sh 0.2.0 dist

flatpak:
	./packaging/flatpak/build.sh 0.2.0 dist

clean:
	rm -rf dist build AppDir .flatpak-builder screenshots
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
