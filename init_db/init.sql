CREATE DATABASE IF NOT EXISTS restaurant;
USE restaurant;

-- Создаем таблицу пользователей
CREATE TABLE IF NOT EXISTS `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `telegram_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `telegram_id` (`telegram_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Создаем таблицу столов
CREATE TABLE IF NOT EXISTS `tables` (
  `id` int NOT NULL AUTO_INCREMENT,
  `capacity` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Заполняем столы данными со скриншота
INSERT INTO `tables` (`id`, `capacity`) VALUES
(1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2),
(11, 4), (12, 4), (13, 4), (14, 4), (15, 4), (16, 4), (17, 4), (18, 4),
(19, 6), (20, 6), (21, 6), (22, 6);

-- Создаем таблицу бронирований
CREATE TABLE IF NOT EXISTS `bookings` (
  `order_id` int NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `table_id` int NOT NULL,
  `start_time` datetime NOT NULL,
  `end_time` datetime NOT NULL,
  `count_clients` int NOT NULL,
  PRIMARY KEY (`order_id`),
  KEY `table_id` (`table_id`),
  KEY `bookings_ibfk_1` (`user_id`),
  CONSTRAINT `bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `bookings_ibfk_2` FOREIGN KEY (`table_id`) REFERENCES `tables` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;