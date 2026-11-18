-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS tp_redes
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE tp_redes;

-- tabla usuarios (validación de credenciales al conectar)
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(64) NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- tabla para almacenar repositorios (consulta con /repos usuario)
CREATE TABLE IF NOT EXISTS repositorios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_git VARCHAR(100) NOT NULL,
    nombre_repo VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    url_repo VARCHAR(255) NOT NULL,
    lenguaje VARCHAR(50) NULL,
    estrellas INT DEFAULT 0,
    fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- tabla followers (comando /followers usuario)
CREATE TABLE IF NOT EXISTS followers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_git VARCHAR(100) NOT NULL,
    follower_usuario VARCHAR(100) NOT NULL,
    follower_url VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NULL,
    fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- datos iniciales de prueba (contraseñas hasheadas en SHA-256)
INSERT INTO usuarios (usuario, password_hash) VALUES
('admin',    SHA2('admin123', 256)),
('oriana', SHA2('1234', 256)),
('alumno1',  SHA2('redes2026', 256)),
('alumno2',  SHA2('clave456', 256))
ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash);