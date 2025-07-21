# Database Connection Troubleshooting Guide

This guide helps you diagnose and fix PostgreSQL connection limit issues in your Forge deployment.

## 🚨 Quick Fix for "too many clients already" Error

If you're seeing the PostgreSQL error "sorry, too many clients already", follow these immediate steps:

### 1. **Immediate Actions**

```bash
# Stop your application
docker-compose down
# or
pkill -f gunicorn

# Restart with reduced workers
export WORKERS=3
docker-compose up -d
# or
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 3 --bind 0.0.0.0:8000
```

### 2. **Check Current Status**

```bash
# Run the diagnostic tool
python tools/diagnostics/check_db_connections.py

# Check health endpoint
curl http://localhost:8000/health/database
```

## 📊 Understanding the Problem

### Connection Pool Math

With the default settings:
- **10 Gunicorn workers** × **2 engines** (sync + async) × **15 connections** (5 pool + 10 overflow) = **300 potential connections**
- **PostgreSQL default**: ~100 max_connections
- **Result**: Connection limit exceeded!

### New Optimized Settings

- **5 Gunicorn workers** × **2 engines** × **5 connections** (3 pool + 2 overflow) = **50 connections**
- **Buffer for other connections**: 50 connections remaining
- **Result**: Safe operation within PostgreSQL limits

## 🔧 Configuration Options

### Environment Variables

Add these to your `.env` file or Docker environment:

```env
# Database connection settings
DB_POOL_SIZE=3              # Connections per pool
DB_MAX_OVERFLOW=2           # Additional connections when pool is full
DB_POOL_TIMEOUT=30          # Seconds to wait for connection
DB_POOL_RECYCLE=1800        # Seconds before recycling connections
DB_POOL_PRE_PING=true       # Enable connection health checks

# Application settings
WORKERS=5                   # Number of Gunicorn workers
```

### For High-Load Production

If you need more workers for performance, consider:

```env
# Option 1: Reduce pool sizes further
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=1
WORKERS=8

# Option 2: Increase PostgreSQL max_connections (see PostgreSQL tuning section)
```

## 🐘 PostgreSQL Tuning

### Increase max_connections

1. **Edit postgresql.conf:**
   ```bash
   # Find your config file
   sudo -u postgres psql -c "SHOW config_file;"
   
   # Edit the file
   sudo nano /path/to/postgresql.conf
   ```

2. **Update settings:**
   ```conf
   max_connections = 200          # Increase from default 100
   shared_buffers = 256MB         # Increase with max_connections
   effective_cache_size = 1GB     # Adjust based on available RAM
   ```

3. **Restart PostgreSQL:**
   ```bash
   sudo systemctl restart postgresql
   # or
   sudo service postgresql restart
   ```

### Docker PostgreSQL

For Docker setups, modify `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=forge
      - POSTGRES_PASSWORD=forge
      - POSTGRES_DB=forge
    command: >
      postgres 
      -c max_connections=200
      -c shared_buffers=256MB
      -c effective_cache_size=1GB
    # ... rest of config
```

## 🔍 Monitoring Tools

### 1. **Diagnostic Script**

```bash
# Run comprehensive check
python tools/diagnostics/check_db_connections.py

# Run regularly in production
watch -n 30 "python tools/diagnostics/check_db_connections.py"
```

### 2. **Health Check Endpoints**

```bash
# Basic health check
curl http://localhost:8000/health

# Database-specific health check
curl http://localhost:8000/health/database

# Detailed health check
curl http://localhost:8000/health/detailed
```

### 3. **Direct PostgreSQL Monitoring**

```sql
-- Check current connections
SELECT count(*) as total_connections FROM pg_stat_activity;

-- Check max connections
SHOW max_connections;

-- View connections by database
SELECT datname, count(*) as connections
FROM pg_stat_activity 
WHERE datname IS NOT NULL
GROUP BY datname
ORDER BY connections DESC;

-- Check connection states
SELECT state, count(*) 
FROM pg_stat_activity 
GROUP BY state;
```

## 🚀 Production Deployment Strategies

### 1. **Conservative Approach** (Recommended)

```env
# Prioritize stability
WORKERS=3
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=1
# Max connections: 3 × 2 × 3 = 18 connections
```

### 2. **Balanced Approach**

```env
# Balance performance and stability  
WORKERS=5
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=2
# Max connections: 5 × 2 × 5 = 50 connections
```

### 3. **High-Performance Approach**

```env
# Requires PostgreSQL tuning
WORKERS=8
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=2
# Max connections: 8 × 2 × 5 = 80 connections
# Requires max_connections >= 150 in PostgreSQL
```

## 📈 Performance vs. Connections Trade-off

| Workers | Pool Size | Max Overflow | Total Connections | Performance | Stability |
|---------|-----------|--------------|-------------------|-------------|-----------|
| 3       | 2         | 1            | 18                | ⭐⭐         | ⭐⭐⭐⭐⭐     |
| 5       | 3         | 2            | 50                | ⭐⭐⭐       | ⭐⭐⭐⭐      |
| 8       | 3         | 2            | 80                | ⭐⭐⭐⭐      | ⭐⭐⭐       |
| 10      | 5         | 10           | 300               | ⭐⭐⭐⭐⭐     | ⭐           |

## 🔧 Advanced Solutions

### 1. **Connection Pooling with pgbouncer**

For very high-load scenarios, use pgbouncer:

```bash
# Install pgbouncer
sudo apt-get install pgbouncer

# Configure pgbouncer.ini
[databases]
forge = host=localhost port=5432 dbname=forge

[pgbouncer]
pool_mode = transaction
listen_port = 6432
max_client_conn = 100
default_pool_size = 25
```

Update DATABASE_URL:
```env
DATABASE_URL=postgresql://forge:forge@localhost:6432/forge
```

### 2. **Read Replicas**

For read-heavy workloads, implement read replicas and route read queries separately.

## 🚨 Troubleshooting Common Issues

### Issue 1: "connection timeout"

**Symptoms:** Long delays before connection errors
**Solution:** Increase `DB_POOL_TIMEOUT` or reduce load

```env
DB_POOL_TIMEOUT=60  # Increase from 30
```

### Issue 2: "too many connections" during startup

**Symptoms:** Errors immediately after deployment
**Solution:** Reduce workers and pool sizes

```env
WORKERS=3
DB_POOL_SIZE=2
```

### Issue 3: Intermittent connection errors

**Symptoms:** Occasional connection failures
**Solution:** Enable connection health checks

```env
DB_POOL_PRE_PING=true
DB_POOL_RECYCLE=1800
```

## 📋 Monitoring Checklist

- [ ] Set up regular health checks
- [ ] Monitor connection pool usage
- [ ] Track PostgreSQL connection counts
- [ ] Set up alerts for >80% usage
- [ ] Review logs for connection errors
- [ ] Test with realistic load

## 🆘 Emergency Procedures

If you're experiencing severe connection issues in production:

1. **Immediate relief:**
   ```bash
   # Kill connections
   docker-compose down
   
   # Restart with minimal settings
   export WORKERS=2
   export DB_POOL_SIZE=1
   export DB_MAX_OVERFLOW=1
   docker-compose up -d
   ```

2. **Check database:**
   ```sql
   -- Kill idle connections
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < NOW() - INTERVAL '5 minutes';
   ```

3. **Monitor recovery:**
   ```bash
   watch -n 5 "curl -s http://localhost:8000/health/database | jq '.connection_pools'"
   ```

Remember: **Stability first, performance second**. It's better to have a working system with lower throughput than a broken system. 