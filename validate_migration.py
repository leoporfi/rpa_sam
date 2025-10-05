#!/usr/bin/env python3
"""
Script de Validación Post-Migración
Verifica que la nueva estructura funcione correctamente
"""
import sys
import importlib
from pathlib import Path

def test_imports():
    """Prueba imports críticos"""
    print("🧪 Probando imports...")
    
    tests = [
        ("sam", "Paquete principal"),
        ("sam.common", "Módulo común"),
        ("sam.common.config", "Configuración"),
        ("sam.common.database", "Base de datos"),
        ("sam.balanceador", "Servicio Balanceador"),
        ("sam.lanzador", "Servicio Lanzador"),
        ("sam.callback", "Servicio Callback"),
        ("sam.web", "Servicio Web"),
    ]
    
    results = []
    for module_name, description in tests:
        try:
            importlib.import_module(module_name)
            print(f"  ✅ {description}: OK")
            results.append(True)
        except ImportError as e:
            print(f"  ❌ {description}: FALLO")
            print(f"     Error: {e}")
            results.append(False)
    
    return all(results)

def check_structure():
    """Verifica estructura de directorios"""
    print("\n📁 Verificando estructura...")
    
    required = [
        "src/sam/__init__.py",
        "src/sam/common/__init__.py",
        "src/sam/balanceador/__init__.py",
        "src/sam/lanzador/__init__.py",
        "src/sam/callback/__init__.py",
        "src/sam/web/__init__.py",
        "tests/__init__.py",
        "tests/conftest.py",
        "pyproject.toml",
    ]
    
    root = Path.cwd()
    results = []
    
    for path_str in required:
        path = root / path_str
        exists = path.exists()
        results.append(exists)
        status = "✅" if exists else "❌"
        print(f"  {status} {path_str}")
    
    return all(results)

def check_executables():
    """Verifica que los servicios sean ejecutables"""
    print("\n🎯 Verificando módulos ejecutables...")
    
    services = ["balanceador", "lanzador", "callback", "web"]
    results = []
    
    for service in services:
        main_file = Path(f"src/sam/{service}/__main__.py")
        exists = main_file.exists()
        results.append(exists)
        status = "✅" if exists else "❌"
        print(f"  {status} sam.{service}")
    
    return all(results)

def main():
    print("="*60)
    print("🔍 VALIDACIÓN DE MIGRACIÓN SAM")
    print("="*60)
    
    all_passed = True
    
    # Test 1: Imports
    if not test_imports():
        all_passed = False
    
    # Test 2: Estructura
    if not check_structure():
        all_passed = False
    
    # Test 3: Ejecutables
    if not check_executables():
        all_passed = False
    
    # Resultado final
    print("\n" + "="*60)
    if all_passed:
        print("✅ TODAS LAS VALIDACIONES PASARON")
        print("\nPuedes proceder a:")
        print("  1. Ejecutar tests: uv run pytest")
        print("  2. Instalar proyecto: uv pip install -e .")
        print("  3. Probar servicios: uv run -m sam.balanceador")
    else:
        print("❌ ALGUNAS VALIDACIONES FALLARON")
        print("\nRevisa los errores anteriores y:")
        print("  1. Verifica que todos los archivos se movieron correctamente")
        print("  2. Revisa imports problemáticos manualmente")
        print("  3. Consulta el backup en: backup_migration/")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
