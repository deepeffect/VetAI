import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { Tur } from "../api";
import { CatIcon, DogIcon, PawIcon, SendIcon } from "./Icons";

interface Props {
  onGonder: (metin: string, tur: Tur) => void;
  bekliyor: boolean;
}

const TURLER: { deger: Tur; etiket: string; Ikon: typeof PawIcon }[] = [
  { deger: "genel", etiket: "Otomatik", Ikon: PawIcon },
  { deger: "kedi", etiket: "Kedi", Ikon: CatIcon },
  { deger: "kopek", etiket: "Köpek", Ikon: DogIcon },
];

const MAX = 2000;

/**
 * Şikâyet giriş alanı.
 *
 * Tür seçimi bir "segmented control" olarak üstte durur; metin alanı ve
 * gönder düğmesi tek bir kart içinde toplanır. Kart, odaklanıldığında
 * kenarlığını yeşile çevirerek nereye yazıldığını belli eder.
 */
export default function Composer({ onGonder, bekliyor }: Props) {
  const [metin, setMetin] = useState("");
  const [tur, setTur] = useState<Tur>("genel");
  const alanRef = useRef<HTMLTextAreaElement>(null);

  const kalan = MAX - metin.length;
  const sinirYakin = kalan <= 200;

  function gonder(e?: FormEvent) {
    e?.preventDefault();
    const temiz = metin.trim();
    if (!temiz || bekliyor) return;
    onGonder(temiz, tur);
    setMetin("");
    alanRef.current?.focus();
  }

  // Enter gönderir, Shift+Enter alt satıra geçer.
  function tusaBasildi(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      gonder();
    }
  }

  return (
    <form onSubmit={gonder} className="space-y-3">
      {/* -------------------------------------------------- Tür seçici */}
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-medium text-ink-muted">Tür</span>
        <div
          className="flex items-center gap-1 rounded-xl border border-line bg-canvas-soft p-1"
          role="group"
          aria-label="Hayvan türü"
        >
          {TURLER.map(({ deger, etiket, Ikon }) => (
            <button
              key={deger}
              type="button"
              onClick={() => setTur(deger)}
              aria-pressed={tur === deger}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium transition-colors ${
                tur === deger
                  ? "bg-card text-accent-ink shadow-soft"
                  : "text-ink-muted hover:text-ink-soft"
              }`}
            >
              <Ikon className="h-4 w-4" />
              {etiket}
            </button>
          ))}
        </div>
      </div>

      {/* -------------------------------------------------- Metin alanı */}
      <div className="rounded-2xl border border-line bg-card shadow-soft transition-colors focus-within:border-accent-line">
        <div className="relative">
          <textarea
            ref={alanRef}
            value={metin}
            onChange={(e) => setMetin(e.target.value.slice(0, MAX))}
            onKeyDown={tusaBasildi}
            rows={2}
            disabled={bekliyor}
            aria-label="Şikâyet metni"
            placeholder="Şikâyeti yazın. Örnek: Kedim iki gündür kusuyor, mama yemiyor ve çok halsiz."
            className="max-h-48 min-h-[72px] w-full resize-none bg-transparent px-4 py-3.5 pr-16 text-[14.5px] leading-relaxed text-ink outline-none placeholder:text-ink-muted disabled:opacity-60"
          />

          <button
            type="submit"
            disabled={!metin.trim() || bekliyor}
            aria-label="Analiz et"
            title="Analiz et (Enter)"
            className="absolute bottom-3 right-3 flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-muted"
          >
            {bekliyor ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <SendIcon className="h-[18px] w-[18px]" />
            )}
          </button>
        </div>
      </div>

      {/* -------------------------------------------------- Alt ipuçları */}
      <div className="flex items-center justify-between gap-3 px-1 text-[11.5px] text-ink-muted">
        <span className="hidden sm:block">
          <kbd className="rounded-md border border-line bg-canvas-soft px-1.5 py-0.5 font-sans text-[11px]">
            Enter
          </kbd>{" "}
          gönder
          <span className="mx-2 text-line">·</span>
          <kbd className="rounded-md border border-line bg-canvas-soft px-1.5 py-0.5 font-sans text-[11px]">
            Shift + Enter
          </kbd>{" "}
          alt satır
        </span>
        <span className={`tnum ml-auto ${sinirYakin ? "text-warn-ink" : ""}`}>
          {metin.length} / {MAX}
        </span>
      </div>
    </form>
  );
}
