USE intellibasket;

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
SET hive.exec.max.dynamic.partitions = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2000;
SET hive.exec.max.created.files = 10000;
SET hive.exec.mode.local.auto = false;
SET mapreduce.framework.name = yarn;
SET yarn.resourcemanager.address = resourcemanager:8032;
SET yarn.app.mapreduce.am.resource.mb = 512;
SET yarn.app.mapreduce.am.command-opts = -Xmx384m;
SET mapreduce.map.memory.mb = 512;
SET mapreduce.reduce.memory.mb = 768;
SET mapreduce.map.java.opts = -Xmx384m;
SET mapreduce.reduce.java.opts = -Xmx576m;

DROP TABLE IF EXISTS dwd_retail_order_item;

CREATE TABLE dwd_retail_order_item (
    invoice_no STRING COMMENT 'Standardized invoice number',
    stock_code STRING COMMENT 'Standardized product code',
    description STRING COMMENT 'Normalized product description',
    quantity INT COMMENT 'Purchased quantity',
    invoice_ts TIMESTAMP COMMENT 'Invoice timestamp',
    unit_price DECIMAL(18, 4) COMMENT 'Unit price in GBP',
    line_amount DECIMAL(20, 4) COMMENT 'Quantity multiplied by unit price',
    customer_id STRING COMMENT 'Customer identifier',
    country STRING COMMENT 'Customer country',
    source_year STRING COMMENT 'Source workbook sheet',
    ingest_batch_id STRING COMMENT 'Source ingestion batch identifier',
    is_cancelled TINYINT COMMENT '1 when invoice starts with C',
    quality_status STRING COMMENT 'Primary data quality classification',
    is_valid_analysis TINYINT COMMENT '1 when row satisfies the main analysis rules'
)
COMMENT 'Cleaned order item fact table at invoice-product-line grain'
PARTITIONED BY (invoice_month STRING COMMENT 'Invoice month in yyyy-MM format')
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

INSERT OVERWRITE TABLE dwd_retail_order_item PARTITION (invoice_month)
SELECT
    TRIM(invoice_no) AS invoice_no,
    TRIM(stock_code) AS stock_code,
    TRIM(description) AS description,
    CAST(quantity AS INT) AS quantity,
    CAST(invoice_ts AS TIMESTAMP) AS invoice_ts,
    CAST(unit_price AS DECIMAL(18, 4)) AS unit_price,
    CAST(
        CAST(quantity AS DECIMAL(20, 4))
        * CAST(unit_price AS DECIMAL(18, 4))
        AS DECIMAL(20, 4)
    ) AS line_amount,
    TRIM(customer_id) AS customer_id,
    TRIM(country) AS country,
    source_year,
    ingest_batch_id,
    CASE WHEN UPPER(TRIM(invoice_no)) LIKE 'C%' THEN 1 ELSE 0 END AS is_cancelled,
    CASE
        WHEN TRIM(invoice_no) = '' OR TRIM(stock_code) = '' OR TRIM(invoice_ts) = ''
            THEN 'MISSING_KEY'
        WHEN TRIM(customer_id) = '' THEN 'MISSING_CUSTOMER'
        WHEN UPPER(TRIM(invoice_no)) LIKE 'C%' THEN 'CANCELLED'
        WHEN CAST(quantity AS INT) <= 0 THEN 'NON_POSITIVE_QUANTITY'
        WHEN CAST(unit_price AS DECIMAL(18, 4)) <= 0 THEN 'NON_POSITIVE_PRICE'
        ELSE 'VALID'
    END AS quality_status,
    CASE
        WHEN TRIM(invoice_no) <> ''
            AND TRIM(stock_code) <> ''
            AND TRIM(invoice_ts) <> ''
            AND TRIM(customer_id) <> ''
            AND UPPER(TRIM(invoice_no)) NOT LIKE 'C%'
            AND CAST(quantity AS INT) > 0
            AND CAST(unit_price AS DECIMAL(18, 4)) > 0
        THEN 1
        ELSE 0
    END AS is_valid_analysis,
    SUBSTR(TRIM(invoice_ts), 1, 7) AS invoice_month
FROM ods_retail_transaction_raw;
