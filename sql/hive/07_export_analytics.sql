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

INSERT OVERWRITE DIRECTORY '/data/intellibasket/exports/basket_items'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
SELECT
    invoice_no,
    customer_id,
    CAST(invoice_ts AS STRING),
    stock_code,
    product_name,
    item_quantity,
    item_amount
FROM dws_basket_item;

INSERT OVERWRITE DIRECTORY '/data/intellibasket/exports/monthly_sales'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
SELECT
    invoice_month,
    customer_count,
    order_count,
    sales_amount,
    average_basket_amount
FROM ads_monthly_sales
ORDER BY invoice_month;

INSERT OVERWRITE DIRECTORY '/data/intellibasket/exports/data_quality'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
SELECT
    quality_status,
    row_count,
    invoice_count,
    line_amount
FROM ads_data_quality_summary
ORDER BY row_count DESC;

