# **Documentación Técnica: Servicio Balanceador**

**Módulo:** sam.balanceador

## **1\. Propósito**

El **Servicio Balanceador** es el componente estratégico del ecosistema SAM. A diferencia del Lanzador, que es puramente ejecutivo, el Balanceador actúa como el "cerebro táctico" del sistema. Su responsabilidad es analizar el estado actual de la demanda (robots en cola) y la oferta (recursos disponibles) para optimizar la asignación de licencias y la capacidad de ejecución de manera proactiva.

Opera como un servicio de fondo que, a intervalos regulares, evalúa el ecosistema y toma decisiones para maximizar la eficiencia y el rendimiento.

## **2\. Arquitectura y Componentes**

Al igual que los otros servicios, sigue un estricto patrón de **Inyección de Dependencias** y **Separación de Responsabilidades**.

### **Componentes Principales**

* **BalanceadorService (service/main.py)**:  
  * **Rol:** Orquestador.  
  * **Descripción:** Gestiona el ciclo de vida del servicio.  
    1. Inicializa y recibe todas las dependencias necesarias (DatabaseConnector, clientes de APIs, etc.).  
    2. Ejecuta un bucle principal a un intervalo configurable (ej. cada 5 minutos).  
    3. En cada ciclo, invoca al BalanceadorDataProvider para recolectar toda la información del sistema.  
    4. Pasa los datos recolectados al AlgoritmoBalanceo para su procesamiento.  
    5. Recibe las "decisiones" o "acciones" del algoritmo y las ejecuta (ej. actualizando la base de datos).  
* **BalanceadorDataProvider (service/proveedores.py)**:  
  * **Rol:** Proveedor de Datos.  
  * **Descripción:** Su única función es actuar como una fachada para recolectar y consolidar toda la información que el algoritmo necesita para tomar decisiones. Consulta la base de datos de SAM, el cliente de Clouders y el cliente de Histórico para obtener una "fotografía" completa del estado del sistema en un momento dado.  
* **AlgoritmoBalanceo (service/algoritmo\_balanceo.py)**:  
  * **Rol:** Cerebro de Decisión.  
  * **Descripción:** Es el corazón del servicio. Recibe un objeto de datos consolidado del DataProvider y aplica un conjunto de reglas de negocio para determinar qué acciones se deben tomar. Es un componente puro: no realiza operaciones de I/O (red, disco, BD), solo procesa datos y devuelve un resultado.  
* **CoolingManager (service/cooling\_manager.py)**:  
  * **Rol:** Gestor de Enfriamiento.  
  * **Descripción:** Ayuda al algoritmo a evitar la oscilación (tomar y deshacer la misma decisión repetidamente). Mantiene un registro de las decisiones recientes para asegurar que, por ejemplo, si se asigna un recurso, no se intente desasignar inmediatamente en el siguiente ciclo.

## **3\. Lógica del Algoritmo**

El AlgoritmoBalanceo toma decisiones basadas en la comparación entre la demanda de ejecución y la oferta de recursos.

1. **Cálculo de la Demanda:** Analiza la cantidad de robots en estado PENDIENTE y los agrupa por los pools de recursos que requieren.  
2. **Cálculo de la Oferta:** Obtiene la lista de todos los pools de máquinas (equipos) disponibles y su estado actual (ej. cuántas licencias están en uso).  
3. **Proceso de Decisión:**  
   * **Asignación de Recursos:** Si detecta que hay más demanda que oferta para un pool específico (ej. 5 robots esperando pero solo 3 máquinas asignadas), generará acciones para asignar máquinas adicionales a ese pool, si hay disponibles.  
   * **Desasignación de Recursos:** Si detecta que la oferta supera con creces la demanda (ej. 10 máquinas asignadas a un pool pero solo 1 robot en cola), generará acciones para liberar máquinas de ese pool y devolverlas al estado disponible, optimizando el uso de licencias.  
   * **Priorización:** La lógica puede incluir reglas para priorizar ciertos pools o tipos de robots sobre otros en caso de escasez de recursos.

## **4\. Flujo de Datos**

1. BalanceadorService inicia su bucle.  
2. Invoca a BalanceadorDataProvider.get\_system\_snapshot().  
3. El DataProvider consulta la BD, CloudersClient, HistoricoClient y devuelve un único objeto con toda la información.  
4. BalanceadorService pasa este objeto de datos a AlgoritmoBalanceo.run().  
5. El AlgoritmoBalanceo analiza los datos y devuelve una lista de acciones (ej. \[Asignar(equipo='VM01', pool='Contabilidad'), Desasignar(equipo='VM08')\]).  
6. BalanceadorService itera sobre la lista de acciones y las ejecuta, llamando a los métodos correspondientes del DatabaseConnector.  
7. El bucle espera el intervalo configurado y vuelve a empezar.

## **5\. Variables de Entorno Requeridas**

* BALANCEADOR\_INTERVALO\_MINUTOS: Intervalo en minutos entre cada ciclo de ejecución del balanceo.  
* SQL\_SAM\_SERVER, SQL\_SAM\_DATABASE, SQL\_SAM\_USER, SQL\_SAM\_PASSWORD: Credenciales de la base de datos de SAM.  
* Credenciales y URLs para los servicios externos que consulta (ej. Clouders, Histórico).

## **6\. Ejecución**

Para ejecutar el servicio en un entorno de desarrollo:

uv run \-m sam.balanceador  
