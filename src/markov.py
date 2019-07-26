import numpy
from pandas import pandas

probs = {
    '11': [21/36, 5/12],
    '21': [91/216, 125/216],
    '22': [581/1296, 35/108, 295/1296],
    '31': [441/1296, 855/1296],
    '32': [2275/7776, 2611/7776, 2890/7776],
    '33': [17871/46656, 12348/46656, 10017/46656, 6420/46656]
}
A = 6
D = 6
absorbing_states = []
transient_states = []
for i in range(0, A+1):
    for j in range(0, D+1):
        if i == 0 or j == 0:
            absorbing_states.append((i,j))
        else:
            transient_states.append((i,j))
absorbing_states = absorbing_states[1:]

Q = pandas.DataFrame(
        0,
        columns=transient_states,
        index=pandas.MultiIndex.from_tuples(transient_states)
    )
R = pandas.DataFrame(
        0, 
        columns=absorbing_states,
        index=pandas.MultiIndex.from_tuples(transient_states)
    ) 

for i in range(1, A+1):
    for j in range(1, D+1):
        if i >= j:
            for k, prob in enumerate(probs[str(min(3, i)) + '' + str(min(3, j))]):
                try:
                    Q[(i-j+k, j-k)].loc[(i,j)] = prob
                except KeyError:
                    R[(i-j+k, j-k)].loc[(i,j)] = prob

idx_col = 0
for i in range(1, A+1):
    for j in range(i+1, D+1):
        state = (i,j)
        Q.drop(state, axis=0, inplace=True)
        R.drop(state, axis=0, inplace=True)
        if not Q[state].isna().all():
            col_to_move = Q[state]
            Q.drop(state, axis=1, inplace=True)
            R.insert(loc=idx_col, column=state, value=col_to_move)
            idx_col += 1
        else:
            Q.drop(state, axis=1, inplace=True)

""" idx_col = 0
for state in Q.columns[~Q.isna().all()].tolist():
    if state[0] < state[1]:
        col_to_move = Q[state]
        Q.drop(state, axis=0, inplace=True)
        Q.drop(state, axis=1, inplace=True)
        R.drop(state, axis=0, inplace=True)
        R.insert(loc=idx_col, column=state, value=col_to_move)
        idx_col += 1 """

""" Q.fillna(0, inplace=True)
R.fillna(0, inplace=True) """

Q_mat = numpy.asmatrix(Q.to_numpy(), dtype=float)
R_mat = numpy.asmatrix(R.to_numpy(), dtype=float)
I = numpy.eye(N=Q_mat.shape[0], M=Q_mat.shape[1])
F = numpy.linalg.inv(I - Q_mat) * R_mat
probs_atta_wins = F[:, range(F.shape[1]-A, F.shape[1])]\
                    .sum(axis=1)\
                    .reshape((1, F.shape[0]))\
                    .tolist()[0]

n = int(numpy.sqrt(len(probs_atta_wins)*2))
idx = numpy.tril_indices(n, k=0, m=n)
atta_wins = numpy.zeros((n,n))
atta_wins[idx] = probs_atta_wins
print(atta_wins)