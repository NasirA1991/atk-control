# Maintainer: Nasir A. <112448715+NasirA1991@users.noreply.github.com>
# Local build: run `makepkg -si` inside this repository.
pkgname=atk-control
pkgver=0.4.0
pkgrel=1
pkgdesc="Native GTK4/libadwaita configuration tool for ATK/VXE gaming mice (MAD R, VXE R1)"
arch=('any')
url="https://github.com/NasirA1991/atk-control"
license=('MIT')
depends=('python' 'python-gobject' 'gtk4' 'libadwaita' 'python-cairo' 'python-dbus' 'hicolor-icon-theme')
provides=('compx-control')
conflicts=('compx-control' 'compx-control-git' 'atk-control-git')
replaces=('compx-control')
options=('!strip')
source=()
sha256sums=()

package() {
    cd "$startdir"
    PREFIX=/usr DESTDIR="$pkgdir" ./install.sh
}
