#!/usr/bin/env python3
"""
Database connection monitoring and diagnostic tool.
"""

import asyncio
import os
import sys
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine


def check_postgres_max_connections():
    """Check PostgreSQL max_connections setting"""
    try:
        load_dotenv()
        db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/forge")
        
        print("🔍 Checking PostgreSQL configuration...")
        
        # Use psycopg2 for direct connection
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Get max_connections
        cursor.execute("SHOW max_connections;")
        max_connections = cursor.fetchone()[0]
        
        # Get current connections
        cursor.execute("""
            SELECT count(*) as active_connections 
            FROM pg_stat_activity 
            WHERE state = 'active'
        """)
        active_connections = cursor.fetchone()[0]
        
        # Get total connections
        cursor.execute("""
            SELECT count(*) as total_connections 
            FROM pg_stat_activity
        """)
        total_connections = cursor.fetchone()[0]
        
        # Get connections by database
        cursor.execute("""
            SELECT datname, count(*) as connections
            FROM pg_stat_activity 
            WHERE datname IS NOT NULL
            GROUP BY datname
            ORDER BY connections DESC
        """)
        db_connections = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        print(f"📊 PostgreSQL Connection Status:")
        print(f"   Max connections: {max_connections}")
        print(f"   Total connections: {total_connections}")
        print(f"   Active connections: {active_connections}")
        print(f"   Usage: {(total_connections/int(max_connections)*100):.1f}%")
        
        if int(total_connections) > int(max_connections) * 0.8:
            print("⚠️  WARNING: Connection usage is above 80%!")
        
        print(f"\n📊 Connections by database:")
        for db_name, conn_count in db_connections:
            print(f"   {db_name}: {conn_count}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking PostgreSQL connections: {e}")
        return False


def check_sqlalchemy_pools():
    """Check SQLAlchemy connection pool status"""
    try:
        print("\n🔍 Checking SQLAlchemy connection pools...")
        
        from app.core.database import get_connection_info
        
        info = get_connection_info()
        
        print(f"📊 Connection Pool Configuration:")
        print(f"   Pool size: {info['pool_size']}")
        print(f"   Max overflow: {info['max_overflow']}")
        print(f"   Pool timeout: {info['pool_timeout']}s")
        print(f"   Pool recycle: {info['pool_recycle']}s")
        
        print(f"\n📊 Sync Engine Pool Status:")
        sync_pool = info['sync_engine']
        print(f"   Checked out: {sync_pool['checked_out']}")
        print(f"   Checked in: {sync_pool['checked_in']}")
        print(f"   Pool size: {sync_pool['size']}")
        
        print(f"\n📊 Async Engine Pool Status:")
        async_pool = info['async_engine']  
        print(f"   Checked out: {async_pool['checked_out']}")
        print(f"   Checked in: {async_pool['checked_in']}")
        print(f"   Pool size: {async_pool['size']}")
        
        # Calculate total potential connections with workers
        workers = int(os.getenv("WORKERS", "10"))
        total_potential = workers * (info['pool_size'] + info['max_overflow']) * 2
        print(f"\n📊 Production Calculation (with {workers} workers):")
        print(f"   Max potential connections: {total_potential}")
        print(f"   Per worker: {(info['pool_size'] + info['max_overflow']) * 2}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking SQLAlchemy pools: {e}")
        return False


async def test_async_connection():
    """Test async database connection"""
    try:
        print("\n🔍 Testing async database connection...")
        
        from app.core.database import get_db_session
        
        async with get_db_session() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Async connection successful")
            print(f"   PostgreSQL version: {version}")
            return True
            
    except Exception as e:
        print(f"❌ Async connection failed: {e}")
        return False


def test_sync_connection():
    """Test sync database connection"""
    try:
        print("\n🔍 Testing sync database connection...")
        
        from app.core.database import get_db
        
        with next(get_db()) as session:
            result = session.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"✅ Sync connection successful")
            print(f"   Current database: {db_name}")
            return True
            
    except Exception as e:
        print(f"❌ Sync connection failed: {e}")
        return False


def show_recommendations():
    """Show recommendations for fixing connection issues"""
    print("\n💡 Recommendations for fixing connection issues:")
    print("\n1. **Immediate fixes:**")
    print("   - Restart your application to apply new connection pool settings")
    print("   - Monitor connection usage with this diagnostic tool")
    
    print("\n2. **PostgreSQL tuning:**")
    print("   - Increase max_connections in postgresql.conf")
    print("   - Set max_connections = 200 (or higher based on your needs)")
    print("   - Also increase shared_buffers if you increase max_connections")
    
    print("\n3. **Application tuning:**")
    print("   - Reduce number of Gunicorn workers if needed")
    print("   - Use environment variables to tune connection pools:")
    print("     export DB_POOL_SIZE=2")
    print("     export DB_MAX_OVERFLOW=1") 
    print("     export WORKERS=5")
    
    print("\n4. **Connection pooling (for high-load production):**")
    print("   - Consider using pgbouncer for connection pooling")
    print("   - Set connection_limit in pgbouncer.ini")
    
    print("\n5. **Monitoring:**")
    print("   - Run this script regularly to monitor connection usage")
    print("   - Set up alerts when connection usage exceeds 80%")


async def main():
    """Main diagnostic function"""
    print("🚀 Database Connection Diagnostic Tool")
    print("=" * 50)
    print(f"⏰ Timestamp: {datetime.now()}")
    
    # Load environment
    load_dotenv()
    
    # Run all checks
    postgres_ok = check_postgres_max_connections()
    pools_ok = check_sqlalchemy_pools()
    async_ok = await test_async_connection()
    sync_ok = test_sync_connection()
    
    print("\n" + "=" * 50)
    print("📋 SUMMARY:")
    print(f"   PostgreSQL config: {'✅' if postgres_ok else '❌'}")
    print(f"   SQLAlchemy pools: {'✅' if pools_ok else '❌'}")
    print(f"   Async connection: {'✅' if async_ok else '❌'}")
    print(f"   Sync connection: {'✅' if sync_ok else '❌'}")
    
    if not all([postgres_ok, pools_ok, async_ok, sync_ok]):
        print("\n❌ Issues detected!")
        show_recommendations()
        return False
    else:
        print("\n✅ All checks passed!")
        return True


if __name__ == "__main__":
    # Ensure we can import from the app
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Diagnostic cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1) 