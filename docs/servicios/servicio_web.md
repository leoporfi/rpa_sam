# **Documentación Técnica: Interfaz Web**

**Módulo:** sam.web

## **1\. Propósito**

La **Interfaz Web** es el componente visual y de interacción humana del ecosistema SAM. Proporciona un dashboard centralizado que permite a los administradores y usuarios monitorear el estado de los robots en tiempo real, gestionar la configuración de los pools de máquinas y obtener una visión general del rendimiento del sistema.

Es el único servicio de SAM con una interfaz de usuario (UI).

## **2\. Arquitectura: Backend y Frontend**

Este servicio tiene una arquitectura de dos capas que se ejecutan en el mismo proceso:

1. **Backend (API \- FastAPI):** Una API RESTful responsable de toda la comunicación con la base de datos. Su única función es exponer endpoints seguros que devuelven datos en formato JSON. No tiene ninguna responsabilidad sobre la presentación.  
2. **Frontend (UI \- ReactPy):** Una Single-Page Application (SPA) construida con ReactPy. Se ejecuta en el navegador del usuario y es responsable de toda la lógica de presentación. Para obtener o modificar datos, realiza llamadas HTTP a su propio Backend API.

Esta separación estricta asegura que la lógica de negocio (backend) esté desacoplada de la capa de visualización (frontend), facilitando el mantenimiento y futuras mejoras.

### **Componentes Principales**

* **main.py**: El punto de entrada que monta la aplicación de backend (API) y la aplicación de frontend (ReactPy) para que puedan ser servidas juntas por el servidor Uvicorn.  
* **Backend (backend/)**:  
  * **api.py**: Define todos los endpoints de la API, como /api/robots, /api/pools, etc. Aquí reside la lógica para manejar las solicitudes HTTP.  
  * **database.py**: Contiene las funciones que interactúan directamente con la base de datos para obtener y modificar los datos que la API necesita.  
  * **schemas.py**: Define los modelos de datos Pydantic utilizados para la validación de datos en las solicitudes y la serialización en las respuestas, asegurando una estructura de datos consistente.  
* **Frontend (frontend/)**:  
  * **app.py**: El componente raíz de la aplicación ReactPy. Define la estructura principal de la página, el layout y el enrutamiento.  
  * **api\_client.py**: Un cliente HTTP (basado en httpx) que el frontend utiliza para comunicarse con el backend API. Centraliza toda la lógica de llamadas de red.  
  * **components/ y features/**: Directorios que contienen los componentes reutilizables de la UI (botones, tablas, modales) y las vistas principales de la aplicación (Dashboard, Vista de Pools).  
  * **hooks/**: Contiene la lógica de estado y obtención de datos del frontend (ej. use\_robots\_hook), siguiendo patrones modernos de desarrollo de interfaces.

## **3\. Flujo de Datos Típico**

1. El usuario accede a la URL del servicio en su navegador.  
2. El servidor Uvicorn sirve el HTML y JavaScript iniciales que cargan la aplicación ReactPy.  
3. Un componente del frontend (ej. la tabla de robots) utiliza un hook (ej. use\_robots\_hook) para solicitar los datos.  
4. El hook llama a una función en el api\_client.py.  
5. El api\_client realiza una solicitud GET al endpoint del backend, por ejemplo, /api/robots.  
6. El endpoint en backend/api.py recibe la solicitud, llama a la función correspondiente en backend/database.py para obtener los datos de la base de datos.  
7. El backend serializa los resultados usando un esquema Pydantic y los devuelve como una respuesta JSON.  
8. El api\_client en el frontend recibe el JSON, el hook actualiza el estado de la aplicación.  
9. ReactPy detecta el cambio de estado y vuelve a renderizar la tabla de robots con los nuevos datos.

## **4\. Variables de Entorno Requeridas**

* WEB\_HOST: La dirección IP en la que el servidor escuchará (ej. 0.0.0.0).  
* WEB\_PORT: El puerto en el que se ejecutará el servicio (ej. 8080).  
* SQL\_SAM\_SERVER, SQL\_SAM\_DATABASE, SQL\_SAM\_USER, SQL\_SAM\_PASSWORD: Credenciales de la base de datos de SAM.

## **5\. Ejecución**

Para ejecutar el servicio en un entorno de desarrollo:

uv run \-m sam.web

La interfaz será accesible desde la URL http://127.0.0.1:8080.