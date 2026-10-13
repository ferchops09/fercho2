import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from app.config import settings
from mutagen.mp4 import MP4
from pytubefix import YouTube
from pytubefix.cli import on_progress
from yt_dlp import YoutubeDL


class FallbackState:
    """Gestiona el estado del método de descarga alternativo."""

    def __init__(self, cooldown_seconds: int = 3600):
        self._lock: threading.Lock = threading.Lock()
        self._using_fallback: bool = False
        self._fallback_start_time: float | None = None
        self._cooldown_seconds: int = cooldown_seconds

    @property
    def using_fallback(self) -> bool:
        with self._lock:
            if self._using_fallback and self._fallback_start_time:
                elapsed = time.time() - self._fallback_start_time
                if elapsed >= self._cooldown_seconds:
                    self._using_fallback = False
                    self._fallback_start_time = None
                    return False
            return self._using_fallback

    def activate_fallback(self) -> None:
        with self._lock:
            if not self._using_fallback:
                self._using_fallback = True
                self._fallback_start_time = time.time()

    def reset(self) -> None:
        with self._lock:
            self._using_fallback = False
            self._fallback_start_time = None


fallback_state = FallbackState(cooldown_seconds=3600)


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


def format_view_count(count: float | str | None) -> str:
    """Formatea vistas con sufijos k, M, B."""
    try:
        count_int = int(count) if count else 0
    except (ValueError, TypeError):
        count_int = 0

    if count_int >= 1_000_000_000:
        return f"{count_int / 1_000_000_000:.1f}B".replace(".0", "")
    elif count_int >= 1_000_000:
        return f"{count_int / 1_000_000:.1f}M".replace(".0", "")
    elif count_int >= 1_000:
        return f"{count_int / 1_000:.1f}k".replace(".0", "")
    return str(count_int)


def format_duration_str(seconds: float | str | None) -> str:
    """Formatea duración en segundos a MM:SS o HH:MM:SS."""
    try:
        seconds_int = int(seconds) if seconds else 0
    except (ValueError, TypeError):
        seconds_int = 0

    hours = seconds_int // 3600
    minutes = (seconds_int % 3600) // 60
    secs = seconds_int % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _inject_metadata_common(
    final_path: Path,
    title: str,
    author: str,
    upload_date: str | None,
    description: str | None,
    tags: list[str] | None,
    duration_ms: int,
    youtube_url: str,
    file_size: int,
) -> dict[str, Any]:
    """Inyecta metadatos comunes al archivo M4A y retorna dict de respuesta."""
    audio = MP4(final_path)

    audio['\xa9nam'] = title
    audio['\xa9ART'] = author
    audio['\xa9alb'] = author
    audio['\xa9day'] = upload_date[:4] if upload_date else ''
    audio['\xa9gen'] = 'Music'
    audio['\xa9cmt'] = f"Descargado de YouTube: {youtube_url}"
    audio['\xa9wrt'] = author
    audio['\xa9too'] = 'dlapi (yt-dlp + mutagen)'
    audio['trkn'] = [(1, 1)]
    audio['disk'] = [(1, 1)]

    if duration_ms:
        audio['\xa9dur'] = str(duration_ms)

    if description:
        audio['\xa9des'] = description[:5000]

    if tags:
        audio['\xa9key'] = ', '.join(tags[:20])

    audio.save(final_path)

    return {
        "title": title,
        "artist": author,
        "album": author,
        "year": int(upload_date[:4]) if upload_date else None,
        "genre": "Music",
        "duration_ms": duration_ms,
        "duration_formatted": format_duration(duration_ms),
        "thumbnail_url": f"https://i.ytimg.com/vi/{Path(final_path).stem.split('_')[-1]}/hq720.jpg",
        "youtube_url": youtube_url,
        "filesize_bytes": file_size,
        "filesize_formatted": format_filesize(file_size),
        "views_formatted": "N/A",
        "video_id": Path(final_path).stem.split('_')[-1],
    }


def download_audio_ytdlp(url: str) -> tuple[Path, dict[str, Any]]:
    """
    Descarga audio de YouTube usando yt-dlp como método alternativo.

    Returns:
        Tuple[Path, Dict]: (ruta_archivo, metadata_dict)

    Raises:
        ValueError: URL inválida
        RuntimeError: Error en descarga o metadatos
    """
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise ValueError("URL de YouTube inválida")

    os.makedirs(settings.download_dir, exist_ok=True)

    temp_name_tpl = "ytdlp_temp_%(id)s.%(ext)s"
    temp_path_tpl = str(Path(settings.download_dir) / temp_name_tpl)

    ydl_opts: dict[str, object] = {
        'format': 'bestaudio/best',
        'outtmpl': temp_path_tpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '0',
        }],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }

    with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("yt-dlp no pudo extraer información del video")

        video_id = info.get('id', '')

        temp_files = list(Path(settings.download_dir).glob(f"ytdlp_temp_{video_id}.*"))
        if not temp_files:
            raise RuntimeError("Archivo temporal no encontrado tras descarga con yt-dlp")
        temp_path = temp_files[0]

        file_size = temp_path.stat().st_size
        if file_size > settings.max_file_size_mb * 1024 * 1024:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Archivo excede límite de {settings.max_file_size_mb}MB")

        title = str(info.get('title', 'Sin título'))
        author = str(info.get('uploader', 'Desconocido'))
        safe_title = sanitize_filename(title)
        if len(safe_title) > 200:
            safe_title = safe_title[:200]
        final_name = f"{safe_title}.m4a"
        final_path = Path(settings.download_dir) / final_name

        shutil.copy2(temp_path, final_path)
        temp_path.unlink(missing_ok=True)

        upload_date = info.get('upload_date')
        description = info.get('description')
        tags = info.get('tags')
        duration = info.get('duration')
        duration_ms = int(duration) * 1000 if duration else 0
        youtube_url = info.get('webpage_url') or url

        metadata = _inject_metadata_common(
            final_path=final_path,
            title=title,
            author=author,
            upload_date=upload_date,
            description=description,
            tags=tags,
            duration_ms=duration_ms,
            youtube_url=youtube_url,
            file_size=file_size,
        )
        metadata["video_id"] = video_id
        metadata["thumbnail_url"] = info.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/hq720.jpg")
        if info.get('view_count'):
            metadata["views_formatted"] = format_view_count(info.get('view_count'))

        return final_path, metadata


