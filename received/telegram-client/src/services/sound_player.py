import threading
import os
import sys
import logging

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_ASSETS_DIR = os.path.join(_BASE_DIR, 'assets')
_NOTIFICATION_PATH = os.path.join(_ASSETS_DIR, 'notification.wav')
_RINGTONE_PATH = os.path.join(_ASSETS_DIR, 'ringtone.wav')

_ring_stop = threading.Event()
_ring_thread = None
_has_winsound = False

try:
    import winsound
    _has_winsound = True
except ImportError:
    pass


def _play_wav(path):
    if _has_winsound:
        try:
            winsound.PlaySound(path, winsound.SND_ASYNC)
            return
        except Exception:
            pass
    try:
        import sounddevice as sd
        import soundfile as sf
        data, sr = sf.read(path)
        sd.play(data, sr)
        sd.wait()
    except Exception as e:
        logger.debug(f"Sound play failed: {e}")


def play_notification():
    if not os.path.exists(_NOTIFICATION_PATH):
        return
    _play_wav(_NOTIFICATION_PATH)


def play_ringtone():
    global _ring_thread
    stop_ringtone()
    _ring_stop.clear()
    _ring_thread = threading.Thread(target=_ringtone_loop, daemon=True)
    _ring_thread.start()


def _ringtone_loop():
    if _has_winsound:
        try:
            winsound.PlaySound(_RINGTONE_PATH, winsound.SND_ASYNC | winsound.SND_LOOP)
            _ring_stop.wait()
            winsound.PlaySound(None, winsound.SND_PURGE)
            return
        except Exception:
            pass
    try:
        import soundfile as sf
        import sounddevice as sd
        if not os.path.exists(_RINGTONE_PATH):
            return
        data, sr = sf.read(_RINGTONE_PATH)
        dur = len(data) / sr
        while not _ring_stop.is_set():
            sd.play(data, sr)
            steps = int(dur * 8)
            for _ in range(max(steps, 1)):
                if _ring_stop.wait(1.0 / max(steps, 1)):
                    sd.stop()
                    return
    except Exception as e:
        logger.debug(f"Ringtone loop failed: {e}")


def stop_ringtone():
    global _ring_thread
    _ring_stop.set()
    if _has_winsound:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
    if _ring_thread and _ring_thread.is_alive():
        _ring_thread.join(timeout=1)
    _ring_thread = None


def stop_all():
    stop_ringtone()
