# Options Flow Intelligence Platform

## Equipo
<!-- PLACEHOLDER: Agregar nombres del equipo -->
- [Nombre 1]
- [Nombre 2]
- [Nombre 3]

**Materia:** Bases de Datos No Relacionales  
**Periodo:** Primavera 2026

---

## Tabla de Contenidos

1. [Resumen del Stream](#1-resumen-del-stream)
2. [Origen y Autoria de los Datos](#2-origen-y-autoria-de-los-datos)
3. [Diccionario de Datos](#3-diccionario-de-datos)
4. [Variables Cuantitativas](#4-variables-cuantitativas)
5. [Variables Cualitativas](#5-variables-cualitativas)
6. [Texto No Estructurado](#6-texto-no-estructurado)
7. [Series Temporales](#7-series-temporales)
8. [Consideraciones Eticas](#8-consideraciones-eticas)
9. [Arquitectura del Sistema y Teorema CAP](#9-arquitectura-del-sistema-y-teorema-cap)
10. [Infraestructura](#10-infraestructura)
11. [Capa de Ingesta](#11-capa-de-ingesta)
12. [Capa de Procesamiento (Apache Spark)](#12-capa-de-procesamiento-apache-spark)
13. [Analisis — 5 Queries Analiticas](#13-analisis--5-queries-analiticas)
14. [Trazabilidad del Dato](#14-trazabilidad-del-dato)
15. [Dashboard](#15-dashboard)
16. [Instrucciones de Ejecucion](#16-instrucciones-de-ejecucion)

---

## 1. Resumen del Stream

Este proyecto implementa un **pipeline distribuido end-to-end** que captura, almacena, procesa y visualiza datos de opciones financieras del mercado de valores de Estados Unidos en tiempo real.

### Fuente de datos

El stream proviene de **MASSIVE** (anteriormente Polygon.io), un proveedor de datos financieros que agrega informacion de todas las bolsas de opciones de EE.UU. a traves de los Securities Information Processors (SIPs). Los datos se reciben por dos canales:

| Canal | Protocolo | Datos | Frecuencia |
|-------|-----------|-------|------------|
| WebSocket | `wss://ws.massive.com/options` | Trades, Quotes, Aggregates | Tiempo real (15 min delay en plan basico) |
| REST API | `https://api.polygon.io` | Option chain snapshots con Greeks, IV, OI | Polling cada 60 segundos |

### Volumetria

- **Trades (T.\*)**: Cada transaccion ejecutada de un contrato de opciones en cualquier bolsa de EE.UU.
- **Quotes (Q.\*)**: Cotizaciones bid/ask actualizadas en tiempo real (mejor oferta nacional NBBO).
- **Aggregates (A.\*)**: Velas OHLCV por segundo, generadas por el servidor.
- **Snapshots (REST)**: Chain completo con Greeks (delta, gamma, theta, vega), volatilidad implicita (IV) y open interest (OI) para 10 tickers del watchlist.

Durante horas de mercado (9:30-16:00 ET, lunes a viernes), el stream produce **cientos de eventos por segundo** entre los tres canales de WebSocket, superando ampliamente el requisito de 1 evento/segundo.

### Watchlist

El sistema monitorea activamente 10 subyacentes de alta liquidez:

| Ticker | Sector | Industria |
|--------|--------|-----------|
| AAPL | Technology | Consumer Electronics |
| NVDA | Semiconductors | GPU/AI Chips |
| TSLA | Consumer Discretionary | Electric Vehicles |
| SPY | Index | S&P 500 ETF |
| AMZN | Consumer Discretionary | E-Commerce |
| META | Technology | Social Media |
| MSFT | Technology | Enterprise Software |
| GOOGL | Technology | Search/Cloud |
| QQQ | Index | Nasdaq 100 ETF |
| AMD | Semiconductors | CPU/GPU |

### Enlaces

| Recurso | URL |
|---------|-----|
| API REST | `https://api.polygon.io` (redirige a massive.com) |
| WebSocket de opciones | `wss://ws.massive.com/options` |
| Documentacion oficial | https://massive.com/docs/options |
| Libreria Python | `pip install polygon-api-client` |

---

## 2. Origen y Autoria de los Datos

### Proveedor: MASSIVE (Polygon.io)

**MASSIVE**, anteriormente conocido como **Polygon.io**, es un proveedor de datos financieros de grado institucional con sede en Nueva York. Proporciona acceso a datos de mercado de acciones, opciones, forex, y criptomonedas en Estados Unidos y otros mercados globales.

### Cadena de custodia del dato

El flujo de datos desde su origen hasta nuestro sistema es:

```
Bolsas de Opciones (CBOE, PHLX, NYSE Arca, ISE, MIAX, BOX, BATS, etc.)
         |
         v
Securities Information Processors (SIPs)
    ├── OPRA (Options Price Reporting Authority) — consolida todos los trades/quotes de opciones
    └── Regulados por la SEC bajo Regulation NMS
         |
         v
MASSIVE / Polygon.io — agrega, normaliza y redistribuye
    ├── WebSocket: streaming en tiempo real
    └── REST API: snapshots bajo demanda
         |
         v
Nuestro Pipeline (WebSocket Consumer + REST Poller)
```

### Bolsas de opciones participantes

Los datos provienen de **todas** las bolsas de opciones registradas en EE.UU., incluyendo:

| Bolsa | Exchange ID | Descripcion |
|-------|-------------|-------------|
| **CBOE** | 301 | Chicago Board Options Exchange — la bolsa de opciones mas grande del mundo |
| **NASDAQ PHLX** | 302 | Philadelphia Stock Exchange — segunda mas antigua de EE.UU. |
| **NYSE Arca Options** | 304 | Plataforma electronica de NYSE |
| **ISE** | 305 | International Securities Exchange |
| **MIAX** | 313 | Miami International Securities Exchange |
| **BOX** | 315 | Boston Options Exchange |
| **BATS/Cboe BZX** | 316 | Plataforma electronica de alta velocidad |
| **MEMX** | 326 | Members Exchange — bolsa de nueva generacion |
| **Cboe EDGX** | 311 | Plataforma de baja latencia |
| Otras | Varios | C2, Nasdaq ISE Gemini, Nasdaq MRX, etc. |

### Naturaleza de los datos

- **100% reales** — no son simulados ni sinteticos.
- **Regulados** — los SIPs estan regulados por la SEC bajo la Rule 603 de Regulation NMS.
- **Publicos** — los datos de mercado son informacion publica; cualquier persona puede acceder a ellos a traves de proveedores autorizados.
- **Consolidados** — OPRA consolida todos los trades y quotes de todas las bolsas en un solo feed.
- **15 minutos de delay** — el plan basico proporciona datos con 15 minutos de retraso. Esto es suficiente para analisis y para propositos educativos, y elimina cualquier posibilidad de uso para front-running.

---

## 3. Diccionario de Datos

### 3.1 Trade Event (Canal WebSocket `T.*`)

Cada mensaje representa una **transaccion ejecutada** de un contrato de opciones. Se genera cuando un comprador y un vendedor acuerdan un precio y tamanio en una bolsa.

| Campo | Tipo de Dato | Nullable | Descripcion | Ejemplo |
|-------|-------------|----------|-------------|---------|
| `ev` | `enum("T")` | No | Tipo de evento, siempre `"T"` para trades | `"T"` |
| `sym` | `string` | No | Ticker del contrato de opciones en formato OCC (Options Clearing Corporation) | `"O:AAPL251219C00200000"` |
| `x` | `integer` | No | ID numerico de la bolsa donde se ejecuto el trade. Corresponde a un exchange registrado en OPRA | `301` (CBOE) |
| `p` | `number` (float) | No | Precio del trade en USD. Representa la prima por accion (no por contrato). Para obtener el costo total: `p * s * 100` | `3.45` |
| `s` | `integer` | No | Tamanio del trade en numero de contratos. Cada contrato estandar controla 100 acciones del subyacente | `5` |
| `c` | `array[integer]` | Si | Codigos de condicion de ejecucion definidos por OPRA. Indican circunstancias especiales del trade (ver seccion 6) | `[0, 12]` |
| `t` | `integer` | No | Timestamp Unix en **milisegundos** (ms desde epoch 1970-01-01 00:00:00 UTC) del momento exacto de ejecucion | `1703001600000` |
| `q` | `integer` | No | Sequence number. Identificador unico **por simbolo** (no globalmente). Usado para deduplicacion. No es secuencial pero si unico por ticker | `12345` |

### 3.2 Quote Event (Canal WebSocket `Q.*`)

Cada mensaje representa una **actualizacion de cotizacion** (mejor bid y ask disponibles) para un contrato de opciones.

| Campo | Tipo de Dato | Nullable | Descripcion | Ejemplo |
|-------|-------------|----------|-------------|---------|
| `ev` | `enum("Q")` | No | Tipo de evento, siempre `"Q"` para quotes | `"Q"` |
| `sym` | `string` | No | Ticker del contrato de opciones en formato OCC | `"O:AAPL251219C00200000"` |
| `bx` | `integer` | No | ID de la bolsa que ofrece el mejor precio de compra (bid) | `302` (PHLX) |
| `ax` | `integer` | No | ID de la bolsa que ofrece el mejor precio de venta (ask) | `301` (CBOE) |
| `bp` | `number` (float) | No | Precio bid (mejor oferta de compra). Es el precio mas alto que alguien esta dispuesto a pagar | `3.40` |
| `ap` | `number` (float) | No | Precio ask (mejor oferta de venta). Es el precio mas bajo al que alguien esta dispuesto a vender | `3.50` |
| `bs` | `integer` | No | Tamanio del bid en numero de contratos disponibles a ese precio | `15` |
| `as` | `integer` | No | Tamanio del ask en numero de contratos disponibles a ese precio | `10` |
| `t` | `integer` | No | Timestamp Unix en milisegundos | `1703001600500` |
| `q` | `integer` | No | Sequence number unico por simbolo | `67890` |

### 3.3 Aggregate Event (Canal WebSocket `A.*`)

Cada mensaje representa una **vela OHLCV de 1 segundo** — un resumen estadistico de toda la actividad de un contrato durante esa ventana temporal.

| Campo | Tipo de Dato | Nullable | Descripcion | Ejemplo |
|-------|-------------|----------|-------------|---------|
| `ev` | `enum("A")` | No | Tipo de evento, siempre `"A"` para aggregates | `"A"` |
| `sym` | `string` | No | Ticker del contrato de opciones en formato OCC | `"O:AAPL251219C00200000"` |
| `v` | `integer` | No | Volumen de la ventana: numero total de contratos negociados en este segundo | `42` |
| `av` | `integer` | No | Volumen acumulado del dia: total de contratos negociados desde la apertura hasta este momento | `15340` |
| `op` | `number` (float) | No | Precio oficial de apertura del dia, establecido por la bolsa | `3.20` |
| `vw` | `number` (float) | No | VWAP (Volume Weighted Average Price) de esta ventana de 1 segundo | `3.42` |
| `o` | `number` (float) | No | Precio de apertura de la ventana (primer trade del segundo) | `3.40` |
| `c` | `number` (float) | No | Precio de cierre de la ventana (ultimo trade del segundo) | `3.45` |
| `h` | `number` (float) | No | Precio maximo alcanzado durante la ventana | `3.48` |
| `l` | `number` (float) | No | Precio minimo alcanzado durante la ventana | `3.38` |
| `a` | `number` (float) | No | VWAP del dia completo hasta este momento | `3.35` |
| `z` | `integer` | No | Tamanio promedio de trade en esta ventana (contratos por transaccion) | `3` |
| `s` | `integer` | No | Start timestamp: inicio de la ventana de agregacion en Unix ms | `1703001600000` |
| `e` | `integer` | No | End timestamp: fin de la ventana de agregacion en Unix ms | `1703001601000` |

### 3.4 Option Chain Snapshot (REST API)

Respuesta del endpoint `GET /v3/snapshot/options/{underlying}`. Proporciona una **fotografia completa** de cada contrato de opciones en un momento dado, incluyendo Greeks, IV y OI.

#### Campos de nivel superior

| Campo | Tipo de Dato | Nullable | Descripcion | Ejemplo |
|-------|-------------|----------|-------------|---------|
| `break_even_price` | `number` (float) | No | Precio que el subyacente debe alcanzar para que la opcion sea rentable al vencimiento (incluyendo la prima pagada) | `205.50` |
| `implied_volatility` | `number` (float) | No | Volatilidad implicita como decimal. Representa la expectativa del mercado sobre la volatilidad futura del subyacente, derivada del precio de la opcion usando modelos como Black-Scholes | `0.32` (32%) |
| `open_interest` | `integer` | No | Numero total de contratos abiertos (no cerrados ni ejercidos). Se actualiza una vez al dia tras el cierre | `15234` |
| `fmv` | `number` (float) | Si | Fair Market Value — valor teorico justo del contrato calculado por MASSIVE | `3.42` |

#### Objeto `day` — Estadisticas del dia

| Campo | Tipo de Dato | Descripcion | Ejemplo |
|-------|-------------|-------------|---------|
| `day.open` | `number` | Precio de apertura del dia | `3.20` |
| `day.close` | `number` | Ultimo precio del dia | `3.45` |
| `day.high` | `number` | Precio maximo del dia | `3.80` |
| `day.low` | `number` | Precio minimo del dia | `3.10` |
| `day.volume` | `integer` | Volumen total del dia en contratos | `1234` |
| `day.vwap` | `number` | VWAP del dia | `3.42` |
| `day.change` | `number` | Cambio absoluto vs cierre anterior | `0.25` |
| `day.change_percent` | `number` | Cambio porcentual vs cierre anterior | `7.81` |
| `day.previous_close` | `number` | Precio de cierre del dia anterior | `3.20` |

#### Objeto `details` — Metadatos del contrato

| Campo | Tipo de Dato | Descripcion | Ejemplo |
|-------|-------------|-------------|---------|
| `details.ticker` | `string` | Ticker OCC completo del contrato | `"O:AAPL251219C00200000"` |
| `details.strike_price` | `number` | Precio de ejercicio (strike) en USD | `200.0` |
| `details.expiration_date` | `string` | Fecha de vencimiento en formato YYYY-MM-DD | `"2025-12-19"` |
| `details.contract_type` | `string` | Tipo: `"call"` (derecho a comprar) o `"put"` (derecho a vender) | `"call"` |
| `details.exercise_style` | `string` | Estilo de ejercicio: `"american"` (ejercitable en cualquier momento) | `"american"` |
| `details.shares_per_contract` | `integer` | Acciones controladas por contrato (estandar: 100) | `100` |

#### Objeto `greeks` — Sensibilidades del precio

| Campo | Tipo de Dato | Rango | Descripcion | Ejemplo |
|-------|-------------|-------|-------------|---------|
| `greeks.delta` | `number` | [-1, 1] | Cambio en el precio de la opcion por cada $1 de cambio en el subyacente. Calls: [0,1], Puts: [-1,0] | `0.65` |
| `greeks.gamma` | `number` | [0, +inf) | Tasa de cambio de delta por cada $1 de cambio en el subyacente. Siempre positivo. Maximo en opciones ATM | `0.03` |
| `greeks.theta` | `number` | (-inf, 0] | Decaimiento temporal: cuanto pierde la opcion por dia que pasa. Siempre negativo | `-0.12` |
| `greeks.vega` | `number` | [0, +inf) | Cambio en precio por cada 1% de cambio en la volatilidad implicita. Siempre positivo | `0.45` |

#### Objeto `last_quote` — Ultima cotizacion

| Campo | Tipo de Dato | Descripcion | Ejemplo |
|-------|-------------|-------------|---------|
| `last_quote.bid` | `number` | Mejor precio de compra | `3.40` |
| `last_quote.ask` | `number` | Mejor precio de venta | `3.50` |
| `last_quote.bid_size` | `integer` | Contratos disponibles al bid | `15` |
| `last_quote.ask_size` | `integer` | Contratos disponibles al ask | `10` |
| `last_quote.midpoint` | `number` | Punto medio entre bid y ask: `(bid + ask) / 2` | `3.45` |
| `last_quote.timeframe` | `string` | Marco temporal de la cotizacion | `"REAL-TIME"` |
| `last_quote.last_updated` | `integer` | Timestamp Unix nanosegundos de la ultima actualizacion | `1703001600000000000` |

#### Objeto `last_trade` — Ultimo trade

| Campo | Tipo de Dato | Descripcion | Ejemplo |
|-------|-------------|-------------|---------|
| `last_trade.price` | `number` | Precio del ultimo trade ejecutado | `3.45` |
| `last_trade.size` | `integer` | Tamanio del ultimo trade en contratos | `5` |
| `last_trade.exchange` | `integer` | ID de la bolsa | `302` |
| `last_trade.conditions` | `array[integer]` | Codigos de condicion | `[0]` |
| `last_trade.sip_timestamp` | `integer` | Timestamp del SIP en nanosegundos | `1703001600000000000` |
| `last_trade.timeframe` | `string` | Marco temporal | `"REAL-TIME"` |

#### Objeto `underlying_asset` — Datos del subyacente

| Campo | Tipo de Dato | Descripcion | Ejemplo |
|-------|-------------|-------------|---------|
| `underlying_asset.ticker` | `string` | Ticker del activo subyacente | `"AAPL"` |
| `underlying_asset.price` | `number` | Precio actual del subyacente | `198.50` |
| `underlying_asset.change_to_break_even` | `number` | Diferencia entre precio actual y break-even: cuanto debe moverse el subyacente para que la opcion sea rentable | `7.00` |
| `underlying_asset.timeframe` | `string` | Marco temporal del precio | `"REAL-TIME"` |
| `underlying_asset.last_updated` | `integer` | Timestamp de la ultima actualizacion | `1703001600000000000` |

---

## 4. Variables Cuantitativas

Todas las variables numericas del sistema, organizadas por fuente y tipo.

### Variables cuantitativas continuas (float/number)

| Variable | Fuente | Unidad | Rango tipico | Descripcion |
|----------|--------|--------|-------------|-------------|
| `p` (price) | Trade WS | USD | 0.01 - 500+ | Prima por accion. Opciones OTM baratas pueden costar centavos; ITM deep pueden valer cientos |
| `bp` (bid price) | Quote WS | USD | 0.01 - 500+ | Mejor precio de compra disponible |
| `ap` (ask price) | Quote WS | USD | 0.01 - 500+ | Mejor precio de venta disponible |
| `vw` (tick VWAP) | Aggregate WS | USD | 0.01 - 500+ | Precio promedio ponderado por volumen en la ventana de 1 segundo |
| `o` (open) | Aggregate WS | USD | 0.01 - 500+ | Primer precio de la ventana |
| `c` (close) | Aggregate WS | USD | 0.01 - 500+ | Ultimo precio de la ventana |
| `h` (high) | Aggregate WS | USD | 0.01 - 500+ | Precio maximo de la ventana |
| `l` (low) | Aggregate WS | USD | 0.01 - 500+ | Precio minimo de la ventana |
| `op` (official open) | Aggregate WS | USD | 0.01 - 500+ | Precio oficial de apertura del dia |
| `a` (day VWAP) | Aggregate WS | USD | 0.01 - 500+ | VWAP acumulado del dia |
| `implied_volatility` | Snapshot REST | Decimal | 0.05 - 5.0+ | IV como fraccion (0.32 = 32%). Valores >1.0 indican alta volatilidad esperada |
| `greeks.delta` | Snapshot REST | Adimensional | [-1.0, 1.0] | Sensibilidad al subyacente |
| `greeks.gamma` | Snapshot REST | 1/USD | [0, ~0.5] | Tasa de cambio de delta |
| `greeks.theta` | Snapshot REST | USD/dia | [-50, 0] | Decaimiento temporal diario |
| `greeks.vega` | Snapshot REST | USD/%IV | [0, ~2.0] | Sensibilidad a volatilidad |
| `break_even_price` | Snapshot REST | USD | 50 - 5000+ | Precio de equilibrio |
| `strike_price` | Snapshot REST | USD | 50 - 5000+ | Precio de ejercicio |
| `underlying_asset.price` | Snapshot REST | USD | 1 - 5000+ | Precio spot del subyacente |
| `day.vwap` | Snapshot REST | USD | 0.01 - 500+ | VWAP del dia |
| `day.change_percent` | Snapshot REST | % | -100 - 10000+ | Cambio porcentual diario |
| `last_quote.midpoint` | Snapshot REST | USD | 0.01 - 500+ | Punto medio bid/ask |
| `fmv` | Snapshot REST | USD | 0.01 - 500+ | Fair market value |

### Variables cuantitativas discretas (integer)

| Variable | Fuente | Unidad | Rango tipico | Descripcion |
|----------|--------|--------|-------------|-------------|
| `s` (size) | Trade WS | Contratos | 1 - 10000+ | Numero de contratos en el trade |
| `bs` (bid size) | Quote WS | Contratos | 1 - 5000+ | Contratos disponibles al bid |
| `as` (ask size) | Quote WS | Contratos | 1 - 5000+ | Contratos disponibles al ask |
| `v` (tick volume) | Aggregate WS | Contratos | 0 - 50000 | Volumen en la ventana de 1 seg |
| `av` (accumulated volume) | Aggregate WS | Contratos | 0 - 500000+ | Volumen acumulado del dia |
| `z` (avg trade size) | Aggregate WS | Contratos | 1 - 1000 | Tamanio promedio de trade en la ventana |
| `x` (exchange ID) | Trade WS | ID | 300 - 330 | Identificador numerico de la bolsa |
| `open_interest` | Snapshot REST | Contratos | 0 - 500000+ | Contratos abiertos totales |
| `day.volume` | Snapshot REST | Contratos | 0 - 500000+ | Volumen diario |
| `shares_per_contract` | Snapshot REST | Acciones | 100 | Acciones por contrato (estandar) |

### Variables cuantitativas derivadas (calculadas en Spark)

| Variable | Formula | Unidad | Descripcion |
|----------|---------|--------|-------------|
| `dollar_volume` | `price * size * 100` | USD | Valor monetario total del trade |
| `moneyness_pct` | `(strike - spot) / spot` | Decimal | Distancia porcentual al dinero. Negativo = ITM para calls |
| `vol_oi_ratio` | `volume / max(OI, 1)` | Ratio | Ratio volumen/interes abierto. >1.5 se considera inusual |
| `bid_ask_spread` | `ask - bid` | USD | Spread de cotizacion. Mide liquidez |
| `put_call_ratio` | `put_vol / call_vol` | Ratio | Indicador de sentimiento. >1.0 = bajista |
| `iv_skew` | `avg_iv_puts - avg_iv_calls` | Decimal | Asimetria de volatilidad implicita |
| `net_gamma_exposure` | `SUM(gamma * OI * 100 * spot^2)` | USD | Exposicion gamma neta de market makers |

---

## 5. Variables Cualitativas

| Variable | Tipo | Valores Posibles | Cardinalidad | Descripcion |
|----------|------|-----------------|--------------|-------------|
| `ev` (event type) | Nominal | `"T"`, `"Q"`, `"A"` | 3 | Tipo de evento del WebSocket. Determina la estructura del mensaje |
| `contract_type` | Nominal | `"call"`, `"put"` | 2 | Tipo de contrato. Call = derecho a comprar; Put = derecho a vender |
| `exercise_style` | Nominal | `"american"` | 1 | Estilo de ejercicio. Opciones americanas pueden ejercerse en cualquier momento antes del vencimiento. Las opciones listadas en bolsas de EE.UU. son practicamente todas americanas |
| `moneyness` | Ordinal | `"Deep ITM"`, `"ITM"`, `"ATM"`, `"OTM"`, `"Deep OTM"` | 5 | Relacion entre el strike y el precio spot. ATM = at-the-money (strike ~ spot). ITM = in-the-money (rentable si se ejerce ahora). OTM = out-of-the-money (no rentable si se ejerce ahora) |
| `sentiment` | Ordinal | `"Bullish"`, `"Neutral"`, `"Bearish"` | 3 | Heuristica de sentimiento basada en moneyness y tipo de contrato. Call OTM = apuesta alcista, Put OTM = apuesta bajista |
| `unusual_flag` | Booleano | `true`, `false` | 2 | Bandera de actividad inusual. Se activa cuando vol/OI ratio > 1.5, indicando que el volumen del dia supera significativamente las posiciones abiertas historicas |
| `sector` | Nominal | `"Technology"`, `"Semiconductors"`, `"Consumer Discretionary"`, `"Index"` | 4 | Sector economico del activo subyacente, segun clasificacion propia basada en GICS |
| `industry` | Nominal | `"Consumer Electronics"`, `"GPU/AI Chips"`, `"Electric Vehicles"`, `"S&P 500 ETF"`, `"E-Commerce"`, `"Social Media"`, `"Enterprise Software"`, `"Search/Cloud"`, `"Nasdaq 100 ETF"`, `"CPU/GPU"` | 10 | Industria especifica del subyacente |
| `timeframe` | Nominal | `"REAL-TIME"`, `"DELAYED"` | 2 | Indica si el dato es en tiempo real o con delay |
| `delta_bucket` | Ordinal | `"P50"`, `"P25"`, `"P10"`, `"ATM"`, `"C10"`, `"C25"`, `"C50"` | 7 | Bucket de delta para analisis de IV skew. P = put side, C = call side, numero = delta aproximado |
| `moneyness_bucket` | Ordinal | `"Deep ITM"`, `"ITM"`, `"ATM"`, `"OTM"`, `"Deep OTM"` | 5 | Bucket de moneyness para analisis de spread |

---

## 6. Texto No Estructurado

### Condition Codes (`c` en Trade events)

El campo `c` en los eventos de Trade es un **array de enteros** que codifican las condiciones de ejecucion del trade. Estos codigos son definidos por la **Options Price Reporting Authority (OPRA)** y la **Options Clearing Corporation (OCC)**.

#### Por que es texto no estructurado

Aunque los codigos son numericos, su interpretacion requiere un **codebook externo** no incluido en el mensaje. Un mismo trade puede tener multiples condigos simultaneos, y su combinacion altera la interpretacion. No existe un schema fijo — el array puede estar vacio, tener un elemento, o multiples.

#### Codigos principales de OPRA

| Codigo | Condicion | Descripcion |
|--------|-----------|-------------|
| 0 | Regular Sale | Trade ejecutado en condiciones normales de mercado |
| 2 | Late Report | El trade se reporto con retraso al SIP |
| 4 | Seller | El vendedor tuvo condiciones especiales de entrega |
| 5 | Yellow Flag | Condicion especial no clasificada; requiere revision manual |
| 6 | Spread | Parte de una estrategia de spread (multiples opciones simultaneas) |
| 7 | Straddle | Parte de una estrategia straddle (call + put mismo strike/expiracion) |
| 8 | Buy-Write | Trade de compra de acciones + venta de call simultanea |
| 10 | Combo | Parte de una combinacion de opciones |
| 12 | Multi-Leg | Parte de una orden multi-pierna (butterfly, condor, etc.) |
| 15 | Stopped Stock | Trade ligado a una transaccion de acciones detenida |
| 23 | Intermarket Sweep | ISOs — ordenes de barrido entre bolsas para cumplir Reg NMS |
| 29 | Benchmark | Trade de referencia (no refleja precio de mercado actual) |
| 33 | Average Price | Precio promedio de multiples ejecuciones |
| 52 | Contingent | Trade condicionado a otro evento |
| 53 | Single Leg Auction Non ISO | Trade de subasta de una sola pierna |

#### Ejemplo de uso

```json
{
  "ev": "T",
  "sym": "O:AAPL251219C00200000",
  "c": [6, 12],
  "p": 3.45,
  "s": 50
}
```

Interpretacion: Este trade de 50 contratos fue parte de un **spread** (codigo 6) ejecutado como orden **multi-leg** (codigo 12). Esto sugiere actividad institucional sofisticada, no un trade retail simple.

#### Relevancia analitica

Los condition codes son criticos para analisis avanzado:
- **Filtrar ruido**: Trades con codigo 2 (late report) pueden distorsionar analisis temporal.
- **Detectar institucionales**: Codigos 6, 7, 10, 12 indican estrategias complejas tipicas de hedge funds.
- **ISOs** (codigo 23): Indican urgencia — el trader esta dispuesto a pagar mas para ejecutar inmediatamente.

---

## 7. Series Temporales

El sistema maneja multiples series temporales con granularidades que van desde milisegundos hasta dias.

### Campos temporales primarios

| Campo | Fuente | Formato | Granularidad | Descripcion |
|-------|--------|---------|-------------|-------------|
| `t` | Trade WS | Unix ms (ej: `1703001600000`) | Milisegundos | Momento exacto de ejecucion del trade. Es el timestamp del SIP |
| `t` | Quote WS | Unix ms | Milisegundos | Momento de la cotizacion |
| `s` (start_timestamp) | Aggregate WS | Unix ms | Milisegundos | Inicio de la ventana de agregacion de 1 segundo |
| `e` (end_timestamp) | Aggregate WS | Unix ms | Milisegundos | Fin de la ventana de agregacion |
| `last_quote.last_updated` | Snapshot REST | Unix nanosegundos | Nanosegundos | Ultima actualizacion de la cotizacion |
| `last_trade.sip_timestamp` | Snapshot REST | Unix nanosegundos | Nanosegundos | Timestamp SIP del ultimo trade |
| `underlying_asset.last_updated` | Snapshot REST | Unix nanosegundos | Nanosegundos | Ultima actualizacion del precio spot |

### Campos temporales derivados (generados por el pipeline)

| Campo | Formato | Granularidad | Descripcion |
|-------|---------|-------------|-------------|
| `_ingested_at` | ISO 8601 datetime (ej: `"2025-12-19T14:30:00Z"`) | Segundos | Momento en que el documento fue insertado en MongoDB. Agregado por el consumer |
| `fetched_at` | ISO 8601 datetime | Segundos | Momento en que el snapshot fue obtenido via REST API |
| `timestamp` | String `"YYYY-MM-DD HH:MM:SS"` | Segundos | Timestamp parseado en cleaned_trades (legible por humanos) |
| `hour` | Integer (0-23) | Horas | Hora del dia extraida del timestamp, usada para agregaciones por hora |
| `date` | String `"YYYY-MM-DD"` | Dias | Fecha extraida, usada para agregaciones diarias |
| `expiration_date` | String `"YYYY-MM-DD"` | Dias | Fecha de vencimiento del contrato de opciones |

### Propiedades de la serie temporal

| Propiedad | Valor |
|-----------|-------|
| **Zona horaria de referencia** | Eastern Time (ET) para horas de mercado; UTC para timestamps internos |
| **Horas de mercado** | Lunes a Viernes, 9:30 - 16:00 ET |
| **Frecuencia WS** | Variable: cientos de eventos/segundo durante horas activas, 0 fuera de horario |
| **Frecuencia REST** | Fija: 1 polling cada 60 segundos por ticker (10 tickers = 10 requests/minuto) |
| **Ventana de agregacion WS** | 1 segundo (campo `s` a `e` en Aggregate events) |
| **Ventana de agregacion Spark** | 1 hora (en aggregated_metrics) |
| **Estacionalidad** | Intradiaria (mayor volumen en apertura y cierre), semanal (lunes a viernes) |

---

## 8. Consideraciones Eticas

### 8.1 Datos publicos y regulados

Los datos de mercado de opciones son **informacion publica** regulada por la SEC. Las bolsas estan obligadas por ley a diseminar sus datos de trades y quotes a traves de los SIPs. No contienen **informacion personal identificable (PII)** — los trades son anonimos y no revelan la identidad de compradores ni vendedores.

### 8.2 Riesgos potenciales

#### Sesgo de seleccion
El watchlist de 10 tickers esta fuertemente sesgado hacia:
- **Large-caps de tecnologia** (AAPL, MSFT, GOOGL, META, NVDA, AMD)
- **ETFs de indice** (SPY, QQQ)
- **Acciones de alta volatilidad** (TSLA)

Esto **no representa la totalidad del mercado de opciones**, que incluye miles de subyacentes de todos los sectores. El sesgo es intencional para el alcance del proyecto pero debe declararse. Cualquier conclusion analitica aplica solo a este subset de tickers de alta liquidez.

#### Delay de 15 minutos
El plan basico de MASSIVE proporciona datos con 15 minutos de retraso. Esto:
- **Mitiga** el riesgo de uso para **front-running** o manipulacion de mercado
- **No afecta** la validez analitica para propositos educativos
- **Si afecta** cualquier intento de usar el sistema para trading en tiempo real (lo cual no es el proposito)

#### Interpretacion de "actividad inusual"
La bandera `unusual_flag` (vol/OI > 1.5) es una **heuristica simplificada**. En la practica:
- No toda actividad inusual es informacion privilegiada — puede ser cobertura institucional, rolling de posiciones, o market making
- El umbral de 1.5 es arbitrario; en produccion se usarian modelos estadisticos con z-scores y promedios moviles
- Etiquetar actividad como "inusual" sin contexto podria generar **seniales falsas**

#### Uso educativo vs. financiero
Este proyecto es **exclusivamente educativo**. Ninguno de los analisis, visualizaciones o banderas debe interpretarse como:
- Consejo de inversion
- Recomendacion de compra o venta
- Senal de trading
- Deteccion de uso de informacion privilegiada

### 8.3 Privacidad y acceso

- **No se recopila PII**: Los datos de mercado son anonimos
- **API keys**: Se almacenan en `.env` (excluido de git via `.gitignore`) y nunca se comparten
- **RBAC**: El sistema implementa principio de minimo privilegio — cada componente solo accede a los datos que necesita
- **No hay scraping**: Todos los datos se obtienen via API autorizada con una API key valida

---

## 9. Arquitectura del Sistema y Teorema CAP

### 9.1 Diagrama de arquitectura

```
                            +-----------------------+
                            |    MASSIVE / Polygon   |
                            |      (Data Source)      |
                            +-----+----------+------+
                                  |          |
                         WebSocket|          |REST API
                        T.*/Q.*/A.|          |/v3/snapshot
                                  |          |
                    +-------------+--+  +----+----------+
                    |  ws_consumer.py |  | rest_poller.py |
                    |  (ingest)       |  | (ingest)       |
                    +-------+--------+  +-------+--------+
                            |                   |
                            v                   v
          +----------------------------------------------+
          |            mongos Router (:27025)             |
          |          (Entry point for all clients)        |
          +----------+------------------+----------------+
                     |                  |
         +-----------+---------+  +----+-----------+
         | Shard 1 — RS rs0    |  | Shard 2 — RS rs1    |
         | +-------+ +-------+ |  | +-------+ +-------+ |
         | |mongo1 | |mongo2 | |  | |mongo4 | |mongo5 | |
         | |:27017 | |:27018 | |  | |:27020 | |:27021 | |
         | |PRIMARY| |SECOND.| |  | |PRIMARY| |SECOND.| |
         | +-------+ +-------+ |  | +-------+ +-------+ |
         |   +-------+         |  |   +-------+         |
         |   |mongo3 |         |  |   |mongo6 |         |
         |   |:27019 |         |  |   |:27022 |         |
         |   |SECOND.|         |  |   |SECOND.|         |
         |   +-------+         |  |   +-------+         |
         +---------------------+  +---------------------+
                     |
         +-----------+---------+
         | Config Server (configrs) |
         |   configsvr1 :27100      |
         +-------------------------+
                     |
          +----------+-----------+
          |                      |
+---------+--------+  +----------+---------+
|  Apache Spark    |  |   FastAPI (:8000)   |
|  +------------+  |  |                     |
|  | Clean      |  |  |  /api/flow/scanner  |
|  | Enrich     |  |  |  /api/flow/unusual  |
|  | Transform  |  |  |  /api/analytics/*   |
|  +------------+  |  |  /api/health        |
+------------------+  +----------+----------+
                                 |
                      +----------+----------+
                      |  React Dashboard    |
                      |  Vite (:5173)       |
                      |  7 componentes      |
                      +---------------------+
```

### 9.2 Componentes del sistema

| Componente | Tecnologia | Funcion |
|-----------|-----------|---------|
| **WebSocket Consumer** | Python + polygon-api-client | Captura trades, quotes y aggregates en tiempo real |
| **REST Poller** | Python + polygon-api-client | Obtiene snapshots con Greeks cada 60s |
| **Config Server** | MongoDB 7 (configrs) | Almacena metadatos de sharding |
| **Shard 1 (rs0)** | MongoDB 7 (3 nodos) | Almacena datos distribuidos |
| **Shard 2 (rs1)** | MongoDB 7 (3 nodos) | Almacena datos distribuidos |
| **Mongos Router** | MongoDB 7 | Enruta queries al shard correcto |
| **Apache Spark** | PySpark 3.5 | Procesamiento batch: limpieza, enriquecimiento, agregacion |
| **FastAPI** | Python + Motor (async) | API REST para servir datos al dashboard |
| **React Dashboard** | Vite + React + Recharts | Visualizacion interactiva estilo terminal quant |

### 9.3 Teorema CAP — Justificacion

El **Teorema CAP** (Brewer, 2000) establece que un sistema de datos distribuido solo puede garantizar dos de tres propiedades: **Consistency**, **Availability**, y **Partition Tolerance**.

#### MongoDB = CP (Consistency + Partition Tolerance)

```
        Consistency (C)
           /\
          /  \
         / CP \     <--- MongoDB
        /______\
       /        \
      /__________\
 Availability (A)  Partition Tolerance (P)
```

**Consistency (C)** — Garantizada:
- Con `writeConcern: { w: "majority" }`, una escritura solo se confirma cuando la mayoria del replica set (2 de 3 nodos) la ha replicado.
- Las lecturas del primary siempre ven la version mas reciente.
- En un cluster con sharding, cada shard mantiene su propia consistencia interna.

**Partition Tolerance (P)** — Garantizada:
- Si hay una particion de red que separa nodos, MongoDB sigue funcionando.
- El protocolo de eleccion Raft elige un nuevo primary si el actual queda aislado.
- Los shards operan independientemente — una particion en Shard 1 no afecta Shard 2.

**Availability (A)** — Sacrificada:
- Durante una eleccion de primary (tipicamente ~10 segundos), las escrituras se rechazan.
- Si un shard pierde su primary y no puede elegir uno nuevo (ej: 2 de 3 nodos caen), las escrituras a ese shard fallan.
- El mongos router devuelve errores en lugar de datos potencialmente inconsistentes.

#### Por que CP es correcto para datos financieros

| Requisito | Justificacion |
|-----------|---------------|
| **Precios consistentes** | Un trade con precio incorrecto puede generar Greeks erroneos, IVs distorsionados y seniales falsas |
| **Timestamps confiables** | La serie temporal debe ser monotona y precisa. Datos fuera de orden causan analisis temporales invalidos |
| **Integridad de OI/Greeks** | El open interest y los Greeks se usan para calcular GEX y vol/OI ratio. Datos inconsistentes producen metricas sin sentido |
| **Tolerancia a ~10s de downtime** | Para un proyecto educativo con datos de 15 min de delay, perder 10 segundos de escrituras durante una eleccion es completamente aceptable |

---

## 10. Infraestructura

### 10.1 Docker Compose

El proyecto despliega **9 contenedores** orquestados con Docker Compose:

| # | Servicio | Imagen | Puerto | Rol | Replica Set |
|---|----------|--------|--------|-----|-------------|
| 1 | `configsvr1` | mongo:7 | 27100 | Config server — almacena metadatos de sharding | configrs |
| 2 | `mongo1` | mongo:7 | 27017 | Shard 1 — primary (priority: 2) | rs0 |
| 3 | `mongo2` | mongo:7 | 27018 | Shard 1 — secondary | rs0 |
| 4 | `mongo3` | mongo:7 | 27019 | Shard 1 — secondary | rs0 |
| 5 | `mongo4` | mongo:7 | 27020 | Shard 2 — primary (priority: 2) | rs1 |
| 6 | `mongo5` | mongo:7 | 27021 | Shard 2 — secondary | rs1 |
| 7 | `mongo6` | mongo:7 | 27022 | Shard 2 — secondary | rs1 |
| 8 | `mongos` | mongo:7 | 27025 | Router — punto de entrada para todos los clientes | — |
| 9 | `mongo-init` | mongo:7 | — | Inicializacion (se ejecuta una sola vez y termina) | — |

#### Volumenes persistentes

```yaml
volumes:
  configsvr1-data:   # Metadatos de sharding
  mongo1-data:       # Datos de Shard 1, nodo 1
  mongo2-data:       # Datos de Shard 1, nodo 2
  mongo3-data:       # Datos de Shard 1, nodo 3
  mongo4-data:       # Datos de Shard 2, nodo 1
  mongo5-data:       # Datos de Shard 2, nodo 2
  mongo6-data:       # Datos de Shard 2, nodo 3
```

#### Red

Todos los contenedores comparten la red `options-net` (driver: bridge), lo que permite resolucion por nombre de contenedor.

### 10.2 Estrategia de Sharding

El sharding distribuye los datos entre Shard 1 (rs0) y Shard 2 (rs1) para escalabilidad horizontal.

#### Shard keys

| Base de Datos | Coleccion | Shard Key | Tipo | Justificacion |
|---------------|-----------|-----------|------|---------------|
| `options_raw` | `trades` | `sym` | Hashed | Distribucion uniforme entre tickers. Hashed evita hot spots aunque los tickers tengan distribucion desigual |
| `options_raw` | `quotes` | `sym` | Hashed | Misma logica que trades |
| `options_raw` | `aggregates` | `sym` | Hashed | Misma logica que trades |
| `options_raw` | `snapshots` | `underlying` | Hashed | Agrupa por subyacente para queries eficientes de option chain |
| `options_analytics` | `enriched_trades` | `underlying` | Hashed | La mayoria de queries analiticas filtran por subyacente |
| `options_analytics` | `aggregated_metrics` | `underlying` | Hashed | Misma logica que enriched_trades |

La eleccion de **hashed sharding** garantiza distribucion uniforme de chunks entre los dos shards, evitando el problema de "jumbo chunks" que podria ocurrir con range sharding sobre tickers de muy diferente volumen (SPY genera ordenes de magnitud mas trades que AMD).

### 10.3 Proceso de inicializacion (8 pasos)

El contenedor `mongo-init` ejecuta `init-replica.sh` que realiza la siguiente secuencia:

1. **Iniciar Config Server RS** — `rs.initiate()` de configrs con configsvr1
2. **Iniciar Shard 1 RS (rs0)** — `rs.initiate()` con mongo1 (priority 2), mongo2, mongo3
3. **Iniciar Shard 2 RS (rs1)** — `rs.initiate()` con mongo4 (priority 2), mongo5, mongo6
4. **Crear admin user** — via mongos, sin auth (primera vez)
5. **Agregar shards al cluster** — `sh.addShard("rs0/...")` y `sh.addShard("rs1/...")`
6. **Habilitar sharding** — `sh.enableSharding()` en ambas DBs, `sh.shardCollection()` en cada coleccion
7. **Crear usuarios RBAC** — Los 3 usuarios de aplicacion (ingest_writer, spark_processor, dashboard_reader)
8. **Crear indices** — Ejecuta `init_indexes.js`

### 10.4 Autenticacion

- **Metodo**: KeyFile + SCRAM-SHA-256
- **KeyFile**: Generado con `openssl rand -base64 756`, permisos 400. Montado como volumen read-only en todos los contenedores
- **Passwords**: Almacenadas en `.env`, pasadas como variables de entorno al contenedor init

### 10.5 RBAC (Role-Based Access Control)

El sistema implementa el **principio de minimo privilegio** con 4 usuarios:

| Usuario | Password (env var) | Rol(es) MongoDB | Bases de datos | Uso |
|---------|--------------------|-----------------|----------------|-----|
| `admin` | `MONGO_ADMIN_PWD` | `root` | `admin` | Administracion del cluster, creacion de usuarios, sharding |
| `ingest_writer` | `MONGO_INGEST_PWD` | `readWrite` | `options_raw` | WebSocket consumer y REST poller. Solo puede escribir datos crudos |
| `spark_processor` | `MONGO_SPARK_PWD` | `read` + `readWrite` | `options_raw` (read) + `options_analytics` (readWrite) | Spark jobs. Lee raw, escribe analytics. No puede modificar datos crudos |
| `dashboard_reader` | `MONGO_DASHBOARD_PWD` | `read` | `options_analytics` | FastAPI/Dashboard. Solo lectura de datos procesados. No puede ver datos crudos |

#### Diagrama de acceso

```
                    options_raw        options_analytics
                    (raw data)         (processed data)
                  ┌──────────────┐   ┌──────────────────┐
admin             │  R + W       │   │  R + W           │
                  ├──────────────┤   ├──────────────────┤
ingest_writer     │  R + W       │   │  SIN ACCESO      │
                  ├──────────────┤   ├──────────────────┤
spark_processor   │  R (solo)    │   │  R + W           │
                  ├──────────────┤   ├──────────────────┤
dashboard_reader  │  SIN ACCESO  │   │  R (solo)        │
                  └──────────────┘   └──────────────────┘
```

### 10.6 Indices

Los indices estan disenados para optimizar las queries mas frecuentes del pipeline.

#### Base de datos `options_raw`

```javascript
// trades — busqueda por simbolo+tiempo, deduplicacion por sequence number
db.trades.createIndex({ sym: 1, t: -1 });        // Trades recientes de un contrato
db.trades.createIndex({ t: -1 });                  // Todos los trades recientes (flow scanner)
db.trades.createIndex({ sym: 1, q: 1 }, { unique: true }); // Deduplicacion

// quotes — busqueda por simbolo+tiempo
db.quotes.createIndex({ sym: 1, t: -1 });
db.quotes.createIndex({ t: -1 });

// aggregates — busqueda por simbolo+inicio de ventana
db.aggregates.createIndex({ sym: 1, s: -1 });

// snapshots — busqueda por contrato o por subyacente
db.snapshots.createIndex({ sym: 1, fetched_at: -1 });
db.snapshots.createIndex({ underlying: 1, fetched_at: -1 });
```

#### Base de datos `options_analytics`

```javascript
// enriched_trades — queries analiticas
db.enriched_trades.createIndex({ underlying: 1, timestamp: -1 }); // Q2: IV skew por underlying
db.enriched_trades.createIndex({ sector: 1, timestamp: -1 });     // Q3: P/C ratio por sector
db.enriched_trades.createIndex({ unusual_flag: 1, timestamp: -1 }); // Q1: unusual activity

// aggregated_metrics — metricas pre-calculadas
db.aggregated_metrics.createIndex({ underlying: 1, date: -1, hour: 1 }); // Q5: gamma por ticker
db.aggregated_metrics.createIndex({ sector: 1, date: -1 });               // Q3: P/C por sector
```

---

## 11. Capa de Ingesta

### 11.1 WebSocket Consumer (`ingest/ws_consumer.py`)

El consumer se conecta al WebSocket de MASSIVE y suscribe a los tres canales de opciones simultaneamente.

#### Configuracion de conexion

```python
ws = WebSocketClient(
    api_key=settings.POLYGON_API_KEY,
    market="options",
    subscriptions=["T.*", "Q.*", "A.*"],
)
```

- `T.*` — Todos los trades de opciones de todas las bolsas
- `Q.*` — Todas las cotizaciones (NBBO)
- `A.*` — Aggregates por segundo

#### Estrategia de buffering

El consumer implementa un **double buffering** con flush por tiempo y por tamanio:

```
WebSocket msgs ──> Buffer (in-memory list)
                        |
                        ├── Flush por tamanio: >= 100 eventos totales
                        └── Flush por tiempo: cada 1 segundo (timer periodico)
                               |
                               v
                    MongoDB insert_many(ordered=False)
```

- **Tres buffers separados**: `trade_buffer`, `quote_buffer`, `agg_buffer`
- **Flush atomico**: Cuando se dispara un flush, se copian los buffers, se limpian, y se insertan las copias
- **`ordered=False`**: Si un documento falla (ej: duplicado por indice unico en `sym+q`), los demas se insertan normalmente
- **`BulkWriteError` handling**: Los duplicados se logean como warning, no como error
- **`_ingested_at`**: Cada documento recibe un timestamp UTC de ingesta antes de ser insertado

#### Conversion de mensajes

Los objetos `WebSocketMessage` de la libreria polygon se convierten a diccionarios con los nombres cortos de campo del protocolo:

```python
def trade_to_dict(m) -> dict:
    return {
        "ev": "T",
        "sym": m.symbol,
        "x": getattr(m, "exchange", None),
        "p": m.price,
        "s": m.size,
        "c": getattr(m, "conditions", None),
        "t": m.timestamp,
        "q": m.sequence_number,
    }
```

#### Graceful shutdown

El consumer registra handlers para `SIGINT` y `SIGTERM`:
1. Flush de todos los buffers pendientes
2. Cierre de la conexion MongoDB
3. Exit limpio

#### Logging

Se loguean eventos/minuto por tipo cada 60 segundos:
```
2025-12-19 14:31:00 [INFO] Events/min — Trades: 2340, Quotes: 8920, Aggs: 1580
```

### 11.2 REST Poller (`ingest/rest_poller.py`)

El poller obtiene snapshots completos del option chain para cada ticker del watchlist.

#### Ciclo de polling

```
Cada 60 segundos (solo en market hours 9:30-16:00 ET, lun-vie):
    Para cada ticker en WATCHLIST:
        client.list_snapshot_options_chain(ticker)
            → Parse cada contrato
            → Agregar fetched_at + underlying
            → Upsert en options_raw.snapshots
```

Los snapshots incluyen:
- **Greeks** (delta, gamma, theta, vega) — calculados por MASSIVE
- **IV** (implied volatility) — derivada del precio de la opcion
- **OI** (open interest) — posiciones abiertas, actualizado diariamente
- **Last quote** (bid/ask) — cotizacion mas reciente
- **Underlying price** — precio spot del subyacente

### 11.3 Formato OCC de Simbolos

Todos los contratos de opciones usan el formato estandarizado de la **Options Clearing Corporation (OCC)**:

```
O:{UNDERLYING}{YYMMDD}{C/P}{STRIKE*1000 con padding a 8 digitos}
```

#### Descomposicion

```
O:AAPL251219C00200000
│ │    │      │ │
│ │    │      │ └── 00200000 → $200.000 (strike × 1000, padded a 8 digitos)
│ │    │      └──── C → Call (C) o Put (P)
│ │    └───────── 251219 → 2025-12-19 (YYMMDD)
│ └────────────── AAPL → Ticker del subyacente (largo variable)
└──────────────── O: → Prefijo de opciones
```

#### Parser implementado

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

### 11.4 Pruebas de ingesta

| Test | Archivo | Que verifica |
|------|---------|-------------|
| Consumer unit test | `ingest/tests/test_consumer.py` | Conversion correcta de objetos WebSocket a diccionarios. Verifica que todos los campos se mapean correctamente |
| Poller unit test | `ingest/tests/test_poller.py` | Parsing correcto de simbolos OCC. Verifica extraccion de underlying, fecha, tipo y strike |

---

## 12. Capa de Procesamiento (Apache Spark)

El procesamiento se divide en 3 jobs de Spark que se ejecutan en secuencia. Cada job lee de MongoDB, procesa con Spark DataFrames, y escribe los resultados de vuelta a MongoDB.

> **Nota tecnica**: Se usa pymongo para lectura/escritura y Spark solo para el procesamiento in-memory, evitando problemas de compatibilidad con el conector mongo-spark.

### 12.1 Job 1: Limpieza (`processing/spark_clean.py`)

```
options_raw.trades ──[pymongo read]──> Spark DataFrame ──[clean]──> options_analytics.cleaned_trades
```

#### Operaciones de limpieza

| Paso | Operacion | Detalle |
|------|-----------|---------|
| 1 | **Lectura** | Lee todos los documentos de `options_raw.trades` via pymongo |
| 2 | **Deduplicacion** | Elimina duplicados por `(sym, q)`. El sequence number `q` es unico por simbolo, por lo que esta tupla identifica univocamente cada trade |
| 3 | **Parseo de timestamps** | Convierte `t` (Unix ms) a datetime legible. Extrae `hour` y `date` como campos separados |
| 4 | **Filtrado temporal** | Solo conserva trades de horas de mercado (lunes a viernes, 9:30-16:00 ET). Descarta pre/post market |
| 5 | **Parseo de simbolos** | Aplica el parser OCC para extraer `underlying`, `expiration`, `contract_type`, `strike` del campo `sym` |
| 6 | **Escritura** | Inserta documentos limpios en `options_analytics.cleaned_trades` |

#### Esquema de salida (cleaned_trades)

```json
{
  "sym": "O:AAPL251219C00200000",
  "underlying": "AAPL",
  "expiration": "2025-12-19",
  "contract_type": "call",
  "strike": 200.0,
  "price": 3.45,
  "size": 5,
  "timestamp": "2025-12-19 14:30:00",
  "hour": 14,
  "date": "2025-12-19"
}
```

### 12.2 Job 2: Enriquecimiento (`processing/spark_enrich.py`)

```
cleaned_trades ──┐
                 ├──[join + calculate]──> options_analytics.enriched_trades
snapshots ───────┘
sectors.csv ─────┘
```

#### Operaciones de enriquecimiento

| Paso | Operacion | Detalle |
|------|-----------|---------|
| 1 | **Lectura** | Lee cleaned_trades y snapshots de MongoDB, sectors.csv de disco |
| 2 | **Join con snapshots** | Para cada trade, busca el snapshot mas reciente del mismo contrato (`sym`). Agrega: `delta`, `gamma`, `theta`, `vega`, `implied_volatility`, `open_interest`, `bid`, `ask`, `underlying_price` |
| 3 | **Join con sectors.csv** | Agrega `sector` e `industry` basandose en el campo `underlying` |
| 4 | **Calculo de dollar_volume** | `price * size * 100` — valor monetario total del trade en USD |
| 5 | **Calculo de moneyness_pct** | `(strike - underlying_price) / underlying_price` — distancia porcentual al dinero |
| 6 | **Clasificacion de moneyness** | Basada en `moneyness_pct`: Deep ITM (<-15%), ITM (-15% a -5%), ATM (-5% a +5%), OTM (+5% a +15%), Deep OTM (>+15%) |
| 7 | **Calculo de bid_ask_spread** | `ask - bid` — mide la liquidez del contrato |
| 8 | **Calculo de vol_oi_ratio** | `volume / max(OI, 1)` — ratio de actividad relativa al interes abierto |
| 9 | **Unusual flag** | `vol_oi_ratio > 1.5` — marca actividad anormalmente alta |
| 10 | **Sentiment heuristic** | Basada en contract_type + moneyness: Call OTM/ATM = Bullish, Put OTM/ATM = Bearish, resto = Neutral |
| 11 | **Escritura** | Inserta documentos enriquecidos en `options_analytics.enriched_trades` |

#### Esquema de salida (enriched_trades)

```json
{
  "sym": "O:AAPL251219C00200000",
  "underlying": "AAPL",
  "expiration": "2025-12-19",
  "contract_type": "call",
  "strike": 200.0,
  "price": 3.45,
  "size": 5,
  "timestamp": "2025-12-19 14:30:00",
  "delta": 0.65,
  "gamma": 0.03,
  "theta": -0.12,
  "vega": 0.45,
  "implied_volatility": 0.32,
  "open_interest": 15234,
  "underlying_price": 198.50,
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "dollar_volume": 1725.0,
  "moneyness_pct": 0.0076,
  "moneyness": "ATM",
  "bid_ask_spread": 0.10,
  "vol_oi_ratio": 0.00033,
  "unusual_flag": false,
  "sentiment": "Bullish"
}
```

### 12.3 Job 3: Transformacion/Agregacion (`processing/spark_transform.py`)

```
enriched_trades ──[groupBy + agg]──> options_analytics.aggregated_metrics
```

#### Operaciones de agregacion

Agrupa por `(underlying, sector, date, hour)` y calcula metricas de negocio:

| Metrica | Formula | Tipo | Interpretacion |
|---------|---------|------|---------------|
| `total_call_volume` | `SUM(size) WHERE contract_type = 'call'` | integer | Volumen total de calls en la ventana |
| `total_put_volume` | `SUM(size) WHERE contract_type = 'put'` | integer | Volumen total de puts en la ventana |
| `put_call_ratio` | `put_vol / call_vol` | float | <1.0 alcista, =1.0 neutral, >1.0 bajista |
| `avg_iv_calls` | `AVG(implied_volatility) WHERE call` | float | IV promedio de calls |
| `avg_iv_puts` | `AVG(implied_volatility) WHERE put` | float | IV promedio de puts |
| `iv_skew` | `avg_iv_puts - avg_iv_calls` | float | Positivo = puts mas caros (fear premium) |
| `net_gamma_exposure` | `SUM(gamma * OI * 100 * spot^2) call - put` | float | Impacto de market makers en el precio |
| `call_gamma_exposure` | `SUM(gamma * OI * 100 * spot^2) WHERE call` | float | GEX de calls |
| `put_gamma_exposure` | `SUM(gamma * OI * 100 * spot^2) WHERE put` | float | GEX de puts |
| `avg_bid_ask_spread` | `AVG(bid_ask_spread)` | float | Liquidez promedio |
| `unusual_activity_count` | `COUNT(*) WHERE unusual_flag = true` | integer | Numero de trades inusuales |

#### Esquema de salida (aggregated_metrics)

```json
{
  "underlying": "AAPL",
  "sector": "Technology",
  "date": "2025-12-19",
  "hour": 14,
  "total_call_volume": 45230,
  "total_put_volume": 38100,
  "put_call_ratio": 0.84,
  "avg_iv_calls": 0.31,
  "avg_iv_puts": 0.35,
  "iv_skew": 0.04,
  "net_gamma_exposure": 2450000000,
  "call_gamma_exposure": 3200000000,
  "put_gamma_exposure": 750000000,
  "avg_bid_ask_spread": 0.15,
  "unusual_activity_count": 23
}
```

### 12.4 Ejecucion de los jobs

Los tres jobs se ejecutan secuencialmente via `run_spark_jobs.sh`:

```bash
bash run_spark_jobs.sh
# Ejecuta en orden:
# 1. python processing/spark_clean.py     → options_raw.trades → cleaned_trades
# 2. python processing/spark_enrich.py    → cleaned + snapshots → enriched_trades
# 3. python processing/spark_transform.py → enriched → aggregated_metrics
```

---

## 13. Analisis — 5 Queries Analiticas

Cada query esta implementada como un **aggregation pipeline de MongoDB** en `api/services/query_service.py` y expuesta via FastAPI.

### Q1: Unusual Options Activity (Actividad Inusual de Opciones)

**Objetivo**: Detectar contratos con volumen anormalmente alto respecto a su interes abierto, lo cual puede indicar posicionamiento institucional agresivo, cobertura ante eventos corporativos, o (en casos extremos) trading con informacion privilegiada.

**Endpoint**: `GET /api/flow/unusual?date=YYYY-MM-DD&limit=50`

**Pipeline MongoDB**:

```javascript
db.enriched_trades.aggregate([
  // Paso 1: Filtrar solo trades marcados como inusuales
  { $match: { unusual_flag: true } },

  // Paso 2: Agrupar por contrato (sym)
  { $group: {
    _id: "$sym",
    underlying: { $first: "$underlying" },
    contract_type: { $first: "$contract_type" },
    strike: { $first: "$strike" },
    expiration: { $first: "$expiration" },
    total_volume: { $sum: "$size" },
    total_dollar_volume: { $sum: "$dollar_volume" },
    avg_iv: { $avg: "$implied_volatility" },
    open_interest: { $first: "$open_interest" },
    sentiment: { $first: "$sentiment" },
    sector: { $first: "$sector" },
    last_price: { $last: "$price" }
  }},

  // Paso 3: Calcular vol/OI ratio final
  { $addFields: {
    vol_oi_ratio: {
      $divide: ["$total_volume", { $max: ["$open_interest", 1] }]
    }
  }},

  // Paso 4: Filtro estricto — solo ratios > 1.5
  { $match: { vol_oi_ratio: { $gt: 1.5 } } },

  // Paso 5: Ordenar por volumen en dolares (los trades mas grandes primero)
  { $sort: { total_dollar_volume: -1 } }
])
```

**Interpretacion**: Un `vol_oi_ratio > 1.5` significa que el volumen de trading de un solo dia supera en 1.5x el total de posiciones abiertas acumuladas historicamente. Esto es significativo porque:
- El OI representa la suma de todas las posiciones abiertas desde la creacion del contrato
- Que el volumen de un solo dia lo supere indica un interes repentino y masivo
- Combinado con `dollar_volume` alto, sugiere participacion institucional (no retail)
- La IV promedio (`avg_iv`) del contrato da contexto sobre la expectativa de movimiento del subyacente

**Resultado esperado**:

| sym | underlying | vol/OI | dollar_volume | IV | sentiment |
|-----|-----------|--------|--------------|-----|-----------|
| O:NVDA251219C00150000 | NVDA | 3.2 | $2.4M | 0.48 | Bullish |
| O:TSLA260116P00200000 | TSLA | 2.8 | $1.8M | 0.62 | Bearish |
| O:AAPL251219C00200000 | AAPL | 1.9 | $890K | 0.31 | Bullish |

---

### Q2: IV Skew (Sesgo de Volatilidad Implicita)

**Objetivo**: Visualizar la "sonrisa de volatilidad" — como la IV varia segun el delta de la opcion. Esto revela la percepcion del mercado sobre riesgos asimetricos (ej: crash fears se manifiestan como IV alta en puts OTM).

**Endpoint**: `GET /api/analytics/iv-skew?underlying=AAPL&date=YYYY-MM-DD`

**Pipeline MongoDB**:

```javascript
db.enriched_trades.aggregate([
  // Paso 1: Filtrar por subyacente
  { $match: { underlying: "AAPL" } },

  // Paso 2: Solo trades con delta e IV validos
  { $match: { delta: { $ne: null }, implied_volatility: { $ne: null } } },

  // Paso 3: Clasificar cada trade en un bucket de delta
  { $addFields: {
    delta_bucket: {
      $switch: {
        branches: [
          { case: { $lte: ["$delta", -0.40] }, then: "P50" },   // Deep OTM puts
          { case: { $lte: ["$delta", -0.20] }, then: "P25" },   // OTM puts
          { case: { $lte: ["$delta", -0.05] }, then: "P10" },   // Far OTM puts
          { case: { $lte: ["$delta",  0.05] }, then: "ATM" },   // At the money
          { case: { $lte: ["$delta",  0.20] }, then: "C10" },   // Far OTM calls
          { case: { $lte: ["$delta",  0.40] }, then: "C25" },   // OTM calls
        ],
        default: "C50"                                            // Deep OTM calls
      }
    }
  }},

  // Paso 4: Promediar IV por bucket
  { $group: {
    _id: "$delta_bucket",
    avg_iv: { $avg: "$implied_volatility" },
    count: { $sum: 1 }
  }},

  // Paso 5: Ordenar buckets
  { $sort: { _id: 1 } }
])
```

**Interpretacion**: La curva resultante muestra el IV skew:

```
IV (%)
  |
45|  *                                          *
  |    *                                     *
40|      *                                *
  |        *                           *
35|          *       *     *        *
  |            *  *           *  *
30|              *               *
  +--+----+----+----+----+----+----+-->
   P50  P25  P10  ATM  C10  C25  C50
                   Delta Bucket
```

- **Forma de "sonrisa"**: Indica que el mercado cotiza primas altas tanto para puts OTM como calls OTM — expectativa de movimientos grandes en ambas direcciones
- **Skew negativo** (puts mas caros): Normal en mercados de equities — refleja "crash insurance". Los inversores pagan mas por proteccion a la baja
- **Skew aplanado**: Puede indicar complacencia o incertidumbre sobre la direccion
- **Skew invertido** (calls mas caros): Raro, indica expectativa fuerte de movimiento al alza (ej: pre-earnings de una tech stock)

---

### Q3: Put/Call Ratio por Sector y Hora

**Objetivo**: Medir el sentimiento del mercado de opciones por sector economico a lo largo del dia de trading. Permite detectar rotacion sectorial y cambios de sentimiento intradiarios.

**Endpoint**: `GET /api/analytics/put-call-ratio?date=YYYY-MM-DD`

**Pipeline MongoDB**:

```javascript
db.aggregated_metrics.aggregate([
  // Paso 1: Filtrar por fecha (opcional)
  { $match: { date: "2025-12-19" } },

  // Paso 2: Agrupar por sector y hora
  { $group: {
    _id: { sector: "$sector", hour: "$hour" },
    total_call_volume: { $sum: "$total_call_volume" },
    total_put_volume: { $sum: "$total_put_volume" }
  }},

  // Paso 3: Calcular ratio (evitando division por cero)
  { $addFields: {
    put_call_ratio: {
      $cond: [
        { $gt: ["$total_call_volume", 0] },
        { $divide: ["$total_put_volume", "$total_call_volume"] },
        0
      ]
    }
  }},

  // Paso 4: Ordenar cronologicamente por sector
  { $sort: { "_id.sector": 1, "_id.hour": 1 } }
])
```

**Interpretacion**:

| Rango P/C | Sentimiento | Significado |
|-----------|------------|-------------|
| < 0.7 | Fuertemente Alcista | Dominio claro de calls. Traders esperan subida |
| 0.7 - 0.9 | Alcista | Mas calls que puts, pero no extremo |
| 0.9 - 1.1 | Neutral | Equilibrio entre calls y puts |
| 1.1 - 1.3 | Bajista | Mas puts que calls. Cobertura o apuestas a la baja |
| > 1.3 | Fuertemente Bajista | Dominio claro de puts. Miedo en el mercado |

**Patrones tipicos**:
- **Technology**: P/C ratio tiende a ser <1.0 (sesgo alcista inherente en tech)
- **Index (SPY/QQQ)**: P/C mas alto debido a uso extensivo de puts para cobertura de portfolios
- **Patron intradiario**: P/C sube en la primera hora (apertura volatil) y tiende a normalizarse hacia el cierre

---

### Q4: Spread vs Moneyness (Liquidez por Proximidad al Dinero)

**Objetivo**: Analizar como el costo de ejecucion (spread bid-ask) varia segun el moneyness de la opcion. Esto es fundamental para evaluar la liquidez y viabilidad de diferentes estrategias.

**Endpoint**: `GET /api/analytics/spread-moneyness?date=YYYY-MM-DD`

**Pipeline MongoDB**:

```javascript
db.enriched_trades.aggregate([
  // Paso 1: Solo trades con datos de moneyness y spread
  { $match: { moneyness_pct: { $ne: null }, bid_ask_spread: { $ne: null } } },

  // Paso 2: Clasificar en buckets de moneyness
  { $addFields: {
    moneyness_bucket: {
      $switch: {
        branches: [
          { case: { $lte: ["$moneyness_pct", -0.15] }, then: "Deep ITM" },
          { case: { $lte: ["$moneyness_pct", -0.05] }, then: "ITM" },
          { case: { $lte: ["$moneyness_pct",  0.05] }, then: "ATM" },
          { case: { $lte: ["$moneyness_pct",  0.15] }, then: "OTM" },
        ],
        default: "Deep OTM"
      }
    }
  }},

  // Paso 3: Calcular metricas por bucket
  { $group: {
    _id: "$moneyness_bucket",
    avg_spread: { $avg: "$bid_ask_spread" },
    total_volume: { $sum: "$size" },
    count: { $sum: 1 }
  }},

  // Paso 4: Ordenar
  { $sort: { _id: 1 } }
])
```

**Interpretacion**:

```
Spread ($)         Volume
  |                  |
  |  ██              |                         ░░░░
  |  ██              |              ░░░░       ░░░░
  |  ██    ██        |    ░░░░     ░░░░       ░░░░
  |  ██    ██        |    ░░░░     ░░░░  ░░░░ ░░░░
  |  ██    ██   ██   |    ░░░░░░░░ ░░░░  ░░░░ ░░░░
  |  ██    ██   ██ ██|██  ░░░░░░░░ ░░░░  ░░░░ ░░░░
  +--+-----+----+--+-+---+--------+-----+-----+---->
   Deep   ITM  ATM OTM Deep    Deep   ITM  ATM OTM Deep
   ITM              OTM       ITM              OTM
       SPREAD                     VOLUME
```

- **ATM**: Spread mas bajo, volumen mas alto. Las opciones at-the-money son las mas liquidas porque son las mas sensibles al precio del subyacente (delta ~0.5)
- **Deep ITM/OTM**: Spreads mas amplios, volumenes mas bajos. Menos market makers compiten por estas opciones
- **Implicacion practica**: Traders que necesitan ejecutar grandes ordenes deben preferir opciones ATM para minimizar costos de ejecucion (slippage)

---

### Q5: Gamma Exposure (GEX)

**Objetivo**: Estimar la exposicion gamma neta de los market makers por subyacente. GEX positivo implica que movimientos del subyacente seran **amortiguados** (market makers compran en bajadas, venden en subidas). GEX negativo implica que seran **amplificados**.

**Endpoint**: `GET /api/analytics/gamma-exposure?date=YYYY-MM-DD&limit=20`

**Pipeline MongoDB**:

```javascript
db.aggregated_metrics.aggregate([
  // Paso 1: Filtrar por fecha
  { $match: { date: "2025-12-19" } },

  // Paso 2: Agrupar por subyacente, sumando gamma exposure
  { $group: {
    _id: "$underlying",
    call_gamma: { $sum: "$call_gamma_exposure" },
    put_gamma: { $sum: "$put_gamma_exposure" },
    net_gamma: { $sum: "$net_gamma_exposure" }
  }},

  // Paso 3: Convertir a millones para legibilidad
  { $addFields: {
    call_gamma_m: { $divide: ["$call_gamma", 1000000] },
    put_gamma_m: { $divide: ["$put_gamma", 1000000] },
    net_gamma_m: { $divide: ["$net_gamma", 1000000] }
  }},

  // Paso 4: Ordenar por GEX neto descendente
  { $sort: { net_gamma: -1 } },
  { $limit: 20 }
])
```

**Formula de GEX**:
```
GEX_call = SUM(gamma_i * OI_i * 100 * spot^2)   para todos los calls
GEX_put  = SUM(gamma_i * OI_i * 100 * spot^2)   para todos los puts
GEX_net  = GEX_call - GEX_put
```

Donde:
- `gamma_i` = gamma del contrato i
- `OI_i` = open interest del contrato i
- `100` = acciones por contrato
- `spot^2` = precio del subyacente al cuadrado (normaliza las unidades a dolares)

**Interpretacion**:

| GEX Neto | Efecto en el mercado |
|----------|---------------------|
| **Positivo alto** (>$500M) | Market makers estan "long gamma". Cada movimiento del subyacente les genera PnL en la direccion del movimiento, asi que rebalancean vendiendo en subidas y comprando en bajadas. **Efecto estabilizador** — reduce volatilidad |
| **Cerca de cero** | Efecto neutro. La volatilidad depende de otros factores |
| **Negativo** (<-$500M) | Market makers estan "short gamma". Deben rebalancear comprando en subidas y vendiendo en bajadas. **Efecto desestabilizador** — amplifica movimientos |

**Resultado esperado**:

```
Ticker      Call GEX ($M)    Put GEX ($M)    Net GEX ($M)
─────────────────────────────────────────────────────────
SPY         ████████████ 850  ██████ -320      +530
AAPL        ██████████ 620    ████ -280        +340
NVDA        ████████ 480      █████ -350       +130
TSLA        ████ 210          ██████ -380      -170
QQQ         ███████ 390       █████ -310       +80
```

---

### Lineage Query (Trazabilidad)

**Endpoint**: `GET /api/analytics/lineage?sym=O:AAPL251219C00200000`

Consulta secuencial que busca un documento con el mismo `sym` en cada coleccion del pipeline:

```javascript
// Etapa 1: Raw
db.getSiblingDB("options_raw").trades.findOne({ sym: sym })

// Etapa 2: Cleaned
db.getSiblingDB("options_analytics").cleaned_trades.findOne({ sym: sym })

// Etapa 3: Enriched
db.getSiblingDB("options_analytics").enriched_trades.findOne({ sym: sym })

// Etapa 4: Aggregated (por underlying)
db.getSiblingDB("options_analytics").aggregated_metrics.findOne({ underlying: underlying })
```

Retorna los 4 documentos para que el usuario pueda ver exactamente como se transformo el dato en cada etapa.

---

## 14. Trazabilidad del Dato

### Ciclo de vida completo: Raw -> Cleaned -> Enriched -> Aggregated

A continuacion se muestra el viaje completo de un trade de opciones a traves de las 4 etapas del pipeline, con el JSON exacto en cada fase.

#### Etapa 1 — Raw Trade (`options_raw.trades`)

Documento tal como llega del WebSocket, con el campo `_ingested_at` agregado por el consumer:

```json
{
  "ev": "T",
  "sym": "O:AAPL251219C00200000",
  "x": 301,
  "p": 3.45,
  "s": 5,
  "c": [0, 12],
  "t": 1703001600000,
  "q": 12345,
  "_ingested_at": "2025-12-19T14:30:00.123Z"
}
```

**Campos**: 8 del WebSocket + 1 de ingesta = **9 campos**
**Tamano aproximado**: ~180 bytes

---

#### Etapa 2 — Cleaned Trade (`options_analytics.cleaned_trades`)

Despues de deduplicacion, parseo de timestamps, y descomposicion del simbolo OCC:

```json
{
  "sym": "O:AAPL251219C00200000",
  "underlying": "AAPL",
  "expiration": "2025-12-19",
  "contract_type": "call",
  "strike": 200.0,
  "price": 3.45,
  "size": 5,
  "timestamp": "2025-12-19 14:30:00",
  "hour": 14,
  "date": "2025-12-19"
}
```

**Transformaciones aplicadas**:
- `sym` parseado -> `underlying`, `expiration`, `contract_type`, `strike`
- `t` (Unix ms) -> `timestamp` (datetime legible) + `hour` + `date`
- `p` -> `price`, `s` -> `size` (renombrado a nombres descriptivos)
- Campos `ev`, `x`, `c`, `q`, `_ingested_at` eliminados (no necesarios para analytics)
- Deduplicado por `(sym, q)` — si existia un duplicado, fue eliminado

**Campos**: **10 campos** (1 original + 9 derivados/renombrados)

---

#### Etapa 3 — Enriched Trade (`options_analytics.enriched_trades`)

Enriquecido con Greeks del snapshot, sector/industria, y metricas derivadas:

```json
{
  "sym": "O:AAPL251219C00200000",
  "underlying": "AAPL",
  "expiration": "2025-12-19",
  "contract_type": "call",
  "strike": 200.0,
  "price": 3.45,
  "size": 5,
  "timestamp": "2025-12-19 14:30:00",
  "hour": 14,
  "date": "2025-12-19",
  "delta": 0.65,
  "gamma": 0.03,
  "theta": -0.12,
  "vega": 0.45,
  "implied_volatility": 0.32,
  "open_interest": 15234,
  "underlying_price": 198.50,
  "bid": 3.40,
  "ask": 3.50,
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "dollar_volume": 1725.0,
  "moneyness_pct": 0.0076,
  "moneyness": "ATM",
  "bid_ask_spread": 0.10,
  "vol_oi_ratio": 0.00033,
  "unusual_flag": false,
  "sentiment": "Bullish"
}
```

**Datos agregados**:
- **Del snapshot**: delta, gamma, theta, vega, IV, OI, underlying_price, bid, ask
- **De sectors.csv**: sector, industry
- **Calculados**: dollar_volume, moneyness_pct, moneyness, bid_ask_spread, vol_oi_ratio, unusual_flag, sentiment

**Campos**: **27 campos** (10 de la etapa anterior + 17 nuevos)

---

#### Etapa 4 — Aggregated Metric (`options_analytics.aggregated_metrics`)

Multiples trades de AAPL en la hora 14 agregados en una sola metrica:

```json
{
  "underlying": "AAPL",
  "sector": "Technology",
  "date": "2025-12-19",
  "hour": 14,
  "total_call_volume": 45230,
  "total_put_volume": 38100,
  "put_call_ratio": 0.84,
  "avg_iv_calls": 0.31,
  "avg_iv_puts": 0.35,
  "iv_skew": 0.04,
  "net_gamma_exposure": 2450000000,
  "call_gamma_exposure": 3200000000,
  "put_gamma_exposure": 750000000,
  "avg_bid_ask_spread": 0.15,
  "unusual_activity_count": 23
}
```

**Nivel de agregacion**: Todos los trades de AAPL durante la hora 14 del 2025-12-19.
**Campos**: **15 campos** — metricas de inteligencia de negocio.

---

#### Resumen de la transformacion

```
Etapa       Campos  Fuentes de datos             Operaciones clave
───────────────────────────────────────────────────────────────────
Raw           9     WebSocket                    Ingesta directa
Cleaned      10     Raw                          Dedup, parseo, filtrado
Enriched     27     Cleaned + Snapshot + CSV     Joins, calculos derivados
Aggregated   15     Enriched (muchos → uno)      GroupBy, SUM, AVG, formulas
```

**De 9 campos crudos a 15 metricas analiticas**, enriquecidos con 3 fuentes externas (snapshots, sectors.csv, calculos derivados).

---

## 15. Dashboard

El dashboard es una aplicacion React con estetica de **terminal de quant finance** — oscuro, monospaciado, denso en informacion.

### 15.1 Stack tecnologico

| Tecnologia | Version | Proposito |
|-----------|---------|-----------|
| **Vite** | 5+ | Build tool y dev server (HMR) |
| **React** | 18+ | Framework de UI |
| **TailwindCSS** | v4 | Estilos utility-first |
| **Recharts** | 2+ | Graficas SVG (Line, Area, Bar, Composed) |
| **Lucide React** | latest | Iconos SVG minimalistas |
| **Axios** | 1+ | HTTP client para comunicacion con FastAPI |
| **JetBrains Mono** | Google Fonts | Fuente monoespaciada para toda la interfaz |

### 15.2 Paleta de colores

```
Background:     #0a0e17  (casi negro azulado)
Surface:        #111827  (gris oscuro para cards)
Border:         #1e293b  (gris para bordes sutiles)
Text:           #e2e8f0  (gris claro)
Text Muted:     #64748b  (gris medio para labels)
Green:          #22c55e  (calls, bullish, healthy)
Red:            #ef4444  (puts, bearish, errors)
Cyan:           #06b6d4  (acentos, links)
Amber:          #f59e0b  (unusual activity, warnings)
Purple:         #a78bfa  (acentos secundarios)
```

### 15.3 Layout

```
+------------------------------------------+
| HEADER: Logo | LIVE pulse | Stats         |
+------+-------------------------------+---+
|      |                               |   |
| SIDE |       CONTENT AREA            |   |
| BAR  |                               |   |
|      |   (componente seleccionado)   |   |
| Flow |                               |   |
| IV   |                               |   |
| P/C  |                               |   |
| GEX  |                               |   |
| Sprd |                               |   |
| Lin. |                               |   |
| Stat |                               |   |
+------+-------------------------------+---+
```

### 15.4 Los 7 componentes

#### 1. FlowScanner (`FlowScanner.jsx`)

**Datos**: `GET /api/flow/scanner` + `GET /api/flow/unusual`

Tabla en tiempo real de trades de opciones con:
- **Filtros**: All | Unusual | Bullish | Bearish
- **Columnas**: Time, Symbol, Type (Call/Put badge), Strike, Expiry, Price, Size, $Volume, IV, Sentiment, Unusual
- **Styling**: Filas con unusual_flag resaltadas en amber. Badges de Call en verde, Put en rojo
- **Auto-refresh**: Cada 5 segundos via polling

#### 2. IVSkewChart (`IVSkewChart.jsx`)

**Datos**: `GET /api/analytics/iv-skew?underlying=AAPL`

Grafica de linea (Recharts `LineChart`) mostrando la curva de IV skew:
- **Eje X**: Delta buckets (P50 → ATM → C50)
- **Eje Y**: IV promedio (%)
- **Toggle**: Selector de underlying para comparar skews entre tickers
- **Referencia**: Linea horizontal en la IV media del mercado

#### 3. PutCallRatio (`PutCallRatio.jsx`)

**Datos**: `GET /api/analytics/put-call-ratio`

Grafica de area (Recharts `AreaChart`) mostrando P/C ratio por hora:
- **Eje X**: Hora del dia (9-16)
- **Eje Y**: Put/Call ratio
- **Series**: Una area por sector, con opacidad para superposicion
- **Referencia**: `ReferenceLine` horizontal en y=1.0 (neutral)

#### 4. GammaExposure (`GammaExposure.jsx`)

**Datos**: `GET /api/analytics/gamma-exposure`

Grafica de barras horizontal (Recharts `BarChart`):
- **Eje Y**: Ticker del subyacente
- **Eje X**: Gamma exposure en millones de USD
- **Colores**: Verde para call GEX, rojo para put GEX
- **Ordenamiento**: Por GEX neto descendente

#### 5. SpreadAnalysis (`SpreadAnalysis.jsx`)

**Datos**: `GET /api/analytics/spread-moneyness`

Grafica compuesta (Recharts `ComposedChart`):
- **Barras**: Spread bid-ask promedio por bucket de moneyness
- **Linea**: Volumen total por bucket (eje Y secundario)
- **Eje X**: Buckets de moneyness (Deep ITM → Deep OTM)
- **Insight visual**: La relacion inversa entre spread y volumen

#### 6. DataLineage (`DataLineage.jsx`)

**Datos**: `GET /api/analytics/lineage?sym=O:AAPL251219C00200000`

Visualizacion de trazabilidad con:
- **4 cards** conectadas por flechas: Raw → Clean → Enrich → Aggregated
- **JSON viewer**: Cada card muestra el documento completo de esa etapa
- **Dropdown**: Selector de simbolo para explorar diferentes contratos
- **Diff visual**: Campos nuevos en cada etapa resaltados

#### 7. SystemStatus (`SystemStatus.jsx`)

**Datos**: `GET /api/health`

Panel de estado del sistema:
- **StatCards**: Conteos de documentos por coleccion (trades, quotes, aggs, snapshots, enriched, aggregated)
- **Indicadores**: Verde (healthy) o rojo (down) para MongoDB, API, WebSocket
- **Metricas**: Ultimo ingested_at, ultimo Spark run, uptime

### 15.5 Screenshots

<!-- PLACEHOLDER: Agregar screenshots del dashboard en funcionamiento -->

---

## 16. Instrucciones de Ejecucion

### 16.1 Prerrequisitos

| Software | Version minima | Verificar con |
|----------|---------------|---------------|
| Docker Desktop | 4.0+ | `docker --version` |
| Docker Compose | 2.0+ (incluido en Docker Desktop) | `docker compose version` |
| Python | 3.11+ | `python --version` |
| pip | 23+ | `pip --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

Ademas se necesita una **API key de Polygon.io/MASSIVE**. Se puede obtener en https://polygon.io (plan basico gratuito disponible).

### 16.2 Paso 1: Clonar y configurar

```bash
# Clonar el repositorio
git clone <repo-url>
cd options-flow-platform

# Crear archivo de variables de entorno
cp .env.example .env
```

Editar `.env` con los valores reales:

```env
POLYGON_API_KEY=tu_api_key_aqui

# Passwords de MongoDB (cambiar en produccion)
MONGO_ADMIN_PWD=admin_password_seguro
MONGO_INGEST_PWD=ingest_password_seguro
MONGO_SPARK_PWD=spark_password_seguro
MONGO_DASHBOARD_PWD=dashboard_password_seguro
```

### 16.3 Paso 2: Setup automatico

```bash
bash setup.sh
```

Este script ejecuta:
1. Verifica que Docker, Python y Node esten instalados
2. Instala dependencias Python: `pip install -r requirements.txt`
3. Genera el keyfile de MongoDB: `openssl rand -base64 756 > docker/mongo/keyfile`
4. Levanta el cluster MongoDB (9 contenedores)
5. Espera a que la inicializacion complete (replica sets, sharding, RBAC, indices)
6. Instala dependencias del dashboard: `cd dashboard && npm install`

**Tiempo estimado**: 2-3 minutos (dependiendo de descarga de imagenes Docker).

### 16.4 Paso 3: Verificar infraestructura

```bash
# Verificar que todos los contenedores estan corriendo
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Verificar replica sets y sharding
docker exec mongos mongosh --port 27025 \
  -u admin -p $MONGO_ADMIN_PWD --authenticationDatabase admin \
  --eval "sh.status()"

# Verificar que los indices existen
docker exec mongos mongosh --port 27025 \
  -u admin -p $MONGO_ADMIN_PWD --authenticationDatabase admin \
  --eval "db.getSiblingDB('options_raw').trades.getIndexes()"
```

### 16.5 Paso 4: Iniciar ingesta de datos

Abrir **dos terminales** separadas:

```bash
# Terminal 1: WebSocket consumer (trades, quotes, aggregates en tiempo real)
python -m ingest.ws_consumer

# Terminal 2: REST poller (snapshots con Greeks cada 60s)
python -m ingest.rest_poller
```

**Nota**: El WebSocket consumer mostrara logs de eventos/minuto. Dejar corriendo al menos **2-3 minutos** para acumular datos suficientes para los Spark jobs.

Si se ejecuta fuera de horas de mercado (9:30-16:00 ET), el REST poller no realizara requests (diseniado asi intencionalmente). El WebSocket puede seguir recibiendo datos delayed.

### 16.6 Paso 5: Ejecutar procesamiento Spark

```bash
bash run_spark_jobs.sh
```

Ejecuta secuencialmente:
1. `python processing/spark_clean.py` — Limpieza y deduplicacion
2. `python processing/spark_enrich.py` — Enriquecimiento con Greeks y sector
3. `python processing/spark_transform.py` — Agregacion de metricas

Cada job reporta el numero de documentos procesados y escritos.

### 16.7 Paso 6: Iniciar API

```bash
uvicorn api.main:app --reload --port 8000
```

Verificar que funciona:

```bash
# Health check
curl http://localhost:8000/api/health

# Flow scanner
curl http://localhost:8000/api/flow/scanner?limit=5

# Unusual activity
curl http://localhost:8000/api/flow/unusual

# IV Skew
curl "http://localhost:8000/api/analytics/iv-skew?underlying=AAPL"

# Put/Call ratio
curl http://localhost:8000/api/analytics/put-call-ratio

# Spread vs Moneyness
curl http://localhost:8000/api/analytics/spread-moneyness

# Gamma Exposure
curl http://localhost:8000/api/analytics/gamma-exposure

# Lineage
curl "http://localhost:8000/api/analytics/lineage?sym=O:AAPL251219C00200000"
```

### 16.8 Paso 7: Iniciar dashboard

```bash
cd dashboard
npm run dev
```

Abrir `http://localhost:5173` en el navegador.

### 16.9 Paso 8: Ejecutar pruebas

```bash
# Load test — inserta documentos sinteticos a diferentes velocidades
python scripts/load_test.py

# Resilience test — prueba tolerancia a fallos del replica set
python scripts/resilience_test.py
```

### 16.10 Resumen de puertos

| Servicio | Puerto | URL |
|----------|--------|-----|
| Config Server | 27100 | `mongodb://localhost:27100` |
| Shard 1 Node 1 (Primary) | 27017 | `mongodb://localhost:27017` |
| Shard 1 Node 2 | 27018 | `mongodb://localhost:27018` |
| Shard 1 Node 3 | 27019 | `mongodb://localhost:27019` |
| Shard 2 Node 1 (Primary) | 27020 | `mongodb://localhost:27020` |
| Shard 2 Node 2 | 27021 | `mongodb://localhost:27021` |
| Shard 2 Node 3 | 27022 | `mongodb://localhost:27022` |
| Mongos Router | 27025 | `mongodb://localhost:27025` |
| FastAPI | 8000 | `http://localhost:8000` |
| React Dashboard | 5173 | `http://localhost:5173` |

### 16.11 Troubleshooting

| Problema | Causa probable | Solucion |
|----------|---------------|----------|
| `MongoServerSelectionError` | Contenedores no estan corriendo | `docker ps` para verificar. `docker compose up -d` para reiniciar |
| `mongos: connection refused` | Mongos no esta listo | Esperar 30s despues de `docker compose up`. Verificar: `docker logs mongos` |
| WebSocket no conecta | API key invalida o expirada | Verificar `POLYGON_API_KEY` en `.env`. Probar en https://polygon.io/dashboard |
| `KeyFile too short` | Keyfile no se genero correctamente | `openssl rand -base64 756 > docker/mongo/keyfile && chmod 400 docker/mongo/keyfile` |
| Spark job: "No documents found" | Ingesta no corrio suficiente tiempo | Ejecutar consumer por al menos 2-3 minutos. Verificar con `mongosh` que hay datos |
| Dashboard muestra "No data" | API no esta corriendo o Spark no se ejecuto | Verificar API: `curl localhost:8000/api/health`. Ejecutar Spark jobs |
| `CORS error` en browser | FastAPI no tiene CORS configurado para el puerto correcto | Verificar que CORS incluye `http://localhost:5173` |
| `docker compose` falla | Docker Desktop no esta corriendo | Iniciar Docker Desktop primero |
| Permisos denegados en keyfile | Permisos incorrectos | `chmod 400 docker/mongo/keyfile` |
| REST poller no hace requests | Fuera de horas de mercado | Normal. Solo opera lun-vie 9:30-16:00 ET |

### 16.12 Limpiar todo

```bash
# Detener y eliminar contenedores + volumenes
docker compose down -v

# Eliminar datos locales generados
rm -f docker/mongo/keyfile
```

---

## Estructura del Proyecto

```
options-flow-platform/
├── CLAUDE.md                  # Especificacion del proyecto
├── README.md                  # Esta documentacion
├── .env.example               # Template de variables de entorno
├── .gitignore
├── docker-compose.yml         # Cluster MongoDB (9 contenedores)
├── setup.sh                   # Script de setup automatico
├── run_spark_jobs.sh          # Ejecuta los 3 Spark jobs en secuencia
├── requirements.txt           # Dependencias Python
├── data/
│   └── sectors.csv            # Dataset estatico: ticker → sector + industry
├── docker/
│   └── mongo/
│       ├── init-replica.sh    # Inicializacion del cluster (8 pasos)
│       └── keyfile            # (generado) Auth entre nodos MongoDB
├── scripts/
│   ├── init_mongo_users.js    # Referencia de usuarios RBAC
│   ├── init_indexes.js        # Creacion de indices
│   ├── seed_reference_data.py # Seed de datos de referencia
│   ├── load_test.py           # Prueba de carga (10/50/100/500 docs/seg)
│   └── resilience_test.py     # Prueba de tolerancia a fallos
├── ingest/
│   ├── __init__.py
│   ├── config.py              # Configuracion Pydantic-settings
│   ├── ws_consumer.py         # WebSocket consumer (T.*/Q.*/A.*)
│   ├── rest_poller.py         # REST poller de snapshots
│   └── tests/
│       ├── test_consumer.py   # Tests de conversion de mensajes
│       └── test_poller.py     # Tests de parsing OCC
├── processing/
│   ├── __init__.py
│   ├── spark_clean.py         # Job 1: Limpieza y deduplicacion
│   ├── spark_enrich.py        # Job 2: Enriquecimiento con Greeks/sector
│   └── spark_transform.py     # Job 3: Agregacion de metricas
├── api/
│   ├── __init__.py
│   ├── main.py                # FastAPI app (CORS, routers)
│   ├── routers/
│   │   ├── flow.py            # GET /api/flow/scanner, /api/flow/unusual
│   │   ├── analytics.py       # GET /api/analytics/iv-skew, etc.
│   │   └── health.py          # GET /api/health
│   ├── services/
│   │   ├── mongo_client.py    # Motor async client (dashboard_reader)
│   │   └── query_service.py   # 5 queries analiticas + lineage
│   └── models/
│       └── schemas.py         # Pydantic response schemas
└── dashboard/
    ├── package.json           # Dependencias Node
    ├── vite.config.js         # Config de Vite + Tailwind
    ├── index.html             # HTML entry point
    └── src/
        ├── App.jsx            # Layout principal + sidebar
        ├── main.jsx           # React entry point
        ├── index.css          # Tailwind + estilos globales
        ├── components/
        │   ├── FlowScanner.jsx     # Tabla de trades en tiempo real
        │   ├── IVSkewChart.jsx     # Curva de IV skew
        │   ├── PutCallRatio.jsx    # P/C ratio por sector/hora
        │   ├── GammaExposure.jsx   # GEX por subyacente
        │   ├── SpreadAnalysis.jsx  # Spread vs moneyness
        │   ├── DataLineage.jsx     # Trazabilidad 4 etapas
        │   └── SystemStatus.jsx    # Health del sistema
        ├── hooks/
        │   └── useAPI.js           # Custom hook para data fetching
        └── lib/
            └── api.js              # Axios client configurado
```
