from qns.models.qubit.qubit import Qubit
from qns.models.qubit.const import QUBIT_STATE_0

q0 = Qubit(state=QUBIT_STATE_0, name="q0")
q1 = Qubit(state=QUBIT_STATE_0, name="q1")

from qns.models.qubit.gate import H, CNOT
from qns.models.qubit.gate import OPERATOR_PAULI_I as I
from qns.models.qubit.gate import OPERATOR_PAULI_X as X
from qns.models.qubit.gate import OPERATOR_PAULI_Y as Y
from qns.models.qubit.gate import OPERATOR_PAULI_Z as Z

H(q0)   # hadamard gate = q0.operate(H)
#CNOT(q0, q1)    # controlled-not gate

#q0.stochastic_operate([I, X, Y, Z], [0.7, 0.1, 0.1, 0.1])


print(q0.measure())
