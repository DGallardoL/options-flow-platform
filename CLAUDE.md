# CLAUDE.md — Options Flow Intelligence Platform

## TL;DR para Claude Code

Este archivo es la especificación completa del proyecto. Léelo completo antes de escribir una sola línea de código. Construye el proyecto fase por fase, en orden. Cada fase debe funcionar antes de pasar a la siguiente. Si algo falla, arréglalo antes de avanzar.

**El usuario ya tiene un `.env` con `POLYGON_API_KEY=xxx`. No pidas la API key, solo úsala.**

---

## 1. QUÉ ES ESTE PROYECTO

Proyecto final de la materia "Bases de Datos No Relacionales" (universidad).
Pipeline distribuido end-to-end que:
1. Captura datos de opciones del mercado de US en tiempo real vía WebSocket
2. Los ingesta en MongoDB (replica set con sharding y RBAC)
3. Los procesa con Apache Spark (limpieza, enriquecimiento, transformación)
4. Los sirve a un dashboard React estilo terminal de quant finance vía FastAPI

**Fuente de datos**: MASSIVE (antes Polygon.io) — datos de opciones de todas las bolsas de US.

**Criterios de evaluación**:
- 40% Repositorio funcional (que corra end-to-end)
- 30% README.md (documentación exhaustiva)
- 30% Presentación final

---

## 2. ESTRUCTURA DEL PROYECTO

Crea exactamente esta estructura:

```
options-flow-platform/
├── CLAUDE.md
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── setup.sh
├── run_spark_jobs.sh
├── data/
│   └── sectors.csv
├── docker/
│   └── mongo/
│       └── init-replica.sh
├── scripts/
│   ├── init_mongo_users.js
│   ├── init_indexes.js
│   ├── seed_reference_data.py
│   └── load_test.py
├── ingest/
│   ├── __init__.py
│   ├── config.py
│   ├── ws_consumer.py
│   ├── rest_poller.py
│   └── tests/
│       ├── test_consumer.py
│       └── test_poller.py
├── processing/
│   ├── __init__.py
│   ├── spark_clean.py
│   ├── spark_enrich.py
│   └── spark_transform.py
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── routers/
│   │   ├── flow.py
│   │   ├── analytics.py
│   │   └── health.py
│   ├── services/
│   │   ├── mongo_client.py
│   │   └── query_service.py
│   └── models/
│       └── schemas.py
├── dashboard/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── components/
│       │   ├── FlowScanner.jsx
│       │   ├── IVSkewChart.jsx
│       │   ├── PutCallRatio.jsx
│       │   ├── GammaExposure.jsx
│       │   ├── SpreadAnalysis.jsx
│       │   ├── DataLineage.jsx
│       │   └── SystemStatus.jsx
│       ├── hooks/
│       │   └── useAPI.js
│       └── lib/
│           └── api.js
└── docs/
```

---

## 3. REFERENCIA COMPLETA DE LA API (MASSIVE / Polygon.io)

### 3.1 Autenticación
- **Python client**: `pip install polygon-api-client` → importa `from polygon import RESTClient, WebSocketClient`
- **REST**: header `Authorization: Bearer ${POLYGON_API_KEY}` O query param `?apiKey=${POLYGON_API_KEY}`
- **WebSocket**: después de conectar, enviar `{"action":"auth","params":"${POLYGON_API_KEY}"}`
- La librería de Python maneja auth automáticamente, solo pásale el api_key

### 3.2 WebSocket — Opciones
- **URL**: `wss://ws.massive.com/options`
- **Límite**: 1 conexión concurrente por asset class
- **Plan básico**: datos con 15 min de delay (está bien, siguen siendo reales)

**Canal de Trades (prefijo `T.`)**
Suscripción: `T.*` (todos) o `T.O:AAPL251219C00200000` (uno específico)
```
Campos del evento:
  ev    string   "T" (tipo de evento)
  sym   string   Ticker de la opción en formato OCC, ej: "O:AAPL251219C00200000"
  x     int      Exchange ID
  p     float    Precio del trade
  s     int      Tamaño (contratos)
  c     int[]    Condition codes
  t     int      Timestamp Unix en milisegundos
  q     int      Sequence number (único por sym, no secuencial)
```

