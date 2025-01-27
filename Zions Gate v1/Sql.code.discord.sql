-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
-- -----------------------------------------------------
-- Schema discord_verification
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema discord_verification
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `discord_verification` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci ;
USE `discord_verification` ;

-- -----------------------------------------------------
-- Table `discord_verification`.`global_bans`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `discord_verification`.`global_bans` (
  `discord_id` BIGINT NOT NULL,
  `banned_at` DATETIME NOT NULL,
  `reason` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`discord_id`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `discord_verification`.`onboarding_sessions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `discord_verification`.`onboarding_sessions` (
  `user_id` BIGINT NOT NULL,
  `onboarding_channel_id` BIGINT NULL DEFAULT NULL,
  `current_page` INT NOT NULL DEFAULT '0',
  `message_id` BIGINT NULL DEFAULT NULL,
  PRIMARY KEY (`user_id`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `discord_verification`.`users`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `discord_verification`.`users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `discord_id` BIGINT NOT NULL,
  `username` VARCHAR(100) NOT NULL,
  `verify_status` TINYINT(1) NOT NULL DEFAULT '0',
  `time_created` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `global_bans_discord_id` BIGINT NULL,
  `onboarding_sessions_user_id` BIGINT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `discord_id` (`discord_id` ASC) VISIBLE,
  INDEX `fk_users_global_bans_idx` (`global_bans_discord_id` ASC) VISIBLE,
  INDEX `fk_users_onboarding_sessions1_idx` (`onboarding_sessions_user_id` ASC) VISIBLE,
  CONSTRAINT `fk_users_global_bans`
    FOREIGN KEY (`global_bans_discord_id`)
    REFERENCES `discord_verification`.`global_bans` (`discord_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_users_onboarding_sessions1`
    FOREIGN KEY (`onboarding_sessions_user_id`)
    REFERENCES `discord_verification`.`onboarding_sessions` (`user_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB
AUTO_INCREMENT = 74
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
