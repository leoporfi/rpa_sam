# sam/web/__main__.py
"""Entry point for web service"""
from sam.common.config_loader import ConfigLoader

ConfigLoader.initialize_service("interfaz_web")
from .run_dashboard import main

if __name__ == "__main__":
    main()