**Canal de Quotes (prefijo `Q.`)**
Suscripción: `Q.*` (todos)
```
Campos del evento:
  ev    string   "Q"
  sym   string   Ticker de la opción
  bx    int      Bid exchange ID
  ax    int      Ask exchange ID
  bp    float    Bid price
  ap    float    Ask price
  bs    int      Bid size
  as    int      Ask size
  t     int      Timestamp Unix ms
  q     int      Sequence number
```

**Canal de Aggregates por segundo (prefijo `A.`)**
Suscripción: `A.*` (todos)
```
Campos del evento:
  ev    string   "A"
  sym   string   Ticker de la opción
  v     int      Volumen del tick
  av    int      Volumen acumulado del día
  op    float    Precio oficial de apertura del día
  vw    float    VWAP de esta ventana
  o     float    Open de la ventana
  c     float    Close de la ventana
  h     float    High de la ventana
  l     float    Low de la ventana
  a     float    VWAP del día
  z     int      Tamaño promedio de trade en esta ventana
  s     int      Start timestamp Unix ms
  e     int      End timestamp Unix ms
```

### 3.3 REST API — Endpoints clave
Base URL: `https://api.massive.com`

| Endpoint | Descripción |
|----------|-------------|
| `GET /v3/snapshot/options/{underlying}` | Option chain snapshot con Greeks, IV, OI |
| `GET /v3/snapshot/options/{underlying}/{contract}` | Snapshot de un contrato |
| `GET /v3/reference/options/contracts` | Listar contratos |
| `GET /v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}` | Aggregates históricos |

Query params del chain snapshot: `strike_price`, `expiration_date`, `contract_type`, `limit` (max 250), `sort`, `order`

Estructura de respuesta por contrato:
```json
{
  "break_even_price": 205.50,
  "day": { "open": 3.20, "high": 3.80, "low": 3.10, "close": 3.45, "volume": 1234, "vwap": 3.42 },
  "details": { "contract_type": "call", "exercise_style": "american", "expiration_date": "2025-12-19", "shares_per_contract": 100, "strike_price": 200, "ticker": "O:AAPL251219C00200000" },
  "greeks": { "delta": 0.65, "gamma": 0.03, "theta": -0.12, "vega": 0.45 },
  "implied_volatility": 0.32,
  "last_quote": { "ask": 3.50, "ask_size": 10, "bid": 3.40, "bid_size": 15 },
  "last_trade": { "price": 3.45, "size": 5, "exchange": 302 },
  "open_interest": 15234,
  "underlying_asset": { "ticker": "AAPL", "price": 198.50, "change_to_break_even": 7.00 }
}
```

### 3.4 Formato OCC de Symbols
`O:{UNDERLYING}{YYMMDD}{C/P}{STRIKE*1000 con padding a 8 dígitos}`
Ejemplo: `O:AAPL251219C00200000` = AAPL, Dec 19 2025, Call, Strike $200.00

Parser:
```python
import re
from datetime import datetime

def parse_option_symbol(sym: str) -> dict | None:
    m = re.match(r'^O:(\w+?)(\d{6})([CP])(\d{8})$', sym)
    if not m:
        return None
    underlying, date_str, cp, strike_raw = m.groups()
    return {
        'underlying': underlying,
        'expiration': datetime.strptime(date_str, '%y%m%d').strftime('%Y-%m-%d'),
        'contract_type': 'call' if cp == 'C' else 'put',
        'strike': int(strike_raw) / 1000,
    }
```

### 3.5 Uso de la librería Python

```python
# WebSocket
from polygon import WebSocketClient
import os

ws = WebSocketClient(
    api_key=os.environ["POLYGON_API_KEY"],
    market="options",
    subscriptions=["T.*", "Q.*", "A.*"]
)

def handle_msg(msgs):
    for m in msgs:
        # Trades: m.symbol, m.price, m.size, m.timestamp, m.sequence_number, m.exchange, m.conditions
        # Quotes: m.symbol, m.bid_price, m.ask_price, m.bid_size, m.ask_size, m.timestamp
        # Aggs: m.symbol, m.volume, m.accumulated_volume, m.open, m.close, m.high, m.low, m.vwap, m.start_timestamp, m.end_timestamp
        print(m)

ws.run(handle_msg=handle_msg)

# REST
from polygon import RESTClient
client = RESTClient(api_key=os.environ["POLYGON_API_KEY"])
for snapshot in client.list_snapshot_options_chain("AAPL"):
    print(snapshot.greeks.delta, snapshot.implied_volatility, snapshot.open_interest)
```

