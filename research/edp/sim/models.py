# models.py
# models for EDP simulation
def Fswap(fl, fr):
    return 0.25 * (1 + (1 / 3) * (4 * fl - 1) * (4 * fr - 1))


# Bennett (or Deutsch) の1ラウンド（まずはBennettでOK）
def p_pur(ft, fs):
    return (
        ft * fs
        + ft * (1 - fs) / 3
        + (1 - ft) / 3 * fs
        + 5 * ((1 - ft) / 3) * ((1 - fs) / 3)
    )


def Fpur(ft, fs):
    return (ft * fs + ((1 - ft) / 3) * ((1 - fs) / 3)) / max(p_pur(ft, fs), 1e-12)


# iラウンド・エントanglement pumping（ターゲットtに同fidのsをk回）
def pump_fidelity(fs, k):
    f = fs
    for _ in range(k):
        f = Fpur(f, fs)
    return f


# 待機モデル（memory-assisted）
def Lswap(ll, lr, pf, tau_f=10e-6, tau_c=0.0):
    return (1.5 * max(ll, lr) + tau_f + tau_c) / max(pf, 1e-12)
