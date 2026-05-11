-- 01. Executive KPI summary
WITH base AS (SELECT * FROM orders WHERE order_status <> 'Cancelled') SELECT SUM(net_sales) AS total_revenue, SUM(profit) AS total_profit, SUM(profit)/NULLIF(SUM(net_sales),0) AS profit_margin, AVG(net_sales) AS average_order_value, COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT customer_id) AS customers FROM base;

-- 02. Monthly revenue growth with window functions
WITH m AS (SELECT DATE_TRUNC('month', order_date) AS month, SUM(net_sales) revenue FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1) SELECT month, revenue, LAG(revenue) OVER(ORDER BY month) prior_revenue, (revenue-LAG(revenue) OVER(ORDER BY month))/NULLIF(LAG(revenue) OVER(ORDER BY month),0) AS growth_rate FROM m ORDER BY month;

-- 03. Category revenue ranking
SELECT p.category, SUM(o.net_sales) revenue, RANK() OVER(ORDER BY SUM(o.net_sales) DESC) category_rank FROM orders o JOIN products p ON o.product_id=p.product_id WHERE o.order_status <> 'Cancelled' GROUP BY p.category;

-- 04. Top products by category
WITH perf AS (SELECT p.category,p.product_id,p.product_name,SUM(o.net_sales) revenue,COUNT(*) orders FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2,3) SELECT * FROM (SELECT perf.*,ROW_NUMBER() OVER(PARTITION BY category ORDER BY revenue DESC) rn FROM perf) x WHERE rn<=10;

-- 05. RFM scoring
WITH rfm AS (SELECT customer_id, DATE_DIFF('day', MAX(order_date), CURRENT_DATE) recency, COUNT(DISTINCT order_id) frequency, SUM(net_sales) monetary FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1) SELECT *, NTILE(5) OVER(ORDER BY recency DESC) recency_score, NTILE(5) OVER(ORDER BY frequency) frequency_score, NTILE(5) OVER(ORDER BY monetary) monetary_score FROM rfm;

-- 06. Customer lifetime value
SELECT customer_id, SUM(net_sales) clv, SUM(profit) customer_profit, COUNT(DISTINCT order_id) lifetime_orders, MIN(order_date) first_order, MAX(order_date) last_order FROM orders WHERE order_status <> 'Cancelled' GROUP BY customer_id ORDER BY clv DESC;

-- 07. Repeat purchase rate
WITH c AS (SELECT customer_id, COUNT(DISTINCT order_id) orders FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1) SELECT SUM(CASE WHEN orders>1 THEN 1 ELSE 0 END)*1.0/COUNT(*) repeat_purchase_rate FROM c;

-- 08. Churn rate proxy
WITH last_purchase AS (SELECT customer_id, MAX(order_date) last_order FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1) SELECT AVG(CASE WHEN last_order < CURRENT_DATE - INTERVAL '120 day' THEN 1 ELSE 0 END) churn_rate FROM last_purchase;

-- 09. Cohort retention matrix
WITH firsts AS (SELECT customer_id, DATE_TRUNC('month', MIN(order_date)) cohort_month FROM orders GROUP BY 1), activity AS (SELECT o.customer_id, DATE_TRUNC('month', o.order_date) order_month, f.cohort_month FROM orders o JOIN firsts f ON o.customer_id=f.customer_id), indexed AS (SELECT *, DATE_DIFF('month', cohort_month, order_month)+1 cohort_index FROM activity) SELECT cohort_month, cohort_index, COUNT(DISTINCT customer_id) active_customers FROM indexed GROUP BY 1,2 ORDER BY 1,2;

-- 10. Refund rate by category
SELECT p.category, SUM(CASE WHEN o.refund_amount>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) refund_rate, SUM(o.refund_amount) refund_amount FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY p.category ORDER BY refund_rate DESC;

-- 11. Shipping delay percentage by region
SELECT c.region, AVG(o.shipping_delay_flag) shipping_delay_pct, AVG(o.fulfillment_days) avg_fulfillment_days FROM orders o JOIN customers c ON o.customer_id=c.customer_id GROUP BY c.region ORDER BY shipping_delay_pct DESC;

