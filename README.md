# Dota 2 Counter Picker

Python, Streamlit ve OpenDota API kullanarak gelistirilmis bir Dota 2 counter picker uygulamasi.

Bu repo Streamlit tabanli bir Dota 2 counter picker uygulamasidir.

## Ozellikler

- OpenDota `/api/heroes` endpointinden hero listesini cache'ler
- En fazla 5 rakip hero secimi sunar
- Rol filtresi uygular: `Hepsi`, `Carry`, `Support`, `Mid`, `Offlane`, `Disabler`, `Durable`
- OpenDota Explorer API uzerinden son 30 gun verisiyle counter hero sorgular
- Minimum mac sayisi esigi slider'i ile orneklem kalitesini kontrol eder
- Stabilize win rate, orneklem buyuklugu ve rakip kapsama oranina dayali `confidence score` uretir
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

## Streamlit Community Cloud Deploy

1. Bu projeyi GitHub reposuna push edin.
2. Streamlit Community Cloud panelinde `New app` secin.
3. Repo olarak bu projeyi secin.
4. Branch: `main`
5. Main file path: `app.py`
6. Deploy edin.

## Proje Dosyalari

- `app.py`: Streamlit uygulamasi
- `requirements.txt`: Python bagimliliklari
- `.gitignore`: Git disinda tutulacak dosyalar

## Notlar

- Uygulama OpenDota API'sine runtime sirasinda istek atar.
- Sonuclar son 30 gun verisine dayanir.
- Dusuk mac sayili sonuclar slider ile filtrelenebilir.
