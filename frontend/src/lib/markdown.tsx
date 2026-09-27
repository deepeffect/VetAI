import { Fragment, type ReactNode } from "react";

/**
 * Küçük ve güvenli Markdown işleyici.
 *
 * Gemini yanıtları başlık, madde listesi, kalın/eğik metin, satır içi kod,
 * kod bloğu ve bağlantı içerebilir. Ek bağımlılık almamak ve HTML enjeksiyonu
 * riskini sıfırlamak için metin doğrudan React düğümlerine çevrilir;
 * hiçbir yerde `dangerouslySetInnerHTML` kullanılmaz.
 *
 * Desteklenenler: # başlıklar, -/* ve 1. listeler, ```kod blokları```,
 * `satır içi kod`, **kalın**, *eğik*, [bağlantı](https://…), paragraflar.
 */

type Blok =
  | { tur: "paragraf"; satirlar: string[] }
  | { tur: "baslik"; seviye: number; metin: string }
  | { tur: "liste"; sirali: boolean; ogeler: string[] }
  | { tur: "kod"; dil: string; icerik: string };

function bloklaraAyir(kaynak: string): Blok[] {
  const satirlar = kaynak.replace(/\r\n?/g, "\n").split("\n");
  const bloklar: Blok[] = [];
  let i = 0;

  while (i < satirlar.length) {
    const satir = satirlar[i];

    if (!satir.trim()) {
      i++;
      continue;
    }

    // ``` kod bloğu
    const kodBaslangic = satir.match(/^\s*```\s*([\w+-]*)\s*$/);
    if (kodBaslangic) {
      const govde: string[] = [];
      i++;
      while (i < satirlar.length && !/^\s*```\s*$/.test(satirlar[i])) {
        govde.push(satirlar[i]);
        i++;
      }
      i++; // kapanış satırı (yoksa dosya sonu)
      bloklar.push({ tur: "kod", dil: kodBaslangic[1], icerik: govde.join("\n") });
      continue;
    }

    // # Başlık
    const baslik = satir.match(/^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$/);
    if (baslik) {
      bloklar.push({ tur: "baslik", seviye: baslik[1].length, metin: baslik[2] });
      i++;
      continue;
    }

    // Liste (madde ya da sıralı)
    const listeMi = (s: string) => /^\s{0,3}(?:[-*•]|\d{1,3}[.)])\s+/.test(s);
    if (listeMi(satir)) {
      const sirali = /^\s{0,3}\d/.test(satir);
      const ogeler: string[] = [];
      while (i < satirlar.length && listeMi(satirlar[i])) {
        let oge = satirlar[i].replace(/^\s{0,3}(?:[-*•]|\d{1,3}[.)])\s+/, "");
        i++;
        // Girintili devam satırları aynı maddeye eklenir
        while (i < satirlar.length && /^\s{2,}\S/.test(satirlar[i]) && !listeMi(satirlar[i])) {
          oge += " " + satirlar[i].trim();
          i++;
        }
        ogeler.push(oge);
      }
      bloklar.push({ tur: "liste", sirali, ogeler });
      continue;
    }

    // Paragraf: boş satıra ya da başka bir blok türüne kadar
    const govde: string[] = [];
    while (
      i < satirlar.length &&
      satirlar[i].trim() &&
      !listeMi(satirlar[i]) &&
      !/^\s{0,3}#{1,4}\s/.test(satirlar[i]) &&
      !/^\s*```/.test(satirlar[i])
    ) {
      govde.push(satirlar[i].trim());
      i++;
    }
    // Hiçbir kalıba tam uymayan satır (ör. "```js x") düz metin olarak alınır;
    // böylece döngü her turda mutlaka ilerler.
    if (govde.length === 0) {
      govde.push(satirlar[i].trim());
      i++;
    }
    bloklar.push({ tur: "paragraf", satirlar: govde });
  }

  return bloklar;
}

/** Satır içi biçimlendirme: kod, kalın, eğik, bağlantı. */
function satirIci(metin: string, anahtar: string): ReactNode[] {
  const parcalar: ReactNode[] = [];
  const desen = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(\[[^\]\n]+\]\((https?:\/\/[^\s)]+)\))/g;
  let son = 0;
  let n = 0;
  let eslesme: RegExpExecArray | null;

  while ((eslesme = desen.exec(metin)) !== null) {
    if (eslesme.index > son) parcalar.push(metin.slice(son, eslesme.index));
    const [tam, kod, kalin, egik, baglanti, url] = eslesme;
    const k = `${anahtar}-${n++}`;

    if (kod) {
      parcalar.push(
        <code
          key={k}
          className="rounded-md border border-line bg-canvas-soft px-1.5 py-0.5 font-mono text-[0.86em] text-ink"
        >
          {kod.slice(1, -1)}
        </code>
      );
    } else if (kalin) {
      parcalar.push(
        <strong key={k} className="font-semibold text-ink">
          {kalin.slice(2, -2)}
        </strong>
      );
    } else if (egik) {
      parcalar.push(<em key={k}>{egik.slice(1, -1)}</em>);
    } else if (baglanti && url) {
      const etiket = baglanti.slice(1, baglanti.indexOf("]("));
      parcalar.push(
        <a
          key={k}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="break-all text-accent-ink underline decoration-accent-line underline-offset-2 hover:decoration-accent-ink"
        >
          {etiket}
        </a>
      );
    } else {
      parcalar.push(tam);
    }
    son = eslesme.index + tam.length;
  }
  if (son < metin.length) parcalar.push(metin.slice(son));
  return parcalar;
}

interface Props {
  metin: string;
  className?: string;
}

/**
 * Markdown metnini temaya uygun React düğümlerine çevirir.
 * Uzun kelimeler ve kod blokları kabı taşırmaz (break-words + yatay kaydırma).
 */
export default function Markdown({ metin, className = "" }: Props) {
  const bloklar = bloklaraAyir(metin);

  return (
    <div className={`min-w-0 space-y-3 break-words text-[14.5px] leading-7 text-ink ${className}`}>
      {bloklar.map((blok, bi) => {
        const k = `b${bi}`;
        switch (blok.tur) {
          case "baslik": {
            const stil =
              blok.seviye <= 2
                ? "text-[15.5px] font-semibold"
                : "text-[14.5px] font-semibold";
            return (
              <p key={k} className={`${stil} leading-6 text-ink`}>
                {satirIci(blok.metin, k)}
              </p>
            );
          }
          case "liste": {
            const Etiket = blok.sirali ? "ol" : "ul";
            return (
              <Etiket
                key={k}
                className={`space-y-1 pl-5 ${blok.sirali ? "list-decimal" : "list-disc"} marker:text-ink-muted`}
              >
                {blok.ogeler.map((oge, oi) => (
                  <li key={oi} className="pl-1">
                    {satirIci(oge, `${k}-${oi}`)}
                  </li>
                ))}
              </Etiket>
            );
          }
          case "kod":
            return (
              <pre
                key={k}
                className="overflow-x-auto rounded-xl border border-line bg-canvas-soft px-4 py-3 font-mono text-[12.5px] leading-6 text-ink"
              >
                <code>{blok.icerik}</code>
              </pre>
            );
          default:
            return (
              <p key={k}>
                {blok.satirlar.map((satir, si) => (
                  <Fragment key={si}>
                    {si > 0 && <br />}
                    {satirIci(satir, `${k}-${si}`)}
                  </Fragment>
                ))}
              </p>
            );
        }
      })}
    </div>
  );
}
