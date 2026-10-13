"""
Descarga audio de YouTube en formato M4A con metadatos completos y portada.
Requiere: pip install pytubefix mutagen
"""

import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover
from pytubefix import YouTube
from pytubefix.cli import on_progress


def sanitize_filename(name: str) -> str:
    """Elimina caracteres inválidos para nombres de archivo."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def download_audio(url: str, output_dir: str = "./downloads") -> Path:
    """
    Descarga audio de YouTube y guarda como M4A con metadatos y portada.

    Args:
        url: URL de YouTube (video, music, shorts, etc.)
        output_dir: Directorio de salida

    Returns:
        Path al archivo M4A generado
    """
    os.makedirs(output_dir, exist_ok=True)

    yt = YouTube(url, on_progress_callback=on_progress)

    print(f"[INFO] Titulo: {yt.title}")
    print(f"[INFO] Autor: {yt.author}")
    print(f"[INFO] Duracion: {yt.length}s")
    print("[INFO] Descargando audio...")

    # Obtener stream de audio only (m4a / mp4a)
    audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()

    if not audio_stream:
        raise RuntimeError("No se encontro stream de audio M4A")

    print(f"[INFO] Bitrate: {audio_stream.abr}")

    # Nombre de archivo seguro (truncar si es muy largo)
    safe_title = sanitize_filename(yt.title)
    if len(safe_title) > 200:
        safe_title = safe_title[:200]

    # Usar ID de video para nombre de archivo temporal (evita problemas de filesystem)
    temp_name = f"temp_{yt.video_id}.m4a"
    final_name = f"{safe_title}.m4a"

    temp_path = Path(output_dir) / temp_name
    final_path = Path(output_dir) / final_name

    # Descargar directamente con nombre temporal simple
    audio_stream.download(output_path=output_dir, filename=temp_name)

    # Verificar que el archivo temporal existe
    if not temp_path.exists():
        raise RuntimeError(f"Archivo temporal no encontrado: {temp_path}")

    # Inyectar metadatos y portada
    inject_metadata(temp_path, final_path, yt)

    # Eliminar temporal
    temp_path.unlink(missing_ok=True)

    print(f"[OK] Guardado en: {final_path}")
    return final_path


def inject_metadata(temp_path: Path, final_path: Path, yt: YouTube) -> None:
    """Inyecta metadatos completos + portada al archivo M4A."""
    print(f"[DEBUG] Procesando: {temp_path} -> {final_path}")

    # Copiar temporal a final primero
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
    audio['\xa9too'] = 'pytubefix + mutagen'             # Herramienta
    audio['trkn'] = [(1, 1)]                             # Track number
    audio['disk'] = [(1, 1)]                             # Disk number

    # Duración en milisegundos
    if yt.length:
        audio['\xa9dur'] = str(yt.length * 1000)

    # Descripción como letra / long description
    if yt.description:
        audio['\xa9des'] = yt.description[:5000]

    # Palabras clave / tags
    if yt.keywords:
        audio['\xa9key'] = ', '.join(yt.keywords[:20])

    # Portada (thumbnail)
    if yt.thumbnail_url:
        try:
            with urllib.request.urlopen(yt.thumbnail_url) as resp:
                img_data = resp.read()
            audio['covr'] = [MP4Cover(img_data, imageformat=MP4Cover.FORMAT_JPEG)]
            print("[INFO] Portada inyectada")
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"[WARN] No se pudo descargar portada: {e}")

    # Guardar metadatos
    audio.save(final_path)
    print("[INFO] Metadatos inyectados")


def main():
    if len(sys.argv) < 2:
        print("Uso: python download_audio.py <URL_DE_YOUTUBE> [directorio_salida]")
        print("Ejemplo: python download_audio.py 'https://youtube.com/watch?v=...' ./music")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./downloads"

    try:
        download_audio(url, output_dir)
    except (RuntimeError, ValueError, OSError, KeyboardInterrupt) as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
