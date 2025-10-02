# **Proyecto SAM: Sistema Automático de Robots**

## **📜 Visión General**

SAM (Sistema Automático de Robots) es un proyecto integral diseñado para la implementación, distribución y orquestación automática de robots RPA (Robotic Process Automation) en máquinas virtuales (VMs). El sistema se compone de cuatro servicios independientes que operan en conjunto y se ejecutan de forma continua, gestionados a través de una configuración centralizada y un conjunto de módulos comunes que garantizan la estabilidad y mantenibilidad del ecosistema.  
SAM centraliza la gestión de robots, sincroniza información de forma inteligente con Automation Anywhere A360 (AA360), lanza ejecuciones según la demanda o programaciones, y optimiza la asignación de recursos (VMs) basándose en la carga de trabajo pendiente, segmentando los recursos en pools dedicados o generales para un control granular. Adicionalmente, cuenta con una interfaz web de mantenimiento para gestionar la configuración y las operaciones del sistema directamente desde un navegador.

## **🚀 Servicios Principales**

El proyecto SAM se articula en torno a los siguientes servicios independientes:

### **🤖 Servicio Lanzador**

Actúa como el brazo ejecutor y el cerebro de sincronización con el Control Room de AA360. Es un servicio multifacético con tres responsabilidades clave que se ejecutan en ciclos independientes y configurables:

* **Sincronización Inteligente de Tablas Maestras**: Mantiene las tablas dbo.Robots y dbo.Equipos de SAM actualizadas con la realidad de AA360.  
  * **Sincronización de Equipos (VMs)**: Obtiene la lista de *devices* conectados desde A360, cruza la información con los datos de los usuarios asignados para determinar la licencia (ATTENDEDRUNTIME, etc.) y calcula un estado de actividad (Activo_SAM) antes de actualizar la tabla dbo.Equipos.  
  * **Sincronización de Robots**: Importa únicamente los *taskbots* que cumplen con criterios específicos de nombre y ubicación en el repositorio de A360.  
* **Lanzamiento de Robots**: Es el núcleo ejecutor del servicio.  
  * **Lógica Centralizada en BD**: Su comportamiento se basa en los resultados del Stored Procedure dbo.ObtenerRobotsEjecutables, que determina qué robots deben ejecutarse en cada momento, ya sea por programación o por asignación dinámica del balanceador.  
  * **Ejecución Concurrente y con Reintentos**: Lanza múltiples robots en paralelo utilizando un ThreadPoolExecutor.  
  * **Pausa Operacional**: Se puede configurar una ventana de tiempo durante la cual el servicio no iniciará nuevas ejecuciones.  
* **Conciliación de Estados**: De forma periódica, el Conciliador revisa las ejecuciones que figuran como activas en la base de datos de SAM. Consulta su estado real en A360 y actualiza los registros locales. Si una ejecución ya no se encuentra en la API de A360 (posiblemente finalizada hace tiempo), se marca con el estado UNKNOWN para evitar que quede indefinidamente "activa".

### **⚖️ Servicio Balanceador**

El servicio **Balanceador** se encarga de la gestión estratégica e inteligente de los recursos (VMs), asignándolos dinámicamente a los robots en función de la carga de trabajo real. Su objetivo es maximizar la eficiencia y el rendimiento del clúster de RPA.

#### **Gestión de Pools de Recursos y Aislamiento Configurable (NUEVO)**

**El sistema de balanceo opera sobre una jerarquía de pools de recursos, ofreciendo ahora un control total sobre el aislamiento de estos, que puede ser configurado.**

* **Pools Dedicados**: Es posible crear grupos nombrados de recursos (ej. "Pool de Contabilidad"). Un **Pool Dedicado** consiste en un conjunto específico de **Equipos** (VMs) y **Robots**.  
* **Pool General**: Cualquier robot o equipo que **no** esté asignado a un pool específico (PoolId IS NULL) pertenece automáticamente al Pool General.  
* **Adquisición de Carga de Trabajo**: El sistema determina la cantidad de "tickets" o tareas pendientes para cada robot obteniendo información de **dos fuentes de datos distintas de forma concurrente**.

#### **Modos de Operación del Balanceador (NUEVO)**

El comportamiento del balanceo entre pools se controla mediante la variable de entorno BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO.

* **1. Modo de Aislamiento Estricto (por defecto)**  
  * **Configuración**: BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO=True (o si la variable no está definida).  
  * **Comportamiento**: Los robots asignados a un **Pool Dedicado** operarán **exclusivamente** con los equipos de ese mismo pool. Si el pool se queda sin recursos, los robots esperarán a que uno se libere dentro de su propio silo. **No competirán por los recursos del Pool General.**  
