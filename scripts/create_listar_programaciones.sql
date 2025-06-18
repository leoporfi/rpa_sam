-- =============================================
-- Author:		<Author,,Name>
-- Create date: <Create Date,,>
-- Description:	<Description,,>
-- =============================================
CREATE PROCEDURE [dbo].[ListarProgramaciones]
AS
BEGIN
	-- SET NOCOUNT ON added to prevent extra result sets from
	-- interfering with SELECT statements.
	SET NOCOUNT ON;

    -- Insert statements for procedure here
	SELECT
        P.ProgramacionId,
        P.RobotId,
        R.Robot AS RobotNombre,
        P.TipoProgramacion,
        P.HoraInicio,
        P.DiasSemana,
        P.DiaDelMes,
        P.FechaEspecifica,
        P.Tolerancia,
        P.Activo,
        P.FechaCreacion,
        P.FechaModificacion,
        STRING_AGG(E.Equipo, ', ') WITHIN GROUP (ORDER BY E.Equipo) AS EquiposProgramados
    FROM
        Programaciones P
    INNER JOIN
        Robots R ON P.RobotId = R.RobotId
    LEFT JOIN
        Asignaciones A ON P.ProgramacionId = A.ProgramacionId
    LEFT JOIN
        Equipos E ON A.EquipoId = E.EquipoId
    GROUP BY
        P.ProgramacionId,
        P.RobotId,
        R.Robot,
        P.TipoProgramacion,
        P.HoraInicio,
        P.DiasSemana,
        P.DiaDelMes,
        P.FechaEspecifica,
        P.Tolerancia,
        P.Activo,
        P.FechaCreacion,
        P.FechaModificacion
    ORDER BY
        P.ProgramacionId;
END
GO
