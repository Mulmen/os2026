import json
from pathlib import Path

import pandas as pd
import streamlit as st

PLAYERS = ["Johan", "Göran", "Jesper", "Peter", "Magnus", "Tony"]
MEDALS = ["None", "Bronze", "Silver", "Gold"]

# Repo-data (read-only i Streamlit Cloud)
REPO_DATA_DIR = Path("data")
ATHLETES_CSV = REPO_DATA_DIR / "athletes.csv"

# Writable state directory (avoids read-only repo)
STATE_DIR = Path.home() / ".streamlit" / "os_tips_state"
RESULTS_CSV = STATE_DIR / "results.csv"
PICKS_JSON = STATE_DIR / "picks.json"

# Set to "" to disable password
ADMIN_PASSWORD = "admin"

st.set_page_config(page_title="OS-tips", layout="wide")


def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8"):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def load_athletes() -> pd.DataFrame:
    if not ATHLETES_CSV.exists():
        st.error("Saknar data/athletes.csv i repot. Lägg filen i mappen data/ och committa till GitHub.")
        st.stop()

    df = pd.read_csv(ATHLETES_CSV)
    required = {"athlete_id", "name", "sport"}
    if not required.issubset(df.columns):
        st.error(f"athletes.csv måste ha kolumnerna: {sorted(required)}")
        st.stop()

    df = df.dropna(subset=["athlete_id", "name", "sport"]).copy()
    df["athlete_id"] = df["athlete_id"].astype(str)
    df["name"] = df["name"].astype(str)
    df["sport"] = df["sport"].astype(str)
    return df


def load_results(athletes: pd.DataFrame) -> pd.DataFrame:
    if not RESULTS_CSV.exists():
        out = athletes[["athlete_id"]].copy()
        out["medal"] = "None"
        atomic_write_text(RESULTS_CSV, out.to_csv(index=False))

    df = pd.read_csv(RESULTS_CSV)
    required = {"athlete_id", "medal"}
    if not required.issubset(df.columns):
        st.error(f"results.csv måste ha kolumnerna: {sorted(required)}")
        st.stop()

    df["athlete_id"] = df["athlete_id"].astype(str)
    df["medal"] = df["medal"].astype(str)
    df.loc[~df["medal"].isin(MEDALS), "medal"] = "None"

    merged = athletes[["athlete_id"]].merge(df, on="athlete_id", how="left")
    merged["medal"] = merged["medal"].fillna("None")
    return merged


def save_results(results_df: pd.DataFrame):
    atomic_write_text(RESULTS_CSV, results_df.to_csv(index=False))


def load_picks() -> dict:
    if not PICKS_JSON.exists():
        return {}
    try:
        return json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_picks(picks: dict):
    atomic_write_text(PICKS_JSON, json.dumps(picks, ensure_ascii=False, indent=2))


def score_pick(pick: str, actual: str) -> int:
    if actual == "None":
        return 0
    if pick == actual:
        return 5
    if pick != "None" and actual != "None":
        return 2
    return 0


def build_scoreboard(athletes: pd.DataFrame, results: pd.DataFrame, picks_all: dict) -> pd.DataFrame:
    results_map = dict(zip(results["athlete_id"], results["medal"]))
    rows = []
    for p in PLAYERS:
        user_picks = picks_all.get(p, {})
        total = exact = right_person = 0
        for aid in athletes["athlete_id"].tolist():
            pick = user_picks.get(aid, "None")
            actual = results_map.get(aid, "None")
            pts = score_pick(pick, actual)
            total += pts
            if actual != "None" and pick == actual:
                exact += 1
            elif actual != "None" and pick != "None":
                right_person += 1
        rows.append({"Tippare": p, "Poäng": total, "Exakta (5p)": exact, "Rätt medaljör (2p)": right_person})
    return pd.DataFrame(rows).sort_values(["Poäng", "Exakta (5p)"], ascending=False).reset_index(drop=True)


ensure_state_dir()
athletes = load_athletes()
results = load_results(athletes)
picks_all = load_picks()

st.title("OS-tips – Sverige (vinter-OS 2026)")
st.caption("Tips sparas i en skrivbar state-katalog. Använd Backup/Restore för säkerhetskopia.")

tabs = st.tabs(["Lägg tips", "Scoreboard", "Admin (resultat)", "Backup / Restore"])

