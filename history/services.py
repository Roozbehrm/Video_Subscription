from .models import WatchHistory


def record_watch(user, video, progress_seconds=None) -> WatchHistory:
    entry, _ = WatchHistory.objects.get_or_create(user=user, video=video)
    if progress_seconds is not None:
        entry.progress_seconds = progress_seconds
    entry.save()
    return entry