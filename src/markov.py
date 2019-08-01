import sys
import numpy
from pandas import pandas

"""
Main reference: https://pdfs.semanticscholar.org/0146/d0d16ea44624c48e4cd7afd1646ed4e90c3d.pdf
"""

"""
Let p_ijk be the probability that the defender loses k armies throwing j dice with the attacker 
throwing i dice.
The probs dict contains all those probabilities, so for example probs['11'][0] = 21/36 is the
probability that the defender loses 0 armies throwing 1 dice with the attacker throwing 1 dice
"""
probs = {
    '11': [21/36, 5/12],
    '21': [91/216, 125/216],
    '22': [581/1296, 35/108, 295/1296],
    '31': [441/1296, 855/1296],
    '32': [2275/7776, 2611/7776, 2890/7776],
    '33': [17871/46656, 12348/46656, 10017/46656, 6420/46656]
}

"""
A is the initial number of attacker's armies, while D is the defender's ones
"""
A = 7
D = 4

"""
Compute the absorbing and transient states.
In our case the absorbing states are all those states with a < d, where a and d represent
the actual attacker and defender armies during a battle respectively
"""
absorbing_states = []
transient_states = []
idx_col = 0
for a in range(0, A+1):
    for d in range(0, D+1):
        atta_dice = min(3,a)
        defe_dice = min(3,d)
        if atta_dice >= defe_dice and a > 0 and d > 0:
            transient_states.append((a,d))
        else:
            if a < d and a > 0 and d > 0:
                absorbing_states.append((a,d))
            else:
                absorbing_states[idx_col:idx_col] = [(a,d)]
                idx_col += 1
# Delete the (0,0) state
del absorbing_states[0]

"""
Q = matrix of ordered transient states
R = matrix of ordered absorbing states
"""
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
# Filling those matrices with the precomputed porbabilities
for a in range(1, A+1):
    for d in range(1, D+1):
        atta_dice = min(3,a)
        defe_dice = min(3,d)
        if atta_dice >= defe_dice:
            min_dice = min(atta_dice, defe_dice)
            for k, prob in enumerate(probs[str(atta_dice) + '' + str(defe_dice)]):
                try:
                    Q.loc[(a,d), (a-min_dice+k, d-k)] = prob
                except KeyError:
                    R.loc[(a,d), (a-min_dice+k, d-k)] = prob

""" 
Remove all those absorbing states that contains only Oes, since they don't add
information for the final computation
"""
""" 
R = R.loc[:, (R != 0).any(axis=0)]
absorbing_states = [state for state in absorbing_states if state in R.columns.tolist()] 
"""

""" idx_col = 0
for a in range(1, A+1):
    for d in range(a+1, D+1):
        state = (a,d)
        #Q.drop(state, axis=0, inplace=True)
        #R.drop(state, axis=0, inplace=True)
        if not R[state].isna().all():
            col_to_move = Q[state]
            Q.drop(state, axis=1, inplace=True)
            R.insert(loc=idx_col, column=state, value=col_to_move)
            idx_col += 1
        else:
            Q.drop(state, axis=1, inplace=True) """

""" idx_col = 0
for state in Q.columns[~Q.isna().all()].tolist():
    if state[0] < state[1]:
        col_to_move = Q[state]
        Q.drop(state, axis=0, inplace=True)
        Q.drop(state, axis=1, inplace=True)
        R.drop(state, axis=0, inplace=True)
        R.insert(loc=idx_col, column=state, value=col_to_move)
        idx_col += 1 """

# Theoretical computation: see the main reference
Q_mat = numpy.asmatrix(Q.to_numpy(), dtype=float)
R_mat = numpy.asmatrix(R.to_numpy(), dtype=float)
I_mat = numpy.eye(N=Q_mat.shape[0], M=Q_mat.shape[1])
F_mat = numpy.linalg.inv(I_mat - Q_mat) * R_mat
probs_atta_wins = F_mat[:, range(D, A+D)]\
                    .sum(axis=1)\
                    .reshape((1, F_mat.shape[0]))\
                    .tolist()[0]

atta_wins = numpy.zeros((A,D))
idx_probs_atta_wins = 0
for a in range(1, A+1):
    for d in range(1, D+1):
        atta_dice = min(3,a)
        defe_dice = min(3,d)
        if atta_dice >= defe_dice:
            atta_wins[a-1, d-1] = probs_atta_wins[idx_probs_atta_wins]
            idx_probs_atta_wins += 1

print(atta_wins, '\n')
print(pandas.DataFrame(
        F_mat,
        columns=absorbing_states,
        index=pandas.MultiIndex.from_tuples(transient_states)
    ), '\n')
print(F_mat[-1, :])