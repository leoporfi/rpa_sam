"""Entry point for balanceador service"""
from sam.common.config_loader import ConfigLoader

ConfigLoader.initialize_service("balanceador")
from .run_balanceador import main

if __name__ == "__main__":
    main()
