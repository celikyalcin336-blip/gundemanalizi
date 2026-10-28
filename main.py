"""
Gündem Analizi - Panel Manuel Tetikleme Köprüsü
Otonom 15 dakikalık bot artık doğrudan news_bot.py içinde çalışır.
"""
import news_bot


def run_bot(max_items: int = 1, force: bool = False) -> int:
    """Paneldeki 'Şimdi Haber Çek' butonu için tek seferlik haber hazırlayıp yayınlar."""
    count = 0
    for _ in range(max(1, max_items)):
        prep = news_bot._prepare_next()
        if prep and news_bot._publish(prep):
            count += 1
    return count


if __name__ == "__main__":
    run_bot(max_items=1, force=True)
