"""Prior-regularized equilibrium of a zero-sum matrix game by magnetic mirror descent (float64).

p1 maximizes and p2 minimizes the p1-perspective payoff M. The fixed point is the KL-regularized
(quantal-response) equilibrium with the network priors as magnets:
    pi1 ∝ rho1 · exp(M pi2 / tau),   pi2 ∝ rho2 · exp(-M^T pi1 / tau)
Log-space simultaneous update (Sokota et al. 2023):
    l <- (l + eta·tau·log rho + eta·g) / (1 + eta·tau),  g1 = M pi2,  g2 = -M^T pi1
Duality gap of the regularized game: tau·lse(log rho1 + M pi2/tau) + tau·lse(log rho2 - M^T pi1/tau)
+ tau·KL(pi1||rho1) + tau·KL(pi2||rho2) >= 0, zero exactly at the fixed point.
"""
from __future__ import annotations

import numpy as np

FLOOR = 1e-12


def _prior(rho, size):
    rho = np.asarray(rho, dtype=np.float64)
    if rho.shape != (size,) or not np.all(np.isfinite(rho)) or np.any(rho < 0) or rho.sum() <= 0:
        raise ValueError("invalid prior")
    rho = np.maximum(rho / rho.sum(), FLOOR)
    return rho / rho.sum()


def _softmax(logits):
    z = np.exp(logits - logits.max())
    return z / z.sum()


def _lse(values):
    top = values.max()
    return top + np.log(np.exp(values - top).sum())


def _kl(p, q):
    mask = p > 0
    return float(np.sum(p[mask] * (np.log(p[mask]) - np.log(q[mask]))))


def gap(M, pi1, pi2, rho1, rho2, tau):
    return float(tau * _lse(np.log(rho1) + M @ pi2 / tau) + tau * _lse(np.log(rho2) - M.T @ pi1 / tau)
                 + tau * _kl(pi1, rho1) + tau * _kl(pi2, rho2))


def solve(M, rho1, rho2, *, tau, iterations, tolerance, eta=None):
    M = np.asarray(M, dtype=np.float64)
    if M.ndim != 2 or 0 in M.shape or not np.all(np.isfinite(M)) or np.abs(M).max() > 1 + 1e-9:
        raise ValueError("payoff matrix must be finite within [-1, 1]")
    if not tau > 0 or iterations < 1:
        raise ValueError("positive tau and iterations required")
    K1, K2 = M.shape
    rho1, rho2 = _prior(rho1, K1), _prior(rho2, K2)
    L = max(float(np.abs(M).max()), 1e-3)
    eta = tau / L**2 if eta is None else float(eta)
    if K1 == 1 or K2 == 1:
        # One side has a single (or no) choice: the other side's regularized best response is closed form.
        pi1 = _softmax(np.log(rho1) + M[:, 0] / tau) if K2 == 1 else np.ones(1)
        pi2 = _softmax(np.log(rho2) - M[0, :] / tau) if K1 == 1 else np.ones(1)
        if K1 == 1 and K2 == 1:
            pi1, pi2 = np.ones(1), np.ones(1)
        steps = 0
    else:
        l1, l2 = np.log(rho1), np.log(rho2)
        a1, a2 = eta * tau * np.log(rho1), eta * tau * np.log(rho2)
        steps = 0
        for steps in range(1, iterations + 1):
            pi1, pi2 = _softmax(l1), _softmax(l2)
            g1, g2 = M @ pi2, -(M.T @ pi1)
            l1 = (l1 + a1 + eta * g1) / (1 + eta * tau)
            l2 = (l2 + a2 + eta * g2) / (1 + eta * tau)
            l1, l2 = l1 - l1.max(), l2 - l2.max()
            if steps % 25 == 0 and gap(M, _softmax(l1), _softmax(l2), rho1, rho2, tau) <= tolerance:
                break
        pi1, pi2 = _softmax(l1), _softmax(l2)
    final_gap = gap(M, pi1, pi2, rho1, rho2, tau)
    value = float(pi1 @ M @ pi2)
    entropy = lambda p: float(-(p * np.log(np.maximum(p, FLOOR))).sum())
    info = dict(shape=[K1, K2], iterations=steps, gap=final_gap, eta=eta, scale=L, tau=tau,
                kl=[_kl(pi1, rho1), _kl(pi2, rho2)], entropy=[entropy(pi1), entropy(pi2)],
                prior_entropy=[entropy(rho1), entropy(rho2)], converged=bool(final_gap <= tolerance or (K1 == 1 or K2 == 1)))
    return pi1, pi2, value, info
