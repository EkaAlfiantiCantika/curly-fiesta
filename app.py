"""
Aplikasi Perencanaan Geometrik Jalan
  1. Denah trase tikungan (FC / S-C-S / S-S)
  2. Diagram superelevasi
  3. Profil memanjang (garis rencana + lengkung vertikal)

Acuan: TPGJAK Bina Marga 1997 (Tata Cara Perencanaan Geometrik Jalan Antar Kota)
Jalankan: streamlit run app.py
"""
import io
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.ticker import FuncFormatter

st.set_page_config(page_title="Perencanaan Geometrik Jalan", layout="wide")

# ----------------------------------------------------------------------------
# Tabel acuan (TPGJAK 1997): kecepatan rencana -> R min tanpa lengkung peralihan,
# kelandaian maksimum
# ----------------------------------------------------------------------------
V_TAB = [20, 30, 40, 50, 60, 80, 100, 120]
R_FC_TAB = [60, 130, 250, 350, 500, 900, 1500, 2500]
G_MAX_TAB = [10, 10, 10, 9, 8, 6, 5, 3]


def sta_str(s, d=2):
    """Format stasioning km+meter, contoh 0+250.00"""
    return f"{int(s // 1000)}+{s % 1000:0{4 + d}.{d}f}"


def f_max(V):
    return -0.00065 * V + 0.192 if V < 80 else -0.00125 * V + 0.24


def r_min(V, emax):
    return V**2 / (127 * (emax + f_max(V)))


# ----------------------------------------------------------------------------
# Perhitungan tikungan horizontal
# ----------------------------------------------------------------------------
def hitung_tikungan(V, delta, emax, en, Rc, sta_pi):
    fm = f_max(V)
    Rmin = r_min(V, emax)
    Dmax = 181913.53 * (emax + fm) / V**2
    D = 1432.39 / Rc
    e = -emax * D**2 / Dmax**2 + 2 * emax * D / Dmax  # Bina Marga
    e = max(e, en)

    # Panjang lengkung peralihan minimum
    re = 0.035 if V <= 70 else 0.025  # m/m/detik
    Ls_waktu = V * 3 / 3.6
    Ls_shortt = 0.022 * V**3 / (Rc * 0.4) - 2.727 * V * e / 0.4
    Ls_re = (e + en) * V / (3.6 * re)
    Ls_min = max(Ls_waktu, Ls_shortt, Ls_re)
    Ls_pakai = math.ceil(Ls_min / 5) * 5

    R_fc = float(np.interp(V, V_TAB, R_FC_TAB))
    d2 = math.radians(delta / 2)
    r = dict(V=V, delta=delta, emax=emax, en=en, Rc=Rc, fm=fm, Rmin=Rmin,
             Dmax=Dmax, D=D, e=e, Ls_waktu=Ls_waktu, Ls_shortt=Ls_shortt,
             Ls_re=Ls_re, Ls_min=Ls_min, R_fc=R_fc, sta_pi=sta_pi)

    if Rc >= R_fc:
        Tc = Rc * math.tan(d2)
        Ec = Tc * math.tan(d2 / 2)
        Lc = math.radians(delta) * Rc
        r.update(jenis="Full Circle (FC)", Ls=0.0, Ls_sup=Ls_pakai, ths=0.0,
                 dc=delta, Lc=Lc, T=Tc, E=Ec, Xs=0, Ys=0, p=0, k=0)
    else:
        ths = math.degrees(Ls_pakai / (2 * Rc))
        dc = delta - 2 * ths
        Lc = math.radians(dc) * Rc
        Ls = float(Ls_pakai)
        jenis = "Spiral-Circle-Spiral (S-C-S)"
        if Lc < 25:  # Lc terlalu pendek -> Spiral-Spiral
            jenis = "Spiral-Spiral (S-S)"
            ths = delta / 2
            Ls = math.radians(ths) * 2 * Rc
            Lc, dc = 0.0, 0.0
        Xs = Ls * (1 - Ls**2 / (40 * Rc**2))
        Ys = Ls**2 / (6 * Rc)
        p = Ys - Rc * (1 - math.cos(math.radians(ths)))
        k = Xs - Rc * math.sin(math.radians(ths))
        Ts = (Rc + p) * math.tan(d2) + k
        Es = (Rc + p) / math.cos(d2) - Rc
        r.update(jenis=jenis, Ls=Ls, Ls_sup=Ls, ths=ths, dc=dc, Lc=Lc, T=Ts,
                 E=Es, Xs=Xs, Ys=Ys, p=p, k=k)

    r["Ltot"] = r["Lc"] + 2 * r["Ls"]
    r["sta_awal"] = sta_pi - r["T"]
    r["sta_akhir"] = r["sta_awal"] + r["Ltot"]
    return r


