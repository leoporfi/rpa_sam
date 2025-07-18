USE [SAM]
GO
/****** Object:  UserDefinedFunction [dbo].[EsPrimerJueveDelMes]    Script Date: 17/6/2025 08:43:19 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- Función que determina si una fecha es el primer jueves del mes
CREATE FUNCTION [dbo].[EsPrimerJueveDelMes]
(
    @FechaAVerificar DATE
)
RETURNS BIT
AS
BEGIN
    DECLARE @Resultado BIT = 0

    -- Verificar si la fecha es un jueves
    IF DATEPART(dw, @FechaAVerificar) = 5 -- 5 representa jueves
    BEGIN
        -- Encontrar el primer jueves del mismo mes
        DECLARE @PrimerJueveDelMes DATE = 
        (
            SELECT TOP 1 
                DATEADD(day, number, DATEADD(month, DATEDIFF(month, 0, @FechaAVerificar), 0))
            FROM master.dbo.spt_values
            WHERE type = 'P' AND number <= 6
            AND DATEPART(dw, DATEADD(day, number, DATEADD(month, DATEDIFF(month, 0, @FechaAVerificar), 0))) = 5
            ORDER BY number
        )

        -- Comparar si la fecha de entrada es igual al primer jueves del mes
        IF @FechaAVerificar = @PrimerJueveDelMes
            SET @Resultado = 1
    END

    RETURN @Resultado
END
GO
/****** Object:  Table [dbo].[Equipos]    Script Date: 17/6/2025 08:43:19 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Equipos](
	[EquipoId] [int] NOT NULL,
	[Equipo] [nvarchar](100) NOT NULL,
	[UserId] [int] NOT NULL,
	[UserName] [nvarchar](50) NULL,
	[Licencia] [nvarchar](50) NULL,
	[Activo_SAM] [bit] NOT NULL,
	[EstadoBalanceador] [nvarchar](50) NULL,
	[PermiteBalanceoDinamico] [bit] NOT NULL,
 CONSTRAINT [PK__Equipos__DE8A0BDF6ED005DC] PRIMARY KEY CLUSTERED 
(
	[EquipoId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Robots]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Robots](
	[RobotId] [int] NOT NULL,
	[Robot] [nvarchar](100) NOT NULL,
	[Descripcion] [nvarchar](4000) NULL,
	[Parametros] [nvarchar](max) NULL,
	[EsOnline] [bit] NULL,
	[Activo] [bit] NULL,
	[MinEquipos] [int] NOT NULL,
	[MaxEquipos] [int] NOT NULL,
	[PrioridadBalanceo] [int] NOT NULL,
	[TicketsPorEquipoAdicional] [int] NULL,
PRIMARY KEY CLUSTERED 
(
	[RobotId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Asignaciones]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Asignaciones](
	[RobotId] [int] NULL,
	[EquipoId] [int] NULL,
	[EsProgramado] [bit] NULL,
	[Reservado] [bit] NULL,
	[FechaAsignacion] [datetime2](0) NULL,
	[AsignadoPor] [nvarchar](50) NULL,
	[ProgramacionId] [int] NULL,
 CONSTRAINT [UQ_RobotEquipo] UNIQUE NONCLUSTERED 
(
	[RobotId] ASC,
	[EquipoId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  View [dbo].[AsignacionesView]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE VIEW [dbo].[AsignacionesView]
AS
SELECT R.Robot, EQ.Equipo, A.RobotId, A.EquipoId, A.EsProgramado, A.Reservado
FROM     dbo.Asignaciones AS A INNER JOIN
                  dbo.Equipos AS EQ ON A.EquipoId = EQ.EquipoId INNER JOIN
                  dbo.Robots AS R ON A.RobotId = R.RobotId
GO
/****** Object:  Table [dbo].[Ejecuciones]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Ejecuciones](
	[DeploymentId] [nvarchar](100) NOT NULL,
	[RobotId] [int] NULL,
	[EquipoId] [int] NULL,
	[UserId] [nchar](10) NULL,
	[Hora] [time](0) NULL,
	[FechaInicio] [datetime2](0) NOT NULL,
	[FechaFin] [datetime2](0) NULL,
	[Estado] [nvarchar](20) NOT NULL,
	[FechaActualizacion] [datetime2](0) NULL,
	[CallbackInfo] [nvarchar](max) NULL,
 CONSTRAINT [PK_Ejecuciones] PRIMARY KEY CLUSTERED 
(
	[DeploymentId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  View [dbo].[EjecucionesActivas]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE VIEW [dbo].[EjecucionesActivas]
AS
SELECT TOP (100) PERCENT R.Robot, EQ.Equipo, E.DeploymentId, E.RobotId, E.EquipoId, E.UserId, E.Hora, E.FechaInicio, E.FechaFin, E.Estado, E.CallbackInfo
FROM     dbo.Ejecuciones AS E INNER JOIN
                  dbo.Equipos AS EQ ON E.EquipoId = EQ.EquipoId INNER JOIN
                  dbo.Robots AS R ON E.RobotId = R.RobotId
WHERE  (E.Estado IN ('PENDING_EXECUTION', 'DEPLOYED', 'RUNNING', 'UPDATE', 'RUN_PAUSED', 'QUEUED'))
ORDER BY R.Robot, E.FechaInicio DESC
GO
/****** Object:  View [dbo].[EquiposAsignados]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW  [dbo].[EquiposAsignados] AS
select r.Robot, count(e.Equipo) Equipos from Asignaciones a inner join Robots r on r.RobotId=a.RobotId
inner join Equipos e on e.EquipoId = a.EquipoId
group by Robot;
GO
/****** Object:  Table [dbo].[ErrorLog]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ErrorLog](
	[ErrorLogId] [int] IDENTITY(1,1) NOT NULL,
	[FechaHora] [datetime2](0) NOT NULL,
	[Usuario] [nvarchar](100) NOT NULL,
	[SPNombre] [nvarchar](100) NOT NULL,
	[ErrorMensaje] [nvarchar](max) NOT NULL,
	[Parametros] [nvarchar](max) NULL,
 CONSTRAINT [PK_ErrorLog] PRIMARY KEY CLUSTERED 
(
	[ErrorLogId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[HistoricoBalanceo]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[HistoricoBalanceo](
	[HistoricoId] [int] IDENTITY(1,1) NOT NULL,
	[FechaBalanceo] [datetime2](0) NOT NULL,
	[RobotId] [int] NOT NULL,
	[TicketsPendientes] [int] NOT NULL,
	[EquiposAsignadosAntes] [int] NOT NULL,
	[EquiposAsignadosDespues] [int] NOT NULL,
	[AccionTomada] [nvarchar](50) NOT NULL,
	[Justificacion] [nvarchar](255) NULL,
 CONSTRAINT [PK_HistoricoBalanceo] PRIMARY KEY CLUSTERED 
(
	[HistoricoId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Programaciones]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Programaciones](
	[ProgramacionId] [int] IDENTITY(1,1) NOT NULL,
	[RobotId] [int] NULL,
	[TipoProgramacion] [nvarchar](20) NULL,
	[HoraInicio] [time](0) NOT NULL,
	[DiasSemana] [nvarchar](20) NULL,
	[DiaDelMes] [int] NULL,
	[FechaEspecifica] [date] NULL,
	[Tolerancia] [int] NULL,
	[Activo] [bit] NULL,
	[FechaCreacion] [datetime2](0) NULL,
	[FechaModificacion] [datetime2](0) NULL,
 CONSTRAINT [PK__Programa__B9967C40CEE769DF] PRIMARY KEY CLUSTERED 
(
	[ProgramacionId] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
ALTER TABLE [dbo].[Asignaciones] ADD  CONSTRAINT [DF_Asignaciones_EsProgramado]  DEFAULT ((0)) FOR [EsProgramado]
GO
ALTER TABLE [dbo].[Asignaciones] ADD  CONSTRAINT [DF_Asignaciones_Reservado]  DEFAULT ((0)) FOR [Reservado]
GO
ALTER TABLE [dbo].[Asignaciones] ADD  CONSTRAINT [DF_Asignaciones_FechaAsignacion]  DEFAULT (getdate()) FOR [FechaAsignacion]
GO
ALTER TABLE [dbo].[Ejecuciones] ADD  CONSTRAINT [DF_Ejecuciones_FechaInicio]  DEFAULT (getdate()) FOR [FechaInicio]
GO
ALTER TABLE [dbo].[Equipos] ADD  CONSTRAINT [DF_Equipos_Activo_SAM]  DEFAULT ((1)) FOR [Activo_SAM]
GO
ALTER TABLE [dbo].[Equipos] ADD  CONSTRAINT [DF_Equipos_PermiteBalanceoDinamico]  DEFAULT ((1)) FOR [PermiteBalanceoDinamico]
GO
ALTER TABLE [dbo].[ErrorLog] ADD  CONSTRAINT [DF_ErrorLog_FechaHora]  DEFAULT (getdate()) FOR [FechaHora]
GO
ALTER TABLE [dbo].[HistoricoBalanceo] ADD  DEFAULT (getdate()) FOR [FechaBalanceo]
GO
ALTER TABLE [dbo].[Programaciones] ADD  CONSTRAINT [DF__Programac__Toler__208CD6FA]  DEFAULT ((60)) FOR [Tolerancia]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_EsOnline]  DEFAULT ((0)) FOR [EsOnline]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_Activo]  DEFAULT ((1)) FOR [Activo]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_MinEquipos]  DEFAULT ((1)) FOR [MinEquipos]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_MaxEquipos]  DEFAULT ((-1)) FOR [MaxEquipos]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_PrioridadBalanceo]  DEFAULT ((100)) FOR [PrioridadBalanceo]
GO
ALTER TABLE [dbo].[Robots] ADD  CONSTRAINT [DF_Robots_TicketsPorEquipoAdicional]  DEFAULT (NULL) FOR [TicketsPorEquipoAdicional]
GO
ALTER TABLE [dbo].[Asignaciones]  WITH CHECK ADD  CONSTRAINT [FK_Asignaciones_Programaciones] FOREIGN KEY([ProgramacionId])
REFERENCES [dbo].[Programaciones] ([ProgramacionId])
GO
ALTER TABLE [dbo].[Asignaciones] CHECK CONSTRAINT [FK_Asignaciones_Programaciones]
GO
ALTER TABLE [dbo].[HistoricoBalanceo]  WITH CHECK ADD  CONSTRAINT [FK_HistoricoBalanceo_Robots] FOREIGN KEY([RobotId])
REFERENCES [dbo].[Robots] ([RobotId])
GO
ALTER TABLE [dbo].[HistoricoBalanceo] CHECK CONSTRAINT [FK_HistoricoBalanceo_Robots]
GO
ALTER TABLE [dbo].[Programaciones]  WITH CHECK ADD  CONSTRAINT [CK__Programac__TipoP__1F98B2C1] CHECK  (([TipoProgramacion]='Especifica' OR [TipoProgramacion]='Mensual' OR [TipoProgramacion]='Semanal' OR [TipoProgramacion]='Diaria'))
GO
ALTER TABLE [dbo].[Programaciones] CHECK CONSTRAINT [CK__Programac__TipoP__1F98B2C1]
GO
/****** Object:  StoredProcedure [dbo].[ActualizarProgramacionCompleta]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE   PROCEDURE [dbo].[ActualizarProgramacionCompleta]
    @ProgramacionId INT,
    @RobotId INT,
    @TipoProgramacion NVARCHAR(20),
    @HoraInicio TIME,
    @DiaSemana NVARCHAR(20) = NULL,
    @DiaDelMes INT = NULL,
    @FechaEspecifica DATE = NULL,
    @Tolerancia INT = NULL,
    @Equipos NVARCHAR(MAX), -- Equipos como nombres separados por coma
    @UsuarioModifica NVARCHAR(50) = 'WebApp'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;
    DECLARE @Robot NVARCHAR(100);

    -- Tabla temporal para almacenar los IDs de equipos válidos
    CREATE TABLE #NuevosEquiposProgramados (EquipoId INT PRIMARY KEY);

    BEGIN TRY
        -- Obtener el nombre del robot para logs
        SELECT @Robot = Robot FROM dbo.Robots WHERE RobotId = @RobotId;

        BEGIN TRANSACTION;

        -- 1. Actualizar datos de la programación
        UPDATE dbo.Programaciones
        SET TipoProgramacion = @TipoProgramacion,
            HoraInicio = @HoraInicio,
            DiasSemana = CASE WHEN @TipoProgramacion = 'Semanal' THEN @DiaSemana ELSE NULL END,
            DiaDelMes = CASE WHEN @TipoProgramacion = 'Mensual' THEN @DiaDelMes ELSE NULL END,
            FechaEspecifica = CASE WHEN @TipoProgramacion = 'Especifica' THEN @FechaEspecifica ELSE NULL END,
            Tolerancia = @Tolerancia,
            FechaModificacion = GETDATE()
        WHERE ProgramacionId = @ProgramacionId AND RobotId = @RobotId;

        IF @@ROWCOUNT = 0
        BEGIN
            RAISERROR('Programación no encontrada o no pertenece al RobotId especificado.', 16, 1);
            RETURN;
        END

        -- 2. Poblar #NuevosEquiposProgramados
        INSERT INTO #NuevosEquiposProgramados (EquipoId)
        SELECT E.EquipoId
        FROM STRING_SPLIT(@Equipos, ',') AS S
        JOIN dbo.Equipos E ON LTRIM(RTRIM(S.value)) = E.Equipo
        WHERE E.Activo_SAM = 1;

        -- Mostrar advertencias por equipos inválidos o inactivos
        SELECT 'Warning: Equipo "' + LTRIM(RTRIM(S.value)) + '" no encontrado o inactivo y no será programado.' AS Advertencia
        FROM STRING_SPLIT(@Equipos, ',') S
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.Equipos E
            WHERE E.Equipo = LTRIM(RTRIM(S.value)) AND E.Activo_SAM = 1
        );

        -- 3. Desprogramar equipos que ya no deben estar en esta programación
        UPDATE A
        SET EsProgramado = 0,
            ProgramacionId = NULL,
            AsignadoPor = @UsuarioModifica,
            FechaAsignacion = GETDATE()
        FROM dbo.Asignaciones A
        WHERE A.ProgramacionId = @ProgramacionId AND A.EsProgramado = 1
          AND NOT EXISTS (
              SELECT 1 FROM #NuevosEquiposProgramados NEP WHERE NEP.EquipoId = A.EquipoId
          )
          AND A.RobotId = @RobotId;

        -- Habilitar balanceo dinámico para los equipos que ya no están programados en ningún lado
        UPDATE E
        SET PermiteBalanceoDinamico = 1
        FROM dbo.Equipos E
        WHERE EXISTS (
            SELECT 1
            FROM dbo.Asignaciones A
            WHERE A.EquipoId = E.EquipoId
              AND A.RobotId = @RobotId
              AND A.ProgramacionId = @ProgramacionId
              AND A.EsProgramado = 0
        )
        AND NOT EXISTS (
            SELECT 1
            FROM dbo.Asignaciones A
            WHERE A.EquipoId = E.EquipoId
              AND A.EsProgramado = 1
              AND A.ProgramacionId IS NOT NULL
        );

        -- 4. Programar los nuevos equipos
        MERGE dbo.Asignaciones AS Target
        USING #NuevosEquiposProgramados AS Source
        ON Target.EquipoId = Source.EquipoId AND Target.RobotId = @RobotId
        WHEN MATCHED THEN
            UPDATE SET
                EsProgramado = 1,
                ProgramacionId = @ProgramacionId,
                Reservado = 0,
                AsignadoPor = @UsuarioModifica,
                FechaAsignacion = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (RobotId, EquipoId, EsProgramado, ProgramacionId, Reservado, AsignadoPor, FechaAsignacion)
            VALUES (@RobotId, Source.EquipoId, 1, @ProgramacionId, 0, @UsuarioModifica, GETDATE());

        -- Desactivar balanceo dinámico para equipos recién programados
        UPDATE E
        SET PermiteBalanceoDinamico = 0
        FROM dbo.Equipos E
        JOIN #NuevosEquiposProgramados NEP ON E.EquipoId = NEP.EquipoId;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SET @ErrorMessage = ERROR_MESSAGE();
        SET @ErrorSeverity = ERROR_SEVERITY();
        SET @ErrorState = ERROR_STATE();

        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = 
            '@Robot = ' + ISNULL(@Robot, 'NULL') + 
            ', @Equipos = ' + ISNULL(@Equipos, 'NULL') + 
            ', @HoraInicio = ' + ISNULL(CONVERT(NVARCHAR(8), @HoraInicio, 108), 'NULL') + 
            ', @Tolerancia = ' + ISNULL(CAST(@Tolerancia AS NVARCHAR(10)), 'NULL');

        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (SUSER_NAME(), 'ActualizarProgramacionCompleta', @ErrorMessage, @Parametros);

        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH

    -- Limpieza de tabla temporal
    IF OBJECT_ID('tempdb..#NuevosEquiposProgramados') IS NOT NULL
        DROP TABLE #NuevosEquiposProgramados;
END
GO
/****** Object:  StoredProcedure [dbo].[AsignarRobotOnline]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[AsignarRobotOnline]
    @Robot NVARCHAR(100),
    @Equipos NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRY
        BEGIN TRANSACTION;

		SET @Equipos = UPPER(TRIM(@Equipos))
        -- Validar la existencia del robot
        DECLARE @RobotId INT;
        SELECT @RobotId = RobotId FROM Robots WHERE Robot = @Robot;
        
        IF @RobotId IS NULL
        BEGIN
            RAISERROR('El robot especificado no existe.', 16, 1);
            RETURN;
        END

        -- Preparar la tabla temporal para los equipos
        DECLARE @EquiposTemp TABLE (Equipo NVARCHAR(255));
        INSERT INTO @EquiposTemp (Equipo)
        SELECT TRIM(value) FROM STRING_SPLIT(@Equipos, ',');

        -- Iterar sobre los equipos y asignarlos
        DECLARE @EquipoNombre NVARCHAR(255);
        DECLARE @EquipoId INT;
        
        DECLARE equipo_cursor CURSOR FOR 
        SELECT Equipo FROM @EquiposTemp;

        OPEN equipo_cursor;
        FETCH NEXT FROM equipo_cursor INTO @EquipoNombre;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- Validar la existencia del equipo
            SELECT @EquipoId = EquipoId FROM Equipos WHERE Equipo = @EquipoNombre;
            
            IF @EquipoId IS NULL
            BEGIN
                PRINT 'El equipo "' + @EquipoNombre + '" no existe. Se omitirá su asignación.';
            END
            ELSE
            BEGIN
                -- Verificar si el robot ya está asignado al equipo
                IF EXISTS (SELECT 1 FROM Asignaciones WHERE RobotId = @RobotId AND EquipoId = @EquipoId)
                BEGIN
                    PRINT 'El robot ya está asignado al equipo "' + @EquipoNombre + '". Se omitirá su asignación.';
                END
                ELSE
                BEGIN
                    -- Insertar la nueva asignación no programada
                    INSERT INTO Asignaciones (RobotId, EquipoId, EsProgramado)
                    VALUES (@RobotId, @EquipoId, 0); -- EsProgramado = 0 para robots no programados

                    PRINT 'Robot asignado exitosamente al equipo "' + @EquipoNombre + '".';
                END
            END

            FETCH NEXT FROM equipo_cursor INTO @EquipoNombre;
        END

        CLOSE equipo_cursor;
        DEALLOCATE equipo_cursor;

        COMMIT TRANSACTION;
        PRINT 'Asignaciones completadas exitosamente.';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        -- Registrar el error en la tabla ErrorLog
        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'AsignarRobotOnline',
            ERROR_MESSAGE(),
            '@Robot = ' + @Robot + ', @Equipos = ' + @Equipos
        );

        -- Mostrar un mensaje de error
        PRINT 'Error: ' + ERROR_MESSAGE();
    END CATCH
END
GO
/****** Object:  StoredProcedure [dbo].[CargarProgramacionDiaria]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- Author:      <Author,,Name>
-- Create date: <Create Date,,>
-- Description: Carga una programación diaria para un robot y equipos específicos.
-- Modificado por: AI Agent
-- Fecha Modificación: <Current Date>
-- Descripción Modificación:
--   - @Equipos ahora acepta una lista de nombres de equipo separados por comas.
--   - Se utiliza SCOPE_IDENTITY() para obtener el ProgramacionId.
--   - Se procesan múltiples equipos, insertando o actualizando en dbo.Asignaciones.
--   - Se establece ProgramacionId y EsProgramado=1 en dbo.Asignaciones.
--   - Se manejan advertencias para equipos no encontrados.
--   - Se mantiene la lógica de transacción y actualización de Robot.EsOnline.
-- =============================================
CREATE PROCEDURE [dbo].[CargarProgramacionDiaria]
    @Robot NVARCHAR(100),
    @Equipos NVARCHAR(MAX), -- Comma-separated team names
    @HoraInicio NVARCHAR(MAX),
    @Tolerancia INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RobotId INT;
    DECLARE @NewProgramacionId INT;
    DECLARE @CurrentEquipoId INT;
    DECLARE @CurrentEquipoNombre NVARCHAR(100);
    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Obtener RobotId
        SELECT @RobotId = RobotId FROM dbo.Robots WHERE Robot = @Robot;

        IF @RobotId IS NULL
        BEGIN
            RAISERROR('El robot especificado no existe.', 16, 1);
            RETURN; -- Salir si el robot no existe
        END

        -- Insertar en Programaciones
        INSERT INTO dbo.Programaciones (RobotId, TipoProgramacion, HoraInicio, Tolerancia, Activo, FechaCreacion)
        VALUES (@RobotId, 'Diaria', @HoraInicio, @Tolerancia, 1, GETDATE());

        -- Obtener el ProgramacionId recién insertado
        SET @NewProgramacionId = SCOPE_IDENTITY();

        IF @NewProgramacionId IS NULL
        BEGIN
            RAISERROR('No se pudo obtener el ID de la nueva programación.', 16, 1);
            RETURN; -- Salir si no se pudo crear la programación
        END

        -- Actualizar el estado del Robot
        UPDATE dbo.Robots
        SET EsOnline = 0
        WHERE RobotId = @RobotId;

        -- Procesar cada equipo en la lista @Equipos
        DECLARE team_cursor CURSOR FOR
        SELECT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@Equipos, ',');

        OPEN team_cursor;
        FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @CurrentEquipoId = NULL; -- Reset for each team

            -- Obtener EquipoId para el equipo actual
            SELECT @CurrentEquipoId = EquipoId FROM dbo.Equipos WHERE Equipo = @CurrentEquipoNombre;

            IF @CurrentEquipoId IS NOT NULL
            BEGIN
                -- Verificar si la asignación ya existe
                IF EXISTS (SELECT 1 FROM dbo.Asignaciones WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId)
                BEGIN
                    UPDATE dbo.Asignaciones
                    SET EsProgramado = 1,
                        ProgramacionId = @NewProgramacionId,
                        Reservado = 0, -- Programación anula reserva manual
                        AsignadoPor = 'SP_Programacion_Diaria',
                        FechaAsignacion = GETDATE() -- Actualizar fecha de asignación/modificación
                    WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId;
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, ProgramacionId, Reservado, AsignadoPor, FechaAsignacion)
                    VALUES (@RobotId, @CurrentEquipoId, 1, @NewProgramacionId, 0, 'SP_Programacion_Diaria', GETDATE());
                END

                -- Actualizar el equipo para que no permita balanceo dinámico
                UPDATE dbo.Equipos
                SET PermiteBalanceoDinamico = 0
                WHERE EquipoId = @CurrentEquipoId;
            END
            ELSE
            BEGIN
                -- Equipo no encontrado, imprimir advertencia
                PRINT 'Warning: Equipo ' + @CurrentEquipoNombre + ' no encontrado y no será asignado.';
            END

            FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;
        END

        CLOSE team_cursor;
        DEALLOCATE team_cursor;

        COMMIT TRANSACTION;
        PRINT 'Programación diaria cargada y equipos asignados/actualizados exitosamente para el robot ' + @Robot;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SELECT
            @ErrorMessage = ERROR_MESSAGE(),
            @ErrorSeverity = ERROR_SEVERITY(),
            @ErrorState = ERROR_STATE();

        -- Registrar el error en la tabla ErrorLog
        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = '@Robot = ' + @Robot + 
                        ', @Equipos = ' + @Equipos + 
                        ', @HoraInicio = ' + CONVERT(NVARCHAR(8), @HoraInicio, 108) + 
                        ', @Tolerancia = ' + CAST(@Tolerancia AS NVARCHAR(10));

        -- Luego:
        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'CargarProgramacionEspecifica',
            ERROR_MESSAGE(),
            @Parametros
        );

        -- Mostrar un mensaje de error
        PRINT 'Error: ' + ERROR_MESSAGE();

        -- Relanzar el error para que el cliente lo reciba
        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO
/****** Object:  StoredProcedure [dbo].[CargarProgramacionEspecifica]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- Author:      <Author,,Name>
-- Create date: <Create Date,,>
-- Description: Carga una programación específica para un robot y equipos determinados.
-- Modificado por: AI Agent
-- Fecha Modificación: <Current Date>
-- Descripción Modificación:
--   - @Equipos ahora acepta una lista de nombres de equipo separados por comas.
--   - Se utiliza SCOPE_IDENTITY() para obtener el ProgramacionId.
--   - Se procesan múltiples equipos, insertando o actualizando en dbo.Asignaciones.
--   - Se establece ProgramacionId y EsProgramado=1 en dbo.Asignaciones.
--   - Se manejan advertencias para equipos no encontrados.
--   - Se mantiene la lógica de transacción y actualización de Robot.EsOnline.
-- =============================================
CREATE PROCEDURE [dbo].[CargarProgramacionEspecifica]
    @Robot NVARCHAR(100),
    @Equipos NVARCHAR(MAX), -- Comma-separated team names
    @FechaEspecifica NVARCHAR(MAX),
    @HoraInicio NVARCHAR(MAX),
    @Tolerancia INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RobotId INT;
    DECLARE @NewProgramacionId INT;
    DECLARE @CurrentEquipoId INT;
    DECLARE @CurrentEquipoNombre NVARCHAR(100);
    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Obtener RobotId
        SELECT @RobotId = RobotId FROM dbo.Robots WHERE Robot = @Robot;

        IF @RobotId IS NULL
        BEGIN
            RAISERROR('El robot especificado no existe.', 16, 1);
            RETURN; 
        END

        -- Insertar en Programaciones
        INSERT INTO dbo.Programaciones (RobotId, TipoProgramacion, FechaEspecifica, HoraInicio, Tolerancia, Activo, FechaCreacion)
        VALUES (@RobotId, 'Especifica', @FechaEspecifica, @HoraInicio, @Tolerancia, 1, GETDATE());

        -- Obtener el ProgramacionId recién insertado
        SET @NewProgramacionId = SCOPE_IDENTITY();

        IF @NewProgramacionId IS NULL
        BEGIN
            RAISERROR('No se pudo obtener el ID de la nueva programación.', 16, 1);
            RETURN;
        END

        -- Actualizar el estado del Robot
        UPDATE dbo.Robots
        SET EsOnline = 0
        WHERE RobotId = @RobotId;

        -- Procesar cada equipo en la lista @Equipos
        DECLARE team_cursor CURSOR FOR
        SELECT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@Equipos, ',');

        OPEN team_cursor;
        FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @CurrentEquipoId = NULL; 

            -- Obtener EquipoId para el equipo actual
            SELECT @CurrentEquipoId = EquipoId FROM dbo.Equipos WHERE Equipo = @CurrentEquipoNombre;

            IF @CurrentEquipoId IS NOT NULL
            BEGIN
                -- Verificar si la asignación ya existe
                IF EXISTS (SELECT 1 FROM dbo.Asignaciones WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId)
                BEGIN
                    UPDATE dbo.Asignaciones
                    SET EsProgramado = 1,
                        ProgramacionId = @NewProgramacionId,
                        Reservado = 0, 
                        AsignadoPor = 'SP_Programacion_Especifica',
                        FechaAsignacion = GETDATE() 
                    WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId;
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, ProgramacionId, Reservado, AsignadoPor, FechaAsignacion)
                    VALUES (@RobotId, @CurrentEquipoId, 1, @NewProgramacionId, 0, 'SP_Programacion_Especifica', GETDATE());
                END

                -- Actualizar el equipo para que no permita balanceo dinámico
                UPDATE dbo.Equipos
                SET PermiteBalanceoDinamico = 0
                WHERE EquipoId = @CurrentEquipoId;
            END
            ELSE
            BEGIN
                PRINT 'Warning: Equipo ' + @CurrentEquipoNombre + ' no encontrado y no será asignado.';
            END

            FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;
        END

        CLOSE team_cursor;
        DEALLOCATE team_cursor;

        COMMIT TRANSACTION;
        PRINT 'Programación específica cargada y equipos asignados/actualizados exitosamente para el robot ' + @Robot;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SELECT
            @ErrorMessage = ERROR_MESSAGE(),
            @ErrorSeverity = ERROR_SEVERITY(),
            @ErrorState = ERROR_STATE();

        -- Registrar el error en la tabla ErrorLog
        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = '@Robot = ' + @Robot + 
                        ', @Equipos = ' + @Equipos + 
                        ', @HoraInicio = ' + CONVERT(NVARCHAR(8), @HoraInicio, 108) + 
                        ', @Tolerancia = ' + CAST(@Tolerancia AS NVARCHAR(10));

        -- Luego:
        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'CargarProgramacionEspecifica',
            ERROR_MESSAGE(),
            @Parametros
        );

        -- Mostrar un mensaje de error
        PRINT 'Error: ' + ERROR_MESSAGE();

        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO
/****** Object:  StoredProcedure [dbo].[CargarProgramacionMensual]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- Author:      <Author,,Name>
-- Create date: <Create Date,,>
-- Description: Carga una programación mensual para un robot y equipos específicos.
-- Modificado por: AI Agent
-- Fecha Modificación: <Current Date>
-- Descripción Modificación:
--   - @Equipos ahora acepta una lista de nombres de equipo separados por comas.
--   - Se utiliza SCOPE_IDENTITY() para obtener el ProgramacionId.
--   - Se procesan múltiples equipos, insertando o actualizando en dbo.Asignaciones.
--   - Se establece ProgramacionId y EsProgramado=1 en dbo.Asignaciones.
--   - Se manejan advertencias para equipos no encontrados.
--   - Se mantiene la lógica de transacción y actualización de Robot.EsOnline.
-- =============================================
CREATE PROCEDURE [dbo].[CargarProgramacionMensual]
    @Robot NVARCHAR(100),
    @Equipos NVARCHAR(MAX), -- Comma-separated team names
    @DiaDelMes INT,
    @HoraInicio TIME, -- Assuming HoraInicio is TIME for Mensual, adjust if different
    @Tolerancia INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RobotId INT;
    DECLARE @NewProgramacionId INT;
    DECLARE @CurrentEquipoId INT;
    DECLARE @CurrentEquipoNombre NVARCHAR(100);
    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;
    DECLARE @HoraInicioStr NVARCHAR(MAX);

    -- Convert HoraInicio TIME to NVARCHAR(MAX) for Programaciones table if its type is NVARCHAR(MAX)
    SET @HoraInicioStr = CONVERT(NVARCHAR(8), @HoraInicio); -- HH:MM:SS format

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Obtener RobotId
        SELECT @RobotId = RobotId FROM dbo.Robots WHERE Robot = @Robot;

        IF @RobotId IS NULL
        BEGIN
            RAISERROR('El robot especificado no existe.', 16, 1);
            RETURN; 
        END

        -- Insertar en Programaciones
        -- Note: Assuming Programaciones.HoraInicio is NVARCHAR(MAX). If it's TIME, use @HoraInicio directly.
        INSERT INTO dbo.Programaciones (RobotId, TipoProgramacion, DiaDelMes, HoraInicio, Tolerancia, Activo, FechaCreacion)
        VALUES (@RobotId, 'Mensual', @DiaDelMes, @HoraInicioStr, @Tolerancia, 1, GETDATE());

        -- Obtener el ProgramacionId recién insertado
        SET @NewProgramacionId = SCOPE_IDENTITY();

        IF @NewProgramacionId IS NULL
        BEGIN
            RAISERROR('No se pudo obtener el ID de la nueva programación.', 16, 1);
            RETURN;
        END

        -- Actualizar el estado del Robot
        UPDATE dbo.Robots
        SET EsOnline = 0
        WHERE RobotId = @RobotId;

        -- Procesar cada equipo en la lista @Equipos
        DECLARE team_cursor CURSOR FOR
        SELECT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@Equipos, ',');

        OPEN team_cursor;
        FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @CurrentEquipoId = NULL; 

            -- Obtener EquipoId para el equipo actual
            SELECT @CurrentEquipoId = EquipoId FROM dbo.Equipos WHERE Equipo = @CurrentEquipoNombre;

            IF @CurrentEquipoId IS NOT NULL
            BEGIN
                -- Verificar si la asignación ya existe
                IF EXISTS (SELECT 1 FROM dbo.Asignaciones WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId)
                BEGIN
                    UPDATE dbo.Asignaciones
                    SET EsProgramado = 1,
                        ProgramacionId = @NewProgramacionId,
                        Reservado = 0, 
                        AsignadoPor = 'SP_Programacion_Mensual',
                        FechaAsignacion = GETDATE() 
                    WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId;
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, ProgramacionId, Reservado, AsignadoPor, FechaAsignacion)
                    VALUES (@RobotId, @CurrentEquipoId, 1, @NewProgramacionId, 0, 'SP_Programacion_Mensual', GETDATE());
                END

                -- Actualizar el equipo para que no permita balanceo dinámico
                UPDATE dbo.Equipos
                SET PermiteBalanceoDinamico = 0
                WHERE EquipoId = @CurrentEquipoId;
            END
            ELSE
            BEGIN
                PRINT 'Warning: Equipo ' + @CurrentEquipoNombre + ' no encontrado y no será asignado.';
            END

            FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;
        END

        CLOSE team_cursor;
        DEALLOCATE team_cursor;

        COMMIT TRANSACTION;
        PRINT 'Programación mensual cargada y equipos asignados/actualizados exitosamente para el robot ' + @Robot;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SELECT
            @ErrorMessage = ERROR_MESSAGE(),
            @ErrorSeverity = ERROR_SEVERITY(),
            @ErrorState = ERROR_STATE();

        -- Registrar el error en la tabla ErrorLog
        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = '@Robot = ' + @Robot + 
                        ', @Equipos = ' + @Equipos + 
                        ', @HoraInicio = ' + CONVERT(NVARCHAR(8), @HoraInicio, 108) + 
                        ', @Tolerancia = ' + CAST(@Tolerancia AS NVARCHAR(10));

        -- Luego:
        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'CargarProgramacionEspecifica',
            ERROR_MESSAGE(),
            @Parametros
        );


        -- Mostrar un mensaje de error
        PRINT 'Error: ' + ERROR_MESSAGE();

        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO
/****** Object:  StoredProcedure [dbo].[CargarProgramacionSemanal]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- Author:      <Author,,Name>
-- Create date: <Create Date,,>
-- Description: Carga una programación semanal para un robot y equipos específicos.
-- Modificado por: AI Agent
-- Fecha Modificación: <Current Date>
-- Descripción Modificación:
--   - @Equipos ahora acepta una lista de nombres de equipo separados por comas.
--   - Se utiliza SCOPE_IDENTITY() para obtener el ProgramacionId.
--   - Se procesan múltiples equipos, insertando o actualizando en dbo.Asignaciones.
--   - Se establece ProgramacionId y EsProgramado=1 en dbo.Asignaciones.
--   - Se manejan advertencias para equipos no encontrados.
--   - Se mantiene la lógica de transacción y actualización de Robot.EsOnline.
-- =============================================
CREATE PROCEDURE [dbo].[CargarProgramacionSemanal]
    @Robot NVARCHAR(100),
    @Equipos NVARCHAR(MAX), -- Comma-separated team names
    @DiasSemana NVARCHAR(100),
    @HoraInicio NVARCHAR(MAX),
    @Tolerancia INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RobotId INT;
    DECLARE @NewProgramacionId INT;
    DECLARE @CurrentEquipoId INT;
    DECLARE @CurrentEquipoNombre NVARCHAR(100);
    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Obtener RobotId
        SELECT @RobotId = RobotId FROM dbo.Robots WHERE Robot = @Robot;

        IF @RobotId IS NULL
        BEGIN
            RAISERROR('El robot especificado no existe.', 16, 1);
            RETURN; 
        END

        -- Insertar en Programaciones
        INSERT INTO dbo.Programaciones (RobotId, TipoProgramacion, DiasSemana, HoraInicio, Tolerancia, Activo, FechaCreacion)
        VALUES (@RobotId, 'Semanal', @DiasSemana, @HoraInicio, @Tolerancia, 1, GETDATE());

        -- Obtener el ProgramacionId recién insertado
        SET @NewProgramacionId = SCOPE_IDENTITY();

        IF @NewProgramacionId IS NULL
        BEGIN
            RAISERROR('No se pudo obtener el ID de la nueva programación.', 16, 1);
            RETURN;
        END

        -- Actualizar el estado del Robot
        UPDATE dbo.Robots
        SET EsOnline = 0
        WHERE RobotId = @RobotId;

        -- Procesar cada equipo en la lista @Equipos
        DECLARE team_cursor CURSOR FOR
        SELECT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@Equipos, ',');

        OPEN team_cursor;
        FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @CurrentEquipoId = NULL; 

            -- Obtener EquipoId para el equipo actual
            SELECT @CurrentEquipoId = EquipoId FROM dbo.Equipos WHERE Equipo = @CurrentEquipoNombre;

            IF @CurrentEquipoId IS NOT NULL
            BEGIN
                -- Verificar si la asignación ya existe
                IF EXISTS (SELECT 1 FROM dbo.Asignaciones WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId)
                BEGIN
                    UPDATE dbo.Asignaciones
                    SET EsProgramado = 1,
                        ProgramacionId = @NewProgramacionId,
                        Reservado = 0, 
                        AsignadoPor = 'SP_Programacion_Semanal',
                        FechaAsignacion = GETDATE() 
                    WHERE RobotId = @RobotId AND EquipoId = @CurrentEquipoId;
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, ProgramacionId, Reservado, AsignadoPor, FechaAsignacion)
                    VALUES (@RobotId, @CurrentEquipoId, 1, @NewProgramacionId, 0, 'SP_Programacion_Semanal', GETDATE());
                END

                -- Actualizar el equipo para que no permita balanceo dinámico
                UPDATE dbo.Equipos
                SET PermiteBalanceoDinamico = 0
                WHERE EquipoId = @CurrentEquipoId;
            END
            ELSE
            BEGIN
                PRINT 'Warning: Equipo ' + @CurrentEquipoNombre + ' no encontrado y no será asignado.';
            END

            FETCH NEXT FROM team_cursor INTO @CurrentEquipoNombre;
        END

        CLOSE team_cursor;
        DEALLOCATE team_cursor;

        COMMIT TRANSACTION;
        PRINT 'Programación semanal cargada y equipos asignados/actualizados exitosamente para el robot ' + @Robot;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SELECT
            @ErrorMessage = ERROR_MESSAGE(),
            @ErrorSeverity = ERROR_SEVERITY(),
            @ErrorState = ERROR_STATE();

        -- Registrar el error en la tabla ErrorLog
        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = '@Robot = ' + @Robot + 
                        ', @Equipos = ' + @Equipos + 
                        ', @HoraInicio = ' + CONVERT(NVARCHAR(8), @HoraInicio, 108) + 
                        ', @Tolerancia = ' + CAST(@Tolerancia AS NVARCHAR(10));

        -- Luego:
        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'CargarProgramacionEspecifica',
            ERROR_MESSAGE(),
            @Parametros
        );

        -- Mostrar un mensaje de error
        PRINT 'Error: ' + ERROR_MESSAGE();

        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO
/****** Object:  StoredProcedure [dbo].[EliminarProgramacionCompleta]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[EliminarProgramacionCompleta]
    @ProgramacionId INT,
    @RobotId INT,
    @UsuarioModifica NVARCHAR(50) = 'WebApp_Delete'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @ErrorMessage NVARCHAR(4000);
    DECLARE @ErrorSeverity INT;
    DECLARE @ErrorState INT;

    CREATE TABLE #EquiposDelCronogramaEliminado (EquipoId INT PRIMARY KEY);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 1. Verificación de existencia
        IF NOT EXISTS (
            SELECT 1
            FROM dbo.Programaciones
            WHERE ProgramacionId = @ProgramacionId AND RobotId = @RobotId
        )
        BEGIN
            RAISERROR('Programación no encontrada para el RobotId especificado o ya ha sido eliminada.', 16, 1);
            RETURN;
        END

        -- 2. Equipos afectados
        INSERT INTO #EquiposDelCronogramaEliminado (EquipoId)
        SELECT DISTINCT EquipoId
        FROM dbo.Asignaciones
        WHERE ProgramacionId = @ProgramacionId
          AND EsProgramado = 1
          AND RobotId = @RobotId;

        -- 3. Desasignar equipos de esta programación
        UPDATE dbo.Asignaciones
        SET EsProgramado = 0,
            ProgramacionId = NULL,
            AsignadoPor = @UsuarioModifica,
            FechaAsignacion = GETDATE()
        WHERE ProgramacionId = @ProgramacionId AND RobotId = @RobotId;

        -- 4. Eliminar la programación
        DELETE FROM dbo.Programaciones
        WHERE ProgramacionId = @ProgramacionId AND RobotId = @RobotId;

        -- 5. Restaurar PermiteBalanceoDinamico si el equipo ya no está en ninguna otra programación
        UPDATE E
        SET PermiteBalanceoDinamico = 1
        FROM dbo.Equipos E
        WHERE EXISTS (
            SELECT 1 FROM #EquiposDelCronogramaEliminado ED
            WHERE E.EquipoId = ED.EquipoId
        )
        AND NOT EXISTS (
            SELECT 1 FROM dbo.Asignaciones A
            WHERE A.EquipoId = E.EquipoId AND A.EsProgramado = 1 AND A.ProgramacionId IS NOT NULL
        );

        COMMIT TRANSACTION;

        PRINT 'Programación ID ' + CAST(@ProgramacionId AS VARCHAR(10)) + ' eliminada exitosamente.';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SET @ErrorMessage = ERROR_MESSAGE();
        SET @ErrorSeverity = ERROR_SEVERITY();
        SET @ErrorState = ERROR_STATE();

        DECLARE @Parametros NVARCHAR(MAX);
        SET @Parametros = 
            '@ProgramacionId = ' + CAST(@ProgramacionId AS NVARCHAR) +
            ', @RobotId = ' + CAST(@RobotId AS NVARCHAR);

        INSERT INTO ErrorLog (Usuario, SPNombre, ErrorMensaje, Parametros)
        VALUES (
            SUSER_NAME(),
            'EliminarProgramacionCompleta',
            @ErrorMessage,
            @Parametros
        );

        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH

    -- Limpieza de tabla temporal
    IF OBJECT_ID('tempdb..#EquiposDelCronogramaEliminado') IS NOT NULL
        DROP TABLE #EquiposDelCronogramaEliminado;
END
GO
/****** Object:  StoredProcedure [dbo].[ObtenerRobotsEjecutables]    Script Date: 17/6/2025 08:43:20 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[ObtenerRobotsEjecutables]
AS
BEGIN
    SET NOCOUNT ON;
    -- Configurar el idioma español
    SET LANGUAGE Spanish;

    DECLARE @FechaActual DATETIME = GETDATE();
    DECLARE @HoraActual TIME(0) = CAST(@FechaActual AS TIME(0));
    DECLARE @DiaSemanaActual NVARCHAR(2) = LEFT(DATENAME(WEEKDAY, @FechaActual), 2);

    -- Tabla temporal para almacenar los resultados
    CREATE TABLE #ResultadosRobots (
        RobotId INT,
        EquipoId INT,
        UserId INT,
        Hora TIME(0),
        EsProgramado BIT
    )

    -- Insertar robots programados elegibles
    INSERT INTO #ResultadosRobots (RobotId, EquipoId, UserId, Hora, EsProgramado)
    SELECT 
        R.RobotId,
        A.EquipoId,
        E.UserId,
        P.HoraInicio,
        1 AS EsProgramado
    FROM Robots R
    INNER JOIN Asignaciones A ON R.RobotId = A.RobotId
    INNER JOIN Equipos E ON A.EquipoId = E.EquipoId
    INNER JOIN Programaciones P ON R.RobotId = P.RobotId
    WHERE 
        A.EsProgramado = 1
        AND R.Activo = 1
        AND (
            (P.TipoProgramacion = 'Diaria' AND @HoraActual BETWEEN P.HoraInicio AND DATEADD(MINUTE, P.Tolerancia, P.HoraInicio))
            OR (P.TipoProgramacion = 'Semanal' AND CHARINDEX(@DiaSemanaActual, P.DiasSemana) > 0 AND @HoraActual BETWEEN P.HoraInicio AND DATEADD(MINUTE, P.Tolerancia, P.HoraInicio))
            OR (P.TipoProgramacion = 'Mensual' AND P.DiaDelMes = DAY(@FechaActual) AND @HoraActual BETWEEN P.HoraInicio AND DATEADD(MINUTE, P.Tolerancia, P.HoraInicio))
            OR (P.TipoProgramacion = 'Especifica' AND P.FechaEspecifica = CAST(@FechaActual AS DATE) AND @HoraActual BETWEEN P.HoraInicio AND DATEADD(MINUTE, P.Tolerancia, P.HoraInicio))
        )
        AND NOT EXISTS (
            SELECT 1
            FROM Ejecuciones E
            WHERE 1=1
				AND E.RobotId = R.RobotId
                AND E.EquipoId = A.EquipoId
                AND CAST(E.FechaInicio AS DATE) = CAST(@FechaActual AS DATE)
                AND E.Hora = P.HoraInicio
        )
        AND NOT EXISTS (
            SELECT 1
            FROM Ejecuciones E
            WHERE 1=1
				AND E.EquipoId = A.EquipoId 
				AND E.Estado in ('DEPLOYED', 'QUEUED', 'PENDING_EXECUTION', 'RUNNING', 'UPDATE','RUN_PAUSED')
        )

    -- Insertar robots online elegibles para equipos sin robots programados o en ejecución
    INSERT INTO #ResultadosRobots (RobotId, EquipoId, UserId, Hora, EsProgramado)
    SELECT 
        R.RobotId,
        A.EquipoId,
        E.UserId,
        NULL AS Hora,
        0 AS EsProgramado
    FROM Robots R
    INNER JOIN Asignaciones A ON R.RobotId = A.RobotId
    INNER JOIN Equipos E ON A.EquipoId = E.EquipoId
    WHERE 
        R.EsOnline = 1
        AND R.Activo = 1
        AND A.EsProgramado = 0
        AND NOT EXISTS ( -- no repetir equipo ya asignado
            SELECT 1
            FROM #ResultadosRobots RR
            WHERE RR.EquipoId = A.EquipoId
        )
        AND NOT EXISTS (
            SELECT 1
            FROM Ejecuciones E
            WHERE 1=1
				AND E.EquipoId = A.EquipoId 
				AND E.Estado in ('DEPLOYED', 'QUEUED', 'PENDING_EXECUTION', 'RUNNING', 'UPDATE','RUN_PAUSED')
        )

    -- Devolver los resultados
    SELECT RobotId, EquipoId, UserId, Hora
    FROM #ResultadosRobots
    ORDER BY EsProgramado DESC, Hora

    -- Limpiar la tabla temporal
    DROP TABLE #ResultadosRobots
END
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'(Opcional, pero útil) Podría indicar "DisponibleEnPoolPivote", "AsignadoDinamicoA_RobotX", "EnMantenimientoManual", etc.' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Equipos', @level2type=N'COLUMN',@level2name=N'EstadoBalanceador'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'1-Diaria, 2-Semanal, 3-Mensual, 4-Especifica' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Programaciones', @level2type=N'COLUMN',@level2name=N'TipoProgramacion'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Número mínimo de equipos que el balanceador intentará mantener asignado si hay tickets.' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Robots', @level2type=N'COLUMN',@level2name=N'MinEquipos'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Límite de equipos que el balanceador puede asignar dinámicamente a este robot. (default -1 o un número alto)' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Robots', @level2type=N'COLUMN',@level2name=N'MaxEquipos'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Para decidir qué robot obtiene recursos si son escasos. Menor número = mayor prioridad.' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Robots', @level2type=N'COLUMN',@level2name=N'PrioridadBalanceo'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_DiagramPane1', @value=N'[0E232FF0-B466-11cf-A24F-00AA00A3EFFF, 1.00]
Begin DesignProperties = 
   Begin PaneConfigurations = 
      Begin PaneConfiguration = 0
         NumPanes = 4
         Configuration = "(H (1[40] 4[20] 2[20] 3) )"
      End
      Begin PaneConfiguration = 1
         NumPanes = 3
         Configuration = "(H (1 [50] 4 [25] 3))"
      End
      Begin PaneConfiguration = 2
         NumPanes = 3
         Configuration = "(H (1 [50] 2 [25] 3))"
      End
      Begin PaneConfiguration = 3
         NumPanes = 3
         Configuration = "(H (4 [30] 2 [40] 3))"
      End
      Begin PaneConfiguration = 4
         NumPanes = 2
         Configuration = "(H (1 [56] 3))"
      End
      Begin PaneConfiguration = 5
         NumPanes = 2
         Configuration = "(H (2 [66] 3))"
      End
      Begin PaneConfiguration = 6
         NumPanes = 2
         Configuration = "(H (4 [50] 3))"
      End
      Begin PaneConfiguration = 7
         NumPanes = 1
         Configuration = "(V (3))"
      End
      Begin PaneConfiguration = 8
         NumPanes = 3
         Configuration = "(H (1[56] 4[18] 2) )"
      End
      Begin PaneConfiguration = 9
         NumPanes = 2
         Configuration = "(H (1 [75] 4))"
      End
      Begin PaneConfiguration = 10
         NumPanes = 2
         Configuration = "(H (1[66] 2) )"
      End
      Begin PaneConfiguration = 11
         NumPanes = 2
         Configuration = "(H (4 [60] 2))"
      End
      Begin PaneConfiguration = 12
         NumPanes = 1
         Configuration = "(H (1) )"
      End
      Begin PaneConfiguration = 13
         NumPanes = 1
         Configuration = "(V (4))"
      End
      Begin PaneConfiguration = 14
         NumPanes = 1
         Configuration = "(V (2))"
      End
      ActivePaneConfig = 0
   End
   Begin DiagramPane = 
      Begin Origin = 
         Top = 0
         Left = 0
      End
      Begin Tables = 
         Begin Table = "A"
            Begin Extent = 
               Top = 7
               Left = 48
               Bottom = 170
               Right = 242
            End
            DisplayFlags = 280
            TopColumn = 0
         End
         Begin Table = "EQ"
            Begin Extent = 
               Top = 111
               Left = 303
               Bottom = 274
               Right = 497
            End
            DisplayFlags = 280
            TopColumn = 0
         End
         Begin Table = "R"
            Begin Extent = 
               Top = 7
               Left = 532
               Bottom = 170
               Right = 726
            End
            DisplayFlags = 280
            TopColumn = 0
         End
      End
   End
   Begin SQLPane = 
   End
   Begin DataPane = 
      Begin ParameterDefaults = ""
      End
      Begin ColumnWidths = 9
         Width = 284
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
      End
   End
   Begin CriteriaPane = 
      Begin ColumnWidths = 11
         Column = 1440
         Alias = 900
         Table = 1176
         Output = 720
         Append = 1400
         NewValue = 1170
         SortType = 1356
         SortOrder = 1416
         GroupBy = 1350
         Filter = 1356
         Or = 1350
         Or = 1350
         Or = 1350
      End
   End
End
' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'VIEW',@level1name=N'AsignacionesView'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_DiagramPaneCount', @value=1 , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'VIEW',@level1name=N'AsignacionesView'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_DiagramPane1', @value=N'[0E232FF0-B466-11cf-A24F-00AA00A3EFFF, 1.00]
Begin DesignProperties = 
   Begin PaneConfigurations = 
      Begin PaneConfiguration = 0
         NumPanes = 4
         Configuration = "(H (1[40] 4[20] 2[20] 3) )"
      End
      Begin PaneConfiguration = 1
         NumPanes = 3
         Configuration = "(H (1 [50] 4 [25] 3))"
      End
      Begin PaneConfiguration = 2
         NumPanes = 3
         Configuration = "(H (1 [50] 2 [25] 3))"
      End
      Begin PaneConfiguration = 3
         NumPanes = 3
         Configuration = "(H (4 [30] 2 [40] 3))"
      End
      Begin PaneConfiguration = 4
         NumPanes = 2
         Configuration = "(H (1 [56] 3))"
      End
      Begin PaneConfiguration = 5
         NumPanes = 2
         Configuration = "(H (2 [66] 3))"
      End
      Begin PaneConfiguration = 6
         NumPanes = 2
         Configuration = "(H (4 [50] 3))"
      End
      Begin PaneConfiguration = 7
         NumPanes = 1
         Configuration = "(V (3))"
      End
      Begin PaneConfiguration = 8
         NumPanes = 3
         Configuration = "(H (1[56] 4[18] 2) )"
      End
      Begin PaneConfiguration = 9
         NumPanes = 2
         Configuration = "(H (1 [75] 4))"
      End
      Begin PaneConfiguration = 10
         NumPanes = 2
         Configuration = "(H (1[66] 2) )"
      End
      Begin PaneConfiguration = 11
         NumPanes = 2
         Configuration = "(H (4 [60] 2))"
      End
      Begin PaneConfiguration = 12
         NumPanes = 1
         Configuration = "(H (1) )"
      End
      Begin PaneConfiguration = 13
         NumPanes = 1
         Configuration = "(V (4))"
      End
      Begin PaneConfiguration = 14
         NumPanes = 1
         Configuration = "(V (2))"
      End
      ActivePaneConfig = 0
   End
   Begin DiagramPane = 
      Begin Origin = 
         Top = 0
         Left = 0
      End
      Begin Tables = 
         Begin Table = "E"
            Begin Extent = 
               Top = 7
               Left = 48
               Bottom = 288
               Right = 242
            End
            DisplayFlags = 280
            TopColumn = 0
         End
         Begin Table = "EQ"
            Begin Extent = 
               Top = 7
               Left = 290
               Bottom = 170
               Right = 484
            End
            DisplayFlags = 280
            TopColumn = 0
         End
         Begin Table = "R"
            Begin Extent = 
               Top = 7
               Left = 532
               Bottom = 170
               Right = 726
            End
            DisplayFlags = 280
            TopColumn = 0
         End
      End
   End
   Begin SQLPane = 
   End
   Begin DataPane = 
      Begin ParameterDefaults = ""
      End
      Begin ColumnWidths = 12
         Width = 284
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 1200
         Width = 2496
         Width = 1200
         Width = 1944
         Width = 1200
      End
   End
   Begin CriteriaPane = 
      Begin ColumnWidths = 11
         Column = 1440
         Alias = 900
         Table = 1170
         Output = 720
         Append = 1400
         NewValue = 1170
         SortType = 1350
         SortOrder = 1410
         GroupBy = 1350
         Filter = 1350
         Or = 1350
         Or = 1350
         Or = 1350
      End
   End
End
' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'VIEW',@level1name=N'EjecucionesActivas'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_DiagramPaneCount', @value=1 , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'VIEW',@level1name=N'EjecucionesActivas'
GO
