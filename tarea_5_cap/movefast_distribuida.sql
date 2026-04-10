USE master;
GO

IF DB_ID('DB_Catalogos_MoveFast') IS NOT NULL DROP DATABASE DB_Catalogos_MoveFast;
IF DB_ID('DB_Operaciones_GT') IS NOT NULL DROP DATABASE DB_Operaciones_GT;
IF DB_ID('DB_Operaciones_MX') IS NOT NULL DROP DATABASE DB_Operaciones_MX;
IF DB_ID('DB_Operaciones_US') IS NOT NULL DROP DATABASE DB_Operaciones_US;
IF DB_ID('DB_Reporting_MoveFast') IS NOT NULL DROP DATABASE DB_Reporting_MoveFast;
GO

CREATE DATABASE DB_Catalogos_MoveFast;
CREATE DATABASE DB_Operaciones_GT;
CREATE DATABASE DB_Operaciones_MX;
CREATE DATABASE DB_Operaciones_US;
CREATE DATABASE DB_Reporting_MoveFast;
GO

/* =============================
   CATALOGOS GLOBALES
   ============================= */
USE DB_Catalogos_MoveFast;
GO

CREATE TABLE Paises (
    IdPais INT PRIMARY KEY,
    CodigoPais CHAR(2) NOT NULL UNIQUE,
    NombrePais VARCHAR(60) NOT NULL
);

CREATE TABLE Ciudades (
    IdCiudad INT PRIMARY KEY,
    IdPais INT NOT NULL,
    NombreCiudad VARCHAR(80) NOT NULL,
    Activa BIT NOT NULL DEFAULT 1,
    FOREIGN KEY (IdPais) REFERENCES Paises(IdPais)
);

CREATE TABLE TiposVehiculo (
    IdTipoVehiculo INT PRIMARY KEY,
    NombreTipo VARCHAR(40) NOT NULL,
    TarifaBase DECIMAL(10,2) NOT NULL
);

CREATE TABLE MetodosPago (
    IdMetodoPago INT PRIMARY KEY,
    NombreMetodo VARCHAR(40) NOT NULL
);

INSERT INTO Paises (IdPais, CodigoPais, NombrePais)
VALUES
(1, 'GT', 'Guatemala'),
(2, 'MX', 'Mexico'),
(3, 'US', 'Estados Unidos');

INSERT INTO Ciudades (IdCiudad, IdPais, NombreCiudad, Activa)
VALUES
(101, 1, 'Ciudad de Guatemala', 1),
(102, 1, 'Quetzaltenango', 1),
(201, 2, 'Ciudad de Mexico', 1),
(202, 2, 'Monterrey', 1),
(301, 3, 'Miami', 1),
(302, 3, 'Los Angeles', 1);

INSERT INTO TiposVehiculo (IdTipoVehiculo, NombreTipo, TarifaBase)
VALUES
(1, 'Economico', 12.00),
(2, 'Confort', 20.00),
(3, 'XL', 28.00);

INSERT INTO MetodosPago (IdMetodoPago, NombreMetodo)
VALUES
(1, 'Tarjeta'),
(2, 'Efectivo'),
(3, 'Billetera Digital');
GO

/* =============================
   SHARD GT
   ============================= */
USE DB_Operaciones_GT;
GO

