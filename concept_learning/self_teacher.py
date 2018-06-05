import numpy as np
import concept_learning.utils as utils


class SelfTeacher:
    def __init__(self, n_features, hyp_space_type,
                 true_hyp=None, sampling="max"):
        self.n_features = n_features
        self.n_labels = 2
        self.observed_features = np.array([])
        self.observed_labels = np.array([])
        self.n_obs = 0
        self.features = np.arange(self.n_features)
        self.labels = np.arange(self.n_labels)
        if hyp_space_type == "boundary":
            self.hyp_space = utils.create_boundary_hyp_space(self.n_features)
        elif hyp_space_type == "line":
            self.hyp_space = utils.create_line_hyp_space(self.n_features)
        self.n_hyp = len(self.hyp_space)
        self.learner_prior = (1 / self.n_hyp) * \
            np.ones((self.n_hyp, self.n_features, self.n_labels))
        self.teacher_prior = (1 / self.n_features) * \
            np.ones((self.n_hyp, self.n_features, self.n_labels))
        self.self_teaching_posterior = (1 / self.n_hyp) * \
            np.ones((self.n_hyp, self.n_features, self.n_labels))
        self.learner_posterior = self.learner_prior
        self.sampling = sampling

        if true_hyp is not None:
            self.true_hyp = true_hyp
            self.true_hyp_idx = \
                np.where([np.all(true_hyp == hyp)
                          for hyp in self.hyp_space])[0]
        else:
            self.true_hyp_idx = np.random.randint(self.n_hyp)
            self.true_hyp = self.hyp_space[self.true_hyp_idx]

        self.posterior_true_hyp = np.ones(self.n_features + 1)
        self.posterior_true_hyp[0] = 1 / self.n_hyp
        self.first_feature_prob = np.zeros(self.n_features)

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

    def update_learner_posterior(self):
        """Calculates the unnormalized posterior across all
        possible feature/label observations"""

        lik = self.likelihood()  # p(y|x, h)
        # self_teaching_posterior = self.get_self_teaching_posterior()

        # # calculate posterior
        # self.learner_posterior = lik * self_teaching_posterior * \
        #     self.learner_posterior  # use existing posterior as prior

        # new way of calculating posterior w/o teaching posterior
        self.learner_posterior = lik * self.learner_posterior
        
        # normalize across each hypothesis
        self.learner_posterior = np.nan_to_num(self.learner_posterior /
                                               np.sum(self.learner_posterior, axis=0))

    def update_self_teaching_posterior(self):
        """Calculates the posterior of self teaching for determining which points
        to actively select using the teaching equations"""

        # use same code as teacher.py to calculate teaching posterior
        # uniform joint over data, which is broadcasted into correct shape
        prob_joint_data = (1 / self.n_features * self.n_labels) * \
            np.ones((self.n_hyp, self.n_features, self.n_labels))  # p(x, y)

        # multiply with posterior to get overall joint
        # p(h, x, y) = p(h|, x, y) * p(x, y)
        learner_posterior = self.learner_posterior
        prob_joint = learner_posterior * prob_joint_data

        # marginalize over y, i.e. p(h, x), and broadcast result
        prob_joint_hyp_features = np.sum(prob_joint, axis=2)
        prob_joint_hyp_features = np.repeat(
            prob_joint_hyp_features, self.n_labels).reshape(
                self.n_hyp, self.n_features, self.n_labels)

        # divide by prior over hypotheses to get conditional prob
        # p(x|h) = p(x, h)/p(h)
        # prob_conditional_features = prob_joint_hyp_features / self.learner_prior

        # marginalize over x, i.e. p(h) = \sum_x p(h, x)
        prob_conditional_features = prob_joint_hyp_features / \
            np.repeat(np.sum(prob_joint_hyp_features, axis=1),
                      self.n_features).reshape(
                          self.n_hyp, self.n_features, self.n_labels)
        prob_conditional_features = np.nan_to_num(prob_conditional_features)

        # calculate equation for self-teaching
        # p(x|D) = \sum_h p(x|h) * p(h|D)
        self_teaching_posterior = np.sum(prob_conditional_features * self.learner_prior,
                                         axis=(0, 2))

        # normalize
        self_teaching_posterior = self_teaching_posterior / \
            np.sum(self_teaching_posterior)

        # braodcast self teaching posterior to the right shape, and transpose
        self_teaching_posterior = np.broadcast_to(self_teaching_posterior,
                                                  (self.n_hyp,
                                                   self.n_labels,
                                                   self.n_features))

        # save posterior
        self.self_teaching_posterior = np.array(
            [post.T for post in self_teaching_posterior])

    def sample_self_teaching_posterior(self):
        """Sample a data point based off the self-teaching posterior"""

        # get teacher posterior and select a data point
        self_teaching_posterior = self.self_teaching_posterior
        self_teaching_posterior_sample = self_teaching_posterior[0, :, 0]

        # check posterior sample is a valid probability distribution
        assert np.isclose(np.sum(self_teaching_posterior_sample), 1.0)

        # set probability of selecting observed features to be zero
        self.observed_features = self.observed_features.astype(int)
        if self.observed_features.size != 0:
            self_teaching_posterior_sample[self.observed_features] = 0

        self_teaching_data = -1
        if self.sampling == "max":
            # select max
            self_teaching_data = self.features[np.random.choice(
                np.where(self_teaching_posterior_sample ==
                         np.amax(self_teaching_posterior_sample))[0])]
        else:
            # select proportionally
            if np.all(np.sum(self_teaching_posterior_sample)) != 0:
                self_teaching_prob = self_teaching_posterior_sample / \
                                     np.nansum(self_teaching_posterior_sample)
                self_teaching_data = np.random.choice(np.arange(self.n_features),
                                                  p=self_teaching_prob)
            else:
                print("Error!")
        
        if self.n_obs == 0:
            self.first_feature_prob = self_teaching_posterior_sample

        return self_teaching_data

    def run(self):
        """Run self-teaching until a correct hypothesis is determined"""

        hypothesis_found = False

        # print("true hyp", self.true_hyp)

        while hypothesis_found != True:
            # run updates for learning and teacher posterior once
            self.update_learner_posterior()
            self.update_self_teaching_posterior()

            # sample data point from self-teaching
            self_teaching_sample_feature = self.sample_self_teaching_posterior()
            # print(self_teaching_sample_feature)
            self_teaching_sample_label = self.true_hyp[
                self_teaching_sample_feature]
            self.observed_features = np.append(
                self.observed_features, self_teaching_sample_feature)
            self.observed_labels = np.append(
                self.observed_labels, self_teaching_sample_label)

            # get learner posterior and broadcast
            updated_learner_posterior = \
                self.learner_posterior[:, self_teaching_sample_feature,
                                       self_teaching_sample_label]

            # check for valid probability distribution
            assert np.isclose(np.sum(updated_learner_posterior), 1.0)

            # update new learner posterior by broadcasting
            self.learner_posterior = np.repeat(
                updated_learner_posterior, \
                self.n_labels * self.n_features).reshape(
                    self.n_hyp, self.n_features, self.n_labels)

            # check if any hypothesis has probability one
            if np.any(updated_learner_posterior == 1.0) and \
               self.true_hyp_idx == \
               np.asscalar((np.where(updated_learner_posterior == 1.0))[0]):
                hypothesis_found = True
                true_hyp_found_idx = np.where(updated_learner_posterior == 1)

            # increment observations
            self.n_obs += 1

            # save posterior probability of true hypothesis
            self.posterior_true_hyp[self.n_obs] = updated_learner_posterior[
                self.true_hyp_idx]

        return self.n_obs, self.posterior_true_hyp, self.first_feature_prob
