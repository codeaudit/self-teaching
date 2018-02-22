import numpy as np


def create_line_hyp_space(n_features):
    """Creates a hypothesis space of concepts defined by 1D lines"""
    hyp_space = []
    for i in range(1, n_features + 1):
        for j in range(n_features - i + 1):
            hyp = [0 for _ in range(n_features)]
            hyp[j:j + i] = [1 for _ in range(i)]
            hyp_space.append(hyp)
    hyp_space = np.array(hyp_space)
    return hyp_space


def create_boundary_hyp_space(n_features):
    """Creates a hypothesis space of concepts defined by a linear boundary"""
    hyp_space = []
    for i in range(n_features + 1):
        hyp = [1 for _ in range(n_features)]
        hyp[:i] = [0 for _ in range(i)]
        hyp_space.append(hyp)
    hyp_space = np.array(hyp_space)
    return hyp_space
