"""Allow `python -m spc ...` without installing anything."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
