-- Allium Explorer (Snowflake dialect), run 9 Nov 2026 (UTC 22:28-22:44), query id 6NDb23AENT94xp5k779Z.
-- ONDO token on Ethereum: 0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3
-- Reserve (genesis holder):  0x677fd4ed8ae623f2f625deb2d64f2070e46ca1a1
-- Distributor A (2025-26):   0x524083970c7a1e62fbaa61d38781f87a4f191fd0
-- Distributor B (2026):      0xea5785e1727de2ba2cefd102cb2dd91e018675e1
-- Each query was wrapped as SELECT TO_JSON(ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(*))) FROM (...) to export one JSON cell.

-- 1. reserve-outflows.json: every transfer out of the reserve, by day and recipient.
SELECT x.block_timestamp::date AS d, x.from_address AS src, x.to_address AS r,
       ROUND(SUM(x.amount)/1e6, 3) AS m, COUNT(*) AS n, e.name, e.category
FROM ethereum.assets.erc20_token_transfers x
LEFT JOIN (SELECT address, ANY_VALUE(name) AS name, ANY_VALUE(category) AS category, ANY_VALUE(project) AS project
           FROM common.identity.entities WHERE chain = 'ethereum' GROUP BY 1) e ON e.address = x.to_address
WHERE x.token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
  AND x.from_address LIKE '0x677fd4ed8a%'
GROUP BY 1, 2, 3, 6, 7;

-- 2. distributor-outflows.json / distributor-inflows.json: same shape, with
--    x.from_address IN (A, B)  /  x.to_address IN (A, B).

-- 3. first-hop-recipients.json: what each distributor recipient did with the tokens.
WITH rec AS (
  SELECT to_address AS r, ANY_VALUE(from_address) AS src, MIN(block_timestamp) AS t0, SUM(amount) AS got
  FROM ethereum.assets.erc20_token_transfers
  WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
    AND from_address IN ('0x524083970c7a1e62fbaa61d38781f87a4f191fd0', '0xea5785e1727de2ba2cefd102cb2dd91e018675e1')
  GROUP BY 1
), o AS (
  SELECT rec.r, rec.src, rec.t0, x.to_address AS dst, x.block_timestamp AS ts, x.amount,
         DATEDIFF('minute', rec.t0, x.block_timestamp) / 1440.0 AS lag
  FROM ethereum.assets.erc20_token_transfers x JOIN rec ON x.from_address = rec.r
  WHERE x.token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3' AND x.block_timestamp >= rec.t0
)
SELECT rec.r, rec.src, rec.t0::date AS t0, ROUND(rec.got/1e6, 3) AS got,
       COUNT(DISTINCT o.dst) AS n_dst,
       ROUND(COALESCE(SUM(o.amount), 0)/1e6, 3) AS out_all,
       ROUND(COALESCE(SUM(IFF(o.lag <= 1, o.amount, 0)), 0)/1e6, 3) AS out1,
       ROUND(COALESCE(SUM(IFF(o.lag <= 7, o.amount, 0)), 0)/1e6, 3) AS out7,
       ROUND(COALESCE(SUM(IFF(o.lag <= 30, o.amount, 0)), 0)/1e6, 3) AS out30,
       ROUND(COALESCE(SUM(IFF(o.lag <= 90, o.amount, 0)), 0)/1e6, 3) AS out90
FROM rec LEFT JOIN o ON o.r = rec.r
GROUP BY 1, 2, 3, 4;
-- second-hop-destinations.json groups the same CTE "o" by destination and joins common.identity.entities.

-- 4. address-snapshots.json: balances at T-30, T, T+7, T+30, T+90 around 18 Jan 2025 and 18 Jan 2026, and on 7 Nov 2026,
--    for every address that held >= 2m ONDO at a snapshot or ever received >= 20m.
WITH t AS (
  SELECT block_timestamp AS ts, from_address AS a, to_address AS cp, -amount AS amt
  FROM ethereum.assets.erc20_token_transfers WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
  UNION ALL
  SELECT block_timestamp, to_address, from_address, amount
  FROM ethereum.assets.erc20_token_transfers WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
)
SELECT a,
       ROUND(SUM(IFF(ts < '2024-12-19', amt, 0))/1e6, 3) AS a25_m30,
       ROUND(SUM(IFF(ts < '2025-01-18', amt, 0))/1e6, 3) AS a25_t0,
       ROUND(SUM(IFF(ts < '2025-01-25', amt, 0))/1e6, 3) AS a25_p7,
       ROUND(SUM(IFF(ts < '2025-02-17', amt, 0))/1e6, 3) AS a25_p30,
       ROUND(SUM(IFF(ts < '2025-04-18', amt, 0))/1e6, 3) AS a25_p90,
       ROUND(SUM(IFF(ts < '2025-12-19', amt, 0))/1e6, 3) AS b26_m30,
       ROUND(SUM(IFF(ts < '2026-01-18', amt, 0))/1e6, 3) AS b26_t0,
       ROUND(SUM(IFF(ts < '2026-01-25', amt, 0))/1e6, 3) AS b26_p7,
       ROUND(SUM(IFF(ts < '2026-02-17', amt, 0))/1e6, 3) AS b26_p30,
       ROUND(SUM(IFF(ts < '2026-04-18', amt, 0))/1e6, 3) AS b26_p90,
       ROUND(SUM(IFF(ts < '2026-11-08', amt, 0))/1e6, 3) AS now_m
FROM t GROUP BY 1
HAVING GREATEST(a25_m30, a25_t0, a25_p7, a25_p30, a25_p90, b26_m30, b26_t0, b26_p7, b26_p30, b26_p90, now_m) >= 2
    OR SUM(IFF(amt > 0, amt, 0)) >= 20e6;

-- 5. edges100k.json: every ONDO transfer of at least 100,000 tokens from 1 Oct 2024 (95,858 rows), pulled by quarter.
SELECT DATE_PART(epoch_second, block_timestamp) AS s, from_address AS f, to_address AS t, ROUND(amount) AS a
FROM ethereum.assets.erc20_token_transfers
WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
  AND amount >= 100000 AND block_timestamp >= '2024-10-01' AND block_timestamp < '2026-11-09';

-- 6. addr_stats.json: lifetime counterparties, transfer counts and label for every address that ever received >= 100k ONDO.
WITH t AS (
  SELECT from_address AS a, to_address AS cp, -amount AS amt
  FROM ethereum.assets.erc20_token_transfers WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
  UNION ALL
  SELECT to_address, from_address, amount
  FROM ethereum.assets.erc20_token_transfers WHERE token_address = '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3'
), b AS (
  SELECT a, COUNT(DISTINCT IFF(amt > 0, cp, NULL)) AS ns, COUNT(DISTINCT IFF(amt < 0, cp, NULL)) AS nr,
         SUM(IFF(amt > 0, 1, 0)) AS n_in, SUM(IFF(amt < 0, 1, 0)) AS n_out,
         ROUND(SUM(IFF(amt > 0, amt, 0))) AS gin, ROUND(SUM(IFF(amt < 0, -amt, 0))) AS gout
  FROM t GROUP BY 1 HAVING SUM(IFF(amt > 0, amt, 0)) >= 100000
)
SELECT b.*, e.name, e.category, e.project
FROM b LEFT JOIN (SELECT address, ANY_VALUE(name) AS name, ANY_VALUE(category) AS category, ANY_VALUE(project) AS project
                  FROM common.identity.entities WHERE chain = 'ethereum' GROUP BY 1) e ON e.address = b.a;

-- Tracing (trace.py, prorata.py) runs locally on files 5 and 6.
