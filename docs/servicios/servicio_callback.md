# **Documentación Técnica: Servicio de Callback**

**Módulo:** sam.callback

## **1\. Propósito**

El **Servicio de Callback** es el componente de escucha en tiempo real del ecosistema SAM. Su única función es exponer un endpoint (URL) seguro y de alta disponibilidad para que el sistema externo (Automation 360\) pueda notificar a SAM instantáneamente cuando un despliegue de robot ha finalizado.

Esto elimina la necesidad de que el Sincronizador del Servicio Lanzador consulte constantemente el estado de todos los robots, permitiendo una actualización de estado mucho más eficiente y rápida.

## **2\. Arquitectura y Componentes**

El servicio está construido como una aplicación web ligera utilizando el framework **FastAPI**, lo que le confiere un alto rendimiento y una generación automática de documentación interactiva (Swagger/OpenAPI).

### **Componentes Principales**

* **Aplicación FastAPI (service/main.py)**:  
  * **Rol:** Servidor Web y Punto de Entrada.  
  * **Descripción:** Define la aplicación FastAPI y sus endpoints.  
    1. **Endpoint /callback (POST):** Es la ruta principal que recibe las notificaciones de A360. Valida la solicitud, procesa los datos y actualiza la base de datos.  
    2. **Endpoint /health (GET):** Una ruta simple para verificaciones de estado, que devuelve una respuesta {"status": "ok"} para confirmar que el servicio está en línea.  
* **Gestión del Ciclo de Vida (lifespan)**:  
  * **Rol:** Gestor de Recursos.  
  * **Descripción:** Se utiliza el gestor de contexto lifespan de FastAPI para manejar los recursos de la aplicación.  
    * **Al iniciar (startup):** Se crea una única instancia del DatabaseConnector que será compartida por todas las solicitudes, optimizando las conexiones.  
    * **Al apagar (shutdown):** Se llama al método close() del conector para asegurar que la conexión a la base de datos se cierre de forma limpia.

## **3\. Seguridad**

Dado que el endpoint /callback está expuesto a internet, la seguridad es un pilar fundamental. El acceso está restringido mediante un mecanismo de **clave API (API Key)**.

* **Mecanismo:** Cada solicitud entrante al endpoint /callback **debe** incluir una cabecera HTTP X-API-KEY.  
* **Validación:** El valor de esta cabecera se compara con el valor definido en la variable de entorno CALLBACK\_API\_KEY.  
* **Respuesta:**  
  * Si la cabecera no existe o la clave es incorrecta, el servicio responde inmediatamente con un error 401 Unauthorized y no procesa la solicitud.  
  * Si la clave es correcta, la solicitud se procesa.

## **4\. Flujo de Datos**

1. Un robot finaliza su ejecución en la plataforma A360.  
2. A360 envía una solicitud POST al endpoint https://\<URL\_DEL\_SERVIDOR\>/callback. La solicitud incluye un cuerpo (payload) en formato JSON con los detalles del despliegue (ej. deploymentId, status, etc.) y la cabecera X-API-KEY.  
3. El servicio FastAPI recibe la solicitud.  
4. Un middleware o una dependencia de FastAPI extrae y valida la X-API-KEY.  
5. Si la validación es exitosa, la lógica del endpoint se ejecuta.  
6. Se extrae el deploymentId y el status del cuerpo de la solicitud.  
7. Se utiliza el DatabaseConnector para ejecutar una sentencia UPDATE en la tabla robots, buscando la fila que coincida con el deploymentId y actualizando su estado.  
8. El servicio devuelve una respuesta 200 OK a A360 para confirmar la recepción.

## **5\. Variables de Entorno Requeridas**

* CALLBACK\_HOST: La dirección IP en la que el servidor escuchará (ej. 0.0.0.0 para todas las interfaces).  
* CALLBACK\_PORT: El puerto en el que se ejecutará el servicio (ej. 8000).  
* CALLBACK\_API\_KEY: La clave secreta compartida que se utilizará para autenticar las solicitudes entrantes.  
* SQL\_SAM\_SERVER, SQL\_SAM\_DATABASE, SQL\_SAM\_USER, SQL\_SAM\_PASSWORD: Credenciales de la base de datos de SAM.

## **6\. Ejecución**

Para ejecutar el servicio en un entorno de desarrollo:

uv run \-m sam.callback

Una vez iniciado, la documentación interactiva de la API estará disponible en la URL http://127.0.0.1:8000/docs.