#!/bin/sh

###############################################################################
# var to modify : 

# -- param of the experimentation : 
num_tasks=3
array_features=( 200 1000 10000 20000 50000 ) # range of num_features values
num_samples=1000
num_repeats=10
num_folds=10
num_subsamples=20

# -- about the paths : 

#path='..' # Version BOB 
path="/share/data40T/athenais/" # Version Cluster 

dat_path=$path'dat/experiment_numSNP/'
res_path=$path'res/experiment_numSNP_'`date +%Y-%m-%d-%H:%M`'/'


###############################################################################



for num_features in  "${array_features[@]}"
do
    echo $num_features
    simu_id='numSNP_'$num_features
    data_dir=$dat_path$simu_id'/'
    resu_dir=$res_path$simu_id'/'

	python synthetic_data_experiments.py \
    -k $num_tasks -m $num_features -n $num_samples -r $num_repeats -f $num_folds -s $num_subsamples \
    $data_dir $resu_dir $simu_id --verbose


done


