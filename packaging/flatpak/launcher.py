"""Entry point used inside the Flatpak sandbox."""
import sys

from compx_control.app import main

if __name__ == "__main__":
    sys.exit(main())
