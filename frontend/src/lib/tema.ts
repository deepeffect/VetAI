import { useCallback, useEffect, useState } from "react";

/**
 * Açık / yumuşak koyu tema yönetimi.
 *
 * Tema <html> etiketine eklenen "dark" sınıfıyla uygulanır; renkler
 * index.css içindeki anlamsal token'lardan gelir. İlk seçim index.html'deki
 * küçük betikte yapılır, böylece sayfa açılırken renk sıçraması olmaz.
 */

export type Tema = "acik" | "koyu";

const ANAHTAR = "vetai-tema";

function baslangicTemasi(): Tema {
  try {
    const kayitli = localStorage.getItem(ANAHTAR);
    if (kayitli === "acik" || kayitli === "koyu") return kayitli;
  } catch {
    /* localStorage kapalı olabilir (gizli sekme, katı gizlilik ayarı) */
  }
  // Varsayilan olarak acik tema: ferah gorunum urunun tercih edilen halidir,
  // koyu tema kullanicinin bilincli secimiyle acilir.
  return "acik";
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(baslangicTemasi);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", tema === "koyu");
    try {
      localStorage.setItem(ANAHTAR, tema);
    } catch {
      /* yazılamazsa tema yalnızca bu oturum için geçerli olur */
    }
  }, [tema]);

  const temayiDegistir = useCallback(() => {
    setTema((onceki) => (onceki === "koyu" ? "acik" : "koyu"));
  }, []);

  return { tema, temayiDegistir };
}
