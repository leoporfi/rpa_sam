#!/usr/bin/env python3
"""
Script de Migración Automática para SAM Project - VERSIÓN 2
Adaptado para el código base actual con imports src.* y ConfigLoader
"""
import os
import re
import shutil
from pathlib import Path
from typing import List

class SAMMigrator:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.src_old = self.root / "src"
        self.src_new = self.root / "src" / "sam"
        self.backup_dir = self.root / "backup_migration"
        
    def create_backup(self):
        """Crea backup completo del proyecto"""
        print("📦 Creando backup...")
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        shutil.copytree(self.src_old, self.backup_dir / "src")
        print(f"✅ Backup creado en: {self.backup_dir}")
    
    def create_new_structure(self):
        """Crea la nueva estructura de carpetas"""
        print("\n📁 Creando nueva estructura...")
        
        # Crear directorio principal sam/
        self.src_new.mkdir(parents=True, exist_ok=True)
        
        # Crear __init__.py principal
        (self.src_new / "__init__.py").write_text(
            '"""SAM - Sistema Automático de Robots"""\n'
            '__version__ = "0.1.0"\n',
            encoding='utf-8'
        )
        
        # Mover servicios
        services = ["balanceador", "callback", "lanzador", "web", "common"]
        for service in services:
            old_path = self.src_old / service
            new_path = self.src_new / service
            
            if old_path.exists():
                print(f"  📦 Moviendo {service}...")
                shutil.move(str(old_path), str(new_path))
                
                # Asegurar que tenga __init__.py
                init_file = new_path / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
        
        print("✅ Estructura creada")
    
    def create_main_modules(self):
        """Crea módulos __main__.py para ejecución"""
        print("\n🎯 Creando módulos __main__.py...")
        
        services_mapping = {
            "balanceador": ("run_balanceador", "main"),
            "lanzador": ("run_lanzador", "main_async"),
            "callback": ("run_callback", "main"),
            "web": ("run_dashboard", "main"),
        }
        
        for service, (run_module, main_func) in services_mapping.items():
            service_path = self.src_new / service
            main_file = service_path / "__main__.py"
            run_file = service_path / f"{run_module}.py"
            
            if run_file.exists():
                # Detectar si es asíncrono
                is_async = "async" in main_func or service == "lanzador"
                
                if is_async:
                    main_content = f'''"""Entry point for {service} service"""
import asyncio
from .{run_module} import {main_func}

if __name__ == "__main__":
    asyncio.run({main_func}())
'''
                else:
                    main_content = f'''"""Entry point for {service} service"""
from .{run_module} import {main_func}

if __name__ == "__main__":
    {main_func}()
'''
                main_file.write_text(main_content, encoding='utf-8')
                print(f"  ✅ Creado __main__.py para {service}")
    
    def update_imports(self):
        """Actualiza todos los imports al nuevo formato"""
        print("\n🔄 Actualizando imports...")
        
        # Patrones de imports a actualizar
        patterns = [
            # Cambiar src.common -> sam.common
            (r'from src\.common\.', 'from sam.common.'),
            (r'import src\.common\.', 'import sam.common.'),
            
            # Cambiar src.balanceador -> sam.balanceador
            (r'from src\.balanceador\.', 'from sam.balanceador.'),
            (r'import src\.balanceador\.', 'import sam.balanceador.'),
            
            # Cambiar src.callback -> sam.callback
            (r'from src\.callback\.', 'from sam.callback.'),
            (r'import src\.callback\.', 'import sam.callback.'),
            
            # Cambiar src.lanzador -> sam.lanzador
            (r'from src\.lanzador\.', 'from sam.lanzador.'),
            (r'import src\.lanzador\.', 'import sam.lanzador.'),
            
            # Cambiar src.web -> sam.web
            (r'from src\.web\.', 'from sam.web.'),
            (r'import src\.web\.', 'import sam.web.'),
        ]
        
        updated_files = []
        
        # Recorrer todos los archivos .py
        for py_file in self.src_new.rglob("*.py"):
            content = py_file.read_text(encoding='utf-8')
            original_content = content
            
            # Aplicar cada patrón
            for old_pattern, new_pattern in patterns:
                content = re.sub(old_pattern, new_pattern, content)
            
            # Si hubo cambios, guardar
            if content != original_content:
                py_file.write_text(content, encoding='utf-8')
                updated_files.append(py_file.relative_to(self.root))
        
        print(f"✅ Actualizados {len(updated_files)} archivos")
        if updated_files:
            print("   Archivos modificados:")
            for f in updated_files[:10]:
                print(f"   - {f}")
            if len(updated_files) > 10:
                print(f"   ... y {len(updated_files) - 10} más")
    
    def simplify_run_scripts(self):
        """Simplifica los scripts run_*.py eliminando código innecesario"""
        print("\n🧹 Simplificando scripts de arranque...")
        
        for run_file in self.src_new.rglob("run_*.py"):
            content = run_file.read_text(encoding='utf-8')
            original_content = content
            
            # 1. Eliminar la sección de manipulación de sys.path
            # Patrón que captura el bloque try-except de configuración inicial
            path_setup_pattern = r'# --- Configuración del Path.*?except.*?sys\.exit\(1\)\n'
            content = re.sub(path_setup_pattern, '', content, flags=re.DOTALL)
            
            # 2. Simplificar la inicialización de ConfigLoader
            # Ya no necesita __file__ con la nueva estructura
            content = re.sub(
                r'ConfigLoader\.initialize_service\(["\'](\w+)["\'],\s*__file__\)',
                r'ConfigLoader.initialize_service("\1")',
                content
            )
            
            # 3. Comentar código de sys.path redundante si queda alguno
            lines = content.split('\n')
            new_lines = []
            in_path_block = False
            
            for line in lines:
                if 'sys.path.insert' in line or 'project_root' in line and 'sys.path' in line:
                    if not line.strip().startswith('#'):
                        new_lines.append(f"# DEPRECATED: {line}")
                        in_path_block = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            content = '\n'.join(new_lines)
            
            if content != original_content:
                run_file.write_text(content, encoding='utf-8')
                print(f"  ✅ Simplificado {run_file.name}")
    
    def update_config_loader(self):
        """Actualiza ConfigLoader para la nueva estructura"""
        print("\n⚙️  Actualizando ConfigLoader...")
        
        config_loader_file = self.src_new / "common" / "utils" / "config_loader.py"
        
        if not config_loader_file.exists():
            print("  ⚠️  config_loader.py no encontrado")
            return
        
        content = config_loader_file.read_text(encoding='utf-8')
        
        # Simplificar _setup_python_path para que confíe en la instalación del paquete
        new_setup_method = '''    @classmethod
    def _setup_python_path(cls) -> None:
        """
        Configura el sys.path para importaciones correctas.
        Con la nueva estructura de paquete, esto es mayormente innecesario
        si el proyecto se instala con 'pip install -e .'
        """
        # Solo agregar src/ si realmente no está instalado como paquete
        src_path = str(cls._project_root / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
'''
        
        # Reemplazar el método _setup_python_path
        content = re.sub(
            r'@classmethod\s+def _setup_python_path\(cls\).*?(?=\n    @classmethod|\n    def [^_]|\nclass |\Z)',
            new_setup_method,
            content,
            flags=re.DOTALL
        )
        
        config_loader_file.write_text(content, encoding='utf-8')
        print("  ✅ ConfigLoader actualizado")
    
    def create_tests_structure(self):
        """Crea estructura de tests fuera de src/"""
        print("\n🧪 Creando estructura de tests...")
        
        tests_dir = self.root / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        # Crear conftest.py
        conftest = tests_dir / "conftest.py"
        conftest.write_text('''"""Pytest configuration and fixtures"""
import sys
from pathlib import Path

# Añadir src/ al path para importaciones
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
''', encoding='utf-8')
        
        # Crear __init__.py
        (tests_dir / "__init__.py").touch()
        
        # Mover tests existentes si los hay
        test_count = 0
        for test_file in self.src_new.rglob("test_*.py"):
            dest = tests_dir / test_file.name
            shutil.move(str(test_file), str(dest))
            test_count += 1
            print(f"  📦 Movido {test_file.name}")
        
        if test_count == 0:
            print("  ℹ️  No se encontraron archivos test_*.py para mover")
        
        print("✅ Estructura de tests creada")
    
    def create_pyproject_toml(self):
        """Crea pyproject.toml actualizado"""
        print("\n📝 Creando pyproject.toml...")
        
        pyproject_content = '''[project]
name = "sam"
version = "0.1.0"
description = "Sistema Automático de Robots - RPA Orchestration"
requires-python = ">=3.8"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "httpx>=0.25.0",
    "pyodbc>=5.0.0",
    "python-dotenv>=1.0.0",
    "urllib3>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-v --cov=sam --cov-report=term-missing"
asyncio_mode = "auto"

[tool.ruff]
line-length = 120
target-version = "py38"
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[project.scripts]
sam-lanzador = "sam.lanzador.run_lanzador:main"
sam-balanceador = "sam.balanceador.run_balanceador:main"
sam-callback = "sam.callback.run_callback:main"
sam-web = "sam.web.run_dashboard:main"
'''
        
        pyproject_file = self.root / "pyproject.toml"
        
        if pyproject_file.exists():
            backup_file = self.root / "pyproject.toml.backup"
            shutil.copy(pyproject_file, backup_file)
            print(f"  ⚠️  pyproject.toml existente respaldado como pyproject.toml.backup")
        
        pyproject_file.write_text(pyproject_content, encoding='utf-8')
        print("✅ pyproject.toml creado")
    
    def cleanup_old_structure(self):
        """Limpia archivos innecesarios"""
        print("\n🧹 Limpiando estructura antigua...")
        
        # Eliminar directorios vacíos en src/
        for item in self.src_old.iterdir():
            if item.is_dir() and item.name != "sam":
                try:
                    item.rmdir()
                    print(f"  🗑️  Eliminado directorio vacío: {item.name}")
                except OSError:
                    print(f"  ⚠️  {item.name} no está vacío, se mantiene")
        
        print("✅ Limpieza completada")
    
    def generate_migration_report(self):
        """Genera reporte de migración"""
        print("\n" + "="*70)
        print(" 📊 REPORTE DE MIGRACIÓN ".center(70, "="))
        print("="*70)
        
        print(f"\n✅ Estructura nueva creada en: {self.src_new}")
        print(f"✅ Backup disponible en: {self.backup_dir}")
        
        print("\n📋 PRÓXIMOS PASOS OBLIGATORIOS:")
        print("\n1️⃣  Instalar el paquete en modo desarrollo:")
        print("   cd", self.root)
        print("   uv pip install -e .")
        
        print("\n2️⃣  Verificar imports:")
        print("   uv run python -c \"import sam; print('✅ Imports OK')\"")
        
        print("\n3️⃣  Probar cada servicio:")
        print("   uv run -m sam.balanceador")
        print("   uv run -m sam.lanzador")
        print("   uv run -m sam.callback")
        print("   uv run -m sam.web")
        
        print("\n4️⃣  Ejecutar tests (si existen):")
        print("   uv run pytest")
        
        print("\n5️⃣  Actualizar scripts NSSM:")
        print("   Aplicación: <ruta_venv>\\Scripts\\python.exe")
        print("   Argumentos: -m sam.lanzador")
        print("   Directorio:", self.root)
        
        print("\n⚠️  CAMBIOS CRÍTICOS A REVISAR MANUALMENTE:")
        print("   • ConfigLoader: Puede necesitar ajustes adicionales")
        print("   • Variables de entorno: Verificar que se cargan correctamente")
        print("   • Rutas hardcodeadas: Buscar referencias a 'src/' en configs")
        
        print("\n6️⃣  Si todo funciona, eliminar backup:")
        print(f"   rm -rf {self.backup_dir}")
        
        print("="*70)
        print("="*70)
    
    def run_migration(self):
        """Ejecuta el proceso completo de migración"""
        print("🚀 INICIANDO MIGRACIÓN DE SAM PROJECT (Versión 2)")
        print("="*70)
        
        try:
            self.create_backup()
            self.create_new_structure()
            self.create_main_modules()
            self.update_imports()
            self.simplify_run_scripts()
            self.update_config_loader()
            self.create_tests_structure()
            self.create_pyproject_toml()
            self.cleanup_old_structure()
            self.generate_migration_report()
            
            print("\n✅ ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!")
            
        except Exception as e:
            print(f"\n❌ ERROR durante la migración: {e}")
            print(f"🔄 Puedes restaurar desde: {self.backup_dir}")
            raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Uso: python migrate_sam_structure_v2.py /ruta/al/proyecto/sam")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    if not Path(project_path).exists():
        print(f"❌ El directorio no existe: {project_path}")
        sys.exit(1)
    
    print(f"📂 Proyecto detectado: {project_path}")
    response = input("¿Continuar con la migración? (s/n): ")
    
    if response.lower() != 's':
        print("❌ Migración cancelada")
        sys.exit(0)
    
    migrator = SAMMigrator(project_path)
    migrator.run_migration()