---

## 4. DOCKER COMPOSE

### 4.1 MongoDB Replica Set (3 nodos)
- `mongo1` puerto 27017, `mongo2` puerto 27018, `mongo3` puerto 27019
- Replica set name: `rs0`
- Auth con keyFile (generar con `openssl rand -base64 756 > docker/mongo/keyfile && chmod 400 docker/mongo/keyfile`)
- Volúmenes persistentes: `mongo1-data`, `mongo2-data`, `mongo3-data`
- Network: `options-net`
- Comando: `mongod --replSet rs0 --bind_ip_all --keyFile /etc/mongo/keyfile --auth`
- Healthcheck: `mongosh --eval "db.adminCommand('ping')"` o similar

### 4.2 Init container (mongo-init)
Runs once after all 3 mongos are healthy:
1. Connect to mongo1 sin auth (primera vez)
2. `rs.initiate()` con los 3 miembros
3. Esperar a que haya primary
4. Crear admin user primero
5. Reconectar con admin credentials
6. Crear los otros 3 users (ingest_writer, spark_processor, dashboard_reader)
7. Crear bases de datos y colecciones
8. Crear índices

---

## 5. MONGODB — RBAC

```javascript
// Admin (acceso total)
db.createUser({ user: "admin", pwd: "CHANGE_ME_ADMIN", roles: [{ role: "root", db: "admin" }] });
// Ingest Writer (solo escribe raw)
db.createUser({ user: "ingest_writer", pwd: "CHANGE_ME_INGEST", roles: [{ role: "readWrite", db: "options_raw" }] });
// Spark (lee raw, escribe analytics)
db.createUser({ user: "spark_processor", pwd: "CHANGE_ME_SPARK", roles: [{ role: "read", db: "options_raw" }, { role: "readWrite", db: "options_analytics" }] });
// Dashboard (solo lee analytics)
db.createUser({ user: "dashboard_reader", pwd: "CHANGE_ME_DASHBOARD", roles: [{ role: "read", db: "options_analytics" }] });
```

Passwords vienen del `.env`.

---

## 6. MONGODB — SCHEMAS E ÍNDICES

### DB: `options_raw`
```javascript
// trades
db.trades.createIndex({ sym: 1, t: -1 });
db.trades.createIndex({ t: -1 });
db.trades.createIndex({ sym: 1, q: 1 }, { unique: true });

// quotes
db.quotes.createIndex({ sym: 1, t: -1 });
db.quotes.createIndex({ t: -1 });

// aggregates
db.aggregates.createIndex({ sym: 1, s: -1 });

// snapshots
db.snapshots.createIndex({ sym: 1, fetched_at: -1 });
db.snapshots.createIndex({ underlying: 1, fetched_at: -1 });
```

### DB: `options_analytics`
```javascript
// enriched_trades
db.enriched_trades.createIndex({ underlying: 1, timestamp: -1 });
db.enriched_trades.createIndex({ sector: 1, timestamp: -1 });
db.enriched_trades.createIndex({ unusual_flag: 1, timestamp: -1 });

// aggregated_metrics
db.aggregated_metrics.createIndex({ underlying: 1, date: -1, hour: 1 });
db.aggregated_metrics.createIndex({ sector: 1, date: -1 });
```

---

## 7. CAPA DE INGESTA

### 7.1 Config (`ingest/config.py`)
Pydantic-settings cargando de `.env`:
- POLYGON_API_KEY
- MONGO_URI (default: `mongodb://ingest_writer:${MONGO_INGEST_PWD}@localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0&authSource=admin`)
- MONGO_DB (default: `options_raw`)

### 7.2 WebSocket Consumer (`ingest/ws_consumer.py`)
- Usa `polygon.WebSocketClient(api_key=..., market="options", subscriptions=["T.*","Q.*","A.*"])`
- Handler acumula en 3 buffers (trades, quotes, aggs)
- Flush: cada 1 seg o 100 eventos → `insert_many()` con `ordered=False`
- Agrega `_ingested_at = datetime.utcnow()` a cada doc
- Convierte los objetos WebSocketMessage a dicts con los field names cortos (ev, sym, p, s, etc.)
- Signal handler para SIGINT → flush + close
- Logging: eventos/minuto por tipo
- Entry: `python -m ingest.ws_consumer`

