-- name: control_rows
-- params: units list[text]
-- returns: unit_id text, label text, period date, count_value bigint, amount numeric
-- order: unit_id
SELECT p.unit_id, p.label, p.period, p.count_value, p.amount
FROM control_rows AS p
WHERE p.unit_id = ANY(:units)
ORDER BY p.unit_id ASC NULLS LAST
