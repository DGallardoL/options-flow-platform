# Arquitectura — Options Flow Intelligence Platform

## Diagrama General del Sistema

```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                     OPTIONS FLOW INTELLIGENCE PLATFORM                      │
 │                                                                             │
 │  ┌──────────────────────┐                                                   │
 │  │   DATA SOURCES        │                                                   │
 │  │                        │                                                   │
 │  │  MASSIVE / Polygon.io  │                                                   │
 │  │  ┌──────────────────┐  │                                                   │
 │  │  │ WebSocket Server  │  │    ┌──────────────────────────────────────────┐  │
 │  │  │ wss://ws.massive  │──┼──►│          INGESTION LAYER                 │  │
 │  │  │ .com/options      │  │    │                                          │  │
 │  │  │                    │  │    │  ┌──────────────┐ ┌──────────────────┐  │  │
 │  │  │ Channels:          │  │    │  │ ws_consumer  │ │  rest_poller     │  │  │
 │  │  │  T.* (Trades)      │  │    │  │ .py          │ │  .py             │  │  │
 │  │  │  Q.* (Quotes)      │  │    │  │              │ │                  │  │  │
 │  │  │  A.* (Aggregates)  │  │    │  │ Buffer 1s /  │ │ Poll 60s per    │  │  │
 │  │  └──────────────────┘  │    │  │ 100 events   │ │ ticker in        │  │  │
 │  │                        │    │  │              │ │ WATCHLIST         │  │  │
 │  │  ┌──────────────────┐  │    │  │ insert_many  │ │                  │  │  │
 │  │  │ REST API          │──┼──►│  │ ordered=false│ │ list_snapshot_   │  │  │
 │  │  │ api.massive.com   │  │    │  │              │ │ options_chain()  │  │  │
 │  │  │                    │  │    │  └──────┬───────┘ └────────┬─────────┘  │  │
 │  │  │ /v3/snapshot/      │  │    │         │                  │            │  │
 │  │  │   options/{ticker} │  │    │         │   User: ingest_writer        │  │
 │  │  └──────────────────┘  │    └─────────┼──────────────────┼────────────┘  │
 │  └──────────────────────┘                │                  │               │
 │                                           ▼                  ▼               │
 │  ┌──────────────────────────────────────────────────────────────────────┐   │
 │  │                    MONGODB SHARDED CLUSTER                           │   │
 │  │                                                                      │   │
 │  │  ┌────────────────────────────────────────────────────────────────┐  │   │
 │  │  │                    MONGOS ROUTER (:27025)                      │  │   │
 │  │  │            Client entry point — routes queries to shards       │  │   │
 │  │  └────────────────────────┬───────────────────────────────────────┘  │   │
 │  │                           │                                          │   │
 │  │  ┌────────────────────────┴───────────────────────────────────────┐  │   │
 │  │  │              CONFIG SERVER REPLICA SET (configrs)               │  │   │
 │  │  │                    configsvr1:27100                             │  │   │
 │  │  │              Stores sharding metadata & chunk maps              │  │   │
 │  │  └───────────────────────────────────────────────────────────────┘  │   │
 │  │                                                                      │   │
 │  │  ┌──────────────────────────┐  ┌──────────────────────────┐         │   │
 │  │  │   SHARD 1 — rs0          │  │   SHARD 2 — rs1          │         │   │
 │  │  │                          │  │                          │         │   │
 │  │  │  ┌────────┐ PRIMARY     │  │  ┌────────┐ PRIMARY     │         │   │
 │  │  │  │ mongo1 │ :27017      │  │  │ mongo4 │ :27020      │         │   │
 │  │  │  └────────┘              │  │  └────────┘              │         │   │
 │  │  │  ┌────────┐ SECONDARY   │  │  ┌────────┐ SECONDARY   │         │   │
 │  │  │  │ mongo2 │ :27018      │  │  │ mongo5 │ :27021      │         │   │
 │  │  │  └────────┘              │  │  └────────┘              │         │   │
 │  │  │  ┌────────┐ SECONDARY   │  │  ┌────────┐ SECONDARY   │         │   │
 │  │  │  │ mongo3 │ :27019      │  │  │ mongo6 │ :27022      │         │   │
 │  │  │  └────────┘              │  │  └────────┘              │         │   │
 │  │  └──────────────────────────┘  └──────────────────────────┘         │   │
 │  │                                                                      │   │
 │  │  Databases:                                                          │   │
 │  │    options_raw (sharded)        options_analytics (sharded)          │   │
 │  │    ├── trades     {sym: hashed} ├── cleaned_trades                  │   │
 │  │    ├── quotes     {sym: hashed} ├── enriched_trades {underlying: h} │   │
 │  │    ├── aggregates {sym: hashed} └── aggregated_metrics {underlying} │   │
 │  │    └── snapshots  {underlying}                                      │   │
 │  └──────────────────────────────────────────────────────────────────────┘   │
 │                           │                          │                      │
 │            ┌──────────────┘                          └──────────────┐       │
 │            ▼                                                        ▼       │
 │  ┌──────────────────────────┐                  ┌────────────────────────┐  │
 │  │   PROCESSING LAYER       │                  │   SERVING LAYER        │  │
 │  │   Apache Spark (local)   │                  │                        │  │
 │  │                          │                  │   FastAPI (:8000)      │  │
 │  │   User: spark_processor  │                  │   User: dashboard_     │  │
 │  │                          │                  │         reader         │  │
 │  │  ┌────────────────────┐  │                  │                        │  │
 │  │  │ 1. spark_clean.py  │  │                  │  GET /api/health       │  │
 │  │  │    Dedup + Parse   │  │                  │  GET /api/flow/scanner │  │
 │  │  ├────────────────────┤  │                  │  GET /api/flow/unusual │  │
 │  │  │ 2. spark_enrich.py │  │                  │  GET /api/analytics/   │  │
 │  │  │    Greeks + Sector │  │                  │      iv-skew           │  │
 │  │  ├────────────────────┤  │                  │      put-call-ratio    │  │
 │  │  │ 3. spark_transform │  │                  │      spread-moneyness  │  │
 │  │  │    .py Aggregate   │  │                  │      gamma-exposure    │  │
 │  │  └────────────────────┘  │                  │      lineage           │  │
 │  └──────────────────────────┘                  └───────────┬────────────┘  │
 │                                                             │               │
 │                                                             ▼               │
 │                                                ┌────────────────────────┐  │
 │                                                │   DASHBOARD            │  │
 │                                                │   React + Vite (:5173) │  │
 │                                                │                        │  │
 │                                                │  ┌──────────────────┐  │  │
 │                                                │  │ 1. FlowScanner   │  │  │
 │                                                │  │ 2. IVSkewChart   │  │  │
 │                                                │  │ 3. PutCallRatio  │  │  │
 │                                                │  │ 4. GammaExposure │  │  │
 │                                                │  │ 5. SpreadAnalysis│  │  │
 │                                                │  │ 6. DataLineage   │  │  │
 │                                                │  │ 7. SystemStatus  │  │  │
 │                                                │  └──────────────────┘  │  │
 │                                                └────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────────────┘
```

