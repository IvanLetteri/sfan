# -*- coding: utf-8 -*-
"""synthetic_data_experiments.py -- Run validation experiments on synthetic data

In this version all experiments are run sequentially.
"""

DEBUG_MODE = False
TIME_EXP = False
DATA_GEN = True # have to gene dat or not ?
SEQ_MODE = True

NUM_VALUES=3 #range param


tmp_dir= "/tmp"
#tmp_dir = "/share/data40T/athenais/tmp"



# Importing local libraries first,
# because otherwise Error in `python': free(): invalid pointer
import multitask_sfan
import evaluation_framework as ef
import generate_data
import plot

import argparse
import logging
import os
import numpy as np
import scipy.stats as st
import subprocess
import sys
import tables as tb
import tempfile
import shutil
import shlex
import glob
import random

def get_arguments_values(): 
    """ Use argparse module to get arguments values.

    Return
    ------
    args : Namespace object
        Namespace object populated with arguments converted from strings to objects 
        and assigned as attributes of the namespace object.
        They store arguments values (str or int, according to the specifications in
        the code)
    """
    help_str = "Validation experiments on synthetic data"
    parser = argparse.ArgumentParser(description=help_str,add_help=True)
    parser.add_argument("-k", "--num_tasks", help="Number of tasks", type=int)
    parser.add_argument("-m", "--num_features", help="Number of features",
                        type=int)
    parser.add_argument("-n", "--num_samples", help="Number of samples",
                        type=int)
    parser.add_argument("-r", "--num_repeats", help="Number of repeats",
                        type=int)
    parser.add_argument("-f", "--num_folds", help="Number of CV folds",
                        type=int)
    parser.add_argument("-s", "--num_subsamples", help="Number of subsamples",
                        type=int)
    parser.add_argument("data_dir", help="Simulated data directory")
    parser.add_argument("resu_dir", help="Results directory")
    parser.add_argument("simu_id", help="Simulation name")
    parser.add_argument("-v", "--verbose", help="Turn on detailed info log",
                        action='store_true')
    return parser.parse_args()

