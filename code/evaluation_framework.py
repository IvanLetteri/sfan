"""evaluation_framework.py -- All that is needed to evaluate feature selection algorithms."""

import numpy as np
import sklearn
import sklearn.linear_model as lm
import sklearn.cross_validation as cv
import tables as tb
import subprocess 



def consistency_index(sel1, sel2, num_features):
    """ Compute the consistency index between two sets of features.

    Parameters
    ----------
    sel1: set
        First set of indices of selected features
    sel2: set
        Second set of indices of selected features
    num_features: int
        Total number of features

    Returns
    -------
    cidx: float
        Consistency index between the two sets.

    Reference
    ---------
    Kuncheva, L.I. (2007). A Stability Index for Feature Selection.
    AIAC, pp. 390--395.
    """
    observed = float(len(sel1.intersection(sel2)))
    expected = len(sel1) * len(sel2) / float(num_features)
    maxposbl = float(min(len(sel1), len(sel2)))
    cidx = 0.
    # It's 0 and not 1 as expected if num_features == len(sel1) == len(sel2) => observed = n
    # Because "take everything" and "take nothing" are trivial solutions we don't want to select
    if expected != maxposbl:
        cidx = (observed - expected) / (maxposbl - expected)
    return cidx


def consistency_index_k(sel_list, num_features):
    """ Compute the consistency index between more than 2 sets of features.

    This is done by averaging over all pairwise consistency indices.

    Parameters
    ----------
    sel_list: list of lists
        List of k lists of indices of selected features
    num_features: int
        Total number of features

    Returns
    -------
    cidx: float
        Consistency index between the k sets.

    Reference
    ---------
    Kuncheva, L.I. (2007). A Stability Index for Feature Selection.
    AIAC, pp. 390--395.
    """
    cidx = 0.
    for k1, sel1 in enumerate(sel_list[:-1]):
        # sel_list[:-1] to not take into account the last list.
        # avoid a problem with sel_list[k1+1:] when k1 is the last element,
        # that give an empty list overwise
        # the work is done at the second to last element anyway
        for sel2 in sel_list[k1+1:]:
            cidx += consistency_index(set(sel1), set(sel2), num_features)
    cidx = 2. / (len(sel_list) * (len(sel_list) - 1)) * cidx
    return cidx


def consistency_index_task(selection_fname, num_folds, num_tasks, num_features):
    """ Compute consistency indices between the features selected for each fold at each task

    selection_fname, num_folds, num_tasks, num_features
    Arguments
    ---------
    selection_fname : filename
        Template of path where were write list of selected features
    num_folds: int
        Total number of fold
    num_tasks: int
        Total number of task
    num_features: int
        Total number of features

    Return
    -------
    ci_list
        List of consistency indices between the features selected for each fold, task per task.
    """
    # In the curret repeat repo, there is a file of selected feature for each fold
    # in which each line is a task 
    # on each line, there is the space separated list of selected feature.
    # we want consistency indices between the features selected for each fold, task per task
    # so for each line in these files, we compute the ci between the features selected for each fold


    # As there are ~10 folds, there are 10 files.
    # they don't take a lot of memory
    # so it is ok to open them all :
    fold_f_list = []
    for fold_idx in xrange (num_folds) :
        f_sel = open(selection_fname %fold_idx, 'r')
        fold_f_list.append(f_sel)

    
    ci_list = []
    # For each task : 
    for task_idx in xrange (num_tasks):
        sel_list = []
        for f_sel in fold_f_list :
            # increment aline in each file
            content = f_sel.readline().split()
            # append lines content in sel_list
            sel_list.append(content)
        # compute the ci between the features selected for each fold at this current task
        ci =  consistency_index_k(sel_list, num_features)
        ci_list.append(ci)

    for f in fold_f_list :
        f.close()

    return ci_list


