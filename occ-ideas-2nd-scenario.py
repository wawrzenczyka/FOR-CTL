# %%
from sklearn.decomposition import PCA

def PCA_by_variance(X_train, X_test, variance_threshold=0.9):
    pca = PCA()
    X_train_pca = pca.fit_transform(X_train)

    explained_variance = np.cumsum(pca.explained_variance_ratio_)
    are_features_enough = explained_variance >= variance_threshold
    num_features = np.where(are_features_enough)[0][0] + 1 if np.any(are_features_enough) else X.shape[1]
    X_train_pca = X_train_pca[:, :num_features]

    X_test_pca = pca.transform(X_test)
    X_test_pca = X_test_pca[:, :num_features]
    return X_train_pca, X_test_pca, explained_variance[:num_features]

import numpy as np
from scipy.spatial.distance import cdist, euclidean

def geometric_median(X, eps=1e-5):
    y = np.mean(X, 0)

    while True:
        D = cdist(X, [y])
        nonzeros = (D != 0)[:, 0]

        Dinv = 1 / D[nonzeros]
        Dinvs = np.sum(Dinv)
        W = Dinv / Dinvs
        T = np.sum(W * X[nonzeros], 0)

        num_zeros = len(X) - np.sum(nonzeros)
        if num_zeros == 0:
            y1 = T
        elif num_zeros == len(X):
            return y
        else:
            R = (T - y) * Dinvs
            r = np.linalg.norm(R)
            rinv = 0 if r == 0 else num_zeros/r
            y1 = max(0, 1-rinv)*T + min(1, rinv)*y

        if euclidean(y, y1) < eps:
            return y1

        y = y1

class GeomMedianDistance():
    def fit(self, X, eps=1e-5):
        self.median = geometric_median(X, eps)
        return self
    
    def score_samples(self, X):
        return -np.linalg.norm(X - self.median, 2, axis=1)

import numpy as np

def dot_diag(A, B):
    # Diagonal of the matrix product
    # equivalent to: np.diag(A @ B)
    return np.einsum('ij,ji->i', A, B)

class Mahalanobis():
    def fit(self, X):
        self.mu = np.mean(X, axis=0).reshape(1, -1)

        if X.shape[1] != 1:
            # sometimes non invertible
            # self.sigma_inv = np.linalg.inv(np.cov(X.T))

            # use pseudoinverse
            self.sigma_inv = np.linalg.pinv(np.cov(X.T))
            # another idea: add small number to diagonal
            # self.sigma_inv = np.linalg.inv(np.cov(X.T) + EPS * np.eye(X.shape[1]))
        else:
            self.sigma_inv = np.eye(1)
            
        return self
    
    def score_samples(self, X):
        # (X - self.mu) @ self.sigma_inv @ (X - self.mu).T
        # but we need only the diagonal
        mahal = dot_diag((X - self.mu) @ self.sigma_inv, (X - self.mu).T)
        return 1 / (1 + mahal)

from pyod.models.ecod import ECOD
from ecod_v2 import ECODv2

class PyODWrapper():
    def __init__(self, model):
        self.model = model
    
    def fit(self, X_train):
        self.model.fit(X_train)
        return self

    def score_samples(self, X):
        return -self.model.decision_function(X)

# %%
import os
import occ_datasets
import scipy.stats
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn import metrics
from IPython.display import display

from pyod.models.ecod import ECOD
from ecod_v2 import ECODv2
from ecod_v2_min import ECODv2Min
from sklearn.svm import OneClassSVM
from sklearn.ensemble import IsolationForest

alpha = 0.25
n_repeats = 10
resampling_repeats = 10

# RESULTS_DIR = 'results_fdr'
RESULTS_DIR = f'results_fdr_{alpha:.2f}'
os.makedirs(RESULTS_DIR, exist_ok=True)

# datasets = [(dataset, 'mat') for dataset in occ_datasets.MAT_DATASETS] + \
#     [(dataset, 'arff') for dataset in occ_datasets.ARFF_DATASETS]