def tabel_hasil(r):
    fc = r["jenis"].startswith("Full")
    a, b = ("TC", "CT") if fc else ("TS", "ST")
    rows = [
        ("Jenis tikungan", r["jenis"], ""),
        ("f maks", f"{r['fm']:.4f}", ""),
        ("R minimum", f"{r['Rmin']:.2f}", "m"),
        ("R rencana (Rc)", f"{r['Rc']:.2f}", "m"),
        ("D maks", f"{r['Dmax']:.3f}", "°"),
        ("D rencana", f"{r['D']:.3f}", "°"),
        ("e rencana", f"{r['e'] * 100:.2f}", "%"),
        ("Ls (waktu 3 detik)", f"{r['Ls_waktu']:.2f}", "m"),
        ("Ls (Shortt)", f"{r['Ls_shortt']:.2f}", "m"),
        ("Ls (tingkat perubahan kemiringan)", f"{r['Ls_re']:.2f}", "m"),
        ("Ls dipakai", f"{r['Ls_sup']:.2f}", "m"),
    ]
    if not fc:
        rows += [("θs", f"{r['ths']:.3f}", "°"), ("Δc", f"{r['dc']:.3f}", "°"),
                 ("Xs", f"{r['Xs']:.3f}", "m"), ("Ys", f"{r['Ys']:.3f}", "m"),
                 ("p", f"{r['p']:.3f}", "m"), ("k", f"{r['k']:.3f}", "m")]
    rows += [
        ("Tangen (T)", f"{r['T']:.3f}", "m"),
        ("Eksternal (E)", f"{r['E']:.3f}", "m"),
        ("Lc", f"{r['Lc']:.3f}", "m"),
        ("Panjang tikungan", f"{r['Ltot']:.3f}", "m"),
        (f"STA {a}", sta_str(r["sta_awal"]), ""),
        ("STA PI", sta_str(r["sta_pi"]), ""),
        (f"STA {b}", sta_str(r["sta_akhir"]), ""),
    ]
    return pd.DataFrame(rows, columns=["Parameter", "Nilai", "Satuan"])


# ----------------------------------------------------------------------------
# Gambar 1: denah trase tikungan
# ----------------------------------------------------------------------------
def heading(s, Ls, Lc, Rc, dl):
    Ltot = 2 * Ls + Lc
    th = np.zeros_like(s)
    if Ls > 0:
        ths = Ls / (2 * Rc)
        m = (s > 0) & (s <= Ls)
        th[m] = s[m] ** 2 / (2 * Rc * Ls)
        m = (s > Ls) & (s < Ls + Lc)
        th[m] = ths + (s[m] - Ls) / Rc
        m = (s >= Ls + Lc) & (s <= Ltot)
        th[m] = dl - (Ltot - s[m]) ** 2 / (2 * Rc * Ls)
    else:
        m = (s > 0) & (s <= Ltot)
        th[m] = s[m] / Rc
    th[s > Ltot] = dl
    return th


