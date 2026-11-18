-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS tp_redes
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE tp_redes;

-- Tabla usuarios (validación de credenciales al conectar)
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(64) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'usuario',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla para almacenar repositorios (consulta con /repos usuario)
CREATE TABLE IF NOT EXISTS repositorios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_git VARCHAR(100) NOT NULL,
    nombre_repo VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    repo_url VARCHAR(255) NOT NULL,
    lenguaje VARCHAR(50) NULL,
    fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_repos_usuario (usuario_git)
) ENGINE=InnoDB;

-- Tabla followers (comando /followers usuario)
CREATE TABLE IF NOT EXISTS followers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_git VARCHAR(100) NOT NULL,
    follower_usuario VARCHAR(100) NOT NULL,
    follower_url VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NULL,
    fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_followers_usuario (usuario_git)
) ENGINE=InnoDB;

-- Datos iniciales de prueba (contraseñas hasheadas en SHA-256)
INSERT INTO usuarios (usuario, password_hash, rol) VALUES
('admin',  SHA2('admin123', 256), 'admin'),
('oriana', SHA2('1234', 256), 'admin'),
('profe',  SHA2('redes', 256), 'usuario'),
('alumno', SHA2('clave123', 256), 'usuario')
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    rol = VALUES(rol);