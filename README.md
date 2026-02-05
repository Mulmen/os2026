# OS-tips (Streamlit) – starter

## Ladda upp i GitHub
Ladda upp hela mappen (inkl. `data/`).

## Kör lokalt
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy på Streamlit Community Cloud
New app -> välj repo -> `app.py`.

## Data
- `data/athletes.csv` måste finnas i repot (read-only).
- Tips + resultat sparas i en skrivbar state-katalog i Streamlit-miljön och kan exporteras via Backup/Restore.
