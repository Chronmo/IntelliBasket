CREATE DATABASE IF NOT EXISTS intellibasket
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'intellibasket'@'%' IDENTIFIED BY 'intellibasket';
GRANT ALL PRIVILEGES ON intellibasket.* TO 'intellibasket'@'%';
FLUSH PRIVILEGES;

