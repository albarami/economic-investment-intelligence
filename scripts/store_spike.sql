-- name: spike_unit_totals
-- params: units list[text]
-- returns: unit_id text, label text, period date, count_value bigint, decimal_control numeric
-- order: label, unit_id
SELECT p.unit_id, p.label, p.period, SUM(p.count_value) AS count_value,
       p.decimal_control
FROM spike_control AS p
WHERE p.unit_id = ANY(:units)
GROUP BY p.unit_id, p.label, p.period, p.decimal_control
ORDER BY p.label ASC NULLS LAST, p.unit_id ASC NULLS LAST