datasets = [
    # .mat
    ('Arrhythmia', 'mat'),
    ('Breastw', 'mat'),
    ('Cardio', 'mat'),
    ('Ionosphere', 'mat'),
    ('Lympho', 'mat'),
    ('Mammography', 'mat'),
    ('Optdigits', 'mat'),
    ('Pima', 'mat'),
    ('Satellite', 'mat'),
    ('Satimage-2', 'mat'),
    ('Shuttle', 'mat'),
    ('Speech', 'mat'),
    ('WBC', 'mat'),
    ('Wine', 'mat'),
    # .arff
    ('Arrhythmia', 'arff'),
    ('Cardiotocography', 'arff'),
    ('HeartDisease', 'arff'),
    ('Hepatitis', 'arff'),
    ('InternetAds', 'arff'),
    ('Ionosphere', 'arff'),
    ('KDDCup99', 'arff'),
    ('Lymphography', 'arff'),
    ('Pima', 'arff'),
    ('Shuttle', 'arff'),
    ('SpamBase', 'arff'),
    ('Stamps', 'arff'),
    ('Waveform', 'arff'),
    ('WBC', 'arff'),
    ('WDBC', 'arff'),
    ('WPBC', 'arff'),
]
# datasets = [
#     ('Speech', 'mat'),
#     # ('KDDCup99', 'arff'),
# ]

# datasets = [
#     ('Hepatitis', 'arff'),
# ]

full_results = []