* **2. Modo de Desborde Flexible (Overflow)**  
  * **Configuración**: BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO=False.  
  * **Comportamiento**: Los robots de un **Pool Dedicado** **priorizarán** siempre el uso de los equipos de su propio pool. Sin embargo, si la demanda de trabajo excede los recursos disponibles en su pool, la "demanda restante" de estos robots entrará en una competencia global, ordenada por prioridad, por los equipos que hayan quedado **libres en el Pool General**.


#### **Algoritmo de Balanceo Multifásico**

El núcleo del servicio es su algoritmo de balanceo, que opera en ciclos:

* **Etapa 1: Limpieza Global**: Antes de cualquier cálculo, el sistema valida **todas** las asignaciones dinámicas existentes. Libera recursos de robots inactivos, offline o asignados a equipos fuera de su pool (si el aislamiento estricto está activo).  
* **Etapa 2: Balanceo Interno de Pools**: El algoritmo itera sobre cada pool (dedicados y el general) y, usando **únicamente los recursos de ese pool**, satisface los mínimos de equipos requeridos y desasigna los excedentes.  
* **Etapa 3: Asignación Global por Demanda Adicional y Desborde**: Se calcula la demanda de equipos no cubierta para **todos los robots que tienen permitido participar en esta fase** (todos si el aislamiento es flexible, solo los del Pool General si es estricto). Esta demanda se satisface utilizando los equipos libres restantes del **Pool General**, ordenados por la PrioridadBalanceo de cada robot.

#### **Mecanismos de Control y Auditoría**

* **Mecanismo de Enfriamiento (CoolingManager)**: Previene el "thrashing" (asignar y desasignar recursos a un mismo robot de forma repetida y frecuente). Impone un período de enfriamiento después de una operación, el cual puede ser ignorado si se detecta una variación drástica en la carga de tickets.  
* **Registro Histórico (HistoricoBalanceoClient)**: Cada decisión de asignación o desasignación se registra en la tabla dbo.HistoricoBalanceo, incluyendo el PoolId afectado para una auditoría detallada.

### **📞 Servicio de Callbacks**

Un servidor web ligero y dedicado cuya única responsabilidad es escuchar notificaciones (callbacks) en tiempo real enviadas por AA360 cuando un robot finaliza su ejecución.

* **API Segura y Definida**: El endpoint está formalmente definido por una especificación **OpenAPI (swagger.yaml)**. Requiere un token de seguridad en el encabezado X-Authorization para validar que la llamada es legítima.  
* **Procesamiento Inmediato**: Al recibir un callback válido, actualiza inmediatamente el estado de la ejecución en la tabla dbo.Ejecuciones.  
* **Servidor de Producción**: Utiliza un servidor WSGI de producción (waitress) para manejar múltiples peticiones concurrentes.

### **🖥️ Interfaz Web de Mantenimiento**

Una aplicación web que provee una interfaz de usuario para la administración y monitorización del sistema SAM.

* **Gestión de Robots**: Permite visualizar, filtrar y modificar las propiedades de los robots (Activo, EsOnline, PrioridadBalanceo, etc.).  
* **Gestión de Asignaciones**: Ofrece un modal interactivo para asignar o desasignar equipos (VMs) a un robot de forma manual (reservas).  
* **Gestión de Programaciones**: Interfaz completa para crear, visualizar, editar y eliminar programaciones de ejecución.  
* **(Futuro) Gestión de Pools de Recursos**: Se añadirán interfaces para crear, modificar y eliminar pools, así como para asignar robots y equipos a dichos pools.

## **🛠️ Características Técnicas Clave**

* **Módulos Comunes Centralizados**: Directorio common con utilidades compartidas:  
  * **Gestión de Configuración Jerárquica**: Carga desde archivos .env a nivel de proyecto y de servicio.  
  * **Data Access Layer (DatabaseConnector)**: Conexiones thread-safe, reconexión automática y **reintentos con backoff exponencial** para errores transitorios de base de datos (ej. deadlocks).  
  * **Logging de Producción**: Con rotación de archivos segura para entornos Windows.  
* **Integración con Automation Anywhere A360**: Cliente API con gestión de token automática y paginación completa.  
* **Procesamiento Concurrente**: Uso de ThreadPoolExecutor para paralelizar tareas de I/O.  
* **API Segura para Callbacks**: Basada en OpenAPI y con autenticación por token.  
* **Cierre Controlado (Graceful Shutdown)**: Manejo de señales del sistema para finalizar tareas de forma segura.

## **📂 Estructura del Proyecto**

