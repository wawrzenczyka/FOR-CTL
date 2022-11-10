from occ_all_tests_common import *
from occ_cutoffs import *

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
from typing import List

n_repeats = 10
resampling_repeats = 10
metric_list = ['AUC', 'ACC', 'PRE', 'REC', 'F1', 
    'T1E', 'FOR', '#', '#FD', '#D', 'FDR']
alpha_metric = 'FDR'

test_description = 'FDR tests'

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
    full_results = []

    RESULTS_DIR = f'results_{DATASET_TYPE}_fdr_{alpha:.2f}'
    os.makedirs(RESULTS_DIR, exist_ok=True)

    for (test_case_name, get_dataset_function) in get_all_distribution_configs():
        print(f'{test_description}: {test_case_name} (alpha = {alpha:.2f})')
        results = []

        for exp in range(n_repeats):
            np.random.seed(exp)
            # Load data
            X_train_orig, X_test_orig, y_test_orig = get_dataset_function()
            inlier_rate = np.mean(y_test_orig)

            for baseline in baselines:
                for pca_variance_threshold in pca_thresholds:
                    if pca_variance_threshold is not None and not apply_PCA_to_baseline(baseline):
                        continue

                    np.random.seed(exp)
                    X_train, X_test, y_test = apply_PCA_threshold(X_train_orig, X_test_orig, y_test_orig, pca_variance_threshold)
                    clf = get_occ_from_name(baseline)
                    
                    for cutoff in get_cutoffs(inlier_rate, dim, resampling_repeats, X_train, clf, alpha):
                        if not apply_multisplit_to_baseline(baseline) and (isinstance(cutoff, MultisplitCutoff) or isinstance(cutoff, MultisplitThresholdCutoff)):
                            continue

                        np.random.seed(exp)
                        clf.fit(X_train)
                        scores = clf.score_samples(X_test)

                        occ_metrics = {
                            'Dataset': test_case_name,
                            'Method': baseline + (f"+PCA{pca_variance_threshold:.1f}" if pca_variance_threshold is not None else ""),
                            # 'Cutoff': cutoff_type,
                            'Exp': exp + 1,
                            '#': len(y_test),
                        }

                        y_pred = cutoff.fit_apply(scores)

                        if isinstance(cutoff, MultisplitCutoff):
                            visualize = exp == 0 and pca_variance_threshold is None
                            if visualize:
                                p_vals = cutoff.get_p_vals(scores)

                                train_scores = clf.score_samples(X_train)
                                train_p_vals = cutoff.get_p_vals(train_scores)

                                visualize_scores(scores, p_vals, y_test,
                                    train_scores, train_p_vals,
                                    test_case_name,
                                    baseline,
                                    cutoff.cutoff_type,
                                    RESULTS_DIR,
                                    plot_scores=(cutoff.cutoff_type == 'Multisplit')
                                )
                                
                                sns.set_theme()
                                bh_plot = plt.subplots(2, 2, figsize=(24, 16))
                                plt.suptitle(f'{test_case_name} - {baseline}, {cutoff.cutoff_type}')

                            bh_plots = 0
                            for use_bh, use_pi in [(False, False), (True, False), (True, True)]:
                                cutoff_name = cutoff.cutoff_type + ('+BH' if use_bh else '') + ('+pi' if use_pi else '')

                                if use_bh:
                                    if use_pi:
                                        pi=inlier_rate
                                    else:
                                        pi=None
                                    
                                    np.random.seed(exp)
                                    if visualize:
                                        bh_plots += 1

                                        y_pred = use_BH_procedure(p_vals, alpha, pi,
                                            visualize=True,
                                            y_test=y_test,
                                            test_case_name=test_case_name,
                                            clf_name=baseline,
                                            cutoff_type=cutoff.cutoff_type,
                                            results_dir=RESULTS_DIR,
                                            bh_plot=bh_plot,
                                            save_plot=(bh_plots == 2))
                                    else:
                                        y_pred = use_BH_procedure(p_vals, alpha, pi)
                                
                                occ_metrics['Cutoff'] = cutoff_name
                                method_metrics = prepare_metrics(y_test, y_pred, scores, occ_metrics, metric_list)
                                results.append(method_metrics)
                                full_results.append(method_metrics)

        df = pd.DataFrame.from_records(results)

        dataset_df = df[df.Dataset == test_case_name]
        res_df = dataset_df.groupby(['Dataset', 'Method', 'Cutoff'])\
            [metric_list] \
            .mean()
        if alpha_metric is not None:
            res_df[f'{alpha_metric} < alpha'] = res_df[alpha_metric] < alpha

        for metric in metric_list:
            res_df[metric] = round_and_multiply_metric(res_df[metric], metric)

        res_df = append_mean_row(res_df)
        display(res_df)
        res_df.to_csv(os.path.join(RESULTS_DIR, f'{DATASET_TYPE}-{test_case_name}.csv'))

    # Full result pivots
    df = pd.DataFrame.from_records(full_results)
    df

    pivots = {}
    for metric in metric_list:
        metric_df = df
        if metric == 'AUC':
            metric_df = df.loc[df.Cutoff == 'Empirical']
        
        pivot = metric_df \
            .pivot_table(values=metric, index=['Dataset'], columns=['Method', 'Cutoff'], dropna=False)

        pivot = pivot.dropna(how='all')
        pivots[metric] = pivot
        pivot = append_mean_row(pivot)
        pivot = round_and_multiply_metric(pivot, metric)

        pivot \
            .to_csv(os.path.join(RESULTS_DIR, f'{DATASET_TYPE}-all-{metric}.csv'))

    if alpha_metric is not None:
        append_mean_row(pivots[alpha_metric] < alpha).to_csv(os.path.join(RESULTS_DIR, f'{DATASET_TYPE}-all-{alpha_metric}-alpha.csv'))
