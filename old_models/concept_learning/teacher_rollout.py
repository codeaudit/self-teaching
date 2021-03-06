import numpy as np
from models.active_learner import ActiveLearner


class TeacherRollout:
    def __init__(self, n_features, n_steps):
        self.n_features = n_features
        self.n_labels = 2
        self.n_steps = n_steps
        self.observed_features = np.array([])
        self.observed_labels = np.array([])
        self.n_obs = 0
        self.features = np.arange(self.n_features)
        self.labels = np.arange(self.n_labels)
        self.hyp_space = self.create_boundary_hyp_space()
        self.n_hyp = len(self.hyp_space)
        self.learner_prior = np.array([[[1 / self.n_hyp
                                         for _ in range(self.n_labels)]
                                        for _ in range(self.n_features)]
                                       for _ in range(self.n_hyp)])
        self.teacher_prior = np.array([[[1 / self.n_hyp
                                         for _ in range(self.n_labels)]
                                        for _ in range(self.n_features)]
                                       for _ in range(self.n_hyp)])
        self.teaching_posterior = np.array([[[1 / self.n_hyp
                                              for _ in range(self.n_labels)]
                                             for _ in range(self.n_features)]
                                            for _ in range(self.n_hyp)])
        self.learner_posterior = self.learner_prior
        self.true_hyp_idx = np.random.randint(len(self.hyp_space))
        self.true_hyp = self.hyp_space[self.true_hyp_idx]
        self.posterior_true_hyp = np.zeros(self.n_features + 1)
        self.posterior_true_hyp[0] = 1 / self.n_hyp
        self.ci_iter = 0

    def create_hyp_space(self):
        """Creates a hypothesis space of line concepts"""
        hyp_space = []
        for i in range(1, self.n_features + 1):
            for j in range(self.n_features - i + 1):
                hyp = [0 for _ in range(self.n_features)]
                hyp[j:j + i] = [1 for _ in range(i)]
                hyp_space.append(hyp)
        hyp_space = np.array(hyp_space)
        return hyp_space

    def create_boundary_hyp_space(self):
        """Creates a hypothesis space of concepts defined by a linear boundary"""
        hyp_space = []
        for i in range(self.n_features + 1):
            hyp = [1 for _ in range(self.n_features)]
            hyp[:i] = [0 for _ in range(i)]
            hyp_space.append(hyp)
        hyp_space = np.array(hyp_space)
        return hyp_space

    def likelihood(self):
        """Calculates the likelihood of observing all possible pairs of data points"""
        # returns a 66 x 11 x 2 matrix

        lik = np.ones((self.n_hyp, self.n_features, self.n_labels))

        for i, hyp in enumerate(self.hyp_space):
            for j, feature in enumerate(self.features):
                for k, label in enumerate(self.labels):
                    if hyp[feature] == label:
                        lik[i, j, k] = 1
                    else:
                        lik[i, j, k] = 0
        return lik

    def get_learner_posterior(self):
        return self.learner_posterior

    def get_teaching_posterior(self):
        return self.teaching_posterior

    def get_true_hypothesis(self):
        return self.true_hyp

    def set_learner_posterior(self, learner_posterior):
        self.learner_posterior = learner_posterior

    def set_teaching_posterior(self, teaching_posterior):
        self.teaching_posterior = teaching_posterior

    def set_true_hypothesis(self, true_hyp):
        self.true_hyp = true_hyp
        self.true_hyp_idx = np.where(self.true_hyp in self.hyp_space)[0]

    def update_learner_posterior(self):
        """Calculates the unnormalized posterior across all
        possible feature/label observations"""

        lik = self.likelihood()  # p(y|x, h)
        teaching_posterior = self.get_teaching_posterior()
        # replace zeros with small prob
        teaching_posterior[np.where(
            teaching_posterior == 0.0)] = 10 ** -10

        # scale teaching posterior
        # teaching_posterior = teaching_posterior ** 0.25 / \
        #     np.exp(teaching_posterior) ** 0.25

        # calculate posterior
        # p(h|x, y) = p(y|x, h) * p(x|h) * p(h)
        self.learner_posterior = lik * self.learner_posterior * \
            teaching_posterior  # use existing posterior as prior

        # normalize across each hypothesis
        self.learner_posterior = np.nan_to_num(self.learner_posterior /
                                               np.sum(self.learner_posterior, axis=0))

    def rollout(self):
        # create active learners and set true hypothesis for each learner
        active_learners = [ActiveLearner(self.n_features)
                           for _ in range(self.n_hyp)]

        # run active learner for n steps
        for i in range(len(active_learners)):
            active_learners[i].set_true_hypothesis(self.hyp_space[i])
            active_learners[i].run(n_steps=self.n_steps)

        # construct matrix of posteriors from each active learner, p(h'|h*)
        transition_prob = np.zeros((self.n_hyp, self.n_hyp))
        for i in range(len(active_learners)):
            transition_prob[i, :] = active_learners[i].posterior
        self.transition_prob_matrix = transition_prob

        # calculate p(x|h*) = p(x|h') * p(h'|h*) and marginalize across all hypotheses
        transition_prob = np.broadcast_to(transition_prob, (self.n_labels,
                                                            self.n_features,
                                                            self.n_hyp,
                                                            self.n_hyp)).T

        self.transition_prob = transition_prob

    def conditional_feature_prob(self):
        """Calculates p(x|h)"""
        # calculate p(x|h) using the same method as self teaching
        prob_joint_data = np.array([[1 / (self.n_features * self.n_labels)
                                     for _ in range(self.n_labels)]
                                    for _ in range(self.n_features)])  # p(x, y)

        prob_joint_data = np.tile(prob_joint_data, (self.n_hyp, 1, 1))

        # multiply with posterior to get overall joint
        # p(h, x, y) = p(h|x, y) * p(x, y)
        learner_posterior = self.get_learner_posterior()
        learner_posterior[np.where(learner_posterior == 0.0)] = 10 ** -10
        prob_joint = learner_posterior * prob_joint_data

        # marginalize over y, i.e. p(h, x), and broadcast result
        prob_joint_hyp_features = np.sum(prob_joint, axis=2)
        prob_joint_hyp_features = np.repeat(
            prob_joint_hyp_features, self.n_labels).reshape(
                self.n_hyp, self.n_features, self.n_labels)

        # get conditional prob, i.e. p(x|h) = p(h, x) / \sum_x p(h, x)
        prob_conditional_features = prob_joint_hyp_features / \
            np.repeat(np.sum(prob_joint_hyp_features, axis=1), self.n_features).reshape(
                self.n_hyp, self.n_features, self.n_labels)
        prob_conditional_features = np.nan_to_num(prob_conditional_features)

        # print("prob conditional")
        # print(prob_conditional_features)

        return prob_conditional_features

    def update_teaching_posterior(self):
        """Calculates the posterior for self-teaching with rollout"""

        prob_conditional_features = self.conditional_feature_prob()

        # calculate teaching posterior differently depending on number of observations
        if self.n_obs < self.n_steps:
            # p(x|h*) = sum_h* p(x|h') * p(h'|h*)
            self.teaching_posterior = np.sum(
                prob_conditional_features * self.transition_prob, axis=0)
        else:
            # print("n obs", self.n_obs)
            teaching_posterior = np.sum(
                prob_conditional_features * self.learner_posterior, axis=(0, 2))

            # normalize
            teaching_posterior = teaching_posterior / \
                np.sum(teaching_posterior)

            # braodcast
            teaching_posterior = np.broadcast_to(teaching_posterior,
                                                 (self.n_hyp,
                                                  self.n_labels,
                                                  self.n_features))

            # save posterior
            self.teaching_posterior = np.array(
                [post.T for post in teaching_posterior])

            # print(self.teaching_posterior)

            # print(self.teaching_posterior)
            # TODO: check if symmetric
            assert np.all(
                self.teaching_posterior[:, :, 0] ==
                self.teaching_posterior[:, :, 1])

    def sample_teaching_posterior(self):
        """Sample a data point based off the self-teaching posterior"""

        # get teaching posterior and marginalize across all possible hypotheses
        teaching_posterior = self.get_teaching_posterior()
        if self.n_obs < self.n_steps:
            # while using rollout, select posterior of actual hypothesis
            # teaching_posterior = teaching_posterior[self.true_hyp_idx]

            # get teacher prior
            teacher_prior = self.transition_prob_matrix[self.true_hyp_idx, :]

            # calculate teaching posterior
            teaching_posterior = (self.teaching_posterior.T * teacher_prior).T

            teaching_posterior = np.sum(teaching_posterior, axis=0)

            # get teaching posterior

            # note: summing over y to get this result
            teaching_posterior_sample = np.sum(teaching_posterior, axis=1)
        else:
            # when using self teaching, average across all hypotheses instead
            # print(self.teaching_posterior)
            teaching_posterior_sample = teaching_posterior[0, :, 0]
            # teaching_posterior = np.sum(
            #     self.teaching_posterior * self.learner_posterior, axis=0)
            # print(teaching_posterior)
            # teaching_posterior = self.teaching_posterior

        # set probability of selecting already observed features to be zero
        self.observed_features = self.observed_features.astype(int)

        if self.observed_features.size != 0:
            teaching_posterior_sample[self.observed_features] = 0

        # normalize teaching posterior sample
        teaching_posterior_sample = np.nan_to_num(teaching_posterior_sample /
                                                  np.nansum(teaching_posterior_sample))

        # select new teaching point proportionally
        if np.all(np.sum(teaching_posterior_sample)) != 0:
            teaching_data = np.random.choice(np.arange(self.n_features),
                                             p=teaching_posterior_sample /
                                             np.nansum(teaching_posterior_sample))
            teaching_data = np.nan_to_num(teaching_data)
        else:
            assert False

        return teaching_data

    def run(self):
        """Run self-teaching with rollout until a correct hypothesis is determined"""

        hypothesis_found = False

        # calculate transition prob at the beginning
        self.rollout()
        # print(self.transition_prob_matrix)

        while hypothesis_found != True and self.n_obs < self.n_features:
            ci_iters = 10
            for i in range(ci_iters):
                self.ci_iter = i
                self.update_learner_posterior()
                self.update_teaching_posterior()

            # sample data point from self-teaching
            teaching_sample_feature = self.sample_teaching_posterior()
            teaching_sample_label = self.true_hyp[teaching_sample_feature]
            self.observed_features = np.append(
                self.observed_features, teaching_sample_feature)
            self.observed_labels = np.append(
                self.observed_labels, teaching_sample_label)

            # get learner posteiror and broadcast
            updated_learner_posterior = self.learner_posterior[:, teaching_sample_feature,
                                                               teaching_sample_label]

            # check for valid probability distribution
            assert np.isclose(np.sum(updated_learner_posterior), 1.0)

            # update new learner posterior by broadcasting
            self.learner_posterior = np.repeat(updated_learner_posterior, self.n_labels *
                                               self.n_features).reshape(self.n_hyp,
                                                                        self.n_features,
                                                                        self.n_labels)

            # check if any hypothesis has probability one
            if np.any(updated_learner_posterior == 1.0) and \
               self.true_hyp_idx != np.asscalar((np.where(updated_learner_posterior == 1.0)[0])):
                print("n steps", self.n_steps)
                print(
                    "error, learner converged to the wrong hypothesis, but will continue")
                print("true hyp", self.true_hyp_idx)
                print("guess hyp", np.asscalar(
                    (np.where(updated_learner_posterior == 1.0)[0])))
                # assert False

            if np.any(updated_learner_posterior == 1.0) and \
               self.true_hyp_idx == \
               np.asscalar((np.where(updated_learner_posterior == 1.0))[0]):
                hypothesis_found = True
                true_hyp_found_idx = np.where(
                    updated_learner_posterior == 1.0)
                # print("hypothesis found! in", self.n_obs + 1, "steps")
                # print(updated_learner_posterior)
                # print("true hyp", self.true_hyp_idx)
                # print("guess hyp", np.asscalar(true_hyp_found_idx[0]))
                self.posterior_true_hyp[self.n_obs + 1:] = 1

                # check that true_hyp_found_idx is the true idx
                assert self.true_hyp_idx == np.asscalar(
                    true_hyp_found_idx[0])

            # increment observations
            self.n_obs += 1

            self.posterior_true_hyp[self.n_obs] = updated_learner_posterior[self.true_hyp_idx]

        return self.n_obs, self.posterior_true_hyp
