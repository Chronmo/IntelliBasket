USE intellibasket;

SELECT 'ods_row_count' AS check_name, COUNT(*) AS actual_value
FROM ods_retail_transaction_raw;

SELECT 'dwd_row_count' AS check_name, COUNT(*) AS actual_value
FROM dwd_retail_order_item;

SELECT quality_status, COUNT(*) AS row_count
FROM dwd_retail_order_item
GROUP BY quality_status
ORDER BY row_count DESC;

SELECT
    'valid_analysis' AS check_name,
    COUNT(*) AS row_count,
    COUNT(DISTINCT invoice_no) AS invoice_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    COUNT(DISTINCT stock_code) AS product_count,
    CAST(SUM(line_amount) AS DECIMAL(20, 2)) AS sales_amount
FROM dwd_retail_order_item
WHERE is_valid_analysis = 1;

SELECT
    'basket_reconciliation' AS check_name,
    COUNT(*) AS basket_count,
    CAST(SUM(basket_amount) AS DECIMAL(20, 2)) AS basket_sales_amount
FROM dws_basket_summary;

SELECT
    'ads_reconciliation' AS check_name,
    order_count,
    sales_amount
FROM ads_business_overview;