with tabs[0]:
    left, right = st.columns([1, 1], gap="large")

    with left:
        st.subheader("Välj tippare")
        player = st.selectbox("Tippare", PLAYERS)

        st.subheader("Välj sport och atlet")
        sports = sorted(athletes["sport"].unique().tolist())
        sport = st.selectbox("Sport", sports)

        athletes_in_sport = athletes[athletes["sport"] == sport].sort_values("name")
        athlete_label_map = {
            f"{row['name']} ({row['athlete_id']})": row["athlete_id"]
            for _, row in athletes_in_sport.iterrows()
        }
        athlete_label = st.selectbox("Atlet", list(athlete_label_map.keys()))
        athlete_id = athlete_label_map[athlete_label]

        existing_pick = picks_all.get(player, {}).get(athlete_id, "None")
        medal = st.selectbox("Ditt tips", MEDALS, index=MEDALS.index(existing_pick) if existing_pick in MEDALS else 0)

        colA, colB = st.columns(2)
        with colA:
            if st.button("Spara/uppdatera tips", use_container_width=True):
                picks_all.setdefault(player, {})
                picks_all[player][athlete_id] = medal
                save_picks(picks_all)
                st.success("Sparat!")
        with colB:
            if st.button("Ta bort tips för denna atlet", use_container_width=True):
                if player in picks_all and athlete_id in picks_all[player]:
                    del picks_all[player][athlete_id]
                    save_picks(picks_all)
                    st.success("Borttaget!")

    with right:
        st.subheader(f"{player}s sparade tips")
        user_picks = picks_all.get(player, {})
        if not user_picks:
            st.info("Inga tips sparade ännu.")
        else:
            view = athletes.merge(
                pd.DataFrame([{"athlete_id": k, "pick": v} for k, v in user_picks.items()]),
                on="athlete_id",
                how="right"
            )
            view = view[["sport", "name", "athlete_id", "pick"]].sort_values(["sport", "name"]).reset_index(drop=True)
            st.dataframe(view, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Scoreboard")
    st.dataframe(build_scoreboard(athletes, results, picks_all), use_container_width=True, hide_index=True)

    st.subheader("Resultat")
    res_view = results.merge(athletes[["athlete_id", "name", "sport"]], on="athlete_id", how="left")
    res_view = res_view[["sport", "name", "athlete_id", "medal"]].sort_values(["sport", "name"]).reset_index(drop=True)
    st.dataframe(res_view, use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Admin – uppdatera resultat")

    if ADMIN_PASSWORD == "":
        ok = True
    else:
        pwd = st.text_input("Admin-lösenord", type="password")
        ok = (pwd == ADMIN_PASSWORD)

    if not ok:
        st.info("Ange admin-lösenordet (ADMIN_PASSWORD i app.py) för att ändra resultaten.")
    else:
        st.success("Admin-läge aktivt.")

        res = results.merge(athletes[["athlete_id", "name", "sport"]], on="athlete_id", how="left")
        res = res[["sport", "name", "athlete_id", "medal"]].sort_values(["sport", "name"]).reset_index(drop=True)

        updated = []
        for _, row in res.iterrows():
            c1, c2, c3, c4 = st.columns([2.5, 2.5, 2.5, 1.5])
            with c1: st.write(row["sport"])
            with c2: st.write(row["name"])
            with c3: st.write(row["athlete_id"])
            with c4:
                new_medal = st.selectbox(
                    "Medalj",
                    MEDALS,
                    index=MEDALS.index(row["medal"]) if row["medal"] in MEDALS else 0,
                    key=f"admin_{row['athlete_id']}"
                )
            updated.append((row["athlete_id"], new_medal))

        if st.button("Spara resultat"):
            out = pd.DataFrame(updated, columns=["athlete_id", "medal"])
            save_results(out)
            st.success("Resultat sparade!")

with tabs[3]:
    st.subheader("Backup")
    st.download_button(
        "Ladda ner picks.json",
        data=PICKS_JSON.read_bytes() if PICKS_JSON.exists() else b"{}",
        file_name="picks.json",
        mime="application/json",
        use_container_width=True
    )
    st.download_button(
        "Ladda ner results.csv",
        data=RESULTS_CSV.read_bytes() if RESULTS_CSV.exists() else b"athlete_id,medal\n",
        file_name="results.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.divider()
    st.subheader("Restore")
    up_picks = st.file_uploader("Ladda upp picks.json", type=["json"])
    if up_picks is not None:
        try:
            restored = json.loads(up_picks.read().decode("utf-8"))
            save_picks(restored)
            st.success("Återställde picks.json!")
        except Exception as e:
            st.error(f"Kunde inte läsa JSON: {e}")

    up_results = st.file_uploader("Ladda upp results.csv", type=["csv"])
    if up_results is not None:
        try:
            df = pd.read_csv(up_results)
            if not {"athlete_id", "medal"}.issubset(df.columns):
                st.error("results.csv måste ha kolumnerna athlete_id, medal")
            else:
                df["athlete_id"] = df["athlete_id"].astype(str)
                df["medal"] = df["medal"].astype(str)
                df.loc[~df["medal"].isin(MEDALS), "medal"] = "None"
                save_results(df[["athlete_id", "medal"]])
                st.success("Återställde results.csv!")
        except Exception as e:
            st.error(f"Kunde inte läsa CSV: {e}")
