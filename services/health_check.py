"""
Health check сервер для Render
"""
import asyncio
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

async def health_check_handler(request):
    """Обработчик health check"""
    return web.Response(
        text="OK",
        headers={'Content-Type': 'text/plain'}
    )

async def start_health_check_server(host: str = '0.0.0.0', port: int = 10000):
    """Запустить сервер health check"""
    try:
        app = web.Application()
        app.router.add_get('/health', health_check_handler)
        app.router.add_get('/', health_check_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        
        await site.start()
        
        logger.info(f"🌐 Health check сервер запущен на {host}:{port}")
        logger.info(f"✅ Доступен по: http://{host}:{port}/health")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        logger.info("🔄 Health check сервер останавливается...")
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка health check сервера: {e}")
        raise