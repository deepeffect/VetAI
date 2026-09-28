"""Konsol ciktisinin Turkce karakterleri tasiyabilmesi icin yardimci.

Windows'ta cikti bir dosyaya ya da boruya (pipe) yonlendirildiginde Python
stdout'u sistem kod sayfasiyla (cp1252/cp857) acar; "ı", "ş", "ğ" gibi harfler
UnicodeEncodeError firlatir ve sunucu daha acilmadan duser. Bu yuzden butun
giris noktalari (main.py, init_db.py, olcum.py) once bu fonksiyonu cagirir.
"""

from __future__ import annotations

import sys


def utf8_cikti_ayarla() -> None:
    """stdout/stderr'i UTF-8'e alir; desteklenmeyen karakteri hata yerine degistirir."""
    for akis in (sys.stdout, sys.stderr):
        yeniden_ayarla = getattr(akis, "reconfigure", None)
        if yeniden_ayarla is None:
            continue
        try:
            yeniden_ayarla(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - kapali/ozel akislar
            pass
