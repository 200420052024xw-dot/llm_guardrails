-- LLM Guardrails schema for MySQL 8.0+. Select a database in BaoTa, then import this file.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `users` (
  `id` VARCHAR(36) NOT NULL, `username` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL, `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`), UNIQUE KEY `uq_users_username` (`username`), KEY `ix_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `user_sessions` (
  `id` VARCHAR(36) NOT NULL, `user_id` VARCHAR(36) NOT NULL,
  `token_hash` VARCHAR(64) NOT NULL, `expires_at` DATETIME(6) NOT NULL, `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`), UNIQUE KEY `uq_user_sessions_token_hash` (`token_hash`),
  KEY `ix_user_sessions_user_id` (`user_id`), KEY `ix_user_sessions_token_hash` (`token_hash`),
  CONSTRAINT `fk_user_sessions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `conversations` (
  `id` VARCHAR(36) NOT NULL, `user_id` VARCHAR(36) NOT NULL, `title` VARCHAR(120) NOT NULL DEFAULT '新对话',
  `created_at` DATETIME(6) NOT NULL, `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`), KEY `ix_conversations_user_id` (`user_id`),
  CONSTRAINT `fk_conversations_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `messages` (
  `id` VARCHAR(36) NOT NULL, `conversation_id` VARCHAR(36) NOT NULL, `role` VARCHAR(16) NOT NULL,
  `content` TEXT NOT NULL, `safe_content` TEXT NULL, `action` VARCHAR(16) NULL, `risk_score` FLOAT NULL,
  `guardrail_message` VARCHAR(500) NULL, `risk_types` JSON NOT NULL, `status` VARCHAR(16) NOT NULL DEFAULT 'complete',
  `created_at` DATETIME(6) NOT NULL, PRIMARY KEY (`id`), KEY `ix_messages_conversation_id` (`conversation_id`),
  CONSTRAINT `fk_messages_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `confidential_entries` (
  `id` VARCHAR(36) NOT NULL, `user_id` VARCHAR(36) NOT NULL, `text` TEXT NOT NULL,
  `category` VARCHAR(64) NOT NULL DEFAULT 'confidential', `paraphrases` JSON NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1, `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`), KEY `ix_confidential_entries_user_id` (`user_id`),
  CONSTRAINT `fk_confidential_entries_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `public_entries` (
  `id` VARCHAR(36) NOT NULL, `user_id` VARCHAR(36) NOT NULL, `entity_type` VARCHAR(32) NOT NULL,
  `value` VARCHAR(500) NOT NULL, `label` VARCHAR(120) NOT NULL DEFAULT '', `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL, PRIMARY KEY (`id`), KEY `ix_public_entries_user_id` (`user_id`),
  UNIQUE KEY `uq_public_user_value` (`user_id`, `entity_type`, `value`),
  CONSTRAINT `fk_public_entries_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `model_configs` (
  `user_id` VARCHAR(36) NOT NULL, `api_key_encrypted` TEXT NOT NULL,
  `base_url` VARCHAR(500) NOT NULL, `model` VARCHAR(120) NOT NULL, `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_model_configs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `import_jobs` (
  `id` VARCHAR(36) NOT NULL, `user_id` VARCHAR(36) NOT NULL, `library_type` VARCHAR(24) NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'complete', `imported_count` INT NOT NULL DEFAULT 0,
  `error_count` INT NOT NULL DEFAULT 0, `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`), KEY `ix_import_jobs_user_id` (`user_id`),
  CONSTRAINT `fk_import_jobs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `alembic_version` (
  `version_num` VARCHAR(32) NOT NULL, PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `alembic_version` (`version_num`)
SELECT '0001_initial' WHERE NOT EXISTS (SELECT 1 FROM `alembic_version`);

SET FOREIGN_KEY_CHECKS = 1;
