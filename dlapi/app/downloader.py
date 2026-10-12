import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from mutagen.mp4 import MP4
from pytubefix import YouTube
from pytubefix.cli import on_progress
from yt_dlp import YoutubeDL


def sanitize_filename(name: str) -> str:
    """Elimina caracteres inválidos para nombres de archivo."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def format_duration(ms: int) -> str:
    """Convierte milisegundos a formato MM:SS o HH:MM:SS."""
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_filesize(bytes_size: float) -> str:
    """Convierte bytes a formato legible."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def download_audio(url: str) -> tuple[Path, dict[str, Any]]:
    """
    Descarga audio de YouTube y guarda como M4A con metadatos completos.

    Returns:
        Tuple[Path, Dict]: (ruta_archivo, metadata_dict)

    Raises:
        ValueError: URL inválida o no se encuentra stream
        RuntimeError: Error en descarga o metadatos
    """
    # Validar URL básica
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise ValueError("URL de YouTube inválida")

    os.makedirs(settings.download_dir, exist_ok=True)

    # Configurar YouTube con timeout
    yt = YouTube(
        url,
        on_progress_callback=on_progress,
        use_oauth=False,
        allow_oauth_cache=False
    )

    # Obtener stream de audio only (m4a / mp4a) - mejor bitrate
    audio_stream = yt.streams.filter(
        only_audio=True,
        file_extension='mp4'
    ).order_by('abr').desc().first()

    if not audio_stream:
        raise RuntimeError("No se encontró stream de audio M4A")

    # Nombre de archivo temporal simple (evita problemas de filesystem)
    temp_name = f"temp_{yt.video_id}.m4a"
    safe_title = sanitize_filename(yt.title)
    if len(safe_title) > 200:
        safe_title = safe_title[:200]
    final_name = f"{safe_title}.m4a"

    temp_path = Path(settings.download_dir) / temp_name
    final_path = Path(settings.download_dir) / final_name

    # Descargar
    audio_stream.download(
        output_path=settings.download_dir,
        filename=temp_name,
        timeout=settings.yt_timeout_seconds
    )

    if not temp_path.exists():
        raise RuntimeError("Archivo temporal no encontrado tras descarga")

    # Verificar tamaño
    file_size = temp_path.stat().st_size
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Archivo excede límite de {settings.max_file_size_mb}MB")

    # Inyectar metadatos
    metadata = inject_metadata(temp_path, final_path, yt, file_size)

    # Eliminar temporal
    temp_path.unlink(missing_ok=True)

    return final_path, metadata


def inject_metadata(
    temp_path: Path,
    final_path: Path,
    yt: YouTube,
    file_size: int
) -> dict[str, Any]:
    """Inyecta metadatos completos + portada al archivo M4A."""

    # Copiar temporal a final
    shutil.copy2(temp_path, final_path)

    # Cargar y modificar metadatos
    audio = MP4(final_path)

    # Metadatos básicos
    audio['\xa9nam'] = yt.title                          # Título
    audio['\xa9ART'] = yt.author                         # Artista
    audio['\xa9alb'] = yt.author                         # Álbum (canal)
    audio['\xa9day'] = str(yt.publish_date.year) if yt.publish_date else ''  # Año
    audio['\xa9gen'] = 'Music'                           # Género
    audio['\xa9cmt'] = f"Descargado de YouTube: {yt.watch_url}"  # Comentario
    audio['\xa9wrt'] = yt.author                         # Compositor
    audio['\xa9too'] = 'dlapi (pytubefix + mutagen)'     # Herramienta
    audio['trkn'] = [(1, 1)]                             # Track number
    audio['disk'] = [(1, 1)]                             # Disk number

    # Duración en milisegundos
    duration_ms = yt.length * 1000 if yt.length else 0
    if duration_ms:
        audio['\xa9dur'] = str(duration_ms)

    # Descripción
    if yt.description:
        audio['\xa9des'] = yt.description[:5000]

    # Keywords/tags
    if yt.keywords:
        audio['\xa9key'] = ', '.join(yt.keywords[:20])

    # Guardar metadatos
    audio.save(final_path)

    # Construir dict de respuesta
    metadata = {
        "title": yt.title,
        "artist": yt.author,
        "album": yt.author,
        "year": yt.publish_date.year if yt.publish_date else None,
        "genre": "Music",
        "duration_ms": duration_ms,
        "duration_formatted": format_duration(duration_ms),
        "thumbnail_url": yt.thumbnail_url,
        "youtube_url": yt.watch_url,
        "filesize_bytes": file_size,
        "filesize_formatted": format_filesize(file_size),
        # "has_cover": cover_bytes is not None,
        "video_id": yt.video_id
    }

    return metadata


def format_view_count(count: Any) -> str:
    """Formatea vistas con sufijos k, M, B."""
    try:
        count = int(count) if count else 0
    except (ValueError, TypeError):
        count = 0

    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B".replace(".0", "")
    elif count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M".replace(".0", "")
    elif count >= 1_000:
        return f"{count / 1_000:.1f}k".replace(".0", "")
    return str(count)


def format_duration_str(seconds: Any) -> str:
    """Formatea duración en segundos a MM:SS o HH:MM:SS."""
    try:
        seconds = int(seconds) if seconds else 0
    except (ValueError, TypeError):
        seconds = 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def search_youtube(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    Busca videos en YouTube usando yt-dlp.

    Args:
        query: Término de búsqueda
        max_results: Máximo número de resultados

    Returns:
        Lista de dicts con info de videos
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'default_search': 'ytsearch',
        'max_downloads': max_results,
    }

    results = []
    with YoutubeDL(ydl_opts) as ydl:
        try:
            search_results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if search_results and 'entries' in search_results:
                for entry in search_results['entries'][:max_results]:
                    if entry:
                        results.append({
                            "title": entry.get('title', 'Sin título'),
                            "author": entry.get('uploader', 'Desconocido'),
                            "view_count": entry.get('view_count', 0),
                            "views_formatted": format_view_count(entry.get('view_count', 0)),
                            "duration": entry.get('duration', 0),
                            "duration_formatted": format_duration_str(entry.get('duration', 0)),
                            "video_id": entry.get('id', ''),
                            "url": entry.get('url', f"https://youtube.com/watch?v={entry.get('id', '')}"),
                            "thumbnail": entry.get('thumbnail', f"https://i.ytimg.com/vi/{entry.get('id', '')}/hq720.jpg"),
                        })
        except Exception as e:
            raise RuntimeError(f"Error en búsqueda: {e}")

    return results
