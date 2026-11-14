"""Compatibility launcher NAME only; still requires unified V6 firmware/protocol."""
from app import main
from backend import BackendError
if __name__ == '__main__':
    try: main()
    except BackendError as error: raise SystemExit(str(error)) from None
    except KeyboardInterrupt: pass
