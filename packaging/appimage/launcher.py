"""Entry point used inside the AppImage."""
import sys

from atk_control.app import main

if __name__ == "__main__":
    sys.exit(main())
