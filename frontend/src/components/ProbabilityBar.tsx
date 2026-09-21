/** Logistic Regression olasılığını gösteren sade ilerleme çubuğu. */

interface Props {
  yuzde: number;
  /** Barların sırayla dolması için gecikme (ms). */
  gecikmeMs?: number;
}

/**
 * Olasılık aralığına göre renk seçer.
 * Yüksek = adaçayı yeşili, orta = amber, düşük = nötr gri.
 * Parlama/neon efekti bilinçli olarak kullanılmıyor; değer okunsun yeter.
 */
function renkler(yuzde: number) {
  if (yuzde >= 45) return { bar: "bg-sage-500", metin: "text-accent-ink" };
  if (yuzde >= 25) return { bar: "bg-warn", metin: "text-warn-ink" };
  return { bar: "bg-ink-muted", metin: "text-ink-muted" };
}

export default function ProbabilityBar({ yuzde, gecikmeMs = 0 }: Props) {
  const c = renkler(yuzde);
  // Çok küçük değerlerde bile bir iz kalsın diye alt sınır veriyoruz.
  const genislik = Math.max(2, Math.min(100, yuzde));

  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuenow={Math.round(yuzde)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Model olasılığı yüzde ${Math.round(yuzde)}`}
      >
        <div
          className={`h-full rounded-full ${c.bar}`}
          style={{
            width: `${genislik}%`,
            animation: `grow 0.8s cubic-bezier(0.22, 1, 0.36, 1) ${gecikmeMs}ms both`,
          }}
        />
      </div>
      <span className={`tnum w-14 shrink-0 text-right text-[13px] font-semibold ${c.metin}`}>
        %{yuzde.toFixed(1)}
      </span>
    </div>
  );
}
