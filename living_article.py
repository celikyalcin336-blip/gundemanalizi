# -*- coding: utf-8 -*-
"""
Gündem Analizi - Yaşayan Haber Motoru (living_article.py)

Son 48 saatte yayımlanan bir haberin YENİ ve SOMUT bir gelişmesi geldiğinde (yeni rakam, yeni aşama,
yeni resmi açıklama), ayrı ve ince bir sayfa açmak yerine mevcut haberi '🔴 Güncellendi' bölümüyle büyütür.

Kurallar:
- Yalnızca son 48 saatteki, aynı kategorideki haberler aday alınır.
- Yüksek kelime kökü örtüşmesi + özel isim (büyük harfli kelime) ortaklığı aranır (yanlış birleştirme engeli).
- Yeni kaynak metinde mevcut haberde OLMAYAN en az bir yeni somut bilgi (yeni sayı veya belirgin yeni bilgi)
  yoksa güncelleme yapılmaz (aynı haberi başka sitenin tekrar yazması güncelleme değildir).
- Bir haber en fazla 4 kez güncellenir.
"""
import html as _html
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import config


def _proper_nouns(title: str) -> set:
    """Başlıktaki özel isim adayları: ilk kelime hariç büyük harfle başlayan kelimeler + kısaltmalar."""
    parts = (title or "").strip().split()
    out = set()
    for i, tok in enumerate(parts):
        clean = re.split(r"['’.,:;!?()\"“”]", tok)[0]
        if len(clean) < 3:
            continue
        if clean.isupper() and len(clean) >= 2:
            out.add(clean.replace("İ", "i").replace("I", "ı").lower()[:6])
        elif i > 0 and clean[0].isupper():
            out.add(clean.replace("İ", "i").replace("I", "ı").lower()[:6])
    return out


