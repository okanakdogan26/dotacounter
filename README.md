# Dota 2 Counter Picker

Python, Streamlit ve OpenDota API kullanarak gelistirilmis bir Dota 2 counter picker uygulamasi.

Bu repo Streamlit tabanli bir Dota 2 counter picker uygulamasidir.

OpenDota verisini ana kaynak olarak kullanir ve istege bagli olarak repo icinde tutulan
yerel Dotabuff `Worst Versus` dataset'i ile siralamayi guclendirir.

## Ozellikler

- OpenDota `/api/heroes` endpointinden hero listesini cache'ler
- En fazla 5 rakip hero secimi sunar
- Rol filtresi uygular: `Hepsi`, `Carry`, `Support`, `Mid`, `Offlane`, `Disabler`, `Durable`
- OpenDota Explorer API uzerinden son 30 gun verisiyle counter hero sorgular
- Minimum mac sayisi esigi slider'i ile orneklem kalitesini kontrol eder
- Stabilize win rate, orneklem buyuklugu ve rakip kapsama oranina dayali `confidence score` uretir
- Yerel Dotabuff `Worst Versus` dataset'i varsa `hybrid score` ile siralamayi guclendirir
- Sonuclari tablo ve bar chart olarak gosterir
- Opsiyonel `Invoker Assistant Mode` ile draft zayifliklarini, Quas-Wex vs Quas-Exort yol ayrimini, kritik item timinglerini ve kombo onceligini yorumlar
- Dusuk veri veya API hatalari icin kullanici dostu uyari mesaji verir

## Yerel Calistirma

### 1. Sanal ortam olustur

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Bagimliliklari kur

```bash
pip install -r requirements.txt
```

### 3. Uygulamayi baslat

```bash
streamlit run app.py
```

## Streamlit Community Cloud Deploy

1. Bu projeyi GitHub reposuna push edin.
2. Streamlit Community Cloud panelinde `New app` secin.
3. Repo olarak bu projeyi secin.
4. Branch: `main`
5. Main file path: `app.py`
6. Deploy edin.

## Proje Dosyalari

- `app.py`: Streamlit uygulamasi
- `data/dotabuff_worst_versus.json`: Elle veya yari otomatik doldurulan Dotabuff dataset'i
- `data/dotabuff_import_template.json`: Dotabuff veri iceri aktarma ornek dosyasi
- `scripts/import_dotabuff_data.py`: Import dosyasini ana dataset'e merge eden script
- `scripts/refresh_dotabuff_dataset.py`: OpenDota hero listesi ve Dotabuff hero sayfalarindan `Worst Versus` dataset'ini tam yenileyen script
- `requirements.txt`: Python bagimliliklari
- `.gitignore`: Git disinda tutulacak dosyalar

## Notlar

- Uygulama OpenDota API'sine runtime sirasinda istek atar.
- Dotabuff verisi canli scrape edilmez; `data/dotabuff_worst_versus.json` icinden okunur.
- Sonuclar son 30 gun verisine dayanir.
- Dusuk mac sayili sonuclar slider ile filtrelenebilir.

## Dotabuff Veri Import

Yerel Dotabuff dataset'ini toplu guncellemek icin:

```bash
python3 scripts/import_dotabuff_data.py data/dotabuff_import_template.json
```

Canli Dotabuff verisini tum hero havuzu icin yeniden cekmek icin:

```bash
python3 scripts/refresh_dotabuff_dataset.py
```

Import dosyasi `heroes` objesi altinda su formatta veri bekler:

```json
{
  "heroes": {
    "Elder Titan": [
      {
        "hero": "Chen",
        "disadvantage_pct": 6.12,
        "win_rate_pct": 43.21,
        "matches": 8234
      }
    ]
  }
}
```
