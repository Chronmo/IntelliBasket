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

DROP TABLE IF EXISTS ads_business_overview;
CREATE TABLE ads_business_overview
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    COUNT(DISTINCT customer_id) AS customer_count,
    COUNT(DISTINCT invoice_no) AS order_count,
    COUNT(DISTINCT stock_code) AS product_count,
    SUM(quantity) AS item_quantity,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS sales_amount,
    CAST(
        SUM(line_amount) / COUNT(DISTINCT invoice_no)
        AS DECIMAL(20, 2)
    ) AS average_basket_amount,
    MIN(invoice_ts) AS min_invoice_ts,
    MAX(invoice_ts) AS max_invoice_ts
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1;

DROP TABLE IF EXISTS ads_monthly_sales;
CREATE TABLE ads_monthly_sales
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    SUBSTR(CAST(invoice_ts AS STRING), 1, 7) AS invoice_month,
    COUNT(DISTINCT customer_id) AS customer_count,
    COUNT(DISTINCT invoice_no) AS order_count,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS sales_amount,
    CAST(
        SUM(line_amount) / COUNT(DISTINCT invoice_no)
        AS DECIMAL(20, 2)
    ) AS average_basket_amount
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1
GROUP BY SUBSTR(CAST(invoice_ts AS STRING), 1, 7);

DROP TABLE IF EXISTS ads_data_quality_summary;
CREATE TABLE ads_data_quality_summary
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY')
AS
SELECT
    quality_status,
    COUNT(*) AS row_count,
    COUNT(DISTINCT invoice_no) AS invoice_count,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS line_amount
FROM dwd_retail_order_item
GROUP BY quality_status;
