from occ_all_tests_common import *
from occ_cutoffs import *
from occ_test_base_common import run_tests
from typing import List

metric_list = ['AUC', 'ACC', 'PRE', 'REC', 'F1', 
    'T1E', 'FOR', 'FNR', '#', '#FD', '#D', 'FDR']
alpha_metric = 'FDR'

test_description = 'FDR tests'
get_results_dir = lambda dataset_type, alpha: f'results_{dataset_type}_fdr_{alpha:.2f}'

baselines = [
    # 'ECOD',
    'ECODv2',
    # 'ECODv2Min',
    # 'GeomMedian',
    'Mahalanobis',
    # 'OC-SVM',
    # 'IForest',
]
def get_cutoffs(inlier_rate, dim, resampling_repeats, X_train, clf, alpha) -> List[Cutoff]:
    return [
        EmpiricalCutoff(inlier_rate),
        # ChiSquaredCutoff(inlier_rate, dim),
        # BootstrapThresholdCutoff(inlier_rate, resampling_repeats, X_train, clf),
        MultisplitThresholdCutoff(inlier_rate, resampling_repeats, X_train, clf),
        # MultisplitCutoff(inlier_rate, resampling_repeats, X_train, clf, alpha, median_multiplier=2),
        # MultisplitCutoff(inlier_rate, 1, X_train, clf, alpha, median_multiplier=2),
        MultisplitCutoff(inlier_rate, resampling_repeats, X_train, clf, alpha, median_multiplier=1),
    ]
pca_thresholds = [None, 1.0]

def run_fdr_tests(DATASET_TYPE, get_all_distribution_configs, alpha):
    run_tests(metric_list, alpha_metric, test_description, get_results_dir, baselines, get_cutoffs, pca_thresholds,
        DATASET_TYPE, get_all_distribution_configs, alpha, test_inliers_only=False, visualize_tests=True, apply_control_cutoffs=True)