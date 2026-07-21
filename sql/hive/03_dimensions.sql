USE intellibasket;

SET hive.exec.mode.local.auto = false;
SET mapreduce.framework.name = yarn;
SET yarn.resourcemanager.address = resourcemanager:8032;
SET yarn.app.mapreduce.am.resource.mb = 512;
SET yarn.app.mapreduce.am.command-opts = -Xmx384m;
SET mapreduce.map.memory.mb = 512;
SET mapreduce.reduce.memory.mb = 768;
SET mapreduce.map.java.opts = -Xmx384m;
SET mapreduce.reduce.java.opts = -Xmx576m;

DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    stock_code,
    MAX(description) AS product_name,
    MIN(unit_price) AS min_unit_price,
    MAX(unit_price) AS max_unit_price,
    COUNT(*) AS source_row_count
FROM dwd_retail_order_item
WHERE stock_code <> ''
GROUP BY stock_code;

DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    customer_id,
    MAX(country) AS country,
    MIN(invoice_ts) AS first_seen_ts,
    MAX(invoice_ts) AS last_seen_ts
FROM dwd_retail_order_item
WHERE customer_id <> ''
GROUP BY customer_id;

DROP TABLE IF EXISTS dim_country;
CREATE TABLE dim_country
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    country,
    COUNT(DISTINCT customer_id) AS customer_count,
    COUNT(DISTINCT invoice_no) AS invoice_count
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY country;