CREATE TABLE Conductores (
    IdConductor INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    Estado VARCHAR(20) NOT NULL,
    IdTipoVehiculo INT NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Usuarios (
    IdUsuario INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Viajes (
    IdViaje INT PRIMARY KEY,
    IdUsuario INT NOT NULL,
    IdConductor INT NOT NULL,
    IdCiudad INT NOT NULL,
    FechaSolicitud DATETIME NOT NULL,
    Origen VARCHAR(120) NOT NULL,
    Destino VARCHAR(120) NOT NULL,
    DistanciaKm DECIMAL(8,2) NOT NULL,
    TarifaCalculada DECIMAL(10,2) NOT NULL,
    Estado VARCHAR(30) NOT NULL,
    FOREIGN KEY (IdUsuario) REFERENCES Usuarios(IdUsuario),
    FOREIGN KEY (IdConductor) REFERENCES Conductores(IdConductor)
);

CREATE TABLE Pagos (
    IdPago INT PRIMARY KEY,
    IdViaje INT NOT NULL,
    IdMetodoPago INT NOT NULL,
    Monto DECIMAL(10,2) NOT NULL,
    EstadoPago VARCHAR(20) NOT NULL,
    FechaPago DATETIME NOT NULL DEFAULT GETDATE(),
    FOREIGN KEY (IdViaje) REFERENCES Viajes(IdViaje)
);
GO

INSERT INTO Conductores VALUES
(1101, 'Carlos Ramirez', 'Disponible', 1, GETDATE()),
(1102, 'Ana Lopez', 'En Viaje', 2, GETDATE());

INSERT INTO Usuarios VALUES
(5101, 'Maria Perez', GETDATE()),
(5102, 'Juan Ortiz', GETDATE());

INSERT INTO Viajes VALUES
(9001, 5101, 1102, 101, DATEADD(MINUTE,-40,GETDATE()), 'Zona 10', 'Zona 1', 8.20, 54.00, 'Finalizado'),
(9002, 5102, 1101, 101, DATEADD(MINUTE,-10,GETDATE()), 'Zona 12', 'Zona 15', 5.60, 39.00, 'En Curso');

INSERT INTO Pagos VALUES
(7001, 9001, 1, 54.00, 'Aprobado', DATEADD(MINUTE,-30,GETDATE()));
GO

/* =============================
   SHARD MX
   ============================= */
USE DB_Operaciones_MX;
GO

CREATE TABLE Conductores (
    IdConductor INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    Estado VARCHAR(20) NOT NULL,
    IdTipoVehiculo INT NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Usuarios (
    IdUsuario INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Viajes (
    IdViaje INT PRIMARY KEY,
    IdUsuario INT NOT NULL,
    IdConductor INT NOT NULL,
    IdCiudad INT NOT NULL,
    FechaSolicitud DATETIME NOT NULL,
    Origen VARCHAR(120) NOT NULL,
    Destino VARCHAR(120) NOT NULL,
    DistanciaKm DECIMAL(8,2) NOT NULL,
    TarifaCalculada DECIMAL(10,2) NOT NULL,
    Estado VARCHAR(30) NOT NULL,
    FOREIGN KEY (IdUsuario) REFERENCES Usuarios(IdUsuario),
    FOREIGN KEY (IdConductor) REFERENCES Conductores(IdConductor)
);

CREATE TABLE Pagos (
    IdPago INT PRIMARY KEY,
    IdViaje INT NOT NULL,
    IdMetodoPago INT NOT NULL,
    Monto DECIMAL(10,2) NOT NULL,
    EstadoPago VARCHAR(20) NOT NULL,
    FechaPago DATETIME NOT NULL DEFAULT GETDATE(),
    FOREIGN KEY (IdViaje) REFERENCES Viajes(IdViaje)
);
GO

INSERT INTO Conductores VALUES
(2101, 'Luis Rivera', 'Disponible', 1, GETDATE()),
(2102, 'Sofia Martinez', 'Disponible', 3, GETDATE());

INSERT INTO Usuarios VALUES
(6101, 'Andrea Leon', GETDATE()),
(6102, 'Pedro Ruiz', GETDATE());

INSERT INTO Viajes VALUES
(9101, 6101, 2101, 201, DATEADD(MINUTE,-25,GETDATE()), 'Roma Norte', 'Polanco', 6.40, 88.00, 'Finalizado'),
(9102, 6102, 2102, 201, DATEADD(MINUTE,-7,GETDATE()), 'Condesa', 'Del Valle', 4.80, 76.00, 'En Curso');

INSERT INTO Pagos VALUES
(7101, 9101, 3, 88.00, 'Aprobado', DATEADD(MINUTE,-15,GETDATE()));
GO

/* =============================
   SHARD US
   ============================= */
USE DB_Operaciones_US;
GO

CREATE TABLE Conductores (
    IdConductor INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    Estado VARCHAR(20) NOT NULL,
    IdTipoVehiculo INT NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Usuarios (
    IdUsuario INT PRIMARY KEY,
    Nombre VARCHAR(80) NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT GETDATE()
);

CREATE TABLE Viajes (
    IdViaje INT PRIMARY KEY,
    IdUsuario INT NOT NULL,
    IdConductor INT NOT NULL,
    IdCiudad INT NOT NULL,
    FechaSolicitud DATETIME NOT NULL,
    Origen VARCHAR(120) NOT NULL,
    Destino VARCHAR(120) NOT NULL,
    DistanciaKm DECIMAL(8,2) NOT NULL,
    TarifaCalculada DECIMAL(10,2) NOT NULL,
    Estado VARCHAR(30) NOT NULL,
    FOREIGN KEY (IdUsuario) REFERENCES Usuarios(IdUsuario),
    FOREIGN KEY (IdConductor) REFERENCES Conductores(IdConductor)
);

CREATE TABLE Pagos (
    IdPago INT PRIMARY KEY,
    IdViaje INT NOT NULL,
    IdMetodoPago INT NOT NULL,
    Monto DECIMAL(10,2) NOT NULL,
    EstadoPago VARCHAR(20) NOT NULL,
    FechaPago DATETIME NOT NULL DEFAULT GETDATE(),
    FOREIGN KEY (IdViaje) REFERENCES Viajes(IdViaje)
);
GO

INSERT INTO Conductores VALUES
(3101, 'John Carter', 'Disponible', 2, GETDATE()),
(3102, 'Emily Stone', 'En Viaje', 1, GETDATE());

INSERT INTO Usuarios VALUES
(7101, 'Daniel Brown', GETDATE()),
(7102, 'Emma White', GETDATE());

INSERT INTO Viajes VALUES
(9201, 7101, 3102, 301, DATEADD(MINUTE,-35,GETDATE()), 'Downtown Miami', 'Brickell', 7.10, 42.00, 'Finalizado'),
(9202, 7102, 3101, 301, DATEADD(MINUTE,-6,GETDATE()), 'Wynwood', 'South Beach', 9.30, 51.00, 'En Curso');

INSERT INTO Pagos VALUES
(7201, 9201, 1, 42.00, 'Aprobado', DATEADD(MINUTE,-20,GETDATE()));
GO

/* =============================
   REPORTING CONSOLIDADO
   ============================= */
USE DB_Reporting_MoveFast;
GO

CREATE VIEW vw_ViajesMoveFast
AS
SELECT
    'GT' AS PaisShard,
    v.IdViaje,
    v.IdCiudad,
    v.FechaSolicitud,
    v.Origen,
    v.Destino,
    v.DistanciaKm,
    v.TarifaCalculada,
    v.Estado
FROM DB_Operaciones_GT.dbo.Viajes v

UNION ALL

SELECT
    'MX' AS PaisShard,
    v.IdViaje,
    v.IdCiudad,
    v.FechaSolicitud,
    v.Origen,
    v.Destino,
    v.DistanciaKm,
    v.TarifaCalculada,
    v.Estado
FROM DB_Operaciones_MX.dbo.Viajes v

UNION ALL

SELECT
    'US' AS PaisShard,
    v.IdViaje,
    v.IdCiudad,
    v.FechaSolicitud,
    v.Origen,
    v.Destino,
    v.DistanciaKm,
    v.TarifaCalculada,
    v.Estado
FROM DB_Operaciones_US.dbo.Viajes v;
GO

CREATE TABLE ResumenViajesDiarios (
    PaisShard CHAR(2) NOT NULL,
    Fecha DATE NOT NULL,
    TotalViajes INT NOT NULL,
    TotalFacturado DECIMAL(14,2) NOT NULL,
    ViajesFinalizados INT NOT NULL,
    ViajesEnCurso INT NOT NULL
);
GO

TRUNCATE TABLE ResumenViajesDiarios;
GO

INSERT INTO ResumenViajesDiarios
SELECT
    PaisShard,
    CAST(FechaSolicitud AS DATE) AS Fecha,
    COUNT(*) AS TotalViajes,
    SUM(TarifaCalculada) AS TotalFacturado,
    SUM(CASE WHEN Estado = 'Finalizado' THEN 1 ELSE 0 END) AS ViajesFinalizados,
    SUM(CASE WHEN Estado = 'En Curso' THEN 1 ELSE 0 END) AS ViajesEnCurso
FROM vw_ViajesMoveFast
GROUP BY PaisShard, CAST(FechaSolicitud AS DATE);
GO

/* =============================
   CONSULTAS DE VERIFICACION
   ============================= */
SELECT *
FROM vw_ViajesMoveFast
ORDER BY FechaSolicitud DESC;
GO

SELECT *
FROM ResumenViajesDiarios
ORDER BY Fecha DESC, PaisShard;
GO