for (dataset, format) in datasets:
    results = []

    for exp in range(n_repeats):
        # Load data
        X, y = occ_datasets.load_dataset(dataset, format)
        X_train, X_test, y_test = occ_datasets.split_occ_dataset(X, y, train_ratio=0.6)
        inlier_rate = np.mean(y_test)

        for baseline in [
            # 'ECOD',
            'ECODv2',
            # 'ECODv2Min',
            # 'GeomMedian',
            # 'Mahalanobis',
            # 'OC-SVM',
            # 'IForest',
        ]:
            # for pca_variance_threshold in [0.5, 0.9, None]:
            for pca_variance_threshold in [None]:
                if pca_variance_threshold is not None:
                    if not 'ECODv2' in baseline:
                        continue
                    X_train, X_test, _ = PCA_by_variance(X_train, X_test, pca_variance_threshold)

                if baseline == 'ECOD':
                    clf = PyODWrapper(ECOD())
                elif baseline == 'ECODv2':
                    clf = PyODWrapper(ECODv2())
                elif baseline == 'ECODv2Min':
                    clf = PyODWrapper(ECODv2Min())
                elif baseline == 'GeomMedian':
                    clf = GeomMedianDistance()
                elif baseline == 'Mahalanobis':
                    clf = Mahalanobis()
                elif baseline == 'OC-SVM':
                    clf = OneClassSVM()
                elif baseline == 'IForest':
                    clf = IsolationForest()
                
                for cutoff_type in [
                    'Empirical',
                    # 'Chi-squared',
                    # 'Bootstrap',
                    'Multisplit',
                    'Multisplit+BH',
                    'Multisplit+BH+pi',
                ]:
                    if cutoff_type != 'Empirical' and not 'ECODv2' in baseline:
                        continue
                    
                    N = len(X_train)
                    if cutoff_type == 'Multisplit':
                        cal_scores_all = np.zeros((resampling_repeats, N - int(N/2)))

                        for i in range(resampling_repeats):
                            resampling_samples = np.random.choice(range(N), size=int(N/2), replace=False)
                            is_selected_sample = np.isin(range(N), resampling_samples)
                            X_resampling_train, X_resampling_cal = X_train[is_selected_sample], X_train[~is_selected_sample]
                            
                            clf.fit(X_resampling_train)
                            cal_scores = clf.score_samples(X_resampling_cal)
                            cal_scores_all[i, :] = cal_scores

                    clf.fit(X_train)

                    scores = clf.score_samples(X_test)
                    auc = metrics.roc_auc_score(y_test, scores)


                    if cutoff_type == 'Empirical':
                        emp_quantile = np.quantile(scores, q=1 - inlier_rate)
                        y_pred = np.where(scores > emp_quantile, 1, 0)
                    elif 'Multisplit' in cutoff_type:
                        p_vals_all = np.zeros((resampling_repeats, len(scores)))
                        for i in range(resampling_repeats):
                            cal_scores = cal_scores_all[i, :]
                            num_smaller_cal_scores = (scores > cal_scores.reshape(-1, 1)).sum(axis=0)
                            p_vals = (num_smaller_cal_scores + 1) / (len(cal_scores) + 1)
                            p_vals_all[i, :] = p_vals
                        p_vals = 2 * np.median(p_vals_all, axis=0)
                        y_pred = np.where(p_vals < alpha, 0, 1)

                        if 'BH' in cutoff_type:
                            fdr_ctl_threshold = alpha
                            if 'pi' in cutoff_type:
                                pi = inlier_rate
                                fdr_ctl_threshold = alpha / pi
                            
                            sorted_indices = np.argsort(p_vals)
                            bh_thresholds = np.linspace(
                                fdr_ctl_threshold / len(p_vals), fdr_ctl_threshold, len(p_vals))
                            
                            # is_h0_rejected == is_outlier, H_0: X ~ P_X
                            # OLD WAY
                            is_h0_rejected = p_vals[sorted_indices] < bh_thresholds
                            # NEW WAY
                            rejections = np.where(is_h0_rejected)[0]
                            if len(rejections) > 0:
                                is_h0_rejected[:(np.max(rejections) + 1)] = True
                            # take all the point to the left of last discovery

                            y_pred = np.ones_like(p_vals)
                            y_pred[sorted_indices[is_h0_rejected]] = 0

                    false_detections = np.sum((y_pred == 0) & (y_test == 1))
                    detections = np.sum(y_pred == 0)
                    fdr = false_detections / detections

                    acc = metrics.accuracy_score(y_test, y_pred)
                    pre = metrics.precision_score(y_test, y_pred)
                    rec = metrics.recall_score(y_test, y_pred)
                    f1 = metrics.f1_score(y_test, y_pred)

                    print(f'{dataset}.{format}: {baseline}{f"+PCA{pca_variance_threshold:.1f}" if pca_variance_threshold is not None else ""} ({cutoff_type}, {exp+1}/{n_repeats})' + \
                        f' ||| AUC: {100 * auc:3.2f}, ACC: {100 * acc:3.2f}, F1: {100 * f1:3.2f}, FDR: {fdr:.3f}')
                    occ_metrics = {
                        'Dataset': f'({format}) {dataset}',
                        'Method': baseline + (f"+PCA{pca_variance_threshold:.1f}" if pca_variance_threshold is not None else ""),
                        'Cutoff': cutoff_type,
                        'Exp': exp + 1,
                        'AUC': auc,
                        'ACC': acc,
                        'PRE': pre,
                        'REC': rec,
                        'F1': f1,
                        'FDR': fdr,
                        'alpha': alpha,
                        'pi * alpha': alpha * inlier_rate,
                        '#': len(y_pred),
                        '#FD': false_detections,
                        '#D': detections,
                    }
                    results.append(occ_metrics)
                    full_results.append(occ_metrics)
    
    df = pd.DataFrame.from_records(results)

    dataset_df = df[df.Dataset == f'({format}) {dataset}']
    res_df = dataset_df.groupby(['Dataset', 'Method', 'Cutoff', 'alpha'])\
        [['pi * alpha', 'AUC', 'ACC', 'PRE', 'REC', 'F1', '#', '#FD', '#D', 'FDR']] \
        .mean()

    res_df[['AUC', 'ACC', 'PRE', 'REC', 'F1']] = (res_df[['AUC', 'ACC', 'PRE', 'REC', 'F1']] * 100) \
        .applymap('{0:.2f}'.format)
    res_df[['#FD', '#D']] = (res_df[['#FD', '#D']]) \
        .applymap('{0:.1f}'.format)
    res_df['FDR < alpha'] = res_df['FDR'] < res_df.index.get_level_values('alpha')
    res_df['FDR < pi * alpha'] = (res_df['FDR'] < res_df['pi * alpha'])
    res_df[['FDR', 'pi * alpha']] = res_df[['FDR', 'pi * alpha']].applymap('{0:.3f}'.format)

    display(res_df)
    res_df.to_csv(os.path.join(RESULTS_DIR, f'dataset-{format}-{dataset}.csv'))

# Full result pivots
df = pd.DataFrame.from_records(full_results)
df

pivots = {}
for metric in ['AUC', 'ACC', 'F1', 'PRE', 'REC', 'FDR', 'alpha', 'pi * alpha']:
    metric_df = df
    if metric == 'AUC':
        metric_df = df.loc[df.Cutoff == 'Empirical']
    
    pivot = metric_df \
        .pivot_table(values=metric, index=['Dataset'], columns=['Method', 'Cutoff']) \
        * (100 if metric not in ['FDR', 'alpha', 'pi * alpha'] else 1)

    pivots[metric] = pivot
    if metric in ['alpha', 'pi * alpha']:
        continue

    pivot \
        .applymap("{0:.2f}".format if metric != 'FDR' else "{0:.3f}".format ) \
        .to_csv(os.path.join(RESULTS_DIR, f'dataset-all-{metric}.csv'))

(pivots['FDR'] < pivots['alpha']).to_csv(os.path.join(RESULTS_DIR, f'dataset-all-FDR-alpha.csv'))
(pivots['FDR'] < pivots['pi * alpha']).to_csv(os.path.join(RESULTS_DIR, f'dataset-all-FDR-pi-alpha.csv'))

# %%
