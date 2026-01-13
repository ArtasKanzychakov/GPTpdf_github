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

async def status_handler(request):
    """Обработчик статуса с информацией"""
    info = """
    Бизнес-Навигатор v7.0
    
    Статус: ✅ Работает
    Режим: Polling
    Python: 3.9.16
    
    Эндпоинты:
    • /health - проверка здоровья
    • /status - эта страница
    
    Для работы с ботом:
    • Найти бота в Telegram
    • Отправить команду /start
    """
    
    return web.Response(
        text=info,
        headers={'Content-Type': 'text/plain'}
    )

async def start_health_check_server(host: str = '0.0.0.0', port: int = 10000):
    """Запустить сервер health check"""
    try:
        app = web.Application()
        app.router.add_get('/health', health_check_handler)
        app.router.add_get('/status', status_handler)
        app.router.add_get('/', health_check_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        
        await site.start()
        
        logger.info(f"🌐 Health check сервер запущен на {host}:{port}")
        logger.info(f"✅ Доступен по: http://{host}:{port}/health")
        logger.info(f"📊 Статус по: http://{host}:{port}/status")
        
        # Бесконечный цикл (будет работать пока не отменят)
        try:
            await asyncio.Future()  # Бесконечное ожидание
        except asyncio.CancelledError:
            logger.info("🔄 Health check сервер останавливается...")
            await runner.cleanup()
            
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"⚠️ Порт {port} уже занят. Возможно, сервер уже запущен.")
        else:
            logger.error(f"❌ Ошибка запуска сервера: {e}")
            raise
    except Exception as e:
        logger.error(f"❌ Ошибка health check сервера: {e}")
        raise