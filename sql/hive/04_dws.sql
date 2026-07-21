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

DROP TABLE IF EXISTS dws_basket_summary;
CREATE TABLE dws_basket_summary
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    invoice_no,
    customer_id,
    MIN(invoice_ts) AS invoice_ts,
    MAX(country) AS country,
    COUNT(DISTINCT stock_code) AS product_count,
    SUM(quantity) AS item_quantity,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS basket_amount
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY invoice_no, customer_id;

DROP TABLE IF EXISTS dws_basket_item;
CREATE TABLE dws_basket_item
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    invoice_no,
    customer_id,
    MIN(invoice_ts) AS invoice_ts,
    stock_code,
    MAX(description) AS product_name,
    SUM(quantity) AS item_quantity,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS item_amount
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY invoice_no, customer_id, stock_code;

DROP TABLE IF EXISTS dws_customer_monthly_value;
CREATE TABLE dws_customer_monthly_value
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    SUBSTR(CAST(invoice_ts AS STRING), 1, 7) AS invoice_month,
    customer_id,
    COUNT(DISTINCT invoice_no) AS order_count,
    COUNT(DISTINCT stock_code) AS product_count,
    SUM(quantity) AS item_quantity,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS sales_amount,
    MAX(invoice_ts) AS latest_purchase_ts
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY SUBSTR(CAST(invoice_ts AS STRING), 1, 7), customer_id;

DROP TABLE IF EXISTS dws_customer_purchase_summary;
CREATE TABLE dws_customer_purchase_summary
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    customer_id,
    MIN(invoice_ts) AS first_purchase_ts,
    MAX(invoice_ts) AS latest_purchase_ts,
    COUNT(DISTINCT invoice_no) AS frequency,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS monetary,
    COUNT(DISTINCT stock_code) AS distinct_product_count
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY customer_id;
