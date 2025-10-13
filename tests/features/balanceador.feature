# language: es
Feature: Gestión Dinámica de Recursos RPA (Servicio Balanceador)
  Como orquestador del sistema SAM, el servicio Balanceador debe asignar y desasignar
  equipos (VMs) de forma inteligente a los robots RPA para optimizar el uso de recursos
  basándose en la carga de trabajo pendiente (tickets) y las reglas de aislamiento entre pools.

  Background: Estado inicial del sistema
    Given un conjunto de equipos (VMs) disponibles para balanceo dinámico
    And un conjunto de robots configurados con prioridades, mínimos y máximos de equipos
    And una carga de trabajo definida por la cantidad de tickets pendientes para cada robot
    And un registro histórico para auditar todas las decisiones de balanceo

  Scenario: Aislamiento Estricto de Pools
    El sistema prioriza el aislamiento total de los recursos. Un robot de un pool dedicado
    NUNCA utilizará recursos del Pool General, incluso si su carga de trabajo es alta y hay
    equipos libres fuera de su pool.

    Given la configuración "BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO" está activada ("True")
    And existe un "Pool Dedicado de Contabilidad" con los siguientes recursos:
      | Robot               | Equipos | Tickets Pendientes |
      | Robot_Calculo_Imp   | 1       | 150                |
    And existe un "Pool General" con los siguientes recursos:
      | Robot               | Equipos | Tickets Pendientes |
      | Robot_Generico_A    | 5       | 100                |

    When el ciclo del balanceador se ejecuta

    Then el "Robot_Calculo_Imp" es asignado al único equipo de su "Pool Dedicado de Contabilidad"
    And el "Robot_Generico_A" es asignado a equipos disponibles del "Pool General"
    And el "Robot_Calculo_Imp" NO es asignado a ningún equipo adicional del "Pool General", respetando el aislamiento
    And la decisión de asignación se registra en el histórico, especificando el "Pool Dedicado de Contabilidad"

  Scenario: Desborde Flexible entre Pools (Overflow)
    El sistema permite que los robots de pools dedicados compitan por los recursos sobrantes
    del Pool General si su propia capacidad es superada, priorizando según su configuración.

    Given la configuración "BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO" está desactivada ("False")
    And existe un "Pool Dedicado de Contabilidad" con los siguientes recursos:
      | Robot               | Equipos | Prioridad | Tickets Pendientes |
      | Robot_Calculo_Imp   | 1       | 200       | 150                |
    And existe un "Pool General" con los siguientes recursos:
      | Robot               | Equipos | Prioridad | Tickets Pendientes |
      | Robot_Generico_A    | 5       | 100       | 100                |

    When el ciclo del balanceador se ejecuta

    Then el "Robot_Calculo_Imp" es asignado primero al equipo de su "Pool Dedicado de Contabilidad"
    And debido a su alta carga y al modo flexible, el "Robot_Calculo_Imp" compite por los recursos del "Pool General"
    And por tener mayor prioridad (200 > 100), el "Robot_Calculo_Imp" es asignado a equipos libres del "Pool General" ANTES que el "Robot_Generico_A"
    And el "Robot_Generico_A" es asignado a los equipos restantes del "Pool General"
    And la decisión de desborde ("overflow") se registra en el histórico

  Scenario: Desasignación de Recursos por Excedente
    Si la carga de trabajo de un robot disminuye, el sistema debe liberar los equipos
    que ya no son necesarios para que puedan ser utilizados por otros procesos.

    Given el "Robot_Generico_A" está asignado dinámicamente a 5 equipos
    And la carga de trabajo para "Robot_Generico_A" se reduce a 0 tickets pendientes

    When el ciclo del balanceador se ejecuta

    Then el sistema identifica que los 5 equipos asignados son un excedente
    And el balanceador desasigna los 5 equipos del "Robot_Generico_A"
    And los equipos quedan disponibles en su pool correspondiente para futuras asignaciones
    And la decisión de "DESASIGNAR_EXCEDENTE" se registra en el histórico

  Scenario: Prevención de "Thrashing" (Mecanismo de Enfriamiento)
    Para evitar la asignación y desasignación repetida y frecuente de recursos a un mismo robot
    (thrashing), el sistema impone un período de espera antes de quitar un recurso recién asignado.

    Given el "Robot_Generico_A" fue asignado a un nuevo equipo en el ciclo anterior
    And su carga de trabajo disminuye ligeramente, pero no a cero

    When el ciclo del balanceador se ejecuta

    Then el sistema detecta que un equipo podría ser considerado excedente
    But el robot se encuentra dentro de su "período de enfriamiento" (cooling period)
    And la disminución de la carga no supera el umbral de cambio drástico
    And por lo tanto, el equipo NO es desasignado para mantener la estabilidad