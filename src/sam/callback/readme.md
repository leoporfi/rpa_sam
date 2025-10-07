# **Servidor de Callbacks SAM**

## **Descripción General**

Este servicio es un servidor backend WSGI diseñado para recibir notificaciones (callbacks) HTTP desde **Automation Anywhere A360**. Su función principal es escuchar las actualizaciones de estado de las ejecuciones de bots, validar la autenticidad de cada llamada y registrar los resultados en la base de datos de SAM.

## **Características Principales**

* **Servidor de Producción**: Utiliza **Waitress**, un servidor WSGI de alto rendimiento, cuando está disponible.  
* **Seguridad Estricta**: **Requiere obligatoriamente** un token de autenticación a través del encabezado X-Authorization para cada petición. Utiliza una comparación segura (hmac.compare_digest) para prevenir ataques de temporización.  
* **Código Limpio y Mantenible**: La lógica está claramente separada y se apoya en un gestor de configuración centralizado.  
* **Logging Robusto**: Genera logs detallados en archivos que rotan diariamente para facilitar la auditoría y el diagnóstico de problemas.  
* **Manejo de Errores Estructurado**: Proporciona respuestas de error consistentes y predecibles en formato JSON.

## **Instalación**

1. Clona el repositorio.  
2. Asegúrate de tener Python 3.8 o superior.  
3. Crea y activa un entorno virtual:  
   python -m venv venv  
   source venv/bin/activate  # En Windows: venv\Scripts\activate

4. Instala las dependencias:  
   pip install -r requirements.txt

## **Configuración (.env)**

Crea un archivo .env en la **raíz del proyecto**.

**Nota:** Para producción, es crucial definir CALLBACK_AUTH_MODE="strict" y un CALLBACK_TOKEN seguro.

# .env.example

# --- Configuración del Servidor de Callbacks ---  
CALLBACK_SERVER_HOST=0.0.0.0  
CALLBACK_SERVER_PORT=8008  
CALLBACK_SERVER_THREADS=10

# --- Seguridad (OBLIGATORIO EN PRODUCCIÓN) ---  
# Define el modo de autenticación: "strict" o "optional".  
# En modo "strict", todas las llamadas sin un token válido serán rechazadas.  
CALLBACK_AUTH_MODE="strict"

# Este token debe ser enviado por A360 en el encabezado X-Authorization.  
# DEBE ser un valor secreto, largo y complejo.  
CALLBACK_TOKEN="un-token-secreto-muy-largo-y-dificil-de-adivinar"

# --- Configuración de la Base de Datos SAM ---  
SQL_SAM_HOST=tu-servidor-sql.database.windows.net  
SQL_SAM_DB_NAME=SAM_DATABASE  
SQL_SAM_UID=tu_usuario  
SQL_SAM_PWD=tu_contraseña

# --- Configuración de Logs ---  
LOG_DIRECTORY="C:/RPA/Logs/SAM"  
CALLBACK_LOG_FILENAME="sam_callback_server.log"  
LOG_LEVEL="INFO" # Opciones: DEBUG, INFO, WARNING, ERROR

## **Cómo Ejecutar el Servicio**

Para iniciar el servidor, ejecuta el script run_callback.py desde la raíz del proyecto.

python src/callback/run_callback.py

El servidor imprimirá en la consola la dirección en la que está escuchando y el modo de autenticación activo.

## **Funcionamiento de la API**

* **Endpoint**: POST /  
* **Encabezado Requerido**: X-Authorization: \<tu-token-secreto\>  
* **Cuerpo de la Solicitud (Request Body)**: Un objeto JSON con la siguiente estructura:  
  * deploymentId (string, **requerido**): El ID único de la ejecución.  
  * status (string, **requerido**): El estado final de la ejecución.  
  * deviceId (string, *opcional*): El ID del dispositivo donde se ejecutó.  
  * userId (string, *opcional*): El ID del usuario asociado a la ejecución.  
  * botOutput (object, *opcional*): Un diccionario con las variables de salida del bot.

**Ejemplo de Payload Válido:**

{  
  "deviceId": "44",  
  "userId": "4934",  
  "deploymentId": "dd694f01-f8a0-4470-9240-7d866465d981",  
  "status": "RUN_COMPLETED",  
  "botOutput": {  
    "resultado": "exitoso",  
    "archivo_generado": "reporte.xlsx"  
  }  
}

* **Respuestas**: El servidor responderá con códigos de estado HTTP estándar (200, 401, 405, 500) y un cuerpo JSON que describe el resultado.