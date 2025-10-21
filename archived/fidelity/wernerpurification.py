from qns.models.epr import WernerStateEntanglement

for _ in range(100):
    epr1 = WernerStateEntanglement(fidelity=0.9)
    epr2 = WernerStateEntanglement(fidelity=0.9)

    epr3 = epr1.distillation(epr=epr2) # purification
    if epr3 is None:
        print(epr3)
    else:
        print(epr3.fidelity)