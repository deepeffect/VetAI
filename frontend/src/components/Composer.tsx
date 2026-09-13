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
  { deger: "kopek", etiket: "Kopek", Ikon: DogIcon },
];

const MAX = 2000;

export default function Composer({ onGonder, bekliyor }: Props) {
  const [metin, setMetin] = useState("");
  const [tur, setTur] = useState<Tur>("genel");
  const alanRef = useRef<HTMLTextAreaElement>(null);

  function gonder(e?: FormEvent) {
    e?.preventDefault();
    const temiz = metin.trim();
    if (!temiz || bekliyor) return;
    onGonder(temiz, tur);
    setMetin("");
    alanRef.current?.focus();
  }

  // Enter gonderir, Shift+Enter alt satira gecer.
  function tusaBasildi(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      gonder();
    }
  }

  return (
    <form onSubmit={gonder} className="space-y-2.5">
      {/* Tur secici */}
      <div className="flex items-center gap-1.5">
        <span className="mr-1 text-[11px] font-medium text-slate-500">Tur:</span>
        {TURLER.map(({ deger, etiket, Ikon }) => (
          <button
            key={deger}
            type="button"
            onClick={() => setTur(deger)}
            aria-pressed={tur === deger}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors ${
              tur === deger
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border-line bg-surface-raised/60 text-slate-400 hover:border-slate-600 hover:text-slate-300"
            }`}
          >
            <Ikon className="h-3.5 w-3.5" />
            {etiket}
          </button>
        ))}
      </div>

      <div className="relative rounded-2xl border border-line bg-surface-raised/70 transition-colors focus-within:border-emerald-500/50">
        <textarea
          ref={alanRef}
          value={metin}
          onChange={(e) => setMetin(e.target.value.slice(0, MAX))}
          onKeyDown={tusaBasildi}
          rows={2}
          disabled={bekliyor}
          placeholder="Sikayeti yazin. Ornek: Kedim iki gundur kusuyor, mama yemiyor ve cok halsiz."
          className="max-h-40 min-h-[64px] w-full resize-none bg-transparent px-4 py-3 pr-14 text-[14px] leading-relaxed text-slate-100 outline-none placeholder:text-slate-600 disabled:opacity-60"
        />

        <button
          type="submit"
          disabled={!metin.trim() || bekliyor}
          aria-label="Analiz et"
          className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white transition-all hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
        >
          {bekliyor ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            <SendIcon className="h-4 w-4" />
          )}
        </button>
      </div>

      <div className="flex items-center justify-between px-1 text-[11px] text-slate-600">
        <span>
          <kbd className="rounded border border-line bg-slate-800/70 px-1 py-0.5 font-sans">Enter</kbd> gonder
          <span className="mx-1.5">-</span>
          <kbd className="rounded border border-line bg-slate-800/70 px-1 py-0.5 font-sans">Shift+Enter</kbd> alt satir
        </span>
        <span className={metin.length > MAX * 0.9 ? "text-amber-500" : ""}>
          {metin.length}/{MAX}
        </span>
      </div>
    </form>
  );
}
