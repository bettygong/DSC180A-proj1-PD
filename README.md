# DSC180A-proj1-PD & PDA
Causal Inference for de-confounding popularity bias. This is a replicated project from [Causal Intervention for Leveraging Popularity Bias in
Recommendation](https://arxiv.org/pdf/2105.06067.pdf) based on Tensorflow. 

# Dataset Download
Douban(Movie): The original data is downloaded from the following link, cited as Song, Weiping, et al. "Session-based social recommendation via dynamic graph attention networks." WSDM 2019. You can download processed data from douban.zip and remember to move the unzipped files into the main douban folder.\
[original data](https://github.com/DeepGraphLearning/RecommenderSystems/blob/master/socialRec/README.md#douban-data), [processed_data](https://github.com/bettygong/DSC180A-proj1-PD/tree/main/data/douban)\
You can also produce processed data by running `douban_split.ipynb`.

# Requirement 
tensorflow == 1.14 \
Cython (for neurec evaluator)\
Numpy\
prefetch-generator\
python3\
pandas == 0.25.0

In order to set up the environment and control package versions, please download [environment.yml](https://github.com/bettygong/DSC180A-proj1-PD/blob/main/environment.yml) and create the environment `myenv` by entering `conda env create -f environment.yml` in the terminal. \
Activate `myenv` by entering `conda activate myenv` (or `source activate myenv` for DSMLP terminal).\
Then install employed packages in `myenv` by entering:\
`pip install tensorflow==1.14` \
`python -m pip install scipy` \
`pip install prefetch-generator` \
`pip install -U matplotlib` 

After version control, you then can run the code in `myenv`. (Simply activate the environment by `source activate myenv`)

# Parameters
Ket parameters in `simple_reproduce.py` and `train_new_api.py`:\
--pop_exp: gamma in paper (applicable only for PD and PDA models).\
--train: model selection (normal:BPRMF/BPRMF-A | s_condition:PD/PDA | temp_pop:BPR(t)-pop).\
--test: similar to train.\
-- saveID: saved name flag.\
--Ks: list, set top K.\

others: (you can read help, or "python xxx.py --help")\
--dataset: we only use douban dataset \
--lr: learning rate\
--save_dir: path to find the file of the saved model 

# Command (To produce results)
We can directly run saved models to get metric results (recall, precision, hit, NDCG)\
Please download the saved_model folder as the [instruction](https://github.com/bettygong/DSC180A-proj1-PD/tree/main/save_model) said, and move the unzipped folders to the main saved_model folder.
## PD/PDA
Run `python -u MF/simple_reproduce.py --dataset douban --epoch 2000 --save_flag 0 --log_interval 5 --start 0 --end 10 --step 1 --batch_size 2048 --lr 1e-2 --train s_condition --test s_condtion --saveID xxx --cuda 0 --regs 1e-2 --valid_set valid --pop_exp 0.22 --save_dir /home/zgong/private/PDA/save_model/ --Ks [20,50]`\
Note: I'm using DSMLP to run the code so the `save_dir` path includes my username. If you want to run it on DSMLP as well, please modify to your username. If you run on local computer, you should use the path leading to the PDA folder.

## Baseline model (BPRMF)
Run `python -u MF/simple_reproduce.py --dataset douban --epoch 2000 --save_flag 0 --log_interval 5 --start 0 --end 10 --step 1 --batch_size 2048 --lr 1e-2 --train normal --test normal --saveID xxx --cuda 0 --regs 1e-2 --valid_set valid --pop_exp 0.22 --save_dir /home/zgong/private/PDA/save_model/ --Ks [20,50]`\
Note: modify save_dir like above. 






