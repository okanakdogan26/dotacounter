# Dota 2 Counter Picker

Python, Streamlit ve OpenDota API kullanarak gelistirilmis bir Dota 2 counter picker uygulamasi.

Bu repo iki parcadan olusur:

- `app.py`: Streamlit arayuzu
- `backend.py`: Dotabuff verisini cache'leyip JSON olarak servis eden FastAPI backend

## Ozellikler

- OpenDota `/api/heroes` endpointinden hero listesini cache'ler
- En fazla 5 rakip hero secimi sunar
- Rol filtresi uygular: `Hepsi`, `Carry`, `Support`, `Mid`, `Offlane`, `Disabler`, `Durable`
- OpenDota Explorer API uzerinden son 30 gun verisiyle counter hero sorgular
- Minimum mac sayisi esigi slider'i ile orneklem kalitesini kontrol eder
- Opsiyonel Dotabuff `Worst Versus` sinyalini backend uzerinden siralamaya katar
- Sonuclari tablo ve bar chart olarak gosterir
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

### 4. Dotabuff backend'i baslat

Ayri bir terminalde:

```bash
uvicorn backend:app --host 0.0.0.0 --port 8000
```

Ardindan Streamlit'i backend URL ile calistirin:

```bash
BACKEND_API_URL=http://127.0.0.1:8000 streamlit run app.py
```

## Streamlit Community Cloud Deploy

Bu repo artik iki servisli bir yapi kullaniyor:

1. `backend.py` servisini Render, Railway veya benzeri bir platforma deploy edin.
2. Backend URL'sini alin. Ornek: `https://dotacounter-backend.onrender.com`
3. Streamlit Community Cloud uygulamasinda `BACKEND_API_URL` environment variable olarak bu URL'yi ekleyin.
4. Sonra Streamlit app'i deploy edin:
   - Repository: bu repo
   - Branch: `main`
   - Main file path: `app.py`

## Proje Dosyalari

- `app.py`: Streamlit uygulamasi
- `backend.py`: Dotabuff proxy ve cache backend'i
- `requirements.txt`: Python bagimliliklari
- `.gitignore`: Git disinda tutulacak dosyalar

## Notlar

- Uygulama OpenDota API'sine runtime sirasinda istek atar.
- Dotabuff verisi dogrudan Streamlit Cloud'dan cekilmez; backend uzerinden alinmasi gerekir.
- Sonuclar son 30 gun verisine dayanir.
- Dusuk mac sayili sonuclar slider ile filtrelenebilir.