### 7.3 REST Poller (`ingest/rest_poller.py`)
- WATCHLIST = ["AAPL","NVDA","TSLA","SPY","AMZN","META","MSFT","GOOGL","QQQ","AMD"]
- Cada 60 seg: para cada ticker → `client.list_snapshot_options_chain(ticker)` → parse → upsert
- Solo en market hours (9:30-16:00 ET lun-vie)
- Entry: `python -m ingest.rest_poller`

---

## 8. CAPA DE PROCESAMIENTO (SPARK)

### 8.1 Limpieza (`processing/spark_clean.py`)
Lee `options_raw.trades` → deduplica por (sym, q) → parsea timestamps → filtra market hours → parsea sym → escribe a `options_analytics.cleaned_trades`

### 8.2 Enriquecimiento (`processing/spark_enrich.py`)
Lee cleaned_trades + snapshots → join por sym (snapshot más reciente) → agrega Greeks/IV/OI → join con sectors.csv → calcula derivados:
- dollar_volume = price × size × 100
- moneyness_pct = (strike - underlying_price) / underlying_price
- moneyness: "Deep ITM/ITM/ATM/OTM/Deep OTM"
- bid_ask_spread = ask - bid
- vol_oi_ratio = daily_volume / max(OI, 1)
- unusual_flag = vol_oi_ratio > 1.5
- sentiment heuristic
→ escribe a `options_analytics.enriched_trades`

### 8.3 Agregación (`processing/spark_transform.py`)
Lee enriched_trades → agrupa por (underlying, sector, date, hour) → calcula:
- total_call_volume, total_put_volume, put_call_ratio
- avg_iv_calls, avg_iv_puts, iv_skew
- net_gamma_exposure = Σ(gamma × OI × 100 × spot²)
- avg_bid_ask_spread
- unusual_activity_count
→ escribe a `options_analytics.aggregated_metrics`

Si el conector mongo-spark da problemas, usar pymongo para leer/escribir y Spark solo para el procesamiento in-memory.

---

## 9. FASTAPI BACKEND

### Endpoints
```
GET /api/health
GET /api/flow/scanner?limit=100
GET /api/flow/unusual?date=YYYY-MM-DD&limit=50
GET /api/analytics/iv-skew?underlying=AAPL&date=YYYY-MM-DD
GET /api/analytics/put-call-ratio?date=YYYY-MM-DD
GET /api/analytics/spread-moneyness?date=YYYY-MM-DD
GET /api/analytics/gamma-exposure?date=YYYY-MM-DD&limit=20
GET /api/analytics/lineage?sym=O:AAPL251219C00200000
```

Usa `motor` (async pymongo) con user `dashboard_reader`.
CORS habilitado para `localhost:5173`.
Las queries son los aggregation pipelines de la sección 9.3 abajo.

### 9.3 Las 5 Queries Analíticas

**Q1 — Unusual Options Activity**: group enriched_trades by sym → sum volume → divide by OI → filter vol/OI > 1.5 → sort by dollar_volume desc

**Q2 — IV Skew**: filter by underlying → bucket delta into P50/P25/P10/C10/C25/C50 → avg IV per bucket

**Q3 — Put/Call Ratio by Sector**: group by (sector, hour) → sum call_vol and put_vol → ratio

**Q4 — Spread vs Moneyness**: bucket moneyness_pct → avg spread and total volume per bucket

**Q5 — Gamma Exposure**: group by underlying → sum(gamma × OI × 100 × spot²) split by call/put → sort

**Lineage**: fetch one doc with matching sym from each collection (raw.trades, analytics.cleaned_trades, analytics.enriched_trades, analytics.aggregated_metrics)

---

## 10. DASHBOARD REACT

### Setup
Vite + React + TailwindCSS v4 + Recharts + Lucide React + Axios + Google Font JetBrains Mono

### Estética: Terminal Quant Finance
```
--bg: #0a0e17  --surface: #111827  --border: #1e293b
--text: #e2e8f0  --text-muted: #64748b
--green: #22c55e  --red: #ef4444  --cyan: #06b6d4  --amber: #f59e0b  --purple: #a78bfa
Font: JetBrains Mono everywhere. Max border-radius: 6px. No shadows. No UI libraries.
```