def run_sfan(num_tasks, network_fname, weights_fnames, params):
    """ Run single task sfan (on each task).

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    # Ideally, I'd do the following:
    # sfan_solver = Sfan(num_tasks, network_fname, weights_fname,
    #                    lbd, eta, 0, precision_fname)
    # tt = sfan_solver.create_dimacs()
    # sfan_solver.run_maxflow()

    # But because cython output to screen is NOT caught by sys.stdout, 
    # we need to run this externally
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(params.split())
    argum.extend(['-m', '0'])

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)
    p_out = p.communicate()[0].split("\n")[2:2+num_tasks]

    # Process the output to get lists of selected
    # features
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list :
        print "returned sel_list empty !! algo = st ; param = ", params
        #import pdb ; pdb.set_trace() #DEBUG #TODO : don't take the algo into account if the pb can't be solved. 
        sel_list = [[] for i in xrange(num_tasks)]
    return sel_list
                 

def run_msfan_nocorr(num_tasks, network_fname, weights_fnames, params):
    """ Run multitask sfan (no precision matrix).

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(params.split())

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)

    p_out = p.communicate()[0].split("\n")[3:3+num_tasks]

    # Process the output to get lists of selected features
    
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list : #TODO : don't take the algo into account if the pb can't be solved. 
        print "PB : returned sel_list empty !! algo = np ; param = ", params
        sel_list = [[] for i in xrange(num_tasks)]
        #import pdb ; pdb.set_trace() ###???XXXDEBUG

    return sel_list
                 

