# **Especificaciones de Comportamiento del Sistema (BDD)**

Estos documentos, escritos en lenguaje Gherkin, definen el comportamiento esperado de cada servicio del ecosistema SAM. Sirven como una "documentación viva" que puede ser utilizada tanto para el entendimiento del equipo como para la automatización de pruebas de aceptación.

### **Feature: Orquestación de Robots (Servicio Lanzador)**

@core @lanzador

Como motor principal del sistema, el **Servicio Lanzador** es responsable de sincronizar los datos maestros con A360, desplegar los robots según la demanda y conciliar el estado de las ejecuciones.

Background:  
Given una conexión a la base de datos de SAM  
And un cliente API para comunicarse con Automation Anywhere A360  
And una configuración que define los intervalos de ejecución de los ciclos  
Scenario: Sincronización de Entidades desde A360  
El servicio debe mantener las tablas maestras actualizadas con la realidad del Control Room.  
Given existe un nuevo "taskbot" en A360 llamado "P123\_ProcesoFacturas"  
And existe un nuevo "device" conectado en A360  
When el ciclo de sincronización se ejecuta  
Then el servicio invoca al cliente de A360 para obtener la lista de robots y equipos  
And se inserta un nuevo registro para "P123\_ProcesoFacturas" en la tabla \`Robots\` de SAM  
And se inserta un nuevo registro para el equipo en la tabla \`Equipos\` de SAM

Scenario: Lanzamiento de Robots Pendientes  
El servicio debe identificar y desplegar los robots que están listos para ejecutarse.  
Given el Stored Procedure \`ObtenerRobotsEjecutables\` retorna el "Robot\_X"  
And el "Robot\_X" tiene un \`id\_robot\` de 1  
And el "Robot\_X" requiere el \`id\_equipo\` de 5  
When el ciclo de lanzamiento se ejecuta  
Then el servicio llama a la API de A360 para desplegar el bot con \`id\_robot=1\` en el \`id\_equipo=5\`  
And el estado del "Robot\_X" en la base de datos se actualiza a "RUNNING"  
And se guarda el \`deploymentId\` devuelto por la API

### **Feature: Gestión Dinámica de Recursos (Servicio Balanceador)**

@core @balanceador

Como orquestador táctico, el **Servicio Balanceador** debe asignar y desasignar recursos (VMs) de forma inteligente para optimizar su uso basándose en la carga de trabajo.

Background:  
Given un conjunto de equipos disponibles para balanceo dinámico  
And un conjunto de robots configurados con prioridades y límites de equipos  
And una carga de trabajo definida por la cantidad de tickets pendientes  
Scenario: Asignación de Recursos por Aumento de Demanda  
Si la carga de trabajo de un robot supera la capacidad actual, el sistema debe asignarle nuevos recursos.  
Given el "Robot\_Contable" tiene 100 tickets pendientes  
And su configuración permite un máximo de 5 equipos  
And actualmente tiene solo 1 equipo asignado  
When el ciclo del balanceador se ejecuta  
Then el sistema identifica una alta demanda y una baja asignación  
And el balanceador asigna 4 equipos adicionales al "Robot\_Contable" desde el pool disponible  
And la decisión de "ASIGNAR\_DEMANDA" se registra en el histórico

### **Feature: Recepción de Notificaciones (Servicio de Callback)**

@security @callback

Como componente de escucha, el **Servicio de Callback** debe exponer un endpoint seguro para recibir notificaciones de A360 y actualizar el estado de las ejecuciones de forma inmediata.

Background:  
Given un servidor FastAPI está corriendo y escuchando peticiones  
And el endpoint /api/callback está disponible para recibir peticiones POST  
Scenario: Rechazo de Petición sin Autenticación  
Cualquier petición que no incluya la clave de API correcta debe ser rechazada.  
Given el servidor requiere una "Clave de API" para la validación  
When se recibe una petición \`POST\` en \`/api/callback\`  
And la petición NO incluye la cabecera \`X-API-KEY\`  
Then el servicio rechaza la petición con un código de estado \`401 Unauthorized\`  
And no se realiza ninguna operación en la base de datos

### **Feature: Interfaz Web de Mantenimiento (Servicio Web)**

@ui @web

Como administrador, necesito una interfaz web para gestionar y monitorizar los robots, pools y recursos del sistema SAM.

Background:  
Given un usuario ha accedido a la Interfaz Web  
And la interfaz se comunica con su backend a través de una API RESTful  
Scenario: Visualizar y filtrar la lista de robots  
El usuario debe poder encontrar robots específicos de forma rápida.  
Given el usuario está en el "Dashboard de Robots" (ruta \`/\`)  
When el usuario escribe "Facturas" en la barra de búsqueda  
And selecciona "Solo Activos" en el filtro de estado  
Then la interfaz realiza una petición \`GET\` al endpoint \`/api/robots?name=Facturas\&active=true\`  
And la tabla de robots se actualiza para mostrar únicamente los robots que coinciden con los filtros  
