CREATE DATABASE IF NOT EXISTS intellibasket
COMMENT 'IntelliBasket customer value and market basket warehouse';

USE intellibasket;

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
SET hive.exec.max.dynamic.partitions = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2000;
SET hive.exec.parallel = true;