def find_living_match(title: str, summary: str, category: str, recent_articles: List[Dict]) -> Optional[Dict]:
    """Son 48 saatteki haberler içinde aynı olayın devamı olan haberi döner (yoksa None)."""
    try:
        import database
        import fact_guard
        import multisource
    except Exception:
        return None

    in_tok = multisource._tokens(title)
    if len(in_tok) < 3:
        return None
    in_prop = _proper_nouns(title)
    now_tr = datetime.now(database.TR_TZ).replace(tzinfo=None)
    cutoff = now_tr - timedelta(hours=48)

    best = None
    best_score = 0.0
    for art in recent_articles or []:
        if (art.get("category") or "") == "Analiz":
            continue
        if category and art.get("category") and art.get("category") != category:
            continue
        raw_c = art.get("content") or ""
        if raw_c.count('class="ga-live-update"') >= 4:
            continue
        try:
            art_dt = datetime.strptime(str(art.get("created_at") or "")[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if art_dt < cutoff:
            continue
        a_title = art.get("title") or ""
        if a_title.strip().lower() == title.strip().lower():
            return None  # birebir aynı başlık = kopya, güncelleme değil
        a_tok = multisource._tokens(a_title)
        if len(a_tok) < 3:
            continue
        inter = len(in_tok & a_tok)
        ratio = inter / max(1, min(len(in_tok), len(a_tok)))
        prop_inter = len(in_prop & _proper_nouns(a_title))
        # Güçlü eşleşme: en az 3 ortak kök ve (%55+ oran VEYA 2+ özel isim ortaklığı)
        if inter < 3:
            continue
        if not (ratio >= 0.55 or (inter >= 3 and prop_inter >= 1 and ratio >= 0.45)):
            continue

        # Yeni bilgi şartı: yeni kaynakta mevcut haberde geçmeyen en az 1 sayı VEYA belirgin yeni kökler olmalı
        existing_plain = re.sub(r"<[^>]+>", " ", f"{a_title} {art.get('summary') or ''} {raw_c}")
        existing_nums = fact_guard.source_number_set([existing_plain])
        new_nums = fact_guard.unverified_numbers(f"{title} {summary or ''}", existing_nums)
        novel_tokens = in_tok - multisource._tokens(existing_plain[:3000])
        if not new_nums and len(novel_tokens) < 2:
            continue

        sc = inter + ratio + (0.5 if new_nums else 0.0) + (0.3 * prop_inter)
        if sc > best_score:
            best_score = sc
            best = art
    return best


def generate_update_block(existing: Dict, new_title: str, new_body: str, new_source: str, new_link: str = "") -> Optional[Dict]:
    """Yeni gelişmeyi 2-4 cümlelik doğrulanmış bir güncelleme kutusuna dönüştürür."""
    if not getattr(config, "GEMINI_API_KEY", ""):
        return None
    import content_quality
    import database
    import fact_guard

    src_clean = fact_guard.strip_source_junk((new_body or "").strip())
    if len(src_clean.split()) < 35:
        return None

    prompt = f"""Sen Gündem Analizi haber merkezinin editörüsün. Sitemizde yayında olan bir haberle ilgili YENİ bir gelişme geldi.
Mevcut haberdeki bilgileri tekrar etmeden, YALNIZCA yeni gelişmeyi 2-4 net cümleyle yaz.

Mevcut haber başlığı: {existing.get('title', '')}
Mevcut haber özeti: {existing.get('summary', '')}

Yeni gelişme kaynağı: {new_source}
Yeni gelişme başlığı: {new_title}
Yeni gelişme metni:
\"\"\"{src_clean[:3000]}\"\"\"

KESİN KURALLAR:
1. SADECE yeni gelişme metninde geçen bilgi, isim, tarih ve rakamları kullan. Kaynakta olmayan hiçbir rakam veya iddia yazma.
2. Mevcut haber zaten yeni gelişmedeki bilginin aynısını anlatıyorsa (yeni bir şey yoksa) yalnızca YOK yaz.
3. "Sonuç olarak", "yakından takip ediliyor", "merakla bekleniyor" gibi kalıplar kullanma. Duru Türkçe.
4. Yanıtı yalnızca şu iki etiketle düz metin ver:

[KISA_BASLIK]
Yeni gelişmeyi özetleyen 4-9 kelimelik cümle düzeninde ara başlık

[METIN]
Yeni gelişmeyi aktaran 2-4 cümlelik tek paragraf (veya yeni bilgi yoksa YOK)
"""
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=genai_types.HttpOptions(timeout=45000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
        )
    except Exception:
        return None

    allowed = fact_guard.source_number_set([f"{new_title} {src_clean}"])
    for m_name in ("gemini-3.5-flash", "gemini-3.5-flash-lite"):
        try:
            res = client.models.generate_content(model=m_name, contents=prompt)
            raw = (res.text or "").strip() if res else ""
            if not raw or "[METIN]" not in raw:
                continue
            h_part, b_part = raw.split("[METIN]", 1)
            sub_h = h_part.replace("[KISA_BASLIK]", "").strip().strip('"#*:- ')
            para = re.sub(r"\s+", " ", b_part.strip())
            if not para or para.upper().startswith("YOK") or len(para.split()) < 14:
                return None
            if fact_guard.unverified_numbers(para, allowed):
                para = fact_guard.drop_unverified_sentences(para, allowed)
            if len(para.split()) < 12:
                continue
            sub_h = fact_guard.to_turkish_sentence_case(content_quality.clean_title_text(sub_h or new_title), f"{new_title}. {src_clean}")
            ts_str = datetime.now(database.TR_TZ).strftime("%d.%m.%Y %H:%M")
            src_esc = _html.escape(content_quality.clean_source_name(new_source) or "Ajans", quote=True)
            link_html = (
                f' <a href="{_html.escape(new_link, quote=True)}" target="_blank" rel="nofollow noopener" class="underline font-semibold">Habere git →</a>'
                if (new_link or "").startswith("http") else ""
            )
            box = (
                '<div class="ga-live-update not-prose my-5 p-4 rounded-2xl bg-red-50/80 border-l-4 border-red-600 border border-red-200">'
                '<div class="flex flex-wrap items-center justify-between gap-2 mb-1.5">'
                f'<span class="text-[11px] font-black text-red-700 uppercase tracking-wide">🔴 Güncellendi • {ts_str}</span>'
                f'<span class="text-[11px] text-slate-600">Kaynak: <strong>{src_esc}</strong>{link_html}</span>'
                '</div>'
                f'<h4 class="text-sm sm:text-base font-extrabold text-slate-900 mb-1">{_html.escape(sub_h, quote=True)}</h4>'
                f'<p class="text-xs sm:text-sm text-slate-800 leading-relaxed m-0">{_html.escape(para, quote=True)}</p>'
                '</div>'
            )
            return {"html": box, "headline": sub_h, "text": para}
        except Exception as e:
            print(f"⚠️ [Yaşayan Haber] {m_name} hatası: {str(e)[:120]}")
            continue
    return None
