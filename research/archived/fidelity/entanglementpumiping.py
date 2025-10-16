from qns.models.epr import WernerStateEntanglement
from qns.utils import get_rand

init_fidelity = 0.9
th_fidelity = 0.8
p_gen = 0.8

prev_epr = WernerStateEntanglement(fidelity=init_fidelity)

for i in range(100):
    if get_rand() <= 0.8:
        epr = WernerStateEntanglement(fidelity=init_fidelity)
        if prev_epr is not None:
            new_epr = epr.distillation(prev_epr)
            if new_epr is None:
                prev_epr = None
                print("purification failed")
            elif new_epr.fidelity < th_fidelity:
                prev_epr = None
                print(new_epr.fidelity, "current fidelity is low")
            else:
                prev_epr = new_epr
                print(prev_epr.fidelity)
        else:
            prev_epr = epr
            print("new epr generated", prev_epr.fidelity)
    else:
        if prev_epr is not None:
            prev_epr.fidelity = prev_epr.fidelity - 0.05