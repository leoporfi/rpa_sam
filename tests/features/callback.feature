# language: es
Feature: Recepción de Notificaciones de A360 (Servicio de Callbacks)
  Como un componente de escucha en tiempo real, el servicio Callback debe
  exponer un endpoint seguro para recibir notificaciones (callbacks) de
  Automation Anywhere A360, actualizar el estado de las ejecuciones de forma
  inmediata y manejar las peticiones de manera idempotente.

  Background:
    Given un servicio web FastAPI está corriendo y escuchando en un puerto configurado
    And el servicio tiene una conexión activa a la base de datos de SAM
    And el endpoint "/api/callback" está disponible para recibir peticiones POST

  Scenario: Procesamiento Exitoso de un Callback con Autenticación Válida
    El servicio debe procesar una notificación legítima, actualizar la base de datos y
    responder con un estado de éxito.

    Given una ejecución con "deploymentId" 'xyz-789' tiene el estado "RUNNING" en la tabla "dbo.Ejecuciones"
    And el servidor está configurado con una "Clave de API" secreta para la validación
    When se recibe una petición POST en "/api/callback" con el siguiente payload:
      """json
      {
        "deploymentId": "xyz-789",
        "status": "COMPLETED",
        "botOutput": { "resultado": "OK" }
      }
      """
    And la petición incluye un header "X-Authorization" con la "Clave de API" correcta
    Then el servicio valida la "Clave de API" exitosamente
    And actualiza el registro de la ejecución 'xyz-789' en la base de datos, cambiando su estado a "COMPLETED" y guardando el payload del callback
    And el servicio responde con un código de estado HTTP 200 OK
    And el cuerpo de la respuesta contiene el mensaje: "Callback procesado y estado actualizado correctamente."

  Scenario: Autenticación Fallida por Clave de API Inválida
    Para proteger el sistema de peticiones no autorizadas, el servicio debe rechazar
    cualquier callback que no presente una credencial válida.

    Given el servidor está configurado con una "Clave de API" secreta
    When se recibe una petición POST en "/api/callback"
    And la petición NO incluye el header "X-Authorization" o su valor es incorrecto
    Then el servicio rechaza la petición con un código de estado HTTP 401 Unauthorized
    And NO se realiza ninguna modificación en la base de datos
    And el cuerpo de la respuesta contiene un mensaje de error indicando "Clave de API inválida o ausente."

  Scenario: Manejo de Callbacks Duplicados (Idempotencia)
    Si se recibe una notificación para una ejecución que ya ha finalizado, el servicio
    no debe intentar actualizarla de nuevo, pero debe confirmar la recepción exitosa para
    evitar reintentos innecesarios por parte de A360.

    Given una ejecución con "deploymentId" 'abc-123' ya tiene el estado "COMPLETED" en la base de datos
    When se recibe una segunda petición POST (duplicada) en "/api/callback" para el "deploymentId" 'abc-123'
    And la petición contiene una "Clave de API" válida
    Then el servicio consulta la base de datos y detecta que el estado de la ejecución ya es final
    And NO se realiza ninguna modificación en la base de datos
    And el servicio responde con un código de estado HTTP 200 OK
    And el cuerpo de la respuesta contiene el mensaje: "Callback recibido, pero la ejecución ya se encontraba en un estado final. No se realizaron cambios."

  Scenario: Rechazo de Petición con Payload Inválido
    El servicio debe validar la estructura del cuerpo de la petición y rechazarla si
    los campos obligatorios no están presentes.

    Given el servidor está esperando peticiones
    When se recibe una petición POST en "/api/callback" con una "Clave de API" válida
    And el payload JSON no incluye el campo requerido "status"
    Then el servicio de validación Pydantic detecta el error
    And la petición es rechazada con un código de estado HTTP 400 Bad Request
    And el cuerpo de la respuesta contiene un mensaje de error indicando que la petición es inválida