def fig_denah(r, arah, B):
    sg = 1 if arah == "Kiri" else -1
    Ls, Lc, Rc = r["Ls"], r["Lc"], r["Rc"]
    dl = math.radians(r["delta"])
    Ltot = r["Ltot"]
    ext = math.ceil(max(100, 1.3 * r["T"]) / 10) * 10

    s = np.unique(np.concatenate([np.arange(-ext, Ltot + ext, 0.5),
                                  [0, Ls, Ls + Lc, Ltot]]))
    th = heading(s, Ls, Lc, Rc, dl)
    dS = np.diff(s)
    x = np.concatenate([[0], np.cumsum(dS * (np.cos(th[:-1]) + np.cos(th[1:])) / 2)])
    y = np.concatenate([[0], np.cumsum(dS * (np.sin(th[:-1]) + np.sin(th[1:])) / 2)])
    i0 = np.argmin(np.abs(s))
    x, y = x - x[i0], (y - y[i0]) * sg
    ths_ = th * sg
    nx, ny = -np.sin(ths_), np.cos(ths_)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.plot(x + B / 2 * nx, y + B / 2 * ny, color="gray", lw=1)
    ax.plot(x - B / 2 * nx, y - B / 2 * ny, color="gray", lw=1)
    ax.plot(x, y, "k", lw=1.6, label="As jalan")

    # garis singgung & PI
    pi = np.array([r["T"], 0.0])
    p2 = pi + ext * np.array([math.cos(dl), sg * math.sin(dl)])
    ax.plot([-ext, pi[0], p2[0]], [0, pi[1], p2[1]], "b--", lw=0.9,
            label="Garis singgung")
    ax.plot(*pi, "ks")
    ax.annotate(f"PI\nΔ = {r['delta']:.1f}°\nSTA {sta_str(r['sta_pi'])}", pi,
                textcoords="offset points", xytext=(8, -34 * sg), fontsize=8)

    # titik penting
    fc = r["jenis"].startswith("Full")
    if fc:
        keys = [("TC", 0), ("CT", Lc)]
    elif Lc == 0:
        keys = [("TS", 0), ("SC=CS", Ls), ("ST", Ltot)]
    else:
        keys = [("TS", 0), ("SC", Ls), ("CS", Ls + Lc), ("ST", Ltot)]
    pts = {}
    for nm, sk in keys:
        px, py = np.interp(sk, s, x), np.interp(sk, s, y)
        pts[nm] = (px, py, sk)
        ax.plot(px, py, "ro")
        ax.annotate(f"{nm}\n{sta_str(r['sta_awal'] + sk)}", (px, py),
                    textcoords="offset points", xytext=(-14, 10 * sg + (-24 if sg < 0 else 0)),
                    fontsize=8, color="darkred")

    # pusat lingkaran
    s_ref = Ls if not fc else 0
    cx = np.interp(s_ref, s, x) + Rc * np.interp(s_ref, s, nx)
    cy = np.interp(s_ref, s, y) + Rc * np.interp(s_ref, s, ny)
    ax.plot(cx, cy, "g+", ms=10)
    for nm, (px, py, _) in pts.items():
        if nm in ("SC", "CS", "SC=CS", "TC", "CT"):
            ax.plot([cx, px], [cy, py], "g:", lw=0.8)
    ax.annotate(f"R = {Rc:.0f} m", (cx, cy), textcoords="offset points",
                xytext=(6, 4), fontsize=8, color="green")

    # tick stasioning tiap 50 m
    sta0 = r["sta_awal"]
    for st_ in np.arange(math.ceil((sta0 - ext) / 50) * 50, sta0 + Ltot + ext, 50):
        sv = st_ - sta0
        if sv < s[0] or sv > s[-1]:
            continue
        px, py = np.interp(sv, s, x), np.interp(sv, s, y)
        qx, qy = np.interp(sv, s, nx), np.interp(sv, s, ny)
        ax.plot([px - (B / 2 + 2) * qx, px + (B / 2 + 2) * qx],
                [py - (B / 2 + 2) * qy, py + (B / 2 + 2) * qy], color="gray", lw=0.6)
        ax.text(px - (B / 2 + 4) * qx, py - (B / 2 + 4) * qy,
                f"{int(st_ // 1000)}+{st_ % 1000:03.0f}", fontsize=6, ha="center",
                va="center", color="gray")

    ax.set_aspect("equal")
    ax.grid(alpha=0.25)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Denah Trase Tikungan - {r['jenis']} (tikungan ke {arah.lower()})")
    ax.legend(loc="best", fontsize=8)
    return fig


