CREATE TABLE `qq_user` (
  `id` char(20) NOT NULL DEFAULT '',
  `auth` int DEFAULT NULL,
  `last_luck` timestamp NULL DEFAULT NULL,
  `credit` int DEFAULT NULL,
  `last_remake` timestamp NULL DEFAULT NULL,
  `waifu` longtext DEFAULT '',
  `message` longtext,
  PRIMARY KEY (`id`)
);

CREATE TABLE `qq_waifu` (
  `id` char(40) NOT NULL DEFAULT '',
  `waifuId` char(40) NOT NULL DEFAULT '',
  `waifuDict` longtext NOT NULL,
  `otherDict` longtext,
  `name` longtext,
  `credit` int DEFAULT '0',
  `last_ntr` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
);

CREATE TABLE `remake_data` (
  `seed` varchar(50) NOT NULL DEFAULT '',
  `time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `name` varchar(50) NOT NULL DEFAULT '',
  `score` float NOT NULL,
  `nation` varchar(50) NOT NULL DEFAULT '',
  `possibility` float NOT NULL,
  `rank` int NOT NULL,
  `race` varchar(50) NOT NULL DEFAULT '',
  `sexual` varchar(50) NOT NULL DEFAULT '',
  `group` varchar(50) DEFAULT '',
  `user_id` varchar(50) DEFAULT '',
  PRIMARY KEY (`seed`)
);
