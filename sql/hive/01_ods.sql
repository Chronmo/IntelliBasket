USE intellibasket;

DROP TABLE IF EXISTS ods_retail_transaction_raw;

CREATE EXTERNAL TABLE ods_retail_transaction_raw (
    source_year STRING COMMENT 'Source workbook sheet',
    invoice_no STRING COMMENT 'Raw invoice number',
    stock_code STRING COMMENT 'Raw product code',
    description STRING COMMENT 'Raw product description',
    quantity STRING COMMENT 'Raw item quantity',
    invoice_ts STRING COMMENT 'Raw invoice timestamp',
    unit_price STRING COMMENT 'Raw unit price in GBP',
    customer_id STRING COMMENT 'Raw customer identifier',
    country STRING COMMENT 'Raw customer country',
    ingest_batch_id STRING COMMENT 'Source ingestion batch identifier'
)
COMMENT 'Unmodified standardized rows exported from Online Retail II'
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
    'separatorChar' = ',',
    'quoteChar' = '"',
    'escapeChar' = '\\'
)
STORED AS TEXTFILE
LOCATION '/data/intellibasket/ods/online_retail_ii'
TBLPROPERTIES ('skip.header.line.count' = '1');