-- 12. Campaign profitability
SELECT campaign, COUNT(*) orders, SUM(net_sales) revenue, SUM(profit) profit, SUM(profit)/NULLIF(SUM(net_sales),0) margin FROM orders GROUP BY campaign ORDER BY revenue DESC;

-- 13. Payment method mix
SELECT payment_method, COUNT(*) payments, SUM(amount) amount, COUNT(*)*1.0/SUM(COUNT(*)) OVER() share FROM payments GROUP BY payment_method ORDER BY amount DESC;

-- 14. Seller SLA scorecard
SELECT seller_id, COUNT(*) orders, SUM(net_sales) revenue, AVG(shipping_delay_flag) delay_rate, AVG(fulfillment_days) avg_fulfillment FROM orders GROUP BY seller_id HAVING COUNT(*)>=50 ORDER BY delay_rate DESC;

-- 15. Low performing categories
WITH cat AS (SELECT p.category, SUM(o.net_sales) revenue, SUM(o.profit)/NULLIF(SUM(o.net_sales),0) margin FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1) SELECT * FROM cat WHERE revenue < (SELECT AVG(revenue) FROM cat) OR margin < .15 ORDER BY revenue;

-- 16. Discount elasticity by category
SELECT p.category, CASE WHEN o.discount_pct=0 THEN '0%' WHEN o.discount_pct<=.10 THEN '1-10%' WHEN o.discount_pct<=.25 THEN '11-25%' ELSE '25%+' END discount_band, COUNT(*) orders, SUM(o.net_sales) revenue, SUM(o.profit)/NULLIF(SUM(o.net_sales),0) margin FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2;

-- 17. Geo revenue heatmap extract
SELECT c.city,c.state,c.region,COUNT(DISTINCT o.order_id) orders,SUM(o.net_sales) revenue,AVG(o.shipping_delay_flag) delay_rate FROM orders o JOIN customers c ON o.customer_id=c.customer_id GROUP BY 1,2,3;

-- 18. Product return outliers
WITH perf AS (SELECT p.product_id,p.product_name,p.category,COUNT(*) orders,AVG(CASE WHEN o.order_status='Returned' THEN 1 ELSE 0 END) return_rate FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2,3) SELECT * FROM perf WHERE orders>=50 AND return_rate > (SELECT AVG(return_rate)+2*STDDEV(return_rate) FROM perf) ORDER BY return_rate DESC;

-- 19. Customer category affinity
WITH x AS (SELECT o.customer_id,p.category,SUM(o.net_sales) revenue FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2) SELECT * FROM (SELECT x.*,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY revenue DESC) rn FROM x) y WHERE rn=1;

-- 20. Market basket co-purchase pairs
SELECT a.product_id product_a,b.product_id product_b,COUNT(*) pair_orders FROM orders a JOIN orders b ON a.customer_id=b.customer_id AND a.order_id<>b.order_id AND a.product_id<b.product_id GROUP BY 1,2 HAVING COUNT(*)>=10 ORDER BY pair_orders DESC;

-- 21. Rolling 7 day revenue
WITH d AS (SELECT CAST(order_date AS DATE) day,SUM(net_sales) revenue FROM orders GROUP BY 1) SELECT day,revenue,AVG(revenue) OVER(ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) rolling_7d_revenue FROM d ORDER BY day;

-- 22. New vs returning revenue
WITH firsts AS (SELECT customer_id, MIN(CAST(order_date AS DATE)) first_order FROM orders GROUP BY 1) SELECT DATE_TRUNC('month', o.order_date) month, CASE WHEN CAST(o.order_date AS DATE)=f.first_order THEN 'New' ELSE 'Returning' END customer_type, SUM(o.net_sales) revenue FROM orders o JOIN firsts f ON o.customer_id=f.customer_id GROUP BY 1,2;

-- 23. Retention rate by acquisition channel
WITH c AS (SELECT o.customer_id, COUNT(DISTINCT o.order_id) orders FROM orders o GROUP BY 1) SELECT cu.acquisition_channel, AVG(CASE WHEN c.orders>1 THEN 1 ELSE 0 END) retention_rate FROM c JOIN customers cu ON c.customer_id=cu.customer_id GROUP BY 1 ORDER BY retention_rate DESC;

