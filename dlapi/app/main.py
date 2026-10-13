import logging

from aiohttp import web
from app.config import settings
from app.downloader import download_audio, search_youtube

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dlapi")


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "dlapi"})


async def download_endpoint(request: web.Request) -> web.Response:
    """
    Descarga audio de YouTube y retorna la ruta local del archivo M4A.

    Query params:
    - url: URL de YouTube (watch, youtu.be, music, shorts)
    """
    url = request.query.get("url", "")

    # Validar URL básica
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return web.json_response(
            {"status": "error", "code": "INVALID_URL", "message": "URL de YouTube inválida"},
            status=400
        )

    logger.info(f"Descargando: {url}")

    try:
        file_path, metadata = download_audio(url)

        logger.info(f"Completado: {file_path.name} ({metadata['filesize_formatted']})")

        return web.json_response({
            "status": "ok",
            "file_path": str(file_path.resolve()),
            "file_id": metadata["video_id"],
            "metadata": metadata
        })

    except ValueError as e:
        logger.warning(f"URL inválida: {url} - {e}")
        return web.json_response(
            {"status": "error", "code": "INVALID_URL", "message": str(e)},
            status=400
        )
    except RuntimeError as e:
        logger.error(f"Error en descarga: {url} - {e}")
        return web.json_response(
            {"status": "error", "code": "DOWNLOAD_FAILED", "message": str(e)},
            status=500
        )
    except Exception:
        logger.exception(f"Error inesperado: {url}")
        return web.json_response(
            {"status": "error", "code": "INTERNAL_ERROR", "message": "Error interno del servidor"},
            status=500
        )


async def search_endpoint(request: web.Request) -> web.Response:
    """
    Busca videos en YouTube.

    Query params:
    - q: Término de búsqueda
    - limit: Máximo resultados (default 10, max 20)
    """
    query = request.query.get("q", "").strip()
    limit = min(int(request.query.get("limit", "10")), 20)

    if not query:
        return web.json_response(
            {"status": "error", "code": "INVALID_QUERY", "message": "Parámetro 'q' requerido"},
            status=400
        )

    logger.info(f"Buscando: {query} (limit={limit})")

    try:
        # Ejecutar búsqueda en executor para no bloquear el event loop
        import asyncio
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, search_youtube, query, limit)

        logger.info(f"Encontrados {len(results)} resultados para: {query}")

        return web.json_response({
            "status": "ok",
            "query": query,
            "count": len(results),
            "results": results
        })

    except RuntimeError as e:
        logger.error(f"Error en búsqueda: {query} - {e}")
        return web.json_response(
            {"status": "error", "code": "SEARCH_FAILED", "message": str(e)},
            status=500
        )
    except Exception:
        logger.exception(f"Error inesperado en búsqueda: {query}")
        return web.json_response(
            {"status": "error", "code": "INTERNAL_ERROR", "message": "Error interno del servidor"},
            status=500
        )


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/download", download_endpoint)
    app.router.add_get("/search", search_endpoint)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host=settings.host, port=settings.port, print=logger.info)
