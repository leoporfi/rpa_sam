# **Documentación Técnica: Servicio Lanzador**

**Módulo:** sam.lanzador

## **1\. Propósito**

El **Servicio Lanzador** es el componente principal del ecosistema SAM. Su única responsabilidad es orquestar el ciclo de vida de las ejecuciones de robots: desde que se marcan como PENDIENTE en la base de datos hasta que se registran como FINALIZADO o ERROR.

Es un servicio de fondo (demonio) que opera en un bucle continuo para asegurar que los robots se procesen de manera oportuna.

## **2\. Arquitectura y Componentes**

El servicio sigue un patrón de diseño de **Inyección de Dependencias** y **Separación de Responsabilidades**, donde la clase principal actúa como un orquestador y delega la lógica de negocio a componentes especializados ("cerebros").

### **Componentes Principales**

* **LanzadorService (service/main.py)**:  
  * **Rol:** Orquestador.  
  * **Descripción:** Es la clase principal que gestiona el bucle de ejecución del servicio. No contiene lógica de negocio compleja. Sus tareas son:  
    1. Inicializar y recibir las dependencias (DatabaseConnector, AutomationAnywhereClient).  
    2. Ejecutar un bucle infinito que se repite cada X segundos (configurable).  
    3. Dentro del bucle, invocar secuencialmente a los componentes Desplegador y Sincronizador.  
    4. Gestionar el cierre ordenado (graceful shutdown) para liberar las conexiones.  
* **Desplegador (service/desplegador.py)**:  
  * **Rol:** Cerebro de Despliegue.  
  * **Descripción:** Encapsula toda la lógica para iniciar nuevos robots.  
    1. Recibe el DatabaseConnector y el AutomationAnywhereClient en su constructor.  
    2. Su método run() busca en la base de datos el próximo robot con estado PENDIENTE.  
    3. Si encuentra uno, llama al método deploy\_bot() del cliente de A360.  
    4. Si el despliegue es exitoso, actualiza el estado del robot en la base de datos a EN\_CURSO, almacenando el deploymentId devuelto por la API.  
    5. Si el despliegue falla, actualiza el estado a ERROR.  
* **Sincronizador (service/sincronizador.py)**:  
  * **Rol:** Cerebro de Sincronización.  
  * **Descripción:** Se encarga de verificar el estado de los robots que ya están en ejecución.  
    1. Recibe sus dependencias en el constructor.  
    2. Su método run() busca en la base de datos todos los robots con estado EN\_CURSO.  
    3. Para cada uno, utiliza su deploymentId para consultar el estado del despliegue a través del método get\_deployment\_status() del cliente de A360.  
    4. Actualiza el estado en la base de datos a FINALIZADO o ERROR según la respuesta de la API.

## **3\. Flujo de Datos**

El flujo de trabajo del servicio es un ciclo continuo y predecible:

1. LanzadorService inicia su bucle principal.  
2. Invoca a Desplegador.run().  
3. Desplegador consulta la tabla robots buscando estado \= 'PENDIENTE'.  
4. Si encuentra un robot, lo despliega vía API y actualiza su fila a estado \= 'EN\_CURSO' y deployment\_id \= '...'.  
5. LanzadorService invoca a Sincronizador.run().  
6. Sincronizador consulta la tabla robots buscando estado \= 'EN\_CURSO'.  
7. Para cada robot encontrado, consulta su estado en A360 usando el deployment\_id.  
8. Actualiza la fila del robot a estado \= 'FINALIZADO' o estado \= 'ERROR'.  
9. El bucle de LanzadorService espera el intervalo configurado y vuelve a empezar.

## **4\. Variables de Entorno Requeridas**

Este servicio depende de las siguientes variables definidas en el archivo .env:

* LANZADOR\_INTERVALO\_LANZAMIENTO\_SEG: Intervalo en segundos entre cada ciclo de ejecución.  
* A360\_CONTROL\_ROOM\_URL: URL de la Control Room de Automation Anywhere.  
* A360\_USERNAME: Nombre de usuario para la autenticación API.  
* A360\_API\_KEY: Clave API para la autenticación.  
* SQL\_SAM\_SERVER, SQL\_SAM\_DATABASE, SQL\_SAM\_USER, SQL\_SAM\_PASSWORD: Credenciales de la base de datos de SAM.

## **5\. Ejecución**

Para ejecutar el servicio en un entorno de desarrollo:

uv run \-m sam.lanzador  