### Layout
Header fijo: logo + LIVE pulse + stats. Sidebar tabs: Flow | IV Skew | P/C | Gamma | Spread | Lineage | Status. Content area.

### 7 Componentes
1. **FlowScanner** — Tabla de trades. Filtros: All/Unusual/Bullish/Bearish. Badges de Call/Put, Sentiment. Unusual rows highlighted amber. Auto-refresh 5s.
2. **IVSkewChart** — LineChart: X=delta bucket, Y=IV%. Toggle underlyings. Recharts.
3. **PutCallRatio** — AreaChart: X=hora, Y=ratio. Una área por sector. ReferenceLine y=1.0.
4. **GammaExposure** — Horizontal BarChart: Y=ticker, X=gamma $M. Green=call, Red=put.
5. **SpreadAnalysis** — ComposedChart: Bar=spread, Line=volume. X=moneyness bucket.
6. **DataLineage** — 4 cards con flechas: Raw→Clean→Enrich→Analytical. JSON de cada etapa. Dropdown de sym.
7. **SystemStatus** — StatCards de conteos + indicadores verde/rojo.

---

## 11. DATOS ESTÁTICOS (`data/sectors.csv`)
```csv
ticker,sector,industry
AAPL,Technology,Consumer Electronics
NVDA,Semiconductors,GPU/AI Chips
TSLA,Consumer Discretionary,Electric Vehicles
SPY,Index,S&P 500 ETF
AMZN,Consumer Discretionary,E-Commerce
META,Technology,Social Media
MSFT,Technology,Enterprise Software
GOOGL,Technology,Search/Cloud
QQQ,Index,Nasdaq 100 ETF
AMD,Semiconductors,CPU/GPU
```

---

## 12. PRUEBAS

### Load Test (`scripts/load_test.py`)
Genera docs sintéticos → inserta a 10/50/100/500 docs/seg durante 30s → mide latencia y throughput → output tabla + CSV

### Resilience Test (`scripts/resilience_test.py`)
Insert continuo → docker stop mongo2 → verify writes OK → docker stop mongo3 → verify → docker start ambos → verify resync

---

## 13. CAP THEOREM
MongoDB = **CP**. Write concern majority garantiza consistency. Si cae primary, hay elección (~10s sin writes). Para datos financieros, consistency > availability.

---

## 14. README.md DEBE CUBRIR
1. Título + Equipo [PLACEHOLDER]
2. Resumen del Stream
3. Origen y Autoría (MASSIVE/Polygon.io, bolsas US)
4. Diccionario de Datos (tabla completa por evento)
5. Variables Cuantitativas
6. Variables Cualitativas
7. Texto No Estructurado (condition codes)
8. Series Temporales
9. Consideraciones Éticas
10. Arquitectura + diagrama + CAP
11. Infraestructura (Docker, MongoDB RS, Spark, RBAC)
12. Capa de Ingesta + pruebas
13. Capa de Procesamiento (3 Spark jobs)
14. Análisis (5 queries + resultados + interpretación)
15. Trazabilidad (ejemplo raw→analytical)
16. Dashboard (descripción + screenshots placeholder)
17. Instrucciones de Ejecución paso a paso

---

## 15. DEPENDENCIAS

### requirements.txt
```
polygon-api-client>=1.14.0
pymongo>=4.6.0
motor>=3.3.0
pyspark>=3.5.0
fastapi>=0.110.0
uvicorn>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

### dashboard/package.json deps
```
react, react-dom, recharts, lucide-react, axios
devDeps: vite, @vitejs/plugin-react, tailwindcss, @tailwindcss/vite
```

---

## 16. ORDEN DE CONSTRUCCIÓN (SEGUIR ESTRICTAMENTE)

1. Scaffolding (dirs, .gitignore, .env.example, sectors.csv, deps)
2. Docker + MongoDB (docker-compose, init scripts, verificar RS + RBAC + índices)
3. WebSocket Consumer (conectar, ingestar, verificar datos en Mongo)
4. REST Poller (snapshots con Greeks, verificar en Mongo)
5. Spark Jobs (clean → enrich → transform, verificar analytics DB)
6. FastAPI (endpoints, verificar con curl)
7. Dashboard React (completo, conectado al API)
8. Tests (load + resilience, guardar output)
9. README.md (documentación completa)
10. Scripts finales (setup.sh, run_spark_jobs.sh, verificar end-to-end)