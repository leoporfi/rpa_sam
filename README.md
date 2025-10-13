# **SAM: Sistema Automático de Robots**

SAM es un ecosistema de orquestación de RPA (Robotic Process Automation) diseñado para gestionar, lanzar, balancear y monitorear la ejecución de robots construidos sobre la plataforma Automation 360 (Automation Anywhere). Su arquitectura modular y desacoplada permite una alta escalabilidad y un mantenimiento sencillo.

## **Arquitectura**

El sistema está compuesto por cuatro microservicios independientes que se comunican a través de una base de datos central:

1. **Servicio Lanzador (sam.lanzador):** El corazón del sistema. Se encarga de consultar la base de datos en busca de robots pendientes de ejecución, los despliega a través de la API de A360 y sincroniza su estado final.  
2. **Servicio Balanceador (sam.balanceador):** Monitorea la carga de trabajo y los recursos disponibles (pools de bots y máquinas) para tomar decisiones estratégicas sobre la asignación de licencias y la priorización de ejecuciones.  
3. **Servicio de Callback (sam.callback):** Un servidor web FastAPI que expone un endpoint seguro para recibir notificaciones de A360 cuando un robot finaliza, permitiendo una actualización de estado casi en tiempo real.  
4. **Interfaz Web (sam.web):** Un dashboard interactivo construido con ReactPy y FastAPI que permite a los usuarios monitorear el estado de los robots, gestionar pools y visualizar el rendimiento del sistema.

## **🚀 Puesta en Marcha (Entorno de Desarrollo)**

Sigue estos pasos para configurar y ejecutar el proyecto en tu máquina local.

### **1. Prerrequisitos**

* **Python 3.8+**  
* **Git**  
* **UV:** Un instalador y gestor de paquetes de Python extremadamente rápido. Se recomienda su uso para este proyecto.  
  pip install uv

### **2. Instalación**

1. **Clona el repositorio:**  
   git clone <URL_DEL_REPOSITORIO>  
   cd rpa_sam

2. **Crea y activa el entorno virtual:**  
   uv venv  
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate

3. Instala las dependencias:  
   Este comando instala el proyecto en modo editable (-e .) junto con todas las dependencias de desarrollo ([dev]).  
   uv pip install -e .[dev]

4. Configura las variables de entorno:  
   Copia el archivo de ejemplo y rellénalo con tus credenciales y configuraciones locales.  
   copy .env.example .env  
   # Abre el archivo .env y edita los valores

### **3. Ejecución de los Servicios**

Cada servicio se ejecuta como un módulo de Python. Abre una terminal separada para cada servicio que necesites ejecutar.

* **Ejecutar el Servicio Lanzador:**  
  uv run -m sam.lanzador

* **Ejecutar el Servicio Balanceador:**  
  uv run -m sam.balanceador

* **Ejecutar el Servidor de Callback:**  
  uv run -m sam.callback

* **Ejecutar la Interfaz Web:**  
  uv run -m sam.web

### **4. Ejecución de Pruebas**

Para validar la integridad del código, ejecuta la suite de pruebas con el siguiente comando:

uv run pytest

## **📦 Despliegue en Producción (Windows)**

Para instalar los servicios de forma persistente en un servidor Windows, se proporciona un script de PowerShell que utiliza **NSSM (Non-Sucking Service Manager)**.

1. **Prerrequisitos en el Servidor:**  
   * Asegúrate de que nssm.exe esté instalado y accesible en el PATH del sistema.  
   * Clona el repositorio y configura el archivo .env con los valores de producción.  
2. Ejecución del Script:  
   Abre una terminal de PowerShell como Administrador y ejecuta el script de instalación:  
   .\scripts\install_services.ps1

   El script se encargará de detener y eliminar versiones antiguas de los servicios antes de instalar y configurar las nuevas, apuntando a los logs en C:\RPA\Logs\SAM.