SAM_PROJECT_ROOT/  
├── src/  
│   ├── balanceador/             # Código del Servicio Balanceador  
│   │   ├── clients/  
│   │   ├── database/  
│   │   └── service/  
│   ├── callback/                # Código del Servicio de Callbacks  
│   │   └── service/  
│   ├── interfaz_web/           # Código de la Interfaz Web de Mantenimiento  
│   │   ├── components/  
│   │   ├── hooks/  
│   │   └── services/  
│   ├── lanzador/                # Código del Servicio Lanzador  
│   │   ├── clients/  
│   │   └── service/  
│   └── common/                  # Módulos compartidos por todos los servicios  
│       ├── database/  
│       └── utils/  
├── .env                         # Archivo principal de configuración  
├── requirements.txt             # Dependencias Python  
├── SAM.sql                      # Script DDL para la base de datos SAM  
└── README.md                    # Este archivo

## **📋 Prerrequisitos**

* Python 3.8 o superior.  
* Acceso a una instancia de Automation Anywhere A360 Control Room.  
* Una base de datos SQL Server con el esquema de SAM.sql aplicado.  
* Un servidor SMTP accesible para el envío de alertas por correo.  
* **NSSM (Non-Sucking Service Manager)** o una herramienta similar para ejecutar los servicios en producción en Windows.

## **⚙️ Configuración e Instalación**

1. **Clonar/Descomprimir** el repositorio.  
2. **Crear y activar un entorno virtual** de Python.  
3. **Instalar Dependencias:**  
   pip install -r requirements.txt

4. **Configurar .env**: Crea un archivo .env en la raíz del proyecto y completa todas las variables. **Añade BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO (True o False) si deseas controlar el comportamiento del balanceador.**  
5. **Base de Datos**: Aplica el script SAM.sql a tu instancia de SQL Server.  
6. **Firewall**: Asegura que los puertos de los servicios de Callbacks e Interfaz Web estén abiertos.

## **▶️ Despliegue y Ejecución (NSSM)**

Para un entorno de producción, se recomienda ejecutar los **cuatro servicios** como servicios de Windows utilizando NSSM.

1. **Servicio SAM-Lanzador:**  
   * **Aplicación:** python.exe (ruta completa).  
   * **Argumentos:** C:\ruta\a\SAM_PROJECT_ROOT\src\lanzador\run_lanzador.py.  
   * **Directorio de Inicio:** C:\ruta\a\SAM_PROJECT_ROOT.  
2. **Servicio SAM-Balanceador:**  
   * **Aplicación:** python.exe.  
   * **Argumentos:** C:\ruta\a\SAM_PROJECT_ROOT\src\balanceador\run_balanceador.py.  
   * **Directorio de Inicio:** C:\ruta\a\SAM_PROJECT_ROOT.  
3. **Servicio SAM-Callback:**  
   * **Aplicación:** python.exe.  
   * **Argumentos:** C:\ruta\a\SAM_PROJECT_ROOT\src\callback\run_callback.py.  
   * **Directorio de Inicio:** C:\ruta\a\SAM_PROJECT_ROOT.  
4. **Servicio SAM-InterfazWeb:**  
   * **Aplicación:** python.exe.  
   * **Argumentos:** C:\ruta\a\SAM_PROJECT_ROOT\src\interfaz_web\run_interfaz_web.py.  
   * **Directorio de Inicio:** C:\ruta\a\SAM_PROJECT_ROOT.

   

## **🐛 Troubleshooting Básico**

* **Verificar Logs**: Revisa los archivos de log generados por cada servicio. Aumenta el LOG_LEVEL a DEBUG en .env para obtener más detalles.  
* **Conectividad de Base de Datos**: Asegúrate de que las credenciales y los nombres de host/instancia sean correctos.  
* **Callbacks No Llegan**:  
  * La URL de callback en A360 debe ser públicamente accesible.  
  * El CALLBACK_TOKEN debe coincidir entre .env y A360.  
* **Lanzador no inicia robots**:  
  * Verifica que no estés en la ventana de Pausa de Lanzamiento.  
  * Asegúrate de que la sincronización de tablas esté funcionando y que los robots y equipos tengan el estado Activo correcto.  
* **Balanceador no asigna/desasigna VMs**: Revisa los logs del Balanceador para entender las decisiones del algoritmo y el CoolingManager. Verifica la carga de trabajo, la configuración de los robots (MinEquipos, PrioridadBalanceo) y el estado BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO.  
* **Interfaz Web no carga o no responde**: Asegúrate de que el servicio esté corriendo y revisa sus logs en busca de errores de conexión o del servidor.