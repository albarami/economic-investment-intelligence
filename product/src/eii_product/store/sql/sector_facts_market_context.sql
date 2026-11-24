-- name: sector_facts_market_context
-- params: activity text
-- returns: trade_type text, period text, indicator text, value numeric, unit text, source_id text
-- order: trade_type, period, indicator
SELECT p.trade_type, p.period, p.indicator, p.value, p.unit, p.source_id
FROM pub_trade_wr AS p
WHERE p.trade_type = :activity
ORDER BY p.trade_type ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
