Agent reasoning encountered a failure: (sqlite3.OperationalError) no such table: persistent_cache
[SQL: SELECT persistent_cache.id AS persistent_cache_id, persistent_cache.ticker AS persistent_cache_ticker, persistent_cache.resource_type AS persistent_cache_resource_type, persistent_cache.timeframe AS persistent_cache_timeframe, persistent_cache.reference_price AS persistent_cache_reference_price, persistent_cache.data AS persistent_cache_data, persistent_cache.heat_score AS persistent_cache_heat_score, persistent_cache.last_accessed AS persistent_cache_last_accessed, persistent_cache.expires_at AS persistent_cache_expires_at, persistent_cache.created_at AS persistent_cache_created_at 
FROM persistent_cache 
WHERE persistent_cache.ticker = ? AND persistent_cache.resource_type = ? AND persistent_cache.timeframe = ?
 LIMIT ? OFFSET ?]
[parameters: ('AAPL', 'smc_analysis', 'auto', 1, 0)]
(Background on this error at: https://sqlalche.me/e/20/e3q8)