# Maintainer: Nasir A. <112448715+NasirA1991@users.noreply.github.com>
# Local build: run `makepkg -si` inside this repository.
pkgname=atk-control
pkgver=0.8.0
pkgrel=1
pkgdesc="Native GTK4/libadwaita configuration tool for ATK/VXE gaming mice"
arch=('any')
url="https://github.com/NasirA1991/atk-control"
license=('MIT')
depends=('python' 'python-gobject' 'gtk4' 'libadwaita' 'python-cairo' 'python-dbus' 'hicolor-icon-theme')
provides=('compx-control')
conflicts=('compx-control' 'compx-control-git' 'atk-control-git')
replaces=('compx-control')
options=('!strip')
# This local PKGBUILD builds the checked-out working tree ($startdir); it has
# no remote source to verify. The published AUR atk-control package pins the
# release tarball and its real SHA-256 (see packaging/aur/atk-control/PKGBUILD.in).
source=()
sha256sums=()

package() {
    cd "$startdir"
    PREFIX=/usr DESTDIR="$pkgdir" ./install.sh
}
