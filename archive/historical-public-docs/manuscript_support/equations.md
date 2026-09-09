# Equations (clean sources)

## Decision utility and constraints

\[
U(x)=\sum_{i=0}^{5} b_i x_i + \sum_{i<j}s_{ij}x_i x_j
\]

\[
\sum_i x_i=k,\qquad x_i x_j=0\ \forall(i,j)\in C,\qquad x_i\in\{0,1\}
\]

## Penalty energy

\[
E(x)=-U(x)+A\left[\left(\sum_i x_i-k\right)^2+\sum_{(i,j)\in C}x_i x_j\right]
\]

\[
A=1+\sum_i|b_i|+\sum_{i<j}|s_{ij}|
\]

## Hellinger fidelity (distributional)

\[
F(P,Q)=\left(\sum_x\sqrt{P(x)Q(x)}\right)^2
\]

This is agreement of two probability distributions over bitstrings, not quantum state fidelity, not entanglement certification, and not decision accuracy.