def check_arguments_integrity(args): 
    """ Check integrity of arguments pass through the command line. 

    Parameter
    ---------
    args : namespace object
        Its attributes are arguments names 
        and contain arguments values. 

    Side effect
    -----------
    If one arg is not integrous, exit the script printing why. 
    """
    try:
        assert(args.num_tasks >= 1)
    except AssertionError:
        logging.error("There must be at least one task specified.\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)
    
    try:
        assert(args.num_features >= generate_data.NUM_CAUSAL_TOTAL)
    except AssertionError:
        logging.error("The number of features must be larger than" + \
                      " NUM_CAUSAL_TOTAL (%d).\n" % \
                      generate_data.NUM_CAUSAL_TOTAL)
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_samples > 0)
    except AssertionError:
        logging.error("The number of samples must be strictly positive\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_repeats > 0)
    except AssertionError:
        logging.error("The number of repeats must be strictly positive\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_folds > 0)
    except AssertionError:
        logging.error("The number of cross-validation folds must be strictly positive\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_subsamples > 0)
    except AssertionError:
        logging.error("The number of subsamples must be strictly positive\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    # Verbose
    if args.verbose:
        logging.basicConfig(format="[%(levelname)s] %(message)s",
                            level=logging.DEBUG)
        logging.info("Verbose output.")
    else:
        logging.basicConfig(format="%[(levelname)s] %(message)s")

def get_integrous_arguments_values(): 
    """ Get arguments passed through command line and check their integrity.

    Return
    ------
    args : namespace object
        Its attributes are arguments names 
        and contain arguments values (str or int according to code specifications). 
    """
    args = get_arguments_values()
    check_arguments_integrity(args)
    return args

def create_dir_if_not_exists(dir_name): 
    """ Create a dir named <dir_name> if it does not already exists. 

    Parameter
    ---------
    dir_name : str
        Path of the wanted new dir. 

    Side effect
    -----------
    Create a dir named <dir_name> if it does not already exists.
    """
    if not os.path.isdir(dir_name):
        logging.info("Creating %s\n" % dir_name)
        try: 
            os.makedirs(dir_name)
        except OSError:
            if not os.path.isdir(dir_name):
                raise

def get_analysis_files_names(resu_dir, simu_id): 
    """ Give analysis files names. 

    Parameters
    ----------
    resu_dir: filename
        Path of the directory in which to save the results.
    simu_id: string
        Name of the simulation, to be used to name files.

    Returns
    -------
    analysis_files : dictionary
        analysis_files[<measure abbreviation>_<algo>] = filename
    """
    # - to hold accuracy values  
    acc_st_fname = '%s/%s.sfan.acc' % (resu_dir, simu_id) 
    acc_np_fname = '%s/%s.msfan_np.acc' % (resu_dir, simu_id) 
    acc_fname = '%s/%s.msfan.acc' % (resu_dir, simu_id)    
    # - to hold mcc values
    mcc_st_fname = '%s/%s.sfan.mcc' % (resu_dir, simu_id) 
    mcc_np_fname = '%s/%s.msfan_np.mcc' % (resu_dir, simu_id) 
    mcc_fname = '%s/%s.msfan.mcc' % (resu_dir, simu_id)    
    # - to hold PPV values
    ppv_st_fname = '%s/%s.sfan.ppv' % (resu_dir, simu_id)
    ppv_np_fname = '%s/%s.msfan_np.ppv' % (resu_dir, simu_id)
    ppv_fname = '%s/%s.msfan.ppv' % (resu_dir, simu_id)
    # - to hold sensitivity = TPR values
    tpr_st_fname = '%s/%s.sfan.tpr' % (resu_dir, simu_id)    
    tpr_np_fname = '%s/%s.msfan_np.tpr' % (resu_dir, simu_id)
    tpr_fname = '%s/%s.msfan.tpr' % (resu_dir, simu_id)
    # - to hold consistency values
    ci_st_fname = '%s/%s.sfan.consistency' % (resu_dir, simu_id)
    ci_np_fname = '%s/%s.msfan_np.consistency' % (resu_dir, simu_id)
    ci_fname = '%s/%s.msfan.consistency' % (resu_dir, simu_id)
    # - to hold RMSE values
    rmse_st_fname = '%s/%s.sfan.rmse' % (resu_dir, simu_id)
    rmse_np_fname = '%s/%s.msfan_np.rmse' % (resu_dir, simu_id)
    rmse_fname = '%s/%s.msfan.rmse' % (resu_dir, simu_id)
    # - to hold timing values
    timing_st_fname = '%s/%s.sfan.timing' % (resu_dir, simu_id)
    timing_np_fname = '%s/%s.msfan_np.timing' % (resu_dir, simu_id)
    timing_fname = '%s/%s.msfan.timing' % (resu_dir, simu_id)
    # - to hold maxRSS values 
    maxRSS_st_fname = '%s/%s.sfan.maxRSS' % (resu_dir, simu_id)
    maxRSS_np_fname = '%s/%s.msfan_np.maxRSS' % (resu_dir, simu_id)
    maxRSS_fname = '%s/%s.msfan.maxRSS' % (resu_dir, simu_id)
    
    analysis_files = {
        'acc_st':acc_st_fname, 
        'acc_msfan_np': acc_np_fname, 
        'acc_msfan': acc_fname, 
        'mcc_st': mcc_st_fname, 
        'mcc_msfan_np': mcc_np_fname, 
        'mcc_msfan': mcc_fname, 
        'ppv_st':ppv_st_fname,
        'ppv_msfan_np':ppv_np_fname,
        'ppv_msfan':ppv_fname,
        'tpr_st':tpr_st_fname,
        'tpr_msfan_np':tpr_np_fname,
        'tpr_msfan':tpr_fname,
        'ci_st':ci_st_fname ,
        'ci_msfan_np':ci_np_fname ,
        'ci_msfan':ci_fname, 
        'rmse_st':rmse_st_fname ,
        'rmse_msfan_np':rmse_np_fname ,
        'rmse_msfan':rmse_fname,
        'timing_st':timing_st_fname,
        'timing_msfan_np':timing_np_fname,
        'timing_msfan':timing_fname,
        'maxRSS_st':maxRSS_st_fname,
        'maxRSS_msfan_np':maxRSS_np_fname,
        'maxRSS_msfan':maxRSS_fname
    }

    return analysis_files

def determine_hyperparamaters(args, genotype_fname, phenotype_fnames, network_fname, covariance_fname = None, precision_fname=None):
    """ Determine hyperparameters. 

    Parameters
    ----------
    args : Namespace object
        Its attributes are arguments names 
        and contain arguments values (str or int according to code specifications).
    genotype_fname: filename
        Path to genotype data.
    phenotype_fname: filename
        Path to phenotype data.
    network_fname: filename
        Path to the network file.
    covariance_fname: filename
        Path to the correlation matrix file. 
    precision_fname: filename
        Path to the precision matrix
    
    Returns
    -------
    lbd_eta_values: list of strings
        Values of hyperparameters, in the format:
        "-l <lambda -e <eta>". -> for Sfan
    lbd_eta_mu_values_np: list of strings
        Values of hyperparameters, in the format:
        "-l <lambda -e <eta> -m <mu>". -> for MSfan_np 
    lbd_eta_mu_values: list of strings
        Values of hyperparameters, in the format:
        "-l <lambda -e <eta> -m <mu>". -> for MSfan

    """
    # Define the grid of hyperparameters
    # see paper/tech_note
    # Randomly sample 50% of the data
    tmp_scores_f_list = []
    with tb.open_file(genotype_fname, 'r') as h5f:
        Xtr = h5f.root.Xtr[:, :]

        # Define subsample of 50% of the data
        sample_indices = range(args.num_samples)
        np.random.shuffle(sample_indices)
        sample_indices = sample_indices[:(args.num_samples/2)]
        Xtr = Xtr[:, sample_indices]

        # Compute scores for the subsample
        for task_idx in range(args.num_tasks):
            # Read phenotype
            y = np.loadtxt(phenotype_fnames[task_idx])[sample_indices]

            # Compute feature-phenotype correlations
            r2 = [st.pearsonr(Xtr[feat_idx, :].transpose(), y)[0]**2 \
                  for feat_idx in range(args.num_features)]

            # Create temporary file of name tmp_fname 
            fd, tmp_fname = tempfile.mkstemp()

            # Save to temporary file
            np.savetxt(tmp_fname, r2, fmt='%.3e')

            # Append temporary file to list
            tmp_scores_f_list.append(tmp_fname)

    # Compute grid (WARNING: STILL NOT WORKING WELL)
    sfan_ = multitask_sfan.Sfan(args.num_tasks, [network_fname],
                                tmp_scores_f_list, 1, 1, 1,
                                covariance_matrix_f=covariance_fname,
                                precision_matrix_f=precision_fname)
    # not 0, 0, 0 but 1, 1, 1 (or anything else > 0)
    # because if mu = 0, the matrix is not use 
    # -> no matrix, no phi, etc. 

    # for Sfan & MSfan np : 
    lbd_eta_mu_values_np = sfan_.compute_hyperparameters_range(num_values=NUM_VALUES)
    lbd_eta_values = [" ".join(plist.split()[:-2]) \
                      for plist in lbd_eta_mu_values_np]
    # for MSfan : 
    lbd_eta_mu_values = sfan_.compute_hyperparameters_range_multiscones(num_values=NUM_VALUES)

    # Delete temporary files from tmp_scores_f_list
    for fname in tmp_scores_f_list:
        os.remove(fname)

    return lbd_eta_values, lbd_eta_mu_values_np, lbd_eta_mu_values


def get_tmp_weights_fnames(args, genotype_fname, phenotype_fnames, ssIndices): 
    """
    Parameters
    ----------
    args : Namespace object
        Its attributes are arguments names 
        and contain arguments values (str or int according to code specifications).
    genotype_fname: filename
        Path to genotype data.
    phenotype_fname: filename
        Path to phenotype data.
    ssIndices: list of list of int
        [subsample_idx] = list of subsample indices for the current fold_idx
    
    Returns
    -------
    tmp_weights_fnames : list of list of strings
        [subsample_idx][task_idx] = tmp filename
    """
    tmp_weights_fnames = []
    for ss_idx in xrange(args.num_subsamples):
        # Get samples
        sample_indices = ssIndices[ss_idx]
        # Generate sample-specific network scores from phenotypes and genotypes
        tmp_weights_f_list = [] # to hold temp files storing these scores
        with tb.open_file(genotype_fname, 'r') as h5f:
            Xtr = h5f.root.Xtr[:, sample_indices]
            for task_idx in xrange(args.num_tasks):
                # Read phenotype
                y = np.loadtxt(phenotype_fnames[task_idx])[sample_indices]

                # Compute feature-phenotype correlations
                r2 = [st.pearsonr(Xtr[feat_idx, :].transpose(), y)[0]**2 \
                      for feat_idx in xrange(args.num_features)]

                # Save to temporary file tmp_weights_f_list[task_idx]
                # Create temporary file of name tmp_fname (use tempfile)
                fd, tmp_fname = tempfile.mkstemp(dir = tmp_dir) #TODO : use arg.tmpdir / change TMP TMPDIR TEMP
                # /!\ tmp_fname is open, fd is the file object
                #-> close it to avoid 'Too many open files' error
                os.close(fd)
                # Save to temporary file
                np.savetxt(tmp_fname, r2, fmt='%.3e')
                # Append temporary file to list
                tmp_weights_f_list.append(tmp_fname)
        tmp_weights_fnames.append(tmp_weights_f_list)
    return tmp_weights_fnames

def save_tmp_weights_fnames (resu_dir, simu_id, fold_idx, tmp_weights_fnames) :
    """ Save temporary filenames in a filename

    Parameters
    ----------
    resu_dir: filename
        Path of the directory in which to save the results.
    simu_id: string
        Name of the simulation, to be used to name files.
    fold_idx : int 
        Index of the current fold
    tmp_weights_fnames : list of list of strings
        [subsample_idx][task_idx] = tmp filename

    Side effects
    ------------
    Create a file named "<resu_dir>/<simu_id>.fold_<fold_idx>.tmp_weights_fnames 
    holding temporary filenames. 
    One line per subsample. 
    On each line : space-separated list of tmp file names. (one per task)

    """ 
    fname = "%s/%s.fold_%d.tmp_weights_fnames" % (resu_dir, simu_id, fold_idx)
    with open (fname, 'w') as f : 
        for subsample in tmp_weights_fnames : 
            f.write("%s\n" % ' '.join(subsample))

def fetch_tmp_weights_fnames(resu_dir, simu_id, fold_idx) : 
    """ Get temporary weights filenames

    Parameters
    ----------
    resu_dir: filename
        Path of the directory in which to save the results.
    simu_id: string
        Name of the simulation, to be used to name files.
    fold_idx : int 
        Index of the current fold

    Return
    ------
    tmp_weights_fnames : list of list of strings
        [subsample_idx][task_idx] = tmp filename

    """
    fname = "%s/%s.fold_%d.tmp_weights_fnames" % (resu_dir, simu_id, fold_idx)
    with open (fname, 'r' ) as f : 
        tmp_weights_fnames = [line.split() for line in f.readlines()]
    return tmp_weights_fnames

def run_fold(   fold_idx, 
                args, 
                lbd_eta_values, lbd_eta_mu_values_np, lbd_eta_mu_values, 
                indices, 
                genotype_fname, network_fname , 
                tmp_weights_fnames, 
                covariance_fname, causal_fname, phenotype_fnames, scores_fnames, 
                resu_dir
            ):
    """ Run the fold n° <fold_idx> of a repeat

    Parameters
    ----------
    fold_idx : int 
        Index of the current fold. 
    args : Namespace object
        Its attributes are arguments names 
        and contain arguments values (str or int according to code specifications).
    lbd_eta_values : list of strings
        Values of hyperparameters for sfan, in the format:
        "-l <lambda -e <eta>".
    lbd_eta_mu_values_np : list of strings
        Values of hyperparameters for msfannp, in the format:
        "-l <lambda -e <eta> -m <mu>".
    lbd_eta_mu_values : list of strings
        Values of hyperparameters for msfan, in the format:
        "-l <lambda -e <eta> -m <mu>".
    indices : list of dictionaries
        fold_idx
        {
            'trIndices': list of train indices,
            'teIndices': list of test indices,
            'ssIndices': list of list of subsample indices
        }
    genotype_fname : filename
        Path to genotype data.
    network_fname  : filename
        Path to the network file.

    tmp_weights_fnames : list of list of strings
        [subsample_idx][task_idx] = tmp filename

    covariance_fname : filename
        Path to the covariance matrix file.

    causal_fname : filename
        Path to the causal weights file.

    phenotype_fnames : filename
        Path to the phenotype data file.

    scores_fnames : filename
        Path to the observed scores file.
    resu_dir : dirname
        Path to the <args.resu_dir>/repeat_<repeat_idx> directory.

    Side effect 
    -----------
    If SEQ_MODE = False, launch qsub job arrays.

    """
    analysis_files = get_analysis_files_names(args.resu_dir, args.simu_id)

    # If real TIME_EXP (no DEBUG_MODE) : 
    #   Do not search for opt_param but take those found before
    if not DEBUG_MODE and TIME_EXP :

        # For each algorithm, get optimal parameters saved in file
        # use rstrinp in case there is \n
        # Single task
        fname = '%s/%s.sfan.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
        with open(fname, 'r') as f:
            opt_params_st = f.read().rstrip() 
        # Multitask (no precision)
        fname = '%s/%s.msfan_np.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
        with open(fname, 'r') as f:
            opt_params_np = f.read().rstrip() 
        # Multitask (precision)
        fname = '%s/%s.msfan.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
        with open(fname, 'r') as f:
            opt_params = f.read().rstrip()

    elif not DEBUG_MODE and not TIME_EXP: 
        logging.info ("======== Feature selection :")
        #XXX DEBUG ???

        # Inititalize dictionary to store selected features
        # sf_dict is a nested dictionary, indexed by
        #   - value of the parameters
        #   - value of task_idx
        #   - subsample idx
        # sf is a list of lists of selected features
        # (one per subsample iteration)
        # you get a specific sf from sf_dict by querying
        # sf_dict[params][task_idx]
        sf_st_dict = {}       # single task
        sf_np_dict = {}       # not using precision matrix
        sf_dict = {}          # using precision matrix
        for params in lbd_eta_values:
            sf_st_dict[params] = {}
            for task_idx in range(args.num_tasks):
                sf_st_dict[params][task_idx] = []
        for params in lbd_eta_mu_values_np:
            sf_np_dict[params] = {}
            for task_idx in range(args.num_tasks):
                sf_np_dict[params][task_idx] = []
        for params in lbd_eta_mu_values:
            sf_dict[params] = {}
            for task_idx in range(args.num_tasks):
                sf_dict[params][task_idx] = []

        #process_time files template : 
        process_time_file_template = resu_dir+'/'+args.simu_id+'.%s.fold_'+str(fold_idx)+'.ss.processTime'
        #max RSS files template : 
        max_RSS_file_template = resu_dir+'/'+args.simu_id+'.%s.fold_'+str(fold_idx)+'.ss.maxRSS'

        for ss_idx in range(args.num_subsamples):
            logging.info ("========                        SS : %d" % ss_idx)

            # Used to get_tms_weight_f_list
            tmp_weights_f_list = tmp_weights_fnames[ss_idx]
        
            for params in lbd_eta_values:
                logging.info("========                        lbd_eta_values : "+ `params`)
                # Select features with single-task sfan
                logging.info("                                   run_sfan")
                sel_, timing, max_RSS = ef.run_sfan(args.num_tasks, network_fname,
                                   tmp_weights_f_list, params)
                if not sel_ : import pdb; pdb.set_trace() #DEBUG
                # Store selected features in the dictionary
                for task_idx, sel_list in enumerate(sel_):
                    sf_st_dict[params][task_idx].append(sel_list)
                #Store process time
                process_time = timing.split()[-1]
                fname= process_time_file_template % 'sfan'
                with open(fname, 'a') as f:
                    f.write("%s\n" % process_time)
                #Store max RSS : 
                fname= max_RSS_file_template % 'sfan'
                with open(fname, 'a') as f:
                    f.write("%s\n" % max_RSS)
            
            for params in lbd_eta_mu_values_np:
                logging.info("========                        lbd_eta_mu_values_np"+ `params`)
                # Select features with multi-task (no precision) sfan
                logging.info("                                   run_msfan_nocorr")
                sel_ , timing, max_RSS = ef.run_msfan_nocorr(args.num_tasks, network_fname,
                                           tmp_weights_f_list, params)
                if not sel_ : import pdb; pdb.set_trace()#DEBUG
                # Store selected features in the dictionary
                for task_idx, sel_list in enumerate(sel_):
                    sf_np_dict[params][task_idx].append(sel_list)
                #Store process time
                process_time = timing.split()[-1]
                fname= process_time_file_template % 'msfan_np'
                with open(fname, 'a') as f:
                    f.write("%s\n" % process_time)
                #Store max RSS : 
                fname= max_RSS_file_template %  'msfan_np'
                with open(fname, 'a') as f:
                    f.write("%s\n" % max_RSS)

            for params in lbd_eta_mu_values:
                logging.info("========                        lbd_eta_mu_values"+ `params`)
                # Select features with multi-task sfan
                logging.info("                                   run_msfan")
                sel_, timing, max_RSS = ef.run_msfan(args.num_tasks, network_fname,
                                    tmp_weights_f_list, covariance_fname,
                                    params)
                if not sel_ : import pdb; pdb.set_trace() #DEBUG                                      
                # Store selected features in the dictionary
                for task_idx, sel_list in enumerate(sel_):
                    sf_dict[params][task_idx].append(sel_list)
                #Store process time
                process_time = timing.split()[-1]
                fname= process_time_file_template % 'msfan'
                with open(fname, 'a') as f:
                    f.write("%s\n" % process_time)
                #Store max RSS : 
                fname= max_RSS_file_template % 'msfan'
                with open(fname, 'a') as f:
                    f.write("%s\n" % max_RSS)


          
            # Delete the temporary files stored in tmp_weights_f_list
            for fname in tmp_weights_f_list:
                os.remove(fname)
        
        # END for ss_idx in range(args.num_subsamples)
        
        #-----------------------------------   
        # Get optimal parameter values for each algo.
        # ??? some lists are empty, is it normal ??? 
        logging.info( "======== Get opt params")
        opt_params_st = ef.get_optimal_parameters_from_dict(sf_st_dict, args.num_features)
        print 'opt param st ', opt_params_st
        opt_params_np = ef.get_optimal_parameters_from_dict(sf_np_dict, args.num_features)
        print 'opt param np ', opt_params_np
        opt_params = ef.get_optimal_parameters_from_dict(sf_dict, args.num_features)
        print 'opt params ', opt_params

    else : 
        # XXX DEBUG : ??? : 
        opt_params_st = "-l 5.97e-03 -e 1.60e-02"
        opt_params_np = "-l 2.94e-03 -e 7.65e-03 -m 1.42e-02"
        opt_params =    "-l 2.94e-03 -e 7.65e-03 -m 1.42e-02"

    # For each algorithm, save optimal parameters to file
    # Single task
    fname = '%s/%s.sfan.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
    with open(fname, 'w') as f:
        f.write(opt_params_st)
    # Multitask (no precision)
    fname = '%s/%s.msfan_np.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
    with open(fname, 'w') as f:
        f.write(opt_params_np)
    # Multitask (precision)
    fname = '%s/%s.msfan.fold_%d.parameters' % (resu_dir, args.simu_id, fold_idx)
    with open(fname, 'w') as f:
        f.write(opt_params)
    #------------------------------------------------------------------


    #------------------------------------------------------------------
    logging.info( "======== Features selection using all training set and opt param")
    #------
    # For each algorithm, run algorithms again to select features,
    # (got a list of list : list of selected features for each task)
    # using the whole training set (i.e. scores_fnames)
    # and optimal parameters.
    logging.info("          run st")
    selected_st, timing_st, maxRSS_st = ef.run_sfan(args.num_tasks, network_fname,
                               scores_fnames, opt_params_st)
    logging.info("          run np")
    selected_np, timing_np, maxRSS_np = ef.run_msfan_nocorr(args.num_tasks, network_fname,
                                       scores_fnames, opt_params_np)
    logging.info("          run msfan")
    selected, timing,maxRSS = ef.run_msfan(args.num_tasks, network_fname,
                                scores_fnames, covariance_fname,
                                opt_params)

    #------
    # For each algorithm, save timing to file
    # Single task 
    with open(analysis_files['timing_st'], 'a') as f:
        f.write("%s\n" % timing_st)
    # Multitask (no precision)
    with open(analysis_files['timing_msfan_np'], 'a') as f:
        f.write("%s\n" % timing_np)
    # Multitask (precision)
    with open(analysis_files['timing_msfan'], 'a') as f:
        f.write("%s\n" % timing)


    #------
    # For each algorithm, save maxRSS to file
    # Single task 
    with open(analysis_files['maxRSS_st'], 'a') as f:
        f.write("%s\n" % maxRSS_st)
    # Multitask (no precision)
    with open(analysis_files['maxRSS_msfan_np'], 'a') as f:
        f.write("%s\n" % maxRSS_np)
    # Multitask (precision)
    with open(analysis_files['maxRSS_msfan'], 'a') as f:
        f.write("%s\n" % maxRSS)


    #------
    # For each algorithm, save selected features to file
    # Single task
    fname = '%s/%s.sfan.fold_%d.selected_features' % \
            (resu_dir, args.simu_id, fold_idx)
    
    with open(fname, 'w') as f:
        for selected_features_list in selected_st:
            f.write("%s\n" % ' '.join(str(x) for x in selected_features_list))
                                    # selected_features_list is a list of int 
                                    # that have to be cast as string so we can join them
    # Multitask (no precision)
    fname = '%s/%s.msfan_np.fold_%d.selected_features' % \
            (resu_dir, args.simu_id, fold_idx)
    
    with open(fname, 'w') as f:
        for selected_features_list in selected_np:
            f.write("%s\n" % ' '.join(str(x) for x in selected_features_list))
    # Multitask (precision)
    fname = '%s/%s.msfan.fold_%d.selected_features' % \
            (resu_dir, args.simu_id, fold_idx)
    
    with open(fname, 'w') as f:
        for selected_features_list in selected:
            f.write("%s\n" % ' '.join(str(x) for x in selected_features_list))
    
    #------


    #------------------------------------------------------------------


def run_repeat(repeat_idx, args, analysis_files):
    """ Run the repeat n° <repeat_idx>.

    Parameters
    ----------
    repeat_idx : int 
        Index of the current repeat. 
    args : Namespace object
        Its attributes are arguments names 
        and contain arguments values (str or int according to code specifications).
    analysis_files: dictionary
        key : <measure>_<algo> 
        value : filename

    """

    logging.info ("=============== REPETITION : %d" %repeat_idx)

    # Create <resu_dir>/repeat_<repeat_id> if it does not exist
    resu_dir = "%s/repeat_%d" % (args.resu_dir, repeat_idx)
    create_dir_if_not_exists(resu_dir)


    #-------------------------------------------------------------------------
    # Data generation : 
    logging.info( "======== Data generation")
    # Data generation : 

    # Instantiate data generator
    data_dir = '%s/repeat_%d' % (args.data_dir, repeat_idx)

    if DATA_GEN : 
        data_gen = generate_data.SyntheticDataGenerator(args.num_tasks,
                                                        args.num_features,
                                                        args.num_samples,
                                                        data_dir,
                                                        args.simu_id)
        # Generate modular data
        data_gen.generate_modular()

    # Name of data files
    # "Hard-coded here", but maybe edit generate_modular
    # to return the names of these files
    genotype_fname = '%s/%s.genotypes.txt' % (data_dir, args.simu_id)
    network_fname = '%s/%s.network.dimacs' % (data_dir, args.simu_id)
    covariance_fname = '%s/%s.task_similarities.txt' % (data_dir,
                                                         args.simu_id)
    causal_fname = '%s/%s.causal_features.txt' % (data_dir, args.simu_id)
    phenotype_fnames = ['%s/%s.phenotype_%d.txt' % \
                        (data_dir, args.simu_id, task_idx) \
                        for task_idx in range(args.num_tasks)]
    scores_fnames = ['%s/%s.scores_%d.txt' % \
                     (data_dir, args.simu_id, task_idx) \
                     for task_idx in range(args.num_tasks)]

    
    #-------------------------------------------------------------------------


    #-------------------------------------------------------------------------
    logging.info("======== Ef setup")

    # Instantiate evaluation framework
    evalf = ef.Framework(args.num_samples, args.num_folds,
                         args.num_subsamples)

    # Compute cross-validation folds and subsample indices
    evalf.compute_indices()

    # Save cross-validation folds and subsample indices to file
    evalf.save_indices(resu_dir, args.simu_id)


    #-------------------------------------------------------------------------
    # Looking for optimal parameters : 

    logging.info ("======== Defining grid of hyperparameters")
    lbd_eta_values, lbd_eta_mu_values_np, lbd_eta_mu_values  = determine_hyperparamaters(
                                                                    args, 
                                                                    genotype_fname, 
                                                                    phenotype_fnames,
                                                                    network_fname,
                                                                    covariance_fname = covariance_fname, 
                                                                    precision_fname = None
                                                                    )

    # and save them :
    hyperparam_fname_np = '%s/%s.hyperparameters_np.txt' % (data_dir, args.simu_id)
    with open (hyperparam_fname_np, 'w') as hp_f : 
        for combinaison in lbd_eta_mu_values_np : 
            hp_f.write("%s\n" % combinaison)
    hyperparam_fname = '%s/%s.hyperparameters.txt' % (data_dir, args.simu_id)
    with open (hyperparam_fname, 'w') as hp_f : 
        for combinaison in lbd_eta_mu_values : 
            hp_f.write("%s\n" % combinaison)
    #-----------------------------------

    #-----------------------------------
    # For each fold : 
    # use subsamble to test feature selection with combinaisons of hyperparameters from the grid
    # find opt param
    # use these opt param to select feature using the all training set. = predict causal status of features <- quantify these perf
    # use a ridge regression trained with selected features only to predict quantitativ phenotypes on test set <- quantify these perf
    if SEQ_MODE : 
        for fold_idx in xrange(args.num_folds):
            logging.info ("============= FOLD : %d"%fold_idx)
            tmp_weights_fnames = get_tmp_weights_fnames(args, genotype_fname, phenotype_fnames, evalf.xp_indices[fold_idx]['ssIndices'])
            run_fold(
                fold_idx,
                args, 
                lbd_eta_values, lbd_eta_mu_values_np, lbd_eta_mu_values, 
                evalf.xp_indices[fold_idx], 
                genotype_fname, network_fname ,tmp_weights_fnames,  covariance_fname , causal_fname, phenotype_fnames, scores_fnames,
                resu_dir)

    else :
        for fold_idx in xrange(args.num_folds):
            tmp_weights_fnames = get_tmp_weights_fnames(args, genotype_fname, phenotype_fnames, evalf.xp_indices[fold_idx]['ssIndices'])
            save_tmp_weights_fnames(resu_dir, args.simu_id, fold_idx, tmp_weights_fnames)
        if  TIME_EXP :
            cmd = "qsub -l hostname='compute-0-%d' -cwd -V -N snp%dr%df -t 1-%d -e %/dev/null -o /dev/null\
                   qsub_run-fold.sh  %d %d %d %d %d %d %s %s %s %s %s %d" \
                   %( 
                      random.randint(15,24), #random node compute-0-N, with N :  15 <= N <= 24
                      args.num_features, repeat_idx, args.num_folds,
                      args.num_tasks, args.num_features, args.num_samples, args.num_repeats, args.num_folds, args.num_subsamples,
                      args.data_dir, args.resu_dir, args.simu_id, hyperparam_fname_np, hyperparam_fname, repeat_idx)

        else : 
            cmd = "qsub -cwd -V -N snp%dr%df -t 1-%d -e /dev/null -o /dev/null\
               qsub_run-fold.sh  %d %d %d %d %d %d %s %s %s %s %s %d" \
               %( 
                  args.num_features, repeat_idx, args.num_folds,
                  args.num_tasks, args.num_features, args.num_samples, args.num_repeats, args.num_folds, args.num_subsamples,
                  args.data_dir, args.resu_dir, args.simu_id, hyperparam_fname_np, hyperparam_fname, repeat_idx)

        print cmd
        p = subprocess.Popen(shlex.split(cmd))

    # run predictions -> in main
    # print analysis_files -> in main



def main():
    """ Run validation experiments on synthetic data .

    Arguments
    ---------
    args.num_tasks: int
        Number of tasks.
    args.num_features: int
        Number of features.
    args.num_samples: int
        Number of samples
    args.num_repeats: int
        Number of repeats.
    args.num_folds: int
        Number of cross-validation folds.
    args.num_subsamples: int
        Number of subsamples (for stability evaluation).
    args.data_dir: filename
        Path of the directory in which to save the simulated data.
    args.resu_dir: filename
        Path of the directory in which to save the simulated data.
    args.simu_id: string
        Name of the simulation, to be used to name files within args.root_dir.
    args.verbose: boolean
        If true, turn on detailed information logging.

    Generated files
    ---------------
    1. Simulated data
    For each repeat, under <args.data_dir>/repeat_<repeat_id>:
        <simu_id>.readme:
            README file describing the simulation paramters
        <simu_id>.task_similarities.txt:
            Matrix of covariance between tasks
        <simu_id>.causal_features:
            Lists of causal features.
            One list per task. Indices start at 0.
        <simu_id>.causal_weights:
            Lists of the weights given to the causal features.
            One list per task. Same order as in <data_dir>/<simu_id>.causal_features.
        <simu_id>.genotypes.txt:
            num_features x num_samples matrix of {0, 1, 2} (representing SNPs).
        <simu_id>.network.dimacs:
            Network over the features.
        For task_id in 0, ..., args.num_tasks:
            <simu_id>.phenotype_<task_id>.txt:
                Phenotype vector (of size args.num_samples) for task <task_id>.
            <simu_id>.scores_<task_id>.txt
                Node weights (of size args.num_features) for task <task_id>.
                Computed as Pearson correlation.

    2. Results
    For each repeat, under <args.resu_dir>/repeat_<repeat_idx>:

        For each fold_idx:
            <simu_id>.<fold_idx>.trIndices
                Space-separated list of training indices.
            <simu_id>.<fold_idx>.teIndices
                Space-separated list of test indices.
            For each subsample_idx:
                <data_dir>/<simu_id>.<fold_idx>.<ss_idx>.ssIndices
                    Space-separated lists of subsample indices,
                    one line per list / subsample.
        
            For each algo in ('sfan', 'msfan_np', 'msfan'):
                <simu_id>.<algo>.fold_<fold_idx>.parameters
                     Optimal parameters.

                <simu_id>.<algo>.fold_<fold_idx>.selected_features
                    List of list of selected features, one per task.
                    Each line corresponds to a task and contains a 
                    space-separated list of indices, STARTING AT 0.

                <simu_id>.<algo>.fold_<fold_idx>.task_<task_idx>.predicted
                    Predictions, on the test set, of a ridge regression
                    trained only on the selected features.
        
    For file format specifications, see README.md
    
    Example
    -------
    $ python synthetic_data_experiments.py -k 3 -m 200 -n 100 -r 10 -f 10 -s 10 \
             ../data/simu_synth_01 ../results/simu_synth_01 simu_01 --verbose


    ### Sur le cluster : XXX

    $ python synthetic_data_experiments.py -k 3 -m 50 -n 35 -r 5 -f 3 -s 2 \
             /share/data40T/athenais/data/simu_synth_01 /share/data40T/athenais/results/simu_synth_01 simu_01 --verbose
    """

    # Arguments handling : 
    args = get_integrous_arguments_values()



    #-------------------------------------------------------------------------
    # Insure working repositories exist : 

    # Create simulated data repository if it does not exist
    create_dir_if_not_exists(args.data_dir)

    # (Delete and re)create results repository (if it exists)
    if os.path.isdir(args.resu_dir): 
        logging.info("Deleting %s\n" % args.resu_dir)
        try:
            shutil.rmtree(args.resu_dir)
        except OSError:
            raise #???XXX
    # More pythonic : ??? 
    #import errno
    #try:
    #    os.remove(args.resu_dir)
    #except OSError as e :
    #    if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
    #       raise
    create_dir_if_not_exists(args.resu_dir)

    if not SEQ_MODE: 
        # Create SGE-outputs dir if it does not xist
        create_dir_if_not_exists('%s/SGE-outputs' % args.resu_dir)
    #-------------------------------------------------------------------------



    #-------------------------------------------------------------------------
    # Create analysis file names :
    analysis_files = get_analysis_files_names(args.resu_dir, args.simu_id)
    #-------------------------------------------------------------------------



    #-------------------------------------------------------------------------
    for repeat_idx in xrange(args.num_repeats):
            run_repeat(repeat_idx, args, analysis_files)


    #-------------------------------------------------------------------------

    # Handle ouputs = run script handle-output.py


if __name__ == "__main__":
    

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

    main()
    
    print("THE END")
          