# ----------------------------------------------------------------------------
# Gambar 2: diagram superelevasi
# ----------------------------------------------------------------------------
def fig_super(r):
    e, n = r["e"] * 100, r["en"] * 100
    Ls = r["Ls_sup"]
    fc = r["jenis"].startswith("Full")
    if fc:  # 3/4 Ls sebelum TC, 1/4 Ls pada lengkung
        a, b = r["sta_awal"] - 0.75 * Ls, r["sta_awal"] + 0.25 * Ls
        c, d = r["sta_akhir"] - 0.25 * Ls, r["sta_akhir"] + 0.75 * Ls
        names = ["Awal peralihan", "TC", "CT", "Akhir peralihan"]
    else:
        a, b = r["sta_awal"], r["sta_awal"] + r["Ls"]
        c, d = b + r["Lc"], b + r["Lc"] + r["Ls"]
        names = ["TS", "SC", "CS", "ST"]
    pad = 0.3 * Ls
    xr = (b - a) * 2 * n / (e + n)       # tepi luar mencapai +en
    x0 = (b - a) * n / (e + n)           # tepi luar mencapai 0 %
    outer = [(a - pad, -n), (a, -n), (b, e), (c, e), (d, -n), (d + pad, -n)]
    inner = [(a - pad, -n), (a + xr, -n), (b, -e), (c, -e), (d - xr, -n), (d + pad, -n)]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(*zip(*outer), "r-", lw=2, label="Tepi perkerasan luar")
    ax.plot(*zip(*inner), "b-", lw=2, label="Tepi perkerasan dalam")
    ax.axhline(0, color="k", lw=0.8)
    ax.fill_between(*zip(*outer), 0, alpha=0.05, color="r")
    for nm, xv in zip(names, [a, b, c, d]):
        ax.axvline(xv, color="gray", ls=":", lw=0.9)
        ax.text(xv, ax.get_ylim()[1], f"{nm}\n{sta_str(xv)}", ha="center",
                va="bottom", fontsize=8)
    ax.plot([a + x0, d - x0], [0, 0], "ko", ms=4)
    ax.annotate(f"+e = {e:.2f}%", (b, e), textcoords="offset points", xytext=(5, 6))
    ax.annotate(f"-e = {-e:.2f}%", (b, -e), textcoords="offset points", xytext=(5, -14))
    ax.annotate(f"en = -{n:.1f}%", (a - pad, -n), textcoords="offset points",
                xytext=(0, -14))
    ax.set_ylabel("Kemiringan melintang (%)")
    ax.set_xlabel("Stasioning")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: sta_str(v, 0)))
    ax.set_ylim(-e * 1.35, e * 1.45)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower center", ncol=2, fontsize=8)
    ax.set_title("Diagram Superelevasi (rotasi pada sumbu jalan)", pad=34)
    return fig


# ----------------------------------------------------------------------------
# Profil memanjang
# ----------------------------------------------------------------------------
def hitung_profil(pvi, V):
    d = pvi.dropna().sort_values(pvi.columns[0]).reset_index(drop=True)
    sta = d.iloc[:, 0].to_numpy(float)
    el = d.iloc[:, 1].to_numpy(float)
    lvm = d.iloc[:, 2].to_numpy(float)
    g = np.diff(el) / np.diff(sta)  # m/m
    Jh = 0.278 * V * 2.5 + V**2 / (254 * 0.40)  # jarak pandang henti

    kurva = []
    for i in range(1, len(sta) - 1):
        A = (g[i] - g[i - 1]) * 100
        if abs(A) < 1e-9:
            continue
        a = abs(A)
        if A < 0:   # cembung
            L = a * Jh**2 / 399
            if L < Jh:
                L = 2 * Jh - 399 / a
        else:       # cekung
            L = a * Jh**2 / (120 + 3.5 * Jh)
            if L < Jh:
                L = 2 * Jh - (120 + 3.5 * Jh) / a
        L = math.ceil(max(L, 0.6 * V, V * 3 / 3.6) / 10) * 10
        if lvm[i] > 0:
            L = lvm[i]
        kurva.append(dict(i=i, sta=sta[i], el=el[i], A=A, Lv=L, Ev=a * L / 800,
                          bvc=sta[i] - L / 2, evc=sta[i] + L / 2,
                          jenis="Cembung" if A < 0 else "Cekung",
                          g1=g[i - 1], g2=g[i]))

    x = np.arange(sta[0], sta[-1] + 0.01, 1.0)
    y = np.interp(x, sta, el)
    for k in kurva:
        m = (x >= k["bvc"]) & (x <= k["evc"])
        dx = x[m] - k["bvc"]
        yb = k["el"] - k["g1"] * k["Lv"] / 2
        y[m] = yb + k["g1"] * dx + (k["g2"] - k["g1"]) / (2 * k["Lv"]) * dx**2
    return dict(sta=sta, el=el, g=g * 100, kurva=kurva, x=x, y=y, Jh=Jh)


