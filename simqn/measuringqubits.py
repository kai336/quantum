from qns.models.qubit.qubit import Qubit
from qns.models.qubit.const import QUBIT_STATE_0, QUBIT_STATE_1, QUBIT_STATE_L, QUBIT_STATE_N, QUBIT_STATE_P, QUBIT_STATE_R
from qns.models.qubit.gate import H, CNOT
from qns.models.qubit.gate import OPERATOR_PAULI_I as I
from qns.models.qubit.gate import OPERATOR_PAULI_X as X
from qns.models.qubit.gate import OPERATOR_PAULI_Y as Y
from qns.models.qubit.gate import OPERATOR_PAULI_Z as Z

def meas0():
    q0 = Qubit(state=QUBIT_STATE_0, name="q0")
    return q0.measure()

def meas1():
    q1 = Qubit(state=QUBIT_STATE_1, name="q1")
    return q1.measure()

def measp():
    qp = Qubit(state=QUBIT_STATE_P, name="qp")
    return qp.measure()

def measn():
    qn = Qubit(state=QUBIT_STATE_N, name="qn")
    return qn.measure()

def measr():
    qr = Qubit(state=QUBIT_STATE_R, name="qr")
    return qr.measure()

def measl():
    ql = Qubit(state=QUBIT_STATE_L, name="ql")
    return ql.measure()


def MEASURE(STATE, NUM):
    if STATE == '0':
        for i in range(NUM):
            meas0()
    if STATE == '1':
        for i in range(NUM):
            meas1()
    if STATE == 'p':
        for i in range(NUM):
            measp()
    if STATE == 'n':
        for i in range(NUM):
            measn()
    if STATE == 'r':
        for i in range(NUM):
            measr()
    if STATE == 'l':
        for i in range(NUM):
            measl()


# state, num = input().split()
# num = int(num)
# MEASURE(state, num)

import numpy as np

num = 100000
sum = np.zeros(4)
for i in range(num):
    sum += np.array([measp(), measn(), measr(), measl()])
ans = sum / np.array([num, num, num, num])

print(ans)