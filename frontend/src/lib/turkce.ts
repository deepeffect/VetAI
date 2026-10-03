/**
 * Arayüz metin yardımcıları.
 *
 * Backend'in NLP motoru, TF-IDF tutarlılığı için tüm metni ASCII'ye katlar
 * ("kaşıntı" ve "kasinti" aynı token'ı üretsin diye). Bu yüzden `bulgular` ve
 * `aciklayici_kelimeler` alanları bize "nefes_darligi", "istahsizlik" gibi
 * teknik token'lar olarak gelir.
 *
 * Bu token'ları modelin içinde değiştiremeyiz; değiştirirsek eğitim verisiyle
 * eşleşmeleri bozulur. Onun yerine yalnızca ekranda gösterilirken düzgün
 * Türkçe karşılıklarına çeviriyoruz. Sözlükte olmayan bir token gelirse ham
 * hâli okunabilir biçimde gösterilir, arayüz bozulmaz.
 */

/** Kanonik NLP token'ı -> ekranda görünecek Türkçe etiket. */
export const BULGU_ETIKETLERI: Record<string, string> = {
  // Anlam ayrımı tablosunun (backend/bilgi/anlam_ayrimi.py) ürettiği token'lar
  sicak_carpmasi: "Sıcak çarpması",
  travma_oykusu: "Travma öyküsü",
  elektrik_carpmasi: "Elektrik çarpması",
  kablo_kemirme: "Kablo kemirme",
  kalp_carpintisi: "Kalp çarpıntısı",
  arabada_kaldi: "Arabada kalma",
  ari_sokmasi: "Arı / böcek sokması",
  ilac_zehir_yutma: "İlaç / zehir yutma",
  kahve_yedi: "Kahve yeme",
  kurt_irki: "Kurt ırkı",
  kus_avi: "Kuş avı",
  ates_dustu: "Ateş düştü",
  kulak_uyuzu: "Kulak uyuzu",
  nezle: "Nezle",
  agiz_kokusu: "Ağız kokusu",
  apse: "Apse",
  asiri_salya: "Aşırı salya",
  asiri_seslenme: "Aşırı seslenme",
  asiri_susama: "Aşırı susama",
  ates: "Ateş",
  bilinc_kaybi: "Bilinç kaybı",
  burun_akintisi: "Burun akıntısı",
  burun_kurulugu: "Burun kuruluğu",
  cikolata_zehirlenmesi: "Çikolata zehirlenmesi",
  davranis_degisikligi: "Davranış değişikliği",
  denge_kaybi: "Denge kaybı",
  deri_dokuntusu: "Deri döküntüsü",
  dis_eti_iltihabi: "Diş eti iltihabı",
  dis_tasi: "Diş taşı",
  goz_akintisi: "Göz akıntısı",
  goz_kizarikligi: "Göz kızarıklığı",
  halsizlik: "Halsizlik",
  hapsirma: "Hapşırma",
  hirilti: "Hırıltı",
  ic_parazit: "İç parazit",
  idrar_sikayeti: "İdrar şikâyeti",
  idrar_tikanikligi: "İdrar tıkanıklığı",
  ishal: "İshal",
  istahsizlik: "İştahsızlık",
  kabizlik: "Kabızlık",
  kanama: "Kanama",
  kanli_idrar: "Kanlı idrar",
  kanli_ishal: "Kanlı ishal",
  karin_agrisi: "Karın ağrısı",
  karin_sisligi: "Karın şişliği",
  kasinti: "Kaşıntı",
  kedi: "Kedi",
  kepeklenme: "Kepeklenme",
  kilo_kaybi: "Kilo kaybı",
  kopek: "Köpek",
  kulak_iltihabi: "Kulak iltihabı",
  kulak_kasintisi: "Kulak kaşıntısı",
  kusma: "Kusma",
  mantar: "Mantar",
  nefes_darligi: "Nefes darlığı",
  nobet: "Nöbet",
  oksuruk: "Öksürük",
  parazit: "Parazit",
  sik_idrar: "Sık idrar",
  sislik: "Şişlik",
  sistit: "Sistit",
  titreme: "Titreme",
  topallama: "Topallama",
  travma: "Travma",
  tuy_dokulmesi: "Tüy dökülmesi",
  uyuz: "Uyuz",
  yara: "Yara",
  zehirlenme: "Zehirlenme",
};

/** İlk harfi Türkçe kurallarına göre büyütür ("istahsizlik" -> "İstahsizlik"). */
function basHarfiBuyut(metin: string): string {
  if (!metin) return metin;
  const ilk = metin[0] === "i" ? "İ" : metin[0].toLocaleUpperCase("tr-TR");
  return ilk + metin.slice(1);
}

export interface Bulgu {
  /** Ekranda görünecek Türkçe etiket. */
  etiket: string;
  /** Backend "(yok)" ekiyle işaretlediyse true — belirti yok demektir. */
  olumsuz: boolean;
}

/**
 * Backend'den gelen bulguyu ekrana hazır hâle getirir.
 *
 * Gelen biçimler: "kusma", "nefes darligi", "ates (yok)".
 */
export function bulguyuCoz(ham: string): Bulgu {
  const temiz = ham.trim();
  const olumsuz = temiz.endsWith("(yok)");
  const govde = (olumsuz ? temiz.slice(0, -5) : temiz).trim();
  const anahtar = govde.replace(/\s+/g, "_").toLowerCase();
  const etiket = BULGU_ETIKETLERI[anahtar] ?? basHarfiBuyut(govde.replace(/_/g, " "));
  return { etiket: olumsuz ? `${etiket} yok` : etiket, olumsuz };
}

/**
 * Modelin "bu tahmini destekleyen ifadeler" listesi için etiket üretir.
 *
 * Bu değerler TF-IDF özellikleridir; tek kelime ("kusma") olabileceği gibi
 * iki kelimelik bir kalıp da ("nefes darligi", "iki kusma") olabilir. Önce
 * tamamı sözlükte aranır, bulunamazsa kelimeler tek tek çevrilir; hiçbiri
 * eşleşmezse ham hâli okunabilir biçimde gösterilir.
 */
export function terimEtiketi(token: string): string {
  const ham = token.trim().toLowerCase();

  const tam = BULGU_ETIKETLERI[ham.replace(/\s+/g, "_")];
  if (tam) return tam;

  const parcalar = ham.split(/[\s_]+/).filter(Boolean);
  const metin = parcalar
    .map((parca, i) => {
      const karsilik = BULGU_ETIKETLERI[parca] ?? parca;
      return i === 0 ? karsilik : karsilik.toLocaleLowerCase("tr-TR");
    })
    .join(" ");

  return basHarfiBuyut(metin);
}

/** Tür kodunu ("kedi" | "kopek" | "genel") ekran etiketine çevirir. */
export function turEtiketi(tur: string): string {
  if (tur === "kedi") return "Kedi";
  if (tur === "kopek") return "Köpek";
  return "Tür belirsiz";
}