def fig_profil(P, tanah, tik):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    t = tanah.dropna().sort_values(tanah.columns[0])
    ax.plot(t.iloc[:, 0], t.iloc[:, 1], color="saddlebrown", ls="--", marker="o",
            ms=3, label="Tanah asli")
    ax.plot(P["x"], P["y"], "k", lw=2, label="Garis rencana")
    ax.plot(P["sta"], P["el"], "r^", label="PPV")
    for k in P["kurva"]:
        ax.axvline(k["bvc"], color="gray", ls=":", lw=0.8)
        ax.axvline(k["evc"], color="gray", ls=":", lw=0.8)
        ax.annotate(f"Lv={k['Lv']:.0f} m\nEv={k['Ev']:.2f} m", (k["sta"], k["el"]),
                    textcoords="offset points",
                    xytext=(0, 12 if k["A"] < 0 else -30), ha="center", fontsize=7)
    for i, gi in enumerate(P["g"]):
        xm = (P["sta"][i] + P["sta"][i + 1]) / 2
        ym = (P["el"][i] + P["el"][i + 1]) / 2
        ax.text(xm, ym, f"{gi:+.2f}%", fontsize=8, color="navy", ha="center",
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))
    if tik:
        ax.axvspan(tik[0], tik[1], color="orange", alpha=0.15, label="Tikungan")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: sta_str(v, 0)))
    ax.set_xlabel("Stasioning")
    ax.set_ylabel("Elevasi (m)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    ax.set_title("Profil Memanjang")
    return fig


def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Antarmuka
# ----------------------------------------------------------------------------
st.title("Perencanaan Geometrik Jalan")
st.caption("Tikungan horizontal, superelevasi, dan profil memanjang - acuan TPGJAK Bina Marga 1997")

with st.sidebar:
    st.header("Data input")
    V = st.number_input("Kecepatan rencana Vr (km/jam)", 20, 120, 60, 10)
    delta = st.number_input("Sudut tikungan Δ (°)", 1.0, 179.0, 40.0, 0.5)
    emax = st.number_input("e maks (%)", 4.0, 12.0, 10.0, 0.5) / 100
    en = st.number_input("Kemiringan normal en (%)", 1.0, 4.0, 2.0, 0.5) / 100
    Rmin = r_min(V, emax)
    st.caption(f"R minimum = {Rmin:.1f} m")
    mode = st.radio("Jari-jari tikungan Rc", ["Otomatis (Rmin dibulatkan)", "Manual"])
    if mode.startswith("Oto"):
        Rc = float(math.ceil(Rmin / 10) * 10)
        st.caption(f"Rc = {Rc:.0f} m")
    else:
        Rc = st.number_input("Rc (m)", 10.0, 5000.0, 150.0, 5.0)
    sta_pi = st.number_input("STA PI (m)", 0.0, 100000.0, 250.0, 10.0)
    arah = st.radio("Arah tikungan", ["Kanan", "Kiri"], horizontal=True)
    B = st.number_input("Lebar badan jalan (m)", 3.0, 30.0, 7.0, 0.5)

r = hitung_tikungan(V, delta, emax, en, Rc, sta_pi)
if Rc < Rmin:
    st.error(f"Rc = {Rc:.1f} m lebih kecil dari R minimum ({Rmin:.1f} m). Perbesar Rc.")
if r["jenis"].endswith("(S-S)") and r["Ls"] < r["Ls_min"]:
    st.warning("Ls pada tikungan S-S lebih pendek dari Ls minimum. Perbesar Rc.")

tab1, tab2, tab3, tab4 = st.tabs(["Denah tikungan", "Diagram superelevasi",
                                  "Profil memanjang", "Hasil hitungan"])

with tab1:
    f1 = fig_denah(r, arah, B)
    st.pyplot(f1)
    st.download_button("Unduh gambar (PNG)", png(f1), "denah_tikungan.png", "image/png")

with tab2:
    f2 = fig_super(r)
    st.pyplot(f2)
    st.download_button("Unduh gambar (PNG)", png(f2), "diagram_superelevasi.png", "image/png")

with tab3:
    st.write("Isi tabel PPV (titik perpotongan garis kelandaian) dan tanah asli. "
             "Kolom Lv = 0 berarti panjang lengkung vertikal dihitung otomatis.")
    c1, c2 = st.columns(2)
    with c1:
        pvi = st.data_editor(
            pd.DataFrame({"STA (m)": [0.0, 200.0, 400.0, 600.0],
                          "Elevasi rencana (m)": [100.0, 104.0, 102.0, 106.0],
                          "Lv manual (m)": [0.0, 0.0, 0.0, 0.0]}),
            num_rows="dynamic", key="pvi", hide_index=True)
    with c2:
        tanah = st.data_editor(
            pd.DataFrame({"STA (m)": [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
                          "Elevasi tanah asli (m)": [100.5, 102.3, 103.0, 103.4, 102.6, 103.9, 105.2]}),
            num_rows="dynamic", key="tanah", hide_index=True)

    pvi = pvi.fillna(0.0)
    if len(pvi.dropna()) >= 2 and pvi.iloc[:, 0].is_unique:
        P = hitung_profil(pvi, V)
        gmax = float(np.interp(V, V_TAB, G_MAX_TAB))
        for i, gi in enumerate(P["g"]):
            if abs(gi) > gmax:
                st.warning(f"Kelandaian segmen {i + 1} = {gi:.2f}% melebihi batas {gmax:.0f}% untuk Vr {V} km/jam.")
        for k in P["kurva"]:
            lm = min(P["sta"][k["i"]] - P["sta"][k["i"] - 1], P["sta"][k["i"] + 1] - P["sta"][k["i"]])
            if k["Lv"] / 2 > lm:
                st.warning(f"Lengkung vertikal di STA {sta_str(k['sta'], 0)} saling bertumpuk dengan PPV tetangga.")
        f3 = fig_profil(P, tanah, (r["sta_awal"], r["sta_akhir"]))
        st.pyplot(f3)
        st.download_button("Unduh gambar (PNG)", png(f3), "profil_memanjang.png", "image/png")

        st.caption(f"Jarak pandang henti Jh = {P['Jh']:.1f} m")
        if P["kurva"]:
            st.subheader("Lengkung vertikal")
            st.dataframe(pd.DataFrame([{
                "STA PPV": sta_str(k["sta"], 0), "Jenis": k["jenis"],
                "g1 (%)": round(k["g1"] * 100, 2), "g2 (%)": round(k["g2"] * 100, 2),
                "A (%)": round(abs(k["A"]), 2), "Lv (m)": k["Lv"], "Ev (m)": round(k["Ev"], 3),
                "STA PLV": sta_str(k["bvc"], 0), "STA PTV": sta_str(k["evc"], 0)}
                for k in P["kurva"]]), hide_index=True)

        t = tanah.dropna().sort_values(tanah.columns[0])
        xs = np.arange(math.ceil(P["x"][0] / 50) * 50, P["x"][-1] + 0.1, 50)
        rn = np.interp(xs, P["x"], P["y"])
        ta = np.interp(xs, t.iloc[:, 0], t.iloc[:, 1])
        st.subheader("Galian / timbunan tiap 50 m")
        st.dataframe(pd.DataFrame({
            "STA": [sta_str(v, 0) for v in xs], "Elevasi rencana (m)": rn.round(3),
            "Elevasi tanah (m)": ta.round(3), "Selisih (m)": (rn - ta).round(3),
            "Keterangan": np.where(rn - ta > 0, "Timbunan", "Galian")}), hide_index=True)
    else:
        st.info("Isi minimal 2 PPV dengan STA yang berbeda.")

with tab4:
    st.dataframe(tabel_hasil(r), hide_index=True, height=800)