## Flujo de Datos

```
MASSIVE WebSocket ──► ws_consumer.py ──► options_raw.trades    ─┐
                                     ──► options_raw.quotes     │
                                     ──► options_raw.aggregates │
                                                                │
MASSIVE REST API ───► rest_poller.py ──► options_raw.snapshots  │
                                                                │
data/sectors.csv ──────────────────────────────────────────────►│
                                                                │
                      ┌─────────────────────────────────────────┘
                      ▼
               spark_clean.py
               (dedup, parse timestamps, parse OCC symbols,
                filter market hours)
                      │
                      ▼
              cleaned_trades
                      │
                      ▼
              spark_enrich.py
              (join snapshots → Greeks/IV/OI,
               join sectors.csv → sector/industry,
               compute: dollar_volume, moneyness,
               bid_ask_spread, vol_oi_ratio,
               unusual_flag, sentiment)
                      │
                      ▼
              enriched_trades
                      │
                      ▼
             spark_transform.py
             (group by underlying/sector/date/hour,
              compute: P/C ratio, IV skew,
              gamma exposure, spread avg,
              unusual count)
                      │
                      ▼
            aggregated_metrics
                      │
                      ▼
              FastAPI (:8000)
              5 analytical queries + lineage
                      │
                      ▼
            React Dashboard (:5173)
            7 visualization components
```

## Estrategia de Sharding

```
┌─────────────────────────────────────────────────┐
│              SHARD KEY STRATEGY                   │
│                                                   │
│  Collection              Shard Key    Type        │
│  ─────────────────────── ─────────── ──────────  │
│  options_raw.trades      sym          hashed      │
│  options_raw.quotes      sym          hashed      │
│  options_raw.aggregates  sym          hashed      │
│  options_raw.snapshots   underlying   hashed      │
│  analytics.enriched      underlying   hashed      │
│  analytics.aggregated    underlying   hashed      │
│                                                   │
│  Justificación:                                   │
│  - Hashed sharding distribuye uniformemente       │
│  - sym tiene alta cardinalidad (miles de tickers) │
│  - underlying agrupa contratos del mismo ticker   │
│    en el mismo shard → queries eficientes         │
└─────────────────────────────────────────────────┘
```

## RBAC — Flujo de Acceso

```
                    ┌─────────────┐
                    │    admin     │
                    │  role: root  │
                    └──────┬──────┘
                           │ manages
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
  │ingest_writer│  │spark_processor│  │dashboard_    │
  │             │  │              │  │reader        │
  │ readWrite:  │  │ read:        │  │ read:        │
  │ options_raw │  │ options_raw  │  │ options_     │
  │             │  │ readWrite:   │  │ analytics    │
  │             │  │ options_     │  │              │
  │             │  │ analytics    │  │              │
  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
         │                │                  │
         ▼                ▼                  ▼
  ws_consumer.py   spark_clean.py     FastAPI/Dashboard
  rest_poller.py   spark_enrich.py
                   spark_transform.py
```

## Teorema CAP

```
                    Consistency
                       /\
                      /  \
                     /    \
                    / MongoDB\
                   /  (HERE)  \
                  /     CP     \
                 /──────────────\
                /                \
     Availability ────────────── Partition
                                 Tolerance

  MongoDB = CP (Consistency + Partition Tolerance)

  - Write Concern: majority
  - Durante partición: rechaza escrituras si no hay mayoría
  - Elección de primary: ~10 segundos de downtime
  - Trade-off: disponibilidad sacrificada por consistencia

  ¿Por qué CP para datos financieros?
  → Un precio inconsistente es peor que un servicio
    temporalmente no disponible
  → Greeks calculados sobre precios stale producen
    señales analíticas erróneas
  → Mejor rechazar una escritura que aceptar datos
    que contradicen la realidad del mercado
```