def download_audio_pytubefix(url: str) -> tuple[Path, dict[str, Any]]:
    """
    Descarga audio de YouTube usando pytubefix (método principal).

    Returns:
        Tuple[Path, Dict]: (ruta_archivo, metadata_dict)

    Raises:
        ValueError: URL inválida o no se encuentra stream
        RuntimeError: Error en descarga o metadatos
    """
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise ValueError("URL de YouTube inválida")

    os.makedirs(settings.download_dir, exist_ok=True)

    yt = YouTube(
        url,
        on_progress_callback=on_progress,
        use_oauth=False,
        allow_oauth_cache=False
    )

    audio_stream = yt.streams.filter(
        only_audio=True,
        file_extension='mp4'
    ).order_by('abr').desc().first()

    if not audio_stream:
        raise RuntimeError("No se encontró stream de audio M4A")

    temp_name = f"temp_{yt.video_id}.m4a"
    safe_title = sanitize_filename(yt.title)
    if len(safe_title) > 200:
        safe_title = safe_title[:200]
    final_name = f"{safe_title}.m4a"

    temp_path = Path(settings.download_dir) / temp_name
    final_path = Path(settings.download_dir) / final_name

    audio_stream.download(
        output_path=settings.download_dir,
        filename=temp_name,
        timeout=settings.yt_timeout_seconds
    )

    if not temp_path.exists():
        raise RuntimeError("Archivo temporal no encontrado tras descarga")

    file_size = temp_path.stat().st_size
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Archivo excede límite de {settings.max_file_size_mb}MB")

    shutil.copy2(temp_path, final_path)

    metadata = _inject_metadata_common(
        final_path=final_path,
        title=yt.title,
        author=yt.author,
        upload_date=yt.publish_date.strftime('%Y%m%d') if yt.publish_date else None,
        description=yt.description,
        tags=yt.keywords,
        duration_ms=yt.length * 1000 if yt.length else 0,
        youtube_url=yt.watch_url,
        file_size=file_size,
    )
    metadata["video_id"] = yt.video_id
    metadata["thumbnail_url"] = yt.thumbnail_url
    if hasattr(yt, 'views') and yt.views:
        metadata["views_formatted"] = format_view_count(yt.views)

    temp_path.unlink(missing_ok=True)

    return final_path, metadata


def download_audio(url: str) -> tuple[Path, dict[str, Any]]:
    """
    Descarga audio de YouTube con fallback automático.

    Flujo:
    1. Intenta pytubefix (método principal)
    2. Si falla, activa fallback a yt-dlp por 1 hora
    3. Durante el fallback, usa solo yt-dlp
    4. Tras 1 hora, vuelve a intentar pytubefix
    5. Si pytubefix vuelve a fallar, reactiva fallback

    Returns:
        Tuple[Path, Dict]: (ruta_archivo, metadata_dict)

    Raises:
        ValueError: URL inválida
        RuntimeError: Error en descarga (ambos métodos fallaron)
    """
    if fallback_state.using_fallback:
        try:
            return download_audio_ytdlp(url)
        except (RuntimeError, ValueError, OSError) as e:
            raise RuntimeError(f"Fallback (yt-dlp) falló: {e}")

    try:
        result = download_audio_pytubefix(url)
        if fallback_state.using_fallback:
            fallback_state.reset()
        return result
    except (RuntimeError, ValueError, OSError) as e:
        fallback_state.activate_fallback()
        try:
            return download_audio_ytdlp(url)
        except (RuntimeError, ValueError, OSError) as e2:
            raise RuntimeError(f"pytubefix falló: {e}. Fallback yt-dlp también falló: {e2}")


def search_youtube(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    Busca videos en YouTube usando yt-dlp.

    Args:
        query: Término de búsqueda
        max_results: Máximo número de resultados

    Returns:
        Lista de dicts con info de videos
    """
    ydl_opts: dict[str, object] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'default_search': 'ytsearch',
        'max_downloads': max_results,
    }

    results: list[dict[str, object]] = []
    with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
        try:
            search_results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if search_results and 'entries' in search_results:
                entries = search_results['entries']
                if entries:
                    entries_list = list(entries)  # pyright: ignore[reportArgumentType]
                    for entry in entries_list[:max_results]:
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
        except (RuntimeError, ValueError, KeyError) as e:
            raise RuntimeError(f"Error en búsqueda: {e}")

    return results
