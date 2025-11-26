# models.py
# models for EDP simulation

# もつれ(LinkEP)の時間経過によるデコヒーレンスモデル
from numpy import exp

T_MEM: float = 10000  # コヒーレンス時間


def f_link(f: float, dt: float):
    alpha: float = exp(-dt / T_MEM)
    f_new: float = 1 / 4 + alpha * (f - 1 / 4)
    return f_new


# スワップ後フィデリティの計算
def f_swap(f1, f2):
    return 0.25 * (1 + (1 / 3) * (4 * f1 - 1) * (4 * f2 - 1))


# スワップ後遅延の計算
def l_swap(l1, l2, pf=0.8, tau_f=1, tau_c=1):
    return (1.5 * max(l1, l2) + (tau_f + tau_c)) / pf


# ピュリフィケーション後のフィデリティ（簡易モデル）
def f_pur(ft, fs):
    return (ft * fs + (1 - ft) / 3 * (1 - fs) / 3) / (
        ft * fs
        + ft * (1 - fs) / 3
        + (1 - ft) / 3 * fs
        + 5 * (1 - ft) / 3 * (1 - fs) / 3
    )


# ピュリフィケーションの遅延（簡易モデル）
def l_pur(l, f, pp=0.8, tau_p=10, tau_c=10):
    return (l + tau_p + tau_c) / pp


# Bennett (or Deutsch) の1ラウンド（まずはBennettでOK）
def p_pur(ft, fs):
    return (
        ft * fs
        + ft * (1 - fs) / 3
        + (1 - ft) / 3 * fs
        + 5 * ((1 - ft) / 3) * ((1 - fs) / 3)
    )


# iラウンド・エントanglement pumping（ターゲットtに同fidのsをk回）
def pump_fidelity(fs, k):
    f = fs
    for _ in range(k):
        f = f_pur(f, fs)
    return f
