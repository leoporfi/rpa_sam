# language: es
Feature: Orquestación y Sincronización de Robots RPA (Servicio Lanzador)
  Como motor principal del sistema SAM, el servicio Lanzador es responsable de
  sincronizar los datos maestros con Automation Anywhere (A360), ejecutar los
  robots según la demanda y conciliar el estado de las ejecuciones para
  mantener la integridad del sistema.

  Background: Componentes del servicio
    Given una conexión a la base de datos de SAM
    And un cliente API para comunicarse con Automation Anywhere A360
    And una configuración que define los intervalos de ejecución para cada ciclo

  Scenario: Sincronización de Entidades desde A360
    El servicio mantiene las tablas maestras de SAM actualizadas con la realidad del
    Control Room de A360, asegurando que solo los robots y equipos relevantes sean considerados.

    Given existe un nuevo "taskbot" en A360 llamado "P123_ProcesoFacturas" que cumple con el patrón de nomenclatura
    And existe un nuevo "device" (equipo) conectado en A360 con una licencia "ATTENDEDRUNTIME"
    When el ciclo de sincronización se ejecuta
    Then el servicio invoca al cliente de A360 para obtener la lista de robots, devices y usuarios
    And se inserta o actualiza un registro para "P123_ProcesoFacturas" en la tabla "dbo.Robots" de SAM
    And se inserta o actualiza un registro para el nuevo equipo en la tabla "dbo.Equipos", incluyendo su licencia

  Scenario: Lanzamiento de Robots Ejecutables
    El núcleo del servicio es lanzar los robots que, según la lógica de negocio centralizada
    en la base de datos, están listos para ser ejecutados.

    Given la base de datos de SAM, a través del Stored Procedure "ObtenerRobotsEjecutables", indica que "Robot_X" debe ejecutarse en "Equipo_Y"
    And el servicio no se encuentra en la ventana de pausa operacional
    When el ciclo de lanzamiento se ejecuta
    Then el servicio obtiene las credenciales de autorización para el callback, combinando una ApiKey estática y un token dinámico de un API Gateway
    And se realiza una llamada a la API de A360 para desplegar el "Robot_X"
    And tras una respuesta exitosa, se inserta un nuevo registro en la tabla "dbo.Ejecuciones" con el estado "DEPLOYED" y el "deploymentId" retornado por la API

  Scenario: Conciliación de Ejecuciones "Perdidas"
    Para evitar que una ejecución quede indefinidamente en estado activo si A360 deja de reportarla,
    el conciliador la marca como desconocida después de varios intentos fallidos.

    Given una ejecución con "deploymentId" 'abc-123' tiene el estado "RUNNING" en la base de datos de SAM
    And su contador de intentos de conciliación fallidos es 2
    And la configuración establece el máximo de intentos fallidos en 3
    When el ciclo de conciliación se ejecuta
    Then el servicio consulta la API de A360 por el "deploymentId" 'abc-123', pero no obtiene respuesta
    And el contador "IntentosConciliadorFallidos" para esa ejecución se incrementa a 3
    And como el contador alcanzó el umbral máximo, el estado de la ejecución en la base de datos se actualiza a "UNKNOWN"

  Scenario: Pausa Operacional del Lanzador
    El servicio puede configurarse para detener el lanzamiento de nuevos robots durante
    una ventana de tiempo específica, típicamente durante la noche o mantenimientos.

    Given la configuración establece una ventana de pausa entre las "23:00" y las "05:00"
    And la hora actual del sistema es "02:30"
    And el Stored Procedure "ObtenerRobotsEjecutables" retorna un robot listo para ser lanzado
    When el ciclo de lanzamiento se ejecuta
    Then el servicio detecta que se encuentra dentro de la ventana de pausa
    And se emite un log informativo indicando la pausa
    And NO se realiza ninguna llamada a la API de A360 para desplegar el robot

  Scenario: Reintento de Despliegue por Dispositivo no Activo
    Si un despliegue falla porque el dispositivo de destino no está listo, el servicio
    realiza un reintento automático tras una breve espera.

    Given el ciclo de lanzamiento intenta desplegar el "Robot_Z"
    And la API de A360 responde con un error 400 indicando que el dispositivo "no está activo"
    When la lógica de despliegue maneja la excepción
    Then se registra una advertencia sobre el fallo y el reintento
    And el servicio espera un número de segundos configurado (ej. 15 segundos)
    And se intenta por segunda vez realizar la llamada a la API de A360 para desplegar el "Robot_Z"