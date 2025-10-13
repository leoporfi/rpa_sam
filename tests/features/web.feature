# language: es
Feature: Interfaz Web de Mantenimiento de SAM
  Como administrador del sistema RPA, necesito una interfaz web para gestionar
  y monitorizar los robots, sus asignaciones, programaciones y pools de recursos,
  facilitando la operación diaria del sistema SAM.

  Background:
    Given un usuario ha iniciado sesión y ha accedido a la Interfaz Web de SAM
    And la interfaz se comunica con un backend a través de una API RESTful

  @robots
  Scenario: Visualizar y filtrar la lista de robots
    El usuario necesita poder encontrar robots específicos de forma rápida y eficiente
    utilizando los filtros disponibles en el dashboard principal.

    Given el usuario se encuentra en el "Dashboard de Robots" (ruta "/")
    When el usuario escribe "Facturas" en la barra de búsqueda
    And selecciona "Solo Activos" en el filtro de estado
    Then la interfaz realiza una petición GET a la API en el endpoint "/api/robots" con los parámetros de consulta "?name=Facturas&active=true"
    And la tabla de robots se actualiza para mostrar únicamente los robots activos cuyo nombre contiene "Facturas"

  @robots
  Scenario: Iniciar una sincronización manual con A360
    El usuario debe poder forzar una sincronización de datos entre SAM y Automation
    Anywhere A360 para reflejar cambios de inmediato.

    Given el usuario está en el "Dashboard de Robots"
    When el usuario hace clic en el botón "Sincronizar con A360"
    Then se muestra una notificación informativa: "Iniciando sincronización con A360..."
    And la interfaz realiza una petición POST a la API en el endpoint "/api/sync"
    And al completarse la sincronización, se muestra una notificación de éxito con el resumen (ej. "Robots: 5, Equipos: 10")
    And la tabla de robots se refresca automáticamente para mostrar los datos actualizados

  @robots
  Scenario: Editar los detalles de configuración de un robot
    El usuario necesita modificar parámetros clave de un robot, como su prioridad
    de balanceo o los umbrales de equipos.

    Given el usuario se encuentra en el "Dashboard de Robots" y ve el robot "RPA_Proceso_A" en la lista
    When el usuario hace clic en el icono "Editar" de la fila del robot "RPA_Proceso_A"
    Then se abre un modal con un formulario que contiene los detalles actuales del robot (Nombre, Descripción, Prioridad, etc.)
    And el usuario cambia el valor del campo "PrioridadBalanceo" a "150"
    And hace clic en el botón "Guardar"
    Then la interfaz realiza una petición PUT al endpoint "/api/robots/{id_robot}" con los datos actualizados
    And se muestra una notificación de éxito, el modal se cierra y la tabla de robots se refresca mostrando la nueva prioridad

  @robots
  Scenario: Gestionar las asignaciones manuales de un robot
    El usuario necesita asignar o desasignar manualmente equipos (VMs) a un robot
    para crear reservas o liberarlas.

    Given el usuario está en el "Dashboard de Robots"
    When el usuario hace clic en el icono "Asignar Equipos" para un robot específico
    Then se abre un modal con dos listas: "Equipos Asignados" y "Equipos Disponibles"
    When el usuario selecciona "VM_LIBRE_01" de la lista de "Disponibles"
    And selecciona "VM_ASIGNADA_02" de la lista de "Asignados"
    And hace clic en "Guardar"
    Then la interfaz realiza una petición POST a "/api/robots/{id_robot}/asignaciones" con los IDs de los equipos a asignar y desasignar
    And se muestra una notificación de éxito y el modal se cierra
    And la columna "Equipos" para ese robot en el dashboard se actualiza

  @robots
  Scenario: Crear una nueva programación para un robot
    El usuario necesita crear una nueva ejecución programada (diaria, semanal, etc.) para
    un robot, especificando los equipos que debe usar.

    Given el usuario ha hecho clic en el icono "Programar Tareas" de un robot, abriendo el modal de programaciones
    When el usuario hace clic en el botón "Crear nueva programación"
    Then la vista cambia a un formulario para definir la nueva programación
    And el usuario selecciona "Semanal" como "Tipo de Programación", introduce "Lu,Ma,Mi" en "Días Semana" y selecciona dos equipos de la lista
    And hace clic en "Guardar"
    Then la interfaz realiza una petición POST a "/api/programaciones" con toda la información de la nueva programación
    And se muestra una notificación de éxito, la vista vuelve a la lista de programaciones y la nueva programación aparece en ella

  @pools
  Scenario: Crear un nuevo Pool de Recursos
    El usuario necesita agrupar recursos creando un nuevo Pool.

    Given el usuario navega a la sección "Pools" (ruta "/pools")
    When el usuario hace clic en el botón "Crear Nuevo Pool"
    Then se abre un modal para la creación de un pool
    And el usuario introduce "Pool de Contabilidad" como nombre y "Recursos para procesos financieros" como descripción
    And hace clic en "Guardar"
    Then la interfaz realiza una petición POST a "/api/pools" con los datos del nuevo pool
    And el modal se cierra, se muestra una notificación de éxito y la tabla de pools se refresca mostrando el "Pool de Contabilidad"

  @pools
  Scenario: Asignar recursos a un Pool existente
    El usuario debe poder asignar y desasignar robots y equipos a un pool para definir
    su membresía.

    Given el usuario se encuentra en la sección "Pools"
    When el usuario hace clic en el icono "Asignar Recursos" del "Pool de Contabilidad"
    Then se abre un modal con dos secciones, una para robots y otra para equipos, cada una con listas de "Disponibles" y "Asignados"
    And el usuario mueve el "Robot_Facturas" de "Disponibles" a "Asignados"
    And el usuario mueve el "Equipo_VM_Finanzas_01" de "Disponibles" a "Asignados"
    And hace clic en "Guardar Cambios"
    Then la interfaz realiza una petición PUT a "/api/pools/{id_pool}/asignaciones" con las listas de IDs de los robots y equipos asignados
    And el modal se cierra, se muestra una notificación de éxito y los contadores de "Robots" y "Equipos" para el pool se actualizan en la tabla.
