import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg") # agar bisa dijalankan di server/headless tanpa mencoba membuka jendela GUI di layar monitor.
import matplotlib.pyplot as plt

TICKERS = ["BBRI.JK", "BMRI.JK", "BBCA.JK"]
START = "2020-01-01"
END = "2024-12-31"
TRADING_DAYS = 252
RISK_FREE_ANNUAL = 0.06
OUTPUT_FILE = "output/visual_report_saham.png"


# =====================================================================
# Ambil data
# =====================================================================
def get_data(ticker, start=START, end=END):
    """
    Download data harga harian sebuah saham dari Yahoo Finance.

    Parameters
    ----------
    ticker : str   -> contoh "BBRI.JK"
    start  : str   -> format "YYYY-MM-DD"
    end    : str   -> format "YYYY-MM-DD"

    Returns
    -------
    pd.DataFrame dengan index tanggal dan kolom 'Close'.
    Jika download gagal (misal tidak ada koneksi internet),
    fallback ke data simulasi agar fungsi tetap bisa diuji.
    """
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df is None or df.empty:
            raise ValueError(f"Data kosong untuk {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[["Close"]].dropna()
    except Exception as e:
        print(f"[WARN] {ticker}: gagal download data asli ({type(e).__name__}). "
              f"Memakai data simulasi sebagai fallback.")
        return _generate_dummy(ticker, start, end)


def _generate_dummy(ticker, start, end):
    seed = abs(hash(ticker)) % (2 ** 32)
    rng = np.random.default_rng(seed)
    tanggal = pd.bdate_range(start=start, end=end)
    harga_awal = {"BBRI.JK": 4000, "BMRI.JK": 6500, "BBCA.JK": 8000}.get(ticker, 5000)
    ret = rng.normal(0.0004, 0.018, len(tanggal))
    harga = harga_awal * np.exp(np.cumsum(ret))
    return pd.DataFrame({"Close": harga}, index=tanggal)


def kumpulkan_data(tickers):
    """Download semua ticker, gabungkan jadi satu DataFrame kolom = ticker, index = tanggal."""
    data = {}
    for t in tickers:
        df = get_data(t)
        data[t] = df["Close"]
    gabungan = pd.DataFrame(data)
    gabungan = gabungan.dropna()  # pastikan tanggal yang sama untuk semua saham (perlu untuk korelasi)
    return gabungan


# =====================================================================
# Perhitungan
# =====================================================================
def hitung_return(harga_df):
    return harga_df.pct_change().dropna()


def normalisasi_harga(harga_df, basis=100):
    """Normalisasi tiap kolom supaya mulai dari nilai `basis` di hari pertama."""
    return harga_df / harga_df.iloc[0] * basis


def hitung_sharpe(return_df, risk_free=RISK_FREE_ANNUAL):
    mean_tahunan = return_df.mean() * TRADING_DAYS
    std_tahunan = return_df.std() * np.sqrt(TRADING_DAYS)
    return (mean_tahunan - risk_free) / std_tahunan

def skewness(return_df):
    """Menghitung skewness untuk tiap kolom return."""
    return return_df.skew()

def kurtosis(return_df):
    """Menghitung kurtosis untuk tiap kolom return."""
    return return_df.kurtosis()

# =====================================================================
# Plot: 4 subplot dalam 1 figure
# =====================================================================
def buat_laporan_visual(harga_df, outfile=OUTPUT_FILE):
    return_df = hitung_return(harga_df)
    harga_normal = normalisasi_harga(harga_df)
    sharpe = hitung_sharpe(return_df)
    skew = skewness(return_df)
    kurt = kurtosis(return_df)
    korelasi = return_df.corr()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax1, ax2 = axes[0]
    ax3, ax4 = axes[1]

    # ---- Subplot 1 (kiri atas): harga normalisasi, line chart ----
    for ticker in harga_normal.columns:
        ax1.plot(harga_normal.index, harga_normal[ticker], label=ticker, linewidth=1.2)
    ax1.set_title("Harga Normalisasi (basis=100)")
    ax1.set_xlabel("Tanggal")
    ax1.set_ylabel("Indeks Harga (awal=100)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    # ---- Subplot 2 (kanan atas): bar chart Sharpe ratio ----
    warna = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    ax2.bar(sharpe.index, sharpe.values, color=warna[:len(sharpe)])
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_title("Sharpe Ratio per Saham")
    ax2.set_ylabel("Sharpe Ratio")
    for i, v in enumerate(sharpe.values): # tulis nilai Sharpe di atas/bawah bar atau data label
        ax2.text(i, v, f"{v:.2f}", ha="center",
                  va="bottom" if v >= 0 else "top")
    ax2.grid(alpha=0.3, axis="y")

    # ---- Subplot 3 (kiri bawah): histogram distribusi return BBRI ----
    bbri_col = [c for c in return_df.columns if "BBRI" in c][0]
    ax3.hist(return_df[bbri_col], bins=50, color="#1f77b4",
              edgecolor="white", alpha=0.8, density=True)

    # overlay kurva normal teoretis untuk perbandingan visual
    mu, sigma = return_df[bbri_col].mean(), return_df[bbri_col].std() # menghitung mean dan std deviasi dari return BBRI
    x = np.linspace(return_df[bbri_col].min(), return_df[bbri_col].max(), 200) # buat x untuk kurva normal
    normal_curve = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu) / sigma) ** 2)
    ax3.plot(x, normal_curve, color="red", linewidth=1.5, label="Kurva normal teoretis")

    ax3.set_title(f"Distribusi Return Harian {bbri_col}")
    ax3.set_xlabel("Return Harian")
    ax3.set_ylabel("Densitas")
    ax3.legend()
    ax3.grid(alpha=0.3)

    # ---- Subplot 4 (kanan bawah): heatmap korelasi ----
    im = ax4.imshow(korelasi.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax4.set_xticks(range(len(korelasi.columns)))
    ax4.set_yticks(range(len(korelasi.columns)))
    ax4.set_xticklabels(korelasi.columns, rotation=45, ha="right")
    ax4.set_yticklabels(korelasi.columns)
    ax4.set_title("Korelasi Return Antar Saham")

    # tulis angka korelasi di tiap sel
    for i in range(len(korelasi.columns)):
        for j in range(len(korelasi.columns)):
            nilai = korelasi.values[i, j]
            warna_teks = "white" if abs(nilai) > 0.5 else "black"
            ax4.text(j, i, f"{nilai:.2f}", ha="center", va="center", color=warna_teks)

    fig.colorbar(im, ax=ax4, fraction=0.046, pad=0.04)

    # ---- Judul keseluruhan ----
    fig.suptitle("Analisis Visual Saham Perbankan Indonesia 2020-2024",
                 fontsize=16, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.96])  # beri ruang untuk suptitle
    os.makedirs(os.path.dirname(outfile), exist_ok=True) # Buat folder jika belum ada
    plt.savefig(outfile, dpi=120)
    print(f"[OK] Laporan visual disimpan: {outfile}")

    return {"sharpe": sharpe, "korelasi": korelasi, "skewness": skew, "kurtosis": kurt}


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("Mengumpulkan data...")
    harga_df = kumpulkan_data(TICKERS)
    print(f"Data terkumpul: {harga_df.shape[0]} baris x {harga_df.shape[1]} kolom")

    hasil = buat_laporan_visual(harga_df)
    
    print("\n--- Skewness ---")
    print(hasil["skewness"].round(3).to_string())

    print("\n--- Kurtosis ---")
    print(hasil["kurtosis"].round(3).to_string())

    print("\n--- Sharpe Ratio ---")
    print(hasil["sharpe"].round(3).to_string())

    print("\n--- Matriks Korelasi ---")
    print(hasil["korelasi"].round(3).to_string())


if __name__ == "__main__":
    main()