-- 24. Review rating impact on returns
SELECT r.rating,COUNT(*) reviews,AVG(CASE WHEN o.order_status='Returned' THEN 1 ELSE 0 END) return_rate,AVG(o.net_sales) avg_sales FROM reviews r JOIN orders o ON r.order_id=o.order_id GROUP BY r.rating ORDER BY r.rating;

-- 25. AOV by loyalty tier
SELECT c.loyalty_tier,AVG(o.net_sales) aov,SUM(o.net_sales) revenue,COUNT(*) orders FROM orders o JOIN customers c ON o.customer_id=c.customer_id GROUP BY c.loyalty_tier ORDER BY aov DESC;

-- 26. Pareto customer revenue contribution
WITH ranked AS (SELECT customer_id,SUM(net_sales) revenue, SUM(SUM(net_sales)) OVER() total_revenue, CUME_DIST() OVER(ORDER BY SUM(net_sales) DESC) customer_percentile FROM orders GROUP BY customer_id) SELECT SUM(revenue)/MAX(total_revenue) revenue_share_top_20pct FROM ranked WHERE customer_percentile<=.20;

-- 27. Order fulfillment time percentiles
SELECT shipping_mode, PERCENTILE_CONT(.5) WITHIN GROUP(ORDER BY fulfillment_days) p50_days, PERCENTILE_CONT(.9) WITHIN GROUP(ORDER BY fulfillment_days) p90_days, AVG(fulfillment_days) avg_days FROM orders GROUP BY shipping_mode;

-- 28. Monthly active customers
SELECT DATE_TRUNC('month', order_date) month, COUNT(DISTINCT customer_id) active_customers FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1 ORDER BY 1;

-- 29. Profit leakage from returns
SELECT p.category,SUM(o.refund_amount) refunds,SUM(o.profit) profit,SUM(o.refund_amount)/NULLIF(SUM(o.net_sales),0) refund_to_sales FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1 ORDER BY refunds DESC;

-- 30. High value customers at churn risk
WITH clv AS (SELECT customer_id,SUM(net_sales) revenue,MAX(order_date) last_order FROM orders GROUP BY 1) SELECT * FROM clv WHERE revenue > (SELECT PERCENTILE_CONT(.8) WITHIN GROUP(ORDER BY revenue) FROM clv) AND last_order < CURRENT_DATE - INTERVAL '90 day' ORDER BY revenue DESC;

-- 31. Category month seasonality index
WITH m AS (SELECT p.category,EXTRACT(month FROM o.order_date) month_num,SUM(o.net_sales) revenue FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2), avg_cat AS (SELECT category,AVG(revenue) avg_revenue FROM m GROUP BY 1) SELECT m.*,m.revenue/NULLIF(a.avg_revenue,0) seasonality_index FROM m JOIN avg_cat a ON m.category=a.category ORDER BY category,month_num;

-- 32. Campaign customer acquisition
WITH first_order AS (SELECT customer_id, MIN(order_date) first_order_date FROM orders GROUP BY 1) SELECT o.campaign, COUNT(DISTINCT o.customer_id) new_customers FROM orders o JOIN first_order f ON o.customer_id=f.customer_id AND o.order_date=f.first_order_date GROUP BY o.campaign ORDER BY new_customers DESC;

-- 33. Seller category specialization
WITH x AS (SELECT seller_id,p.category,SUM(o.net_sales) revenue FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY 1,2) SELECT * FROM (SELECT x.*,ROW_NUMBER() OVER(PARTITION BY seller_id ORDER BY revenue DESC) rn FROM x) y WHERE rn=1;

-- 34. Customer purchase interval
WITH seq AS (SELECT customer_id, order_date, LAG(order_date) OVER(PARTITION BY customer_id ORDER BY order_date) prev_order FROM orders) SELECT customer_id, AVG(DATE_DIFF('day', prev_order, order_date)) avg_days_between_orders FROM seq WHERE prev_order IS NOT NULL GROUP BY customer_id;

-- 35. Forecast input monthly sales
SELECT DATE_TRUNC('month', order_date) ds, SUM(net_sales) y FROM orders WHERE order_status <> 'Cancelled' GROUP BY 1 ORDER BY 1;
