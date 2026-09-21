import type { ReactNode } from "react";
import { PawIcon } from "./Icons";

interface Props {
  rol: "kullanici" | "asistan";
  children: ReactNode;
  /** Hata balonları kırmızımsı bir kartla gösterilir. */
  hata?: boolean;
}

/**
 * Sohbet satırı.
 *
 * Kullanıcı mesajı sağda dolu yeşil bir balon, asistan yanıtı ise solda
 * beyaz (koyu temada yumuşak koyu) bir karttır. Asistan kartı, içine analiz
 * sonucu gibi zengin içerik alabildiği için bol iç boşlukla tasarlandı.
 */
export default function ChatBubble({ rol, children, hata = false }: Props) {
  if (rol === "kullanici") {
    return (
      <div className="animate-rise flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-[14.5px] leading-relaxed text-white shadow-soft sm:max-w-[72%]">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-rise flex gap-3">
      <div
        className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
          hata
            ? "border-danger-line bg-danger-soft text-danger-ink"
            : "border-accent-line bg-accent-soft text-accent-ink"
        }`}
        aria-hidden="true"
      >
        <PawIcon className="h-[18px] w-[18px]" />
      </div>

      <div
        className={`min-w-0 flex-1 rounded-2xl rounded-tl-md border px-5 py-4 ${
          hata
            ? "border-danger-line bg-danger-soft text-danger-ink"
            : "border-line bg-card text-ink shadow-soft"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