def run_msfan(num_tasks, network_fname, weights_fnames, precision_fname, params):
    """ Run multitask sfan.

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    precision_fname: filename
        Path to the matrix of precision (similarity) of tasks.
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(['--precision_matrix', precision_fname])
    argum.extend(params.split())

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)

    p_out = p.communicate()[0].split("\n")[3:3+num_tasks]

    # Process the output to get lists of selected features
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list : #TODO : don't take the algo into account if the pb can't be solved. 
        print "returned sel_list empty !! algo = msfan ; param = ", params
        #import pdb ; pdb.set_trace() #DEBUG
        sel_list = [[] for i in xrange(num_tasks)]
    return sel_list
                 

def get_optimal_parameters_from_dict(selected_dict, num_features):
    #TODO : return params leading to the best mean of ci for all tasks. 
    """ Find optimal parameters from dictionary of selected features

    Arguments
    ---------
    selected_dict: dictionary
        keys = parameters
        values = dictionary
            keys = task index
            values = list of list of selected features (for each subsample)
    num_features: int
        Total number of features

    Returns
    -------
    opt_params: string
        Optimal parameters, leading to highest consistency index ???between features selected for each subsample???.
        XXX??? Why it is not params leading to highest ci mean per task ? ???
    """
    opt_params = ''
    opt_cindex = 0
    for (params, selected_dict_p) in selected_dict.iteritems():
        for (task_idx, sel_list) in selected_dict_p.iteritems():
            cidx = consistency_index_k(sel_list, num_features)
            if cidx > opt_cindex:
                opt_cindex = cidx
                opt_params = params
    return opt_params


def run_ridge_selected(selected_features, genotype_fname, phenotype_fname,
                       tr_indices, te_indices, output_fname):
    """ Run a ridge-regression using only the selected features.

    Arguments
    ---------
    selected_features: list
        List of indices of selected features.
    genotype_fname: filename
        Path to genotype data.
    phenotype_fname: filename
        Path to phenotype data.
    tr_indices: list
        List of training indices.
    te_indices: list
        List of test indices.                    
    output_fname: filename
        Path to file where to write list of predictions on the test set.

    Side effects
    ------------
    Write predictions on the test set to output_fname
    """
    # This function : 
    # - Learn a Ridge Regression model that links
    #   genotype of selected features (Xtr)
    #   with continuous phenotype (ytr)
    #   of the train set (tr)
    # - Predicts continuous phenotype (preds) 
    #   using genotype of selected features (Xte)
    #   of the test set (te)
    # - Save predicted continuous phenotypes in a file. 
    # => it's a regression so il can only be used with continuous phenotype
    # TODO : Think of how to handle discret phenotypes. 

    #----------------------------------------
    # Read data : 

    if not selected_features : #DEBUG
        # Safeguard for when SFAN returns empty list
        # Avoid not allowed empty selections
        import pdb; pdb.set_trace() 
        ### XXX ??? 

    # read genotypes : 
    with tb.open_file(genotype_fname, 'r') as h5f:
        table = h5f.root.Xtr
        # table.shape : 
        # For each feature (in line), 
        # there is the genotype of each sample (in column)
        X = table[selected_features, :]

    Xtr = [X[:,tr] for tr in tr_indices]
    Xte = [X[:,te] for te in te_indices]

    # read phenotypes : 
    with open(phenotype_fname, 'r') as f:
        # continuous phenotype for each sample (in line)
        y = f.read().split()
        y = [float(item) for item in y]

    ytr = [ y[tr] for tr in tr_indices]
    #----------------------------------------

    # Instantiate a ridge regression
    model = lm.RidgeCV()

    # Train the ridge regression on the training set
    model.fit(Xtr, ytr)

    #----------------------------------------

    # Make predictions on the test set
    preds = model.predict(Xte)

    # Save predictions
    np.savetxt(output_fname, preds, fmt='%.3e')




def compute_ridge_selected_RMSE(phenotype_fname, y_pred_fname, xp_indices, output_fname):
    """ Compute RMSE (Root Mean Squared Error)

    Arguments
    ---------
    y_true_fname: filename
        Path to phenotype data.
    y_pred_fname: string
        Template of path where were write list of predictions on the test set
    xp_indices: list of dictionaries
        fold_idx
        {
            'trIndices': list of train indices,
            'teIndices': list of test indices,
            'ssIndices': list of list of subsample indices
        }

    output_fname: filename
        Path to file where to write rmse.

    Side effects
    ------------
    Write rmse to output_fname
    """
    # For n inds :
    # RMSE = sqrt { (1/n)  [sum from m=1 to n : (ypred_m - ytrue_m)^2 ]  }

    # read y_true :
    with open(phenotype_fname, 'r') as f_true:
        y_true = [float(y) for y in f_true.read().split()]

    # read y_pred :
    # predictions were made one by one, in order : [fold['teIndices'] for fold in xp_indices]
    # we open each file (one per fold) and append predicted phenotypes
    # then when sort them using y_pred_indices so the order will be 0,1,...,n

    y_pred_indices = [index for sublist in [fold['teIndices'] for fold in xp_indices] for index in sublist]

    y_pred = list()

    for fold in xrange(len(xp_indices)) :
        with open(y_pred_fname%fold, 'r') as f_pred:
            content = f_pred.read().split()
            y_pred.extend(float(y) for y in content)
     
    y_pred_sorted = [y_pred[i] for i in y_pred_indices]

    # compute rmse using metrics :
    rmse = sklearn.metrics.mean_squared_error(y_true, y_pred_sorted)

    # output :
    with open(output_fname, 'a') as f_out:
        f_out.write("%d " %rmse)


def compute_ppv_sensitivity(causal_fname, selected_list, num_features):
    """ Compute PPV (Positive Predicted Values) = Accuracy = Precision
    and sensitivity (true positive rate) for all tasks.

    Arguments
    ---------
    causal_fname: filename
        File containing causal features (one line per task, space-separated).
    selected_list: list of lists
        List of lists of selected features (one list per task).
    num_features : int
        Total number of features

    Returns
    -------
    ppv_list: list
        List of Positive Predicted Values (PPV), task per task.
    tpr_list: list
        List of sensitivities (TPR), task per task.
    """

    ppv_list = []
    tpr_list = []
    
    with open(causal_fname, 'r') as f:

        # For each task, 
        for line_idx, line in enumerate(f):

            # at the beginning, we consider that the features are 
            # neither causal...
            y_true = [False]*num_features
            # ... nor predicted as such.
            y_pred = [False]*num_features

            # Then we change the status of the causal ones 
            # (these are y_true True),
            y_true_indx_list = map(int, line.split())
            for y_true_indx in y_true_indx_list :
                y_true[y_true_indx] = True
            # and of those that have been predicted as such 
            # (these are y_pred True).
            y_pred_indx_list = selected_list[line_idx]            
            for y_pred_indx in y_pred_indx_list :
                y_pred[y_pred_indx] = True

            # and we compute ppv and tpr based on these 2 sets : 

            ppv_list.append( sklearn.metrics.accuracy_score(y_true, y_pred) )

            count_tpr = 0 # Number of features of which real and predicted status is the same. 
            for i, j in zip(y_pred, y_true):
                if (i == j):
                    count_tpr += 1
            tpr_list.append( count_tpr / num_features)
    
    return ppv_list, tpr_list

def extract_res_from_files(f_names, num_tasks, num_repeat, num_folds = None):
    """Compute mean and std per task from files holding values of measures.

    Arguments
    ---------
    f_names : filenames
        Path to files in the order st, np, msfan
        holding values whith space separated lists of values (on per task),
        one line per repeat
    num_tasks: int
        Number of tasks. 
    num_repeat : int 
        Number of repeat
    num_folds : int / None
        Number of folds.
        Needed for ppv and tpr files 
        because values per repeat are per fold then per task. 

    Return
    -------
    means, std : dict of list
        for each algo ('st', 'msfan_np', 'msfan'), a list of means / std task per task
    """
    
    means = {'st' : [float()*num_tasks] , 'np' : [float()*num_tasks], 'msfan' : [float()*num_tasks] }
    std = {'st' : [float()*num_tasks] , 'np' : [float()*num_tasks], 'msfan' : [float()*num_tasks] }

    algos = ['st', 'np', 'msfan']

    if num_folds : 
    # for ppv and tpr file for which values per repeat = per line 
    # are per fold, then per task, 
    # we have to compute means per task taking account of value per repeat and per fold. 
        for algo_idx, algo in enumerate(algos) : 
                val_ci  = [[float() for i in xrange(num_tasks)] for j in xrange(num_repeat)]
                # val[num_repeat = num line][num_tasks]
                with open (f_names[algo_idx], 'r') as f : 
                    for j, line in enumerate(f) : 
                        content = [float (item) for item in line.split()]
                        # content contains every float of the line 
                        # we get values for a task using a slice : 
                        content_task = []
                        for task_idx in xrange(num_tasks) : 
                            content_task.append( np.mean(content[task_idx::num_tasks]) )

                        val_ci[j] = content_task
                means[algo] = np.mean(val_ci, axis=0).tolist() # give the means for each col in the file = per task
                std[algo]= np.std (val_ci, axis = 0).tolist()

    else : 
    # for rmse and cosistency files : 
    # each lines = a repeat, each col : a task. 
    # -> means and std in col
        for algo_idx, algo in enumerate(algos) : 
            val_ci  = [[float() for i in xrange(num_tasks)] for j in xrange(num_repeat)]
            # val[num_repeat = num line][num_tasks = num column]
            with open (f_names[algo_idx], 'r') as f : 
                for j, line in enumerate(f) : 
                    content_task = [float (item) for item in line.split()]
                    val_ci[j] = content_task
            means[algo] = np.mean(val_ci, axis=0) # give the means for each col in the file = per task
            std[algo]= np.std (val_ci, axis = 0)

    return means, std


    
class Framework(object):
    """ Setting up evaluation framework.

    Attributes
    ----------
    self.num_samples: int
        Number of samples.
    self.num_folds: int
        Number of cross-validation folds
    self.num_subsamples: int
        Number of subsamples (to evaluate stability)
    self.xp_indices: list of dictionaries
        fold_idx
        {
            'trIndices': list of train indices,
            'teIndices': list of test indices,
            'ssIndices': list of list of subsample indices
        }

    """
    def __init__(self, num_samples, num_folds, num_subsamples):
        """
        Parameters
        ----------
        num_samples: int
            Number of samples.
        num_folds: int
            Number of cross-validation folds
        num_subsamples: int
            Number of subsamples (to evaluate stability)
        """
        self.num_samples = num_samples
        self.num_folds = num_folds
        self.num_subsamples = num_subsamples
        self.xp_indices = [{'trIndices': list(), 'teIndices':list(), 'ssIndices':list()} for fold in xrange(num_folds)]
        
    def compute_indices(self, seed=None):
        """ Compute the cross-validation folds and subsample indices.

        Parameters
        ----------
        seed: {int, None}, optional
            random seed.
            Will always return the same with the same random seed.

        Modified attributes
        -------------------
        xp_indices: list of dictionaries
            fold_idx
            {
                'trIndices': list of train indices,
                'teIndices': list of test indices,
                'ssIndices': list of list of subsample indices
            }
        """
        # use sklearn.cross_validation
        
        kf = cv.KFold(self.num_samples, n_folds=self.num_folds)# ??? Add shuffle ??? XXX
        for i, (train_index, test_index) in enumerate(kf):
            # Generate cross-validation indices
            self.xp_indices[i]['trIndices'] = train_index.tolist()
            self.xp_indices[i]['teIndices'] = test_index.tolist()
            # For each train set, generate self.num_subsamples subsample sets of indices
            ss = cv.KFold(n=self.num_samples, n_folds=self.num_subsamples, shuffle=True, random_state=seed)
            for train_index, test_index in ss:
                self.xp_indices[i]['ssIndices'].append(train_index.tolist())

        
    def save_indices(self, data_dir, simu_id):
        """ Save the cross-validation folds and subsample indices to files.

        Parameters
        ----------

        Generated files
        ---------------
        For each fold_idx:
            <data_dir>/<simu_id>.<fold_idx>.trIndices:
                Space-separated list of training indices.
            <data_dir>/<simu_id>.<fold_idx>.teIndices:
                Space-separated list of test indices.
            For each subsample_idx:
                <data_dir>/<simu_id>.<fold_idx>.<ss_idx>.ssIndices
                    Space-separated lists of subsample indices,
                    one line per list / subsample.
        """
        # use np.savetxt 