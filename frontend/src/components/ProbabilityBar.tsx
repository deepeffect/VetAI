/** Logistic Regression olasiligini gosteren animasyonlu ilerleme cubugu. */

interface Props {
  yuzde: number;
  /** Ilk siradaki tahmin daha belirgin renklendirilir. */
  vurgulu?: boolean;
  /** Barlarin sirayla dolmasi icin gecikme (ms). */
  gecikmeMs?: number;
}

/** Olasilik araligina gore renk: yuksek=yesil, orta=amber, dusuk=slate. */
function renkler(yuzde: number, vurgulu: boolean) {
  if (yuzde >= 45) {
    return {
      bar: "bg-gradient-to-r from-emerald-500 to-emerald-400",
      metin: "text-emerald-300",
      glow: vurgulu ? "shadow-[0_0_16px_-2px_rgba(16,185,129,0.55)]" : "",
    };
  }
  if (yuzde >= 25) {
    return {
      bar: "bg-gradient-to-r from-amber-500 to-amber-400",
      metin: "text-amber-300",
      glow: vurgulu ? "shadow-[0_0_16px_-2px_rgba(245,158,11,0.45)]" : "",
    };
  }
  return {
    bar: "bg-gradient-to-r from-slate-600 to-slate-500",
    metin: "text-slate-400",
    glow: "",
  };
}

export default function ProbabilityBar({ yuzde, vurgulu = false, gecikmeMs = 0 }: Props) {
  const c = renkler(yuzde, vurgulu);
  // Cok kucuk degerlerde bile bir iz kalsin diye alt sinir veriyoruz.
  const genislik = Math.max(2, Math.min(100, yuzde));

  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800/80"
        role="progressbar"
        aria-valuenow={Math.round(yuzde)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Model olasiligi yuzde ${Math.round(yuzde)}`}
      >
        <div
          className={`h-full rounded-full ${c.bar} ${c.glow}`}
          style={{
            width: `${genislik}%`,
            animation: `grow 0.9s cubic-bezier(0.22, 1, 0.36, 1) ${gecikmeMs}ms both`,
          }}
        />
      </div>
      <span className={`w-14 shrink-0 text-right font-mono text-sm font-semibold tabular-nums ${c.metin}`}>
        %{yuzde.toFixed(1)}
      </span>
    </div>
  );
}
