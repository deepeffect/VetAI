import type { ReactNode } from "react";
import { PawIcon } from "./Icons";

interface Props {
  rol: "kullanici" | "asistan";
  children: ReactNode;
  /** Hata balonlari kirmizi cerceveyle gosterilir. */
  hata?: boolean;
}

export default function ChatBubble({ rol, children, hata = false }: Props) {
  if (rol === "kullanici") {
    return (
      <div className="animate-rise flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-emerald-600 px-4 py-2.5 text-[14px] leading-relaxed text-white shadow-lg shadow-emerald-900/30 sm:max-w-[75%]">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-rise flex gap-3">
      <div
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
          hata
            ? "bg-red-500/15 text-red-400"
            : "bg-gradient-to-br from-emerald-500/25 to-teal-500/15 text-emerald-400"
        }`}
      >
        <PawIcon className="h-4 w-4" />
      </div>
      <div
        className={`min-w-0 flex-1 rounded-2xl rounded-tl-md border px-4 py-3.5 ${
          hata
            ? "border-red-500/30 bg-red-500/5 text-red-200"
            : "border-line bg-surface-raised/40"